import matplotlib.pyplot as plt


class TimemarkIntervalPlot:

    def __init__(self, timemarks, save_path="photo_intervals.png"):
        self.timemarks = timemarks
        self.save_path = save_path

    def show(self):

        intervals = []

        for i in range(1, len(self.timemarks)):
            intervals.append(
                (
                    self.timemarks[i]
                    - self.timemarks[i - 1]
                ).total_seconds()
            )

        plt.figure(figsize=(12, 5))

        plt.plot(intervals)

        plt.title(
            "Timemark Intervals"
        )

        plt.xlabel(
            "Photo Number"
        )

        plt.ylabel(
            "Interval (sec)"
        )

        plt.grid(True)
        plt.savefig(
            self.save_path,
            dpi=300,
            bbox_inches="tight"
        )

        plt.show()
        