import matplotlib.pyplot as plt


class PdopPlot:

    def __init__(self, series, save_path=None):
        self.series = series
        self.save_path = save_path

    def show(self):
        times = [s["time"] for s in self.series]
        pdops = [s["pdop"] for s in self.series]

        plt.figure(figsize=(12, 5))

        plt.plot(times, pdops, "-o", color="tab:purple", linewidth=1, markersize=3)
        plt.axhline(4, color="orange", linestyle="--", linewidth=1, label="Порог \"хорошо\" (4)")
        plt.axhline(6, color="red", linestyle="--", linewidth=1, label="Порог \"плохо\" (6)")

        plt.title("PDOP по времени (GPS)")
        plt.xlabel("Время")
        plt.ylabel("PDOP")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        if self.save_path:
            plt.savefig(self.save_path, dpi=300, bbox_inches="tight")

        plt.show()
