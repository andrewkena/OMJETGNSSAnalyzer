from collections import defaultdict
import numpy as np
from datetime import datetime
from core.obs_file import open_obs


class SatelliteAnalysis:

    def __init__(self, obs_file):
        self.obs_file = obs_file

    def analyze(self):

        epoch_counts = []
        epoch_times = []
        epoch_sat_counts = []
        gps_counts = []
        glo_counts = []
        gal_counts = []
        bds_counts = []

        unique_satellites = set()

        current_satellites = []

        with open_obs(self.obs_file) as f:

            for line in f:

                if line.startswith(">"):

                    parts = line.split()

                    if len(parts) < 8:
                        continue

                    flag = int(parts[7])

                    if flag == 5:
                        continue

                    if flag != 0:
                        current_satellites = []
                        continue

                    # сохраняем предыдущую нормальную эпоху
                    if len(epoch_times) > 0:
                        sat_count = len(current_satellites)
                        if sat_count == 0:
                            pass
                        epoch_counts.append(sat_count)
                        epoch_sat_counts.append(sat_count)

                        gps_counts.append(
                            sum(1 for s in current_satellites if s.startswith("G"))
                        )

                        glo_counts.append(
                            sum(1 for s in current_satellites if s.startswith("R"))
                        )

                        gal_counts.append(
                            sum(1 for s in current_satellites if s.startswith("E"))
                        )

                        bds_counts.append(
                            sum(1 for s in current_satellites if s.startswith("C"))
                        )

                    current_satellites = []

                    year = int(parts[1])
                    month = int(parts[2])
                    day = int(parts[3])

                    hour = int(parts[4])
                    minute = int(parts[5])

                    second = float(parts[6])

                    epoch_time = datetime(
                        year,
                        month,
                        day,
                        hour,
                        minute,
                        int(second),
                        int((second % 1) * 1_000_000)
                    )

                    epoch_times.append(epoch_time)

                    continue

                    continue

                if len(line) < 3:
                    continue

                sat = line[:3]

                if len(sat) == 3:

                    if (
                            len(sat) == 3
                            and sat[0] in ["G", "R", "E", "C"]
                            and sat[1:].isdigit()
                    ):
                        current_satellites.append(
                            sat
                        )

                        unique_satellites.add(
                            sat
                        )

                # сохранить последнюю эпоху файла

            sat_count = len(current_satellites)

            epoch_counts.append(sat_count)
            epoch_sat_counts.append(sat_count)

            gps_counts.append(
                sum(1 for s in current_satellites if s.startswith("G"))
            )

            glo_counts.append(
                sum(1 for s in current_satellites if s.startswith("R"))
            )

            gal_counts.append(
                sum(1 for s in current_satellites if s.startswith("E"))
            )

            bds_counts.append(
                sum(1 for s in current_satellites if s.startswith("C"))
            )


        min_idx = np.argmin(epoch_counts)
        max_idx = np.argmax(epoch_counts)
        return {

            "zero_sat_epochs":
                int(np.sum(np.array(epoch_counts) == 0)),
            "min_time":
                epoch_times[min_idx],

            "max_time":
                epoch_times[max_idx],

            "epoch_times":
                epoch_times,

            "epoch_sat_counts":
                epoch_sat_counts,
            "avg_satellites":
                np.mean(epoch_counts),

            "min_satellites":
                np.min(epoch_counts),

            "max_satellites":
                np.max(epoch_counts),

            "gps_avg":
                np.mean(gps_counts),

            "glo_avg":
                np.mean(glo_counts),

            "gal_avg":
                np.mean(gal_counts),

            "bds_avg":
                np.mean(bds_counts),

            "unique_satellites":
                len(unique_satellites)
        }
