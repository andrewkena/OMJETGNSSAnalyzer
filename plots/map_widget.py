import io
import math
import threading
import tkinter as tk
from PIL import Image, ImageTk
import requests

TILE_SIZE = 256
_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "OMJET-GNSS-Analyzer/0.2"

BASEMAPS = {
    "Satellite Google": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Hybrid Google":    "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "Roads Google":     "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "OpenStreetMap":    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "No basemap":       None,
}
BASEMAP_KEYS = list(BASEMAPS.keys())
DEFAULT_BASEMAP = "Satellite Google"

QUALITY_COLOR = {
    "GOOD":   "#00ff00",
    "NORMAL": "#ffdd00",
    "LOW":    "#ff4444",
}


def _lon_to_wx(lon, zoom):
    return (lon + 180) / 360 * (2 ** zoom) * TILE_SIZE


def _lat_to_wy(lat, zoom):
    lat_r = math.radians(lat)
    return (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * (2 ** zoom) * TILE_SIZE


class MapWidget(tk.Canvas):

    def __init__(self, parent, basemap=DEFAULT_BASEMAP, **kwargs):
        super().__init__(parent, bg="#1a1a1a", highlightthickness=0, **kwargs)

        self._basemap = basemap
        self._zoom = 15
        self._cx = 0.0  # world-pixel x of canvas centre
        self._cy = 0.0  # world-pixel y of canvas centre

        self._tile_cache = {}    # (z,tx,ty) -> ImageTk.PhotoImage | None
        self._tile_loading = set()
        self._tile_refs = []     # prevent GC

        self._points = []
        self._photo_points = []
        self._photo_world = {}   # photo_id -> (lon, lat)
        self._avg_h = None
        self._h_threshold = None
        self._excluded_ids = set()

        self._drag_origin = None
        self._drag_cx = 0.0
        self._drag_cy = 0.0

        self._hovered_id = None
        self._hover_callback = None

        self.bind("<Configure>",      self._on_configure)
        self.bind("<ButtonPress-1>",  self._on_drag_start)
        self.bind("<B1-Motion>",      self._on_drag)
        self.bind("<MouseWheel>",     self._on_scroll)   # Windows
        self.bind("<Button-4>",       self._on_scroll)   # Linux up
        self.bind("<Button-5>",       self._on_scroll)   # Linux down
        self.bind("<Motion>",         self._on_motion)
        self.bind("<Leave>",          self._on_leave)

    # ── public API ──────────────────────────────────────────────────────────

    def set_hover_callback(self, cb):
        self._hover_callback = cb

    def highlight_point(self, photo_id):
        """Highlight marker from external source (table hover). Does not fire callback."""
        if photo_id == self._hovered_id:
            return
        self._hovered_id = photo_id
        self._draw_hover()

    def set_basemap(self, basemap):
        self._basemap = basemap
        self._tile_cache.clear()
        self._tile_loading.clear()
        self._redraw()

    def set_data(self, points, photo_points=None,
                 height_filter=True, height_pct=0.10, excluded_ids=None):
        self._points = points or []
        self._photo_points = photo_points or []
        self._excluded_ids = excluded_ids or set()

        self._photo_world = {
            p["photo_id"]: (p["lon"], p["lat"])
            for p in self._photo_points
            if p.get("photo_id") is not None
        }

        heights = [p["height"] for p in self._photo_points if p.get("height") is not None]
        if heights and height_filter:
            self._avg_h = sum(heights) / len(heights)
            self._h_threshold = self._avg_h * height_pct
        else:
            self._avg_h = None
            self._h_threshold = None

        if self._points:
            self._fit_to_points()
        self._redraw()

    def update_filter(self, height_filter=True, height_pct=0.10, excluded_ids=None):
        if excluded_ids is not None:
            self._excluded_ids = excluded_ids
        heights = [p["height"] for p in self._photo_points if p.get("height") is not None]
        if heights and height_filter:
            self._avg_h = sum(heights) / len(heights)
            self._h_threshold = self._avg_h * height_pct
        else:
            self._avg_h = None
            self._h_threshold = None
        self._redraw()

    # ── internal ────────────────────────────────────────────────────────────

    def _fit_to_points(self):
        lats = [p["lat"] for p in self._points]
        lons = [p["lon"] for p in self._points]
        w = max(self.winfo_width(), 400)
        h = max(self.winfo_height(), 300)

        for z in range(19, 1, -1):
            xs = [_lon_to_wx(lo, z) for lo in lons]
            ys = [_lat_to_wy(la, z) for la in lats]
            if (max(xs) - min(xs)) < w * 0.8 and (max(ys) - min(ys)) < h * 0.8:
                self._zoom = z
                break

        clat = (min(lats) + max(lats)) / 2
        clon = (min(lons) + max(lons)) / 2
        self._cx = _lon_to_wx(clon, self._zoom)
        self._cy = _lat_to_wy(clat, self._zoom)

    def _w2c(self, wx, wy):
        """World-pixel → canvas pixel."""
        cw = self.winfo_width()
        ch = self.winfo_height()
        return wx - self._cx + cw / 2, wy - self._cy + ch / 2

    def _on_configure(self, _event):
        self._redraw()

    def _on_drag_start(self, event):
        self._drag_origin = (event.x, event.y)
        self._drag_cx = self._cx
        self._drag_cy = self._cy

    def _on_drag(self, event):
        if self._drag_origin is None:
            return
        dx = event.x - self._drag_origin[0]
        dy = event.y - self._drag_origin[1]
        self._cx = self._drag_cx - dx
        self._cy = self._drag_cy - dy
        self._redraw()

    def _on_scroll(self, event):
        delta = 1 if (event.num == 4 or event.delta > 0) else -1
        new_z = max(1, min(19, self._zoom + delta))
        if new_z == self._zoom:
            return

        cw = self.winfo_width()
        ch = self.winfo_height()
        wx = event.x + self._cx - cw / 2
        wy = event.y + self._cy - ch / 2
        scale = 2 ** (new_z - self._zoom)
        self._cx = wx * scale - event.x + cw / 2
        self._cy = wy * scale - event.y + ch / 2
        self._zoom = new_z
        self._redraw()

    def _on_motion(self, event):
        if not self._photo_world:
            return
        best_id = None
        best_dist = 12
        for pid, (lon, lat) in self._photo_world.items():
            wx = _lon_to_wx(lon, self._zoom)
            wy = _lat_to_wy(lat, self._zoom)
            cx, cy = self._w2c(wx, wy)
            d = math.hypot(event.x - cx, event.y - cy)
            if d < best_dist:
                best_dist = d
                best_id = pid
        if best_id != self._hovered_id:
            self._hovered_id = best_id
            self._draw_hover()
            if self._hover_callback:
                self._hover_callback(best_id)

    def _on_leave(self, _event):
        if self._hovered_id is not None:
            self._hovered_id = None
            self._draw_hover()
            if self._hover_callback:
                self._hover_callback(None)

    # ── rendering ────────────────────────────────────────────────────────────

    def _redraw(self):
        self.delete("all")
        self._tile_refs = []

        tile_url = BASEMAPS.get(self._basemap)
        if tile_url:
            self._draw_tiles(tile_url)

        self._draw_track()
        self._draw_markers()
        self._draw_hover()

    def _draw_hover(self):
        self.delete("hover_ring")
        if self._hovered_id is None:
            return
        lonlat = self._photo_world.get(self._hovered_id)
        if lonlat is None:
            return
        lon, lat = lonlat
        wx = _lon_to_wx(lon, self._zoom)
        wy = _lat_to_wy(lat, self._zoom)
        cx, cy = self._w2c(wx, wy)
        r = 9
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         outline="#ffffff", width=2, tags="hover_ring")

    def _draw_tiles(self, url_tpl):
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 2 or ch < 2:
            return

        z = self._zoom
        n = 2 ** z
        tx0 = int((self._cx - cw / 2) / TILE_SIZE)
        ty0 = int((self._cy - ch / 2) / TILE_SIZE)
        tx1 = int((self._cx + cw / 2) / TILE_SIZE)
        ty1 = int((self._cy + ch / 2) / TILE_SIZE)

        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                if tx < 0 or ty < 0 or tx >= n or ty >= n:
                    continue
                key = (z, tx, ty)
                cx, cy = self._w2c(tx * TILE_SIZE, ty * TILE_SIZE)

                if key in self._tile_cache:
                    photo = self._tile_cache[key]
                    if photo:
                        self._tile_refs.append(photo)
                        self.create_image(int(cx), int(cy), anchor=tk.NW, image=photo)
                    else:
                        self.create_rectangle(int(cx), int(cy),
                                              int(cx + TILE_SIZE), int(cy + TILE_SIZE),
                                              fill="#2a2a2a", outline="#333")
                else:
                    self.create_rectangle(int(cx), int(cy),
                                          int(cx + TILE_SIZE), int(cy + TILE_SIZE),
                                          fill="#222", outline="#333")
                    if key not in self._tile_loading:
                        self._tile_loading.add(key)
                        threading.Thread(
                            target=self._fetch_tile,
                            args=(url_tpl, tx, ty, z),
                            daemon=True
                        ).start()

    def _fetch_tile(self, url_tpl, tx, ty, z):
        key = (z, tx, ty)
        try:
            r = _SESSION.get(url_tpl.format(x=tx, y=ty, z=z), timeout=10)
            r.raise_for_status()
            data = r.content
            self.after(0, lambda: self._cache_tile(key, data))
        except Exception:
            self.after(0, lambda: self._cache_tile(key, None))

    def _cache_tile(self, key, data):
        self._tile_loading.discard(key)
        if data:
            try:
                photo = ImageTk.PhotoImage(Image.open(io.BytesIO(data)).convert("RGBA"))
                self._tile_cache[key] = photo
            except Exception:
                self._tile_cache[key] = None
        else:
            self._tile_cache[key] = None
        # only redraw if this tile is still relevant
        if key[0] == self._zoom:
            self._redraw()

    def _draw_track(self):
        if len(self._points) < 2:
            return
        coords = []
        for p in self._points:
            cx, cy = self._w2c(_lon_to_wx(p["lon"], self._zoom),
                                _lat_to_wy(p["lat"], self._zoom))
            coords.extend([cx, cy])
        self.create_line(coords, fill="#00c8ff", width=2, smooth=False, tags="track")

    def _draw_markers(self):
        for p in self._photo_points:
            cx, cy = self._w2c(_lon_to_wx(p["lon"], self._zoom),
                                _lat_to_wy(p["lat"], self._zoom))
            pid = p.get("photo_id")
            quality = p.get("quality", "LOW")
            color = QUALITY_COLOR.get(quality, "#ff4444")

            manually_excluded = pid in self._excluded_ids
            height_filtered = (
                self._avg_h is not None
                and p.get("height") is not None
                and abs(p["height"] - self._avg_h) > self._h_threshold
            )

            r = 4
            if manually_excluded:
                color = "#666666"
            elif height_filtered:
                self.create_oval(cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3,
                                 outline="#ff0000", width=2, tags="marker")

            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             fill=color, outline="#000000", width=1, tags="marker")
