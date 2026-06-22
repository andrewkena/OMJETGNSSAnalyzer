import numpy as np


class RinexTimeReader:

    def __init__(self, filename):
        self.filename = filename

    def get_times(self):

        times = []

        with open(
            self.filename,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                if not line.startswith(">"):
                    continue

                parts = line.split()

                year = int(parts[1])
                month = int(parts[2])
                day = int(parts[3])

                hour = int(parts[4])
                minute = int(parts[5])

                second = float(parts[6])

                dt = np.datetime64(
                    f"{year:04d}-{month:02d}-{day:02d}T"
                    f"{hour:02d}:{minute:02d}:{second:06.3f}"
                )

                times.append(dt)

        return np.array(times)