import numpy as np


def _main_cluster(timemarks):
    """Return the largest contiguous group of timemarks without big gaps."""
    if len(timemarks) < 2:
        return timemarks

    intervals = np.array([
        (timemarks[i] - timemarks[i - 1]).total_seconds()
        for i in range(1, len(timemarks))
    ])

    median_interval = np.median(intervals)
    threshold = median_interval * 3

    # Split into clusters at gap positions
    split_at = np.where(intervals > threshold)[0] + 1
    clusters = np.split(np.arange(len(timemarks)), split_at)

    largest = max(clusters, key=len)
    return [timemarks[i] for i in largest]


class PhotoQuality:

    def __init__(self, timemarks):
        self.timemarks = timemarks

    def analyze(self):
        cluster = _main_cluster(self.timemarks)
        excluded = len(self.timemarks) - len(cluster)

        intervals = np.array([
            (cluster[i] - cluster[i - 1]).total_seconds()
            for i in range(1, len(cluster))
        ])

        median_interval = np.median(intervals)
        gap_count = int(np.sum(intervals > median_interval * 2))
        longest_gap = float(np.max(intervals))
        std_dev = float(np.std(intervals))
        p95 = float(np.percentile(intervals, 95))

        if gap_count == 0:
            quality = "EXCELLENT"
        elif gap_count < 5:
            quality = "GOOD"
        elif gap_count < 20:
            quality = "WARNING"
        else:
            quality = "POOR"

        return {
            "median_interval": median_interval,
            "std_dev": std_dev,
            "p95": p95,
            "longest_gap": longest_gap,
            "gap_count": gap_count,
            "quality": quality,
            "cluster_size": len(cluster),
            "excluded_count": excluded,
        }
