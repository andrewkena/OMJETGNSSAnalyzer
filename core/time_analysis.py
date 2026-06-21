import numpy as np


class TimeAnalysis:

    def __init__(self, times):
        self.times = times

    def get_summary(self):

        if len(self.times) == 0:
            raise ValueError("No epochs found in OBS file")

        start = self.times[0]
        end = self.times[-1]

        intervals = np.diff(self.times)

        intervals_sec = (
            intervals.astype("timedelta64[ms]")
            .astype(float)
            / 1000
        )
        zero_intervals = np.sum(intervals_sec == 0)

        negative_intervals = np.sum(intervals_sec < 0)

        min_interval = intervals_sec.min()
        max_interval = intervals_sec.max()
        avg_interval = intervals_sec.mean()
        median_interval = np.median(intervals_sec)

        nominal_rate = (
            1.0 / median_interval
            if median_interval > 0
            else 0
        )

        lost_epochs = 0

        for interval in intervals_sec:

            if interval > median_interval * 1.5:

                lost_epochs += (
                    round(interval / median_interval) - 1
                )

        expected_epochs = len(self.times) + lost_epochs

        completeness = (
            len(self.times)
            / expected_epochs
            * 100
        )
        duplicate_epochs = int(
            np.sum(intervals_sec == 0)
        )

        large_gaps = int(
            np.sum(intervals_sec > 0.15)
        )
        return {
            "duplicate_epochs":
                duplicate_epochs,

            "large_gaps":
                large_gaps,
            "count": len(self.times),
            "duplicate_epochs": int(zero_intervals),
            "negative_intervals": int(negative_intervals),
            "start": start,
            "end": end,

            "duration_sec":
                (end - start)
                .astype("timedelta64[ms]")
                .astype(float)
                / 1000,

            "min_interval": min_interval,
            "max_interval": max_interval,
            "avg_interval": avg_interval,
            "median_interval": median_interval,

            "nominal_rate_hz": nominal_rate,

            "lost_epochs": lost_epochs,

            "completeness_percent":
                completeness
        }