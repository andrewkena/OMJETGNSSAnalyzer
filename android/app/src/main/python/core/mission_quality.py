class MissionQuality:

    def __init__(
            self,
            photo_quality,
            gnss_quality,
            good_percent
    ):
        self.photo_quality = photo_quality
        self.gnss_quality = gnss_quality
        self.good_percent = good_percent

    def analyze(self):

        score_map = {
            "EXCELLENT": 4,
            "GOOD": 3,
            "NORMAL": 2,
            "POOR": 1
        }

        score = 0

        score += score_map.get(
            self.photo_quality,
            1
        )

        score += score_map.get(
            self.gnss_quality,
            1
        )

        if self.good_percent >= 95:
            score += 2
        elif self.good_percent >= 90:
            score += 1
        elif self.good_percent < 80:
            score -= 1

        if score >= 8:
            final = "EXCELLENT"
        elif score >= 6:
            final = "GOOD"
        elif score >= 4:
            final = "NORMAL"
        else:
            final = "POOR"

        return {
            "score": score,
            "final": final
        }