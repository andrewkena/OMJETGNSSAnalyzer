class ReportExporter:

    def __init__(self, report):
        self.report = report

    def save_txt(
            self,
            path="mission_report.txt"
    ):

        with open(
                path,
                "w",
                encoding="utf-8"
        ) as f:

            f.write(
                "MISSION REPORT\n"
            )

            f.write(
                "=" * 50 + "\n\n"
            )

            f.write(
                f"Photo Quality : "
                f"{self.report['photo_quality']}\n"
            )

            f.write(
                f"GNSS Quality  : "
                f"{self.report['gnss_quality']}\n"
            )

            f.write(
                f"Good Photos   : "
                f"{self.report['good_percent']:.1f}%\n"
            )

            f.write("\n")

            f.write(
                f"GOOD   : "
                f"{self.report['good_count']}\n"
            )

            f.write(
                f"NORMAL : "
                f"{self.report['normal_count']}\n"
            )

            f.write(
                f"LOW    : "
                f"{self.report['low_count']}\n"
            )

            f.write("\n")

            f.write(
                f"Average Satellites : "
                f"{self.report['avg_satellites']:.1f}\n"
            )

            f.write(
                f"Minimum Satellites : "
                f"{self.report['min_satellites']}\n"
            )

            f.write(
                f"Maximum Satellites : "
                f"{self.report['max_satellites']}\n"
            )

            f.write("\n")

            f.write(
                f"Final Score : "
                f"{self.report['final_score']}\n"
            )

        print()
        print("REPORT SAVED:")
        print(path)