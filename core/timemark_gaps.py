import numpy as np


class TimemarkGaps:

    def __init__(self, timemarks):
        self.timemarks = timemarks

    def analyze(self):

        intervals = []

        for i in range(1, len(self.timemarks)):

            dt = (
                self.timemarks[i]
                - self.timemarks[i - 1]
            ).total_seconds()

            intervals.append(dt)

        median = np.median(intervals)

        gaps = []

        for i, interval in enumerate(intervals):

            if interval > median * 5:

                gaps.append(
                    {
                        "from":
                            self.timemarks[i],

                        "to":
                            self.timemarks[i + 1],

                        "interval":
                            interval
                    }
                )
        gaps = sorted(
            gaps,
            key=lambda x: x["interval"],
            reverse=True
        )
        return gaps