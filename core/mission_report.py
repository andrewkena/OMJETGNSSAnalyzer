class MissionReport:

    def __init__(self, report):
        self.report = report

    def generate_text(self):

        lines = []

        lines.append("MISSION REPORT")
        lines.append("=" * 50)
        lines.append("")

        lines.append(
            f"Photo Quality : {self.report['photo_quality']}"
        )

        lines.append(
            f"GNSS Quality  : {self.report['gnss_quality']}"
        )

        lines.append(
            f"Good Photos   : {self.report['good_percent']:.1f}%"
        )

        lines.append("")

        lines.append(
            f"GOOD   : {self.report['good_count']}"
        )

        lines.append(
            f"NORMAL : {self.report['normal_count']}"
        )

        lines.append(
            f"LOW    : {self.report['low_count']}"
        )

        lines.append("")

        lines.append(
            f"Average Satellites : {self.report['avg_satellites']:.1f}"
        )

        lines.append(
            f"Minimum Satellites : {self.report['min_satellites']}"
        )

        lines.append(
            f"Maximum Satellites : {self.report['max_satellites']}"
        )

        lines.append("")

        lines.append(
            f"Final Score : {self.report['final_score']}"
        )

        return "\n".join(lines)