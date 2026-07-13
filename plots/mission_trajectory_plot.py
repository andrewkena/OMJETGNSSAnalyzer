import math
import io
import requests
from PIL import Image, ImageDraw

QUALITY_STYLE = {
    "GOOD":   dict(color=(0, 255, 0),   radius=5),
    "NORMAL": dict(color=(255, 220, 0), radius=5),
    "LOW":    dict(color=(255, 0, 0),   radius=7),
}

BASEMAPS = {
    "Satellite Google": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Hybrid Google":    "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "Roads Google":     "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "OpenStreetMap":    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "No basemap":       None,
}
BASEMAP_KEYS = list(BASEMAPS.keys())
DEFAULT_BASEMAP = "Satellite Google"

TILE_SIZE = 256
HEADERS = {"User-Agent": "OMJET-GNSS-Analyzer/0.2 (github.com/andrewkena/OMJETGNSSAnalyzer)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _lat_lon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def _lat_lon_to_pixel(lat, lon, zoom, tile_x0, tile_y0):
    n = 2 ** zoom
    px = (lon + 180) / 360 * n * TILE_SIZE - tile_x0 * TILE_SIZE
    py = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * TILE_SIZE - tile_y0 * TILE_SIZE
    return px, py


def _fetch_tile(url_template, x, y, z):
    url = url_template.format(x=x, y=y, z=z)
    try:
        r = SESSION.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        return Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (40, 40, 40, 255))


def _build_basemap(lats, lons, url_template, img_size=1200):
    zoom = 16
    # auto zoom: fit all points in ~img_size pixels
    for z in range(18, 10, -1):
        txs = [_lat_lon_to_tile(la, lo, z)[0] for la, lo in zip(lats, lons)]
        tys = [_lat_lon_to_tile(la, lo, z)[1] for la, lo in zip(lats, lons)]
        span_x = (max(txs) - min(txs) + 1) * TILE_SIZE
        span_y = (max(tys) - min(tys) + 1) * TILE_SIZE
        if span_x <= img_size and span_y <= img_size:
            zoom = z
            break

    txs = [_lat_lon_to_tile(la, lo, zoom)[0] for la, lo in zip(lats, lons)]
    tys = [_lat_lon_to_tile(la, lo, zoom)[1] for la, lo in zip(lats, lons)]
    tx0, tx1 = min(txs), max(txs)
    ty0, ty1 = min(tys), max(tys)

    # padding
    pad = 1
    tx0 -= pad; ty0 -= pad; tx1 += pad; ty1 += pad

    cols = tx1 - tx0 + 1
    rows = ty1 - ty0 + 1
    canvas = Image.new("RGBA", (cols * TILE_SIZE, rows * TILE_SIZE))

    for row, ty in enumerate(range(ty0, ty1 + 1)):
        for col, tx in enumerate(range(tx0, tx1 + 1)):
            tile = _fetch_tile(url_template, tx, ty, zoom)
            canvas.paste(tile, (col * TILE_SIZE, row * TILE_SIZE))

    return canvas, zoom, tx0, ty0


class MissionTrajectoryPlot:

    def __init__(self, points, photo_points=None, save_path=None, basemap=DEFAULT_BASEMAP):
        self.points = points
        self.photo_points = photo_points or []
        self.save_path = save_path
        self.basemap = basemap

    def show(self):
        lats = [p["lat"] for p in self.points]
        lons = [p["lon"] for p in self.points]

        tile_url = BASEMAPS.get(self.basemap)

        if tile_url:
            img, zoom, tx0, ty0 = _build_basemap(lats, lons, tile_url)
        else:
            # blank dark canvas
            img = Image.new("RGBA", (1200, 1200), (30, 30, 30, 255))
            zoom, tx0, ty0 = 16, 0, 0

        draw = ImageDraw.Draw(img)

        def to_px(lat, lon):
            return _lat_lon_to_pixel(lat, lon, zoom, tx0, ty0)

        # compute height filter threshold
        heights = [p["height"] for p in self.photo_points if p.get("height") is not None]
        if heights:
            avg_h = sum(heights) / len(heights)
            h_threshold = avg_h * 0.10
        else:
            avg_h = None
            h_threshold = None

        # track line
        track_px = [to_px(p["lat"], p["lon"]) for p in self.points]
        if len(track_px) > 1:
            draw.line(track_px, fill=(0, 200, 255, 220), width=3)

        # photo markers
        for p in self.photo_points:
            style = QUALITY_STYLE.get(p.get("quality"), QUALITY_STYLE["LOW"])
            px, py = to_px(p["lat"], p["lon"])
            r = style["radius"]
            c = style["color"] + (255,)

            filtered = (
                avg_h is not None
                and p.get("height") is not None
                and abs(p["height"] - avg_h) > h_threshold
            )

            if filtered:
                # red outline, larger
                draw.ellipse([(px - r - 3, py - r - 3), (px + r + 3, py + r + 3)],
                             fill=None, outline=(255, 0, 0, 255), width=3)

            draw.ellipse([(px - r, py - r), (px + r, py + r)], fill=c, outline=(0, 0, 0, 200))

        # start / end markers
        sx, sy = to_px(lats[0], lons[0])
        ex, ey = to_px(lats[-1], lons[-1])
        for cx, cy, col in [(sx, sy, (0, 255, 0, 255)), (ex, ey, (255, 50, 50, 255))]:
            draw.polygon([(cx, cy - 12), (cx - 8, cy + 6), (cx + 8, cy + 6)], fill=col, outline=(0, 0, 0, 200))

        # legend
        legend = [
            ((0, 200, 255), "Track"),
            ((0, 255, 0),   "GOOD"),
            ((255, 220, 0), "NORMAL"),
            ((255, 0, 0),   "LOW"),
        ]
        lx, ly = 12, 12
        for col, label in legend:
            draw.rectangle([(lx, ly), (lx + 16, ly + 16)], fill=col + (220,))
            draw.text((lx + 22, ly), label, fill=(255, 255, 255))
            ly += 22

        out = img.convert("RGB")
        if self.save_path:
            out.save(self.save_path, dpi=(150, 150))
