import csv
class PhotoSatelliteReport:

    def __init__(
            self,
            timemarks,
            epoch_times,
            sat_counts,
            csv_path="photo_satellite_report.csv"
    ):
        self.timemarks = timemarks
        self.epoch_times = epoch_times
        self.sat_counts = sat_counts
        self.csv_path = csv_path

    def analyze(self):

        report = []

        for photo_id, photo_time in enumerate(
                self.timemarks,
                start=1
        ):

            closest_count = 0
            best_diff = 999999

            for epoch_time, count in zip(
                    self.epoch_times,
                    self.sat_counts
            ):

                if count == 0:
                    continue

                diff = abs(
                    (epoch_time - photo_time)
                    .total_seconds()
                )

                if diff < best_diff:
                    best_diff = diff
                    closest_count = count


            if closest_count >= 20:
                quality = "GOOD"
            elif closest_count >= 15:
                quality = "NORMAL"
            else:
                quality = "LOW"
            report.append({
                "photo_id": photo_id,
                "time": photo_time,
                "satellites": closest_count,
                "quality": quality
            })



        good = sum(
            1 for r in report
            if r["quality"] == "GOOD"
        )

        normal = sum(
            1 for r in report
            if r["quality"] == "NORMAL"
        )

        low = sum(
            1 for r in report
            if r["quality"] == "LOW"
        )



        with open(
                self.csv_path,
                "w",
                newline="",
                encoding="utf-8"
        ) as f:

            writer = csv.writer(f)

            writer.writerow([
                "PhotoID",
                "Time",
                "Satellites",
                "Quality"
            ])

            for row in report:
                writer.writerow([
                    row["photo_id"],
                    row["time"],
                    row["satellites"],
                    row["quality"]
                ])

        return {
            "report": report,
            "good": good,
            "normal": normal,
            "low": low
        }
