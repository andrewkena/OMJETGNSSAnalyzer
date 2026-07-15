import io
import math
import threading
import tkinter as tk
from PIL import Image, ImageTk
import requests

try:
    from shapely.geometry import LineString, MultiPolygon
    from shapely.ops import unary_union
    _HAS_SHAPELY = True
except Exception:
    _HAS_SHAPELY = False


# ── geometry helpers ─────────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _convex_hull(pts):
    """Andrew's monotone chain. pts = list of (x, y). Returns hull CCW."""
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _cruise_heights(points):
    """Heights excluding takeoff and landing phases.

    Finds the first and last index where altitude exceeds
    min + 60% of (max - min), then returns heights in that range.
    """
    heights = [p["height"] for p in points if p.get("height") is not None]
    if not heights:
        return []
    lo, hi = min(heights), max(heights)
    rng = hi - lo
    if rng < 5:
        return heights
    threshold = lo + rng * 0.60
    above = [i for i, h in enumerate(heights) if h >= threshold]
    if not above:
        return heights
    return heights[above[0]: above[-1] + 1]


def _track_buffer_rings(lonlat, buffer_m):
    """Outer boundary of a track as a buffer (offset) around its polyline.

    Projects lon/lat to a local metric plane, buffers the LineString by
    ``buffer_m`` metres so adjacent survey sweeps merge, then returns the
    exterior ring(s) back in lon/lat. Returns a list of rings (each a list
    of (lon, lat)); usually one, more if the track has disjoint areas.
    """
    if not _HAS_SHAPELY or len(lonlat) < 2:
        return []

    mean_lat = sum(p[1] for p in lonlat) / len(lonlat)
    lat_s = 111320.0
    lon_s = 111320.0 * math.cos(math.radians(mean_lat))

    def to_m(lon, lat):
        return (lon * lon_s, lat * lat_s)

    def to_ll(x, y):
        return (x / lon_s, y / lat_s)

    line = LineString([to_m(lon, lat) for lon, lat in lonlat])
    try:
        poly = line.buffer(buffer_m, join_style=1, cap_style=1)
    except Exception:
        return []
    if poly.is_empty:
        return []

    geoms = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
    rings = []
    for g in geoms:
        rings.append([to_ll(x, y) for x, y in g.exterior.coords])
    return rings


def _estimate_buffer_m(lonlat):
    """Adaptive buffer radius: a small fraction of the track's bounding box."""
    if len(lonlat) < 2:
        return 50.0
    lats = [p[1] for p in lonlat]
    lons = [p[0] for p in lonlat]
    mean_lat = sum(lats) / len(lats)
    lat_s = 111320.0
    lon_s = 111320.0 * math.cos(math.radians(mean_lat))
    w = (max(lons) - min(lons)) * lon_s
    h = (max(lats) - min(lats)) * lat_s
    diag = math.hypot(w, h)
    return max(30.0, min(150.0, diag * 0.02))


