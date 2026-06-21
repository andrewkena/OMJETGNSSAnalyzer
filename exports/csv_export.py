import csv


class CsvExporter:

    @staticmethod
    def save_visibility(
        filename,
        visibility
    ):

        with open(
            filename,
            "w",
            newline=""
        ) as f:

            writer = csv.writer(f)

            writer.writerow([
                "Satellite",
                "Epochs"
            ])

            for sat, epochs in visibility.items():

                writer.writerow([
                    sat,
                    epochs
                ])