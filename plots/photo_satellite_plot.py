import matplotlib.pyplot as plt


class PhotoSatellitePlot:

    def __init__(
            self,
            photo_report
    ):
        self.photo_report = photo_report

    def show(self):

        photo_ids = [
            row["photo_id"]
            for row in self.photo_report
        ]

        sat_counts = [
            row["satellites"]
            for row in self.photo_report
        ]

        plt.figure(
            figsize=(12, 5)
        )

        plt.plot(
            photo_ids,
            sat_counts
        )

        plt.title(
            "Satellites per Photo"
        )

        plt.xlabel(
            "Photo Number"
        )

        plt.ylabel(
            "Satellite Count"
        )

        plt.grid(True)

        plt.tight_layout()

        plt.show()