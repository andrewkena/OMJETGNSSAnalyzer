from collections import defaultdict


class SatelliteVisibility:

    def __init__(self, obs_file):
        self.obs_file = obs_file

    def analyze(self):

        satellites = defaultdict(int)

        with open(
            self.obs_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                if len(line) < 3:
                    continue

                sat = line[:3].strip()

                if (
                    len(sat) == 3
                    and sat[0] in ["G", "R", "E", "C"]
                ):
                    satellites[sat] += 1

        return dict(
            sorted(
                satellites.items()
            )
        )