import numpy as np
from core.obs_file import open_obs


class RinexTimeReader:

    def __init__(self, filename):
        self.filename = filename

    def get_times(self):

        times = []

        with open_obs(self.filename) as f:

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

                # Секунды могут быть 60.xxx (артефакт округления у приёмника),
                # а np.datetime64 не принимает >= 60. Строим время от начала
                # минуты и добавляем секунды как timedelta — перенос корректный.
                base = np.datetime64(
                    f"{year:04d}-{month:02d}-{day:02d}T"
                    f"{hour:02d}:{minute:02d}:00"
                )
                dt = base + np.timedelta64(int(round(second * 1000)), "ms")

                times.append(dt)

        return np.array(times)