def _polygon_area_m2(hull_lonlat):
    """Shoelace area of a lon/lat polygon, projected to metres."""
    if len(hull_lonlat) < 3:
        return 0.0
    mean_lat = sum(p[1] for p in hull_lonlat) / len(hull_lonlat)
    lat_s = 111320.0
    lon_s = 111320.0 * math.cos(math.radians(mean_lat))
    pts = [(lon * lon_s, lat * lat_s) for lon, lat in hull_lonlat]
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n))
    return abs(area) / 2.0

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
        self._filtered_ids = set()
        self._excluded_ids = set()
        self._multi_tracks = []  # [{points, color, label}]
        self._single_color = None   # None = разные цвета, иначе строка цвета
        self._legend_visible = True
        self._stats_visible = True
        self._hull_visible = True
        self._stats_cache = None    # вычисляется при изменении _multi_tracks

        self._drag_origin = None
        self._drag_cx = 0.0
        self._drag_cy = 0.0

        self._hovered_id = None
        self._hover_callback = None
        self._hover_mouse_pos = (0, 0)

        self.bind("<Configure>",      self._on_configure)
        self.bind("<ButtonPress-1>",  self._on_drag_start)
        self.bind("<B1-Motion>",      self._on_drag)
        self.bind("<MouseWheel>",     self._on_scroll)   # Windows
        self.bind("<Button-4>",       self._on_scroll)   # Linux up
        self.bind("<Button-5>",       self._on_scroll)   # Linux down
        self.bind("<Motion>",         self._on_motion)
        self.bind("<Leave>",          self._on_leave)

    # ── public API ──────────────────────────────────────────────────────────

    def add_track(self, points, color="#00c8ff", label=""):
        self._multi_tracks.append({"points": points, "color": color, "label": label})
        self._stats_cache = None
        self._fit_to_all_tracks()
        self._redraw()

    def clear_tracks(self):
        self._multi_tracks = []
        self._stats_cache = None
        self._redraw()

    def set_single_color(self, color):
        self._single_color = color
        self._redraw()

    def set_legend_visible(self, visible):
        self._legend_visible = visible
        self._redraw()

    def set_stats_visible(self, visible):
        self._stats_visible = visible
        self._redraw()

    def set_hull_visible(self, visible):
        self._hull_visible = visible
        self._redraw()

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

    def set_data(self, points, photo_points=None, excluded_ids=None, filtered_ids=None):
        self._points = points or []
        self._photo_points = photo_points or []
        self._excluded_ids = excluded_ids or set()
        self._filtered_ids = filtered_ids or set()

        self._photo_world = {
            p["photo_id"]: (p["lon"], p["lat"])
            for p in self._photo_points
            if p.get("photo_id") is not None
        }

        if self._points:
            self._fit_to_points()
        self._redraw()

    def update_filter(self, excluded_ids=None, filtered_ids=None):
        if excluded_ids is not None:
            self._excluded_ids = excluded_ids
        if filtered_ids is not None:
            self._filtered_ids = filtered_ids
        self._redraw()

    # ── internal ────────────────────────────────────────────────────────────

    def _fit_to_all_tracks(self):
        all_pts = [p for t in self._multi_tracks for p in t["points"]]
        if not all_pts:
            return
        lats = [p["lat"] for p in all_pts]
        lons = [p["lon"] for p in all_pts]
        w = max(self.winfo_width(), 400)
        h = max(self.winfo_height(), 300)
        for z in range(19, 1, -1):
            xs = [_lon_to_wx(lo, z) for lo in lons]
            ys = [_lat_to_wy(la, z) for la in lats]
            if (max(xs) - min(xs)) < w * 0.85 and (max(ys) - min(ys)) < h * 0.85:
                self._zoom = z
                break
        clat = (min(lats) + max(lats)) / 2
        clon = (min(lons) + max(lons)) / 2
        self._cx = _lon_to_wx(clon, self._zoom)
        self._cy = _lat_to_wy(clat, self._zoom)

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
        self._hover_mouse_pos = (event.x, event.y)
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
        self._draw_hull()
        self._draw_markers()
        self._draw_hover()
        self._draw_legend()
        self._draw_stats_overlay()

    def _draw_hull(self):
        if not self._hull_visible or not self._multi_tracks:
            return
        for track in self._multi_tracks:
            lonlat = [(p["lon"], p["lat"]) for p in track["points"]]
            buf = _estimate_buffer_m(lonlat)
            for ring in _track_buffer_rings(lonlat, buf):
                if len(ring) < 3:
                    continue
                coords = []
                for lon, lat in ring:
                    cx, cy = self._w2c(_lon_to_wx(lon, self._zoom),
                                       _lat_to_wy(lat, self._zoom))
                    coords.extend([cx, cy])
                self.create_polygon(coords, outline="#ff3333", fill="", width=1,
                                    tags="hull")

    def _draw_legend(self):
        if not self._legend_visible or not self._multi_tracks:
            return
        pad = 8
        line_w = 28
        row_h = 20
        x0, y0 = 10, 10

        # measure max label width (approx 7px per char)
        max_label = max((len(t["label"]) for t in self._multi_tracks), default=10)
        box_w = pad + line_w + 6 + max_label * 7 + pad
        box_h = pad + len(self._multi_tracks) * row_h + pad

        self.create_rectangle(x0, y0, x0 + box_w, y0 + box_h,
                              fill="#111111", stipple="gray50",
                              outline="#555555", tags="legend")
        for i, track in enumerate(self._multi_tracks):
            y = y0 + pad + i * row_h + row_h // 2
            color = track["color"]
            self.create_line(x0 + pad, y, x0 + pad + line_w, y,
                             fill=color, width=3, tags="legend")
            self.create_text(x0 + pad + line_w + 6, y,
                             text=track["label"], anchor=tk.W,
                             fill="#ffffff", font=("Segoe UI", 9), tags="legend")

    def _compute_stats(self):
        if self._stats_cache is not None:
            return self._stats_cache
        total_dist = 0.0
        all_lonlat = []
        cruise_h_all = []
        for track in self._multi_tracks:
            pts = track["points"]
            for i in range(1, len(pts)):
                total_dist += _haversine_m(
                    pts[i - 1]["lat"], pts[i - 1]["lon"],
                    pts[i]["lat"],     pts[i]["lon"]
                )
            all_lonlat += [(p["lon"], p["lat"]) for p in pts]
            cruise_h_all += _cruise_heights(pts)

        area_m2 = self._buffer_area_m2()
        if area_m2 == 0.0 and len(all_lonlat) >= 3:
            area_m2 = _polygon_area_m2(_convex_hull(all_lonlat))

        avg_h = sum(cruise_h_all) / len(cruise_h_all) if cruise_h_all else None

        self._stats_cache = {"dist_m": total_dist, "area_m2": area_m2, "avg_h": avg_h}
        return self._stats_cache

    def _buffer_area_m2(self):
        """Total surveyed area = union of per-track buffer polygons (metres²)."""
        if not _HAS_SHAPELY:
            return 0.0
        all_lonlat = [(p["lon"], p["lat"])
                      for t in self._multi_tracks for p in t["points"]]
        if len(all_lonlat) < 2:
            return 0.0
        mean_lat = sum(p[1] for p in all_lonlat) / len(all_lonlat)
        lat_s = 111320.0
        lon_s = 111320.0 * math.cos(math.radians(mean_lat))
        polys = []
        for track in self._multi_tracks:
            lonlat = [(p["lon"], p["lat"]) for p in track["points"]]
            if len(lonlat) < 2:
                continue
            buf = _estimate_buffer_m(lonlat)
            line = LineString([(lon * lon_s, lat * lat_s) for lon, lat in lonlat])
            try:
                polys.append(line.buffer(buf, join_style=1, cap_style=1))
            except Exception:
                pass
        if not polys:
            return 0.0
        try:
            return unary_union(polys).area
        except Exception:
            return sum(p.area for p in polys)

    def _draw_stats_overlay(self):
        if not self._multi_tracks or not self._stats_visible:
            return
        stats = self._compute_stats()
        dist_m = stats["dist_m"]
        area_m2 = stats["area_m2"]

        if dist_m >= 1000:
            dist_str = f"{dist_m / 1000:.2f} км"
        else:
            dist_str = f"{dist_m:.0f} м"

        area_ha = area_m2 / 10000.0
        area_str = f"{area_ha:.2f} га  /  {area_m2:,.0f} м²"

        avg_h = stats["avg_h"]
        avg_h_str = f"{avg_h:.1f} м" if avg_h is not None else "—"

        n = len(self._multi_tracks)
        total_pts = sum(len(t["points"]) for t in self._multi_tracks)

        rows = [
            f"Треков: {n}  ({total_pts} точек)",
            f"Протяжённость: {dist_str}",
            f"Площадь: {area_str}",
            f"Средняя высота (крейс.): {avg_h_str}",
        ]

        pad = 10
        row_h = 18
        box_w = max(len(r) for r in rows) * 7 + pad * 2
        box_h = len(rows) * row_h + pad * 2

        cw = self.winfo_width()
        ch = self.winfo_height()
        x1 = cw - pad
        y1 = ch - pad
        x0 = x1 - box_w
        y0 = y1 - box_h

        self.create_rectangle(x0, y0, x1, y1,
                              fill="#111111", stipple="gray50",
                              outline="#555555", tags="stats")
        for i, row in enumerate(rows):
            self.create_text(x0 + pad, y0 + pad + i * row_h + row_h // 2,
                             text=row, anchor=tk.W,
                             fill="#ffffff", font=("Segoe UI", 9), tags="stats")

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

        label = str(self._hovered_id)
        pad = 3
        tx, ty = cx + r + 4, cy
        tmp = self.create_text(tx, ty, text=label, anchor=tk.W,
                               font=("Segoe UI", 9, "bold"),
                               fill="#ffffff", tags="hover_ring")
        b = self.bbox(tmp)
        if b:
            self.create_rectangle(b[0] - pad, b[1] - pad,
                                  b[2] + pad, b[3] + pad,
                                  fill="#111111", outline="#555555",
                                  tags="hover_ring")
            self.tag_raise(tmp)

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
        if len(self._points) >= 2:
            coords = []
            for p in self._points:
                cx, cy = self._w2c(_lon_to_wx(p["lon"], self._zoom),
                                    _lat_to_wy(p["lat"], self._zoom))
                coords.extend([cx, cy])
            self.create_line(coords, fill="#00c8ff", width=2, smooth=False, tags="track")

        for track in self._multi_tracks:
            pts = track["points"]
            if not pts:
                continue
            coords = []
            for p in pts:
                cx, cy = self._w2c(_lon_to_wx(p["lon"], self._zoom),
                                    _lat_to_wy(p["lat"], self._zoom))
                coords.extend([cx, cy])
            color = self._single_color if self._single_color else track["color"]
            if len(pts) >= 2:
                self.create_line(coords, fill=color, width=2, smooth=False, tags="track")

            # start marker — green upward triangle
            sx, sy = coords[0], coords[1]
            r = 7
            self.create_polygon(sx, sy - r, sx - r, sy + r, sx + r, sy + r,
                                fill="#00dd44", outline="#000000", width=1, tags="track")
            # end marker — red downward triangle
            ex, ey = coords[-2], coords[-1]
            self.create_polygon(ex, ey + r, ex - r, ey - r, ex + r, ey - r,
                                fill="#ff3333", outline="#000000", width=1, tags="track")

    def _draw_markers(self):
        for p in self._photo_points:
            cx, cy = self._w2c(_lon_to_wx(p["lon"], self._zoom),
                                _lat_to_wy(p["lat"], self._zoom))
            pid = p.get("photo_id")
            quality = p.get("quality", "LOW")
            color = QUALITY_COLOR.get(quality, "#ff4444")

            manually_excluded = pid in self._excluded_ids
            is_filtered = pid in self._filtered_ids

            r = 4
            if manually_excluded:
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill="#666666", outline="#444444", width=1, tags="marker")
            elif is_filtered:
                self.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2,
                                 outline="#ff3333", width=2, tags="marker")
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill="#888888", outline="#555555", width=1, tags="marker")
            else:
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=color, outline="#000000", width=1, tags="marker")

