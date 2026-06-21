import matplotlib.pyplot as plt


class SatellitesPlot:

    def __init__(
            self,
            times,
            sat_counts,
            save_path=None
    ):
        self.times = times
        self.sat_counts = sat_counts
        self.save_path = save_path

    def show(self):

        plt.figure(figsize=(12, 6))

        plt.plot(
            self.times,
            self.sat_counts
        )

        plt.title(
            "Satellites vs Time"
        )

        plt.xlabel(
            "Time"
        )

        plt.ylabel(
            "Satellite Count"
        )

        plt.grid(True)
        if self.save_path:
            plt.savefig(
                self.save_path,
                dpi=300,
                bbox_inches="tight"
            )

        plt.show()