import matplotlib.pyplot as plt
import numpy as np


class TimemarkHistogram:

    def __init__(self, timemarks, save_path="photo_histogram.png"):
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

        plt.figure(figsize=(10, 5))

        plt.hist(
            intervals,
            bins=30
        )

        plt.title(
            "Timemark Interval Distribution"
        )

        plt.xlabel("Interval (sec)")
        plt.ylabel("Count")

        plt.grid(True)
        plt.savefig(
            self.save_path,
            dpi=300,
            bbox_inches="tight"
        )

        plt.show()
        