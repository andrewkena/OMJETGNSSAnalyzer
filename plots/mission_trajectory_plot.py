import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import contextily as ctx
    HAS_CONTEXTILY = True
except ImportError:
    HAS_CONTEXTILY = False

QUALITY_STYLE = {
    "GOOD":   dict(color="lime",    marker="x", size=30),
    "NORMAL": dict(color="yellow",  marker="x", size=30),
    "LOW":    dict(color="red",     marker="o", size=40),
}

# Доступные подложки: (label, provider_attr)
BASEMAPS = {
    "Спутник (Esri)":        ("Esri.WorldImagery",          True),
    "OpenStreetMap":          ("OpenStreetMap.Mapnik",        True),
    "Топо (Esri)":            ("Esri.WorldTopoMap",           True),
    "Серая (CartoDB)":        ("CartoDB.Positron",            True),
    "Без подложки":           (None,                          False),
}
BASEMAP_KEYS = list(BASEMAPS.keys())
DEFAULT_BASEMAP = "Спутник (Esri)"


def _get_provider(name):
    import xyzservices.providers as xyz
    parts = name.split(".")
    obj = xyz
    for p in parts:
        obj = getattr(obj, p)
    return obj


class MissionTrajectoryPlot:

    def __init__(self, points, photo_points=None, save_path=None, basemap=DEFAULT_BASEMAP):
        self.points = points
        self.photo_points = photo_points or []
        self.save_path = save_path
        self.basemap = basemap

    def show(self):
        lats = [p["lat"] for p in self.points]
        lons = [p["lon"] for p in self.points]

        use_basemap = False
        provider_name = None
        if HAS_CONTEXTILY and self.basemap in BASEMAPS:
            provider_name, use_basemap = BASEMAPS[self.basemap]
            if provider_name is None:
                use_basemap = False

        if use_basemap:
            import pyproj
            transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
            mx, my = transformer.transform(lons, lats)

            fig, ax = plt.subplots(figsize=(8, 8))
            ax.plot(mx, my, "-", color="cyan", linewidth=1.5, label="Трек")

            for quality, style in QUALITY_STYLE.items():
                pts = [p for p in self.photo_points if p.get("quality") == quality]
                if not pts:
                    continue
                px, py = transformer.transform(
                    [p["lon"] for p in pts], [p["lat"] for p in pts]
                )
                ax.scatter(px, py, marker=style["marker"], color=style["color"],
                           s=style["size"], zorder=4, label=f"Фото: {quality}")

            sx, sy = transformer.transform([lons[0]], [lats[0]])
            ex, ey = transformer.transform([lons[-1]], [lats[-1]])
            ax.plot(sx, sy, "^", color="lime", markersize=10, zorder=5, label="Старт")
            ax.plot(ex, ey, "s", color="red",  markersize=10, zorder=5, label="Финиш")

            try:
                provider = _get_provider(provider_name)
                ctx.add_basemap(ax, source=provider, zoom="auto", attribution=False)
            except Exception:
                pass

            ax.set_axis_off()
        else:
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.plot(lons, lats, "-", color="tab:blue", linewidth=1, label="Трек")

            for quality, style in QUALITY_STYLE.items():
                pts = [p for p in self.photo_points if p.get("quality") == quality]
                if not pts:
                    continue
                ax.scatter(
                    [p["lon"] for p in pts], [p["lat"] for p in pts],
                    marker=style["marker"], color=style["color"], s=style["size"],
                    zorder=3, label=f"Фото: {quality}"
                )

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
