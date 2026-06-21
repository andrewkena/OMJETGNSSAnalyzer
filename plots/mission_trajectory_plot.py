import matplotlib.pyplot as plt

QUALITY_STYLE = {
    "GOOD": dict(color="tab:green", marker="x", size=20),
    "NORMAL": dict(color="gold", marker="x", size=20),
    "LOW": dict(color="red", marker="o", size=30),
}


class MissionTrajectoryPlot:

    def __init__(self, points, photo_points=None, save_path=None):
        self.points = points
        self.photo_points = photo_points or []
        self.save_path = save_path

    def show(self):
        lats = [p["lat"] for p in self.points]
        lons = [p["lon"] for p in self.points]

        plt.figure(figsize=(8, 8))

        plt.plot(lons, lats, "-", color="tab:blue", linewidth=1, label="Трек")

        for quality, style in QUALITY_STYLE.items():
            pts = [p for p in self.photo_points if p.get("quality") == quality]
            if not pts:
                continue
            plt.scatter(
                [p["lon"] for p in pts], [p["lat"] for p in pts],
                marker=style["marker"], color=style["color"], s=style["size"],
                zorder=3, label=f"Фото: {quality}"
            )

        plt.plot(lons[0], lats[0], "^", color="darkgreen", markersize=10, label="Старт")
        plt.plot(lons[-1], lats[-1], "s", color="darkred", markersize=10, label="Финиш")

        plt.title("Траектория миссии")
        plt.xlabel("Долгота")
        plt.ylabel("Широта")
        plt.axis("equal")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        if self.save_path:
            plt.savefig(self.save_path, dpi=300, bbox_inches="tight")

        plt.show()
