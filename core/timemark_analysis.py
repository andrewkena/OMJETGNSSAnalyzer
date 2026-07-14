import numpy as np
from datetime import datetime
from core.obs_file import open_obs


class TimemarkAnalysis:

    def __init__(self, obs_file):
        self.obs_file = obs_file

    def analyze(self):

        timemarks = []

        with open_obs(self.obs_file) as f:

            for line in f:

                if not line.startswith(">"):
                    continue

                parts = line.split()

                if len(parts) < 8:
                    continue

                flag = int(parts[7])

                if flag != 5:
                    continue

                year = int(parts[1])
                month = int(parts[2])
                day = int(parts[3])

                hour = int(parts[4])
                minute = int(parts[5])

                second = float(parts[6])

                dt = datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    int(second),
                    int((second % 1) * 1_000_000)
                )

                timemarks.append(dt)

        intervals = []

        for i in range(1, len(timemarks)):
            intervals.append(
                (
                    timemarks[i] -
                    timemarks[i - 1]
                ).total_seconds()
            )
        intervals = np.array(intervals)

        median_interval = np.median(intervals)

        photo_gaps = np.sum(
            intervals > median_interval * 2
        )
        return {
            "count": len(timemarks),
            "first": timemarks[0],
            "last": timemarks[-1],
            "min_interval": min(intervals),
            "max_interval": max(intervals),
            "avg_interval": np.mean(intervals),
            "timemarks": timemarks,
            "median_interval": median_interval,

            "photo_gaps": int(photo_gaps),

            "nominal_rate":
                1 / median_interval
                if median_interval > 0
                else 0,

        }
