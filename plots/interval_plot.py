import numpy as np
import matplotlib.pyplot as plt


class IntervalPlot:

    def __init__(self, times):
        self.times = times

    def show(self):

        intervals = np.diff(self.times)

        intervals_sec = (
            intervals.astype("timedelta64[ms]")
            .astype(float)
            / 1000
        )

        plt.figure(figsize=(12, 6))

        plt.plot(intervals_sec)

        plt.title(
            "Time Interval Analysis"
        )

        plt.xlabel(
            "Epoch Number"
        )

        plt.ylabel(
            "Interval (s)"
        )

        plt.grid(True)

        plt.tight_layout()

        plt.show()