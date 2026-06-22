import numpy as np


class PhotoQuality:

    def __init__(self, timemarks):
        self.timemarks = timemarks

    def analyze(self):

        intervals = []

        for i in range(1, len(self.timemarks)):
            intervals.append(
                (
                    self.timemarks[i]
                    - self.timemarks[i - 1]
                ).total_seconds()
            )

        intervals = np.array(intervals)

        median_interval = np.median(intervals)

        gap_count = np.sum(
            intervals > median_interval * 2
        )

        longest_gap = np.max(intervals)

        std_dev = np.std(intervals)

        p95 = np.percentile(
            intervals,
            95
        )

        if gap_count == 0:
            quality = "EXCELLENT"

        elif gap_count < 5:
            quality = "GOOD"

        elif gap_count < 20:
            quality = "WARNING"

        else:
            quality = "POOR"

        return {
            "median_interval":
                median_interval,

            "std_dev":
                std_dev,

            "p95":
                p95,

            "longest_gap":
                longest_gap,

            "gap_count":
                int(gap_count),

            "quality":
                quality
        }