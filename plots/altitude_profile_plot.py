import matplotlib.pyplot as plt


class AltitudeProfilePlot:

    def __init__(self, points, save_path=None):
        self.points = points
        self.save_path = save_path

    def show(self):
        times = [p["time"] for p in self.points]
        heights = [p["height"] for p in self.points]

        plt.figure(figsize=(12, 5))

        plt.plot(times, heights, "-", color="tab:green", linewidth=1)

        plt.title("Профиль высоты полёта (MSL)")
        plt.xlabel("Время")
        plt.ylabel("Высота, м")
        plt.grid(True)
        plt.tight_layout()

        if self.save_path:
            plt.savefig(self.save_path, dpi=300, bbox_inches="tight")

        plt.show()
