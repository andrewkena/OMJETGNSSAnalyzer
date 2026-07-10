import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import contextily as ctx
    import pyproj
    HAS_CONTEXTILY = True
except ImportError:
    HAS_CONTEXTILY = False

QUALITY_STYLE = {
    "GOOD":   dict(color="lime",   marker="x", size=30),
    "NORMAL": dict(color="yellow", marker="x", size=30),
    "LOW":    dict(color="red",    marker="o", size=40),
}

# label -> tile URL (XYZ, EPSG:3857)
BASEMAPS = {
    "Спутник Google":  "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Гибрид Google":   "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "Дороги Google":   "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "OpenStreetMap":   "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Без подложки":    None,
}
BASEMAP_KEYS = list(BASEMAPS.keys())
DEFAULT_BASEMAP = "Спутник Google"

_WGS84_TO_WEB = None


def _transformer():
    global _WGS84_TO_WEB
    if _WGS84_TO_WEB is None:
        _WGS84_TO_WEB = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    return _WGS84_TO_WEB


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
        use_tiles = HAS_CONTEXTILY and tile_url is not None

        fig, ax = plt.subplots(figsize=(8, 8))

        if use_tiles:
            t = _transformer()
            mx, my = t.transform(lons, lats)

            ax.plot(mx, my, "-", color="cyan", linewidth=1.5, label="Трек", zorder=3)

            for quality, style in QUALITY_STYLE.items():
                pts = [p for p in self.photo_points if p.get("quality") == quality]
                if not pts:
                    continue
                px, py = t.transform([p["lon"] for p in pts], [p["lat"] for p in pts])
                ax.scatter(px, py, marker=style["marker"], color=style["color"],
                           s=style["size"], zorder=4, label=f"Фото: {quality}")

            sx, sy = t.transform([lons[0]], [lats[0]])
            ex, ey = t.transform([lons[-1]], [lats[-1]])
            ax.plot(sx, sy, "^", color="lime", markersize=10, zorder=5, label="Старт")
            ax.plot(ex, ey, "s", color="red",  markersize=10, zorder=5, label="Финиш")

            try:
                ctx.add_basemap(ax, source=tile_url, zoom="auto", attribution=False)
            except Exception as e:
                ax.set_facecolor("#1a1a2e")
                ax.text(0.5, 0.5, f"Тайлы недоступны:\n{e}",
                        transform=ax.transAxes, ha="center", va="center",
                        color="white", fontsize=8)

            ax.set_axis_off()
        else:
            ax.plot(lons, lats, "-", color="tab:blue", linewidth=1, label="Трек")

            for quality, style in QUALITY_STYLE.items():
                pts = [p for p in self.photo_points if p.get("quality") == quality]
                if not pts:
                    continue
                ax.scatter([p["lon"] for p in pts], [p["lat"] for p in pts],
                           marker=style["marker"], color=style["color"],
                           s=style["size"], zorder=3, label=f"Фото: {quality}")

            ax.plot(lons[0], lats[0], "^", color="darkgreen", markersize=10, label="Старт")
            ax.plot(lons[-1], lats[-1], "s", color="darkred",  markersize=10, label="Финиш")
            ax.set_xlabel("Долгота")
            ax.set_ylabel("Широта")
            ax.axis("equal")
            ax.grid(True)

        ax.set_title(f"Траектория миссии  [{self.basemap}]")
        ax.legend(fontsize=8, loc="upper left")
        plt.tight_layout()

        if self.save_path:
            plt.savefig(self.save_path, dpi=150, bbox_inches="tight")

        plt.close(fig)
