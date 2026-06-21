from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image
)

from reportlab.lib.styles import getSampleStyleSheet

import os


class PdfReport:

    def __init__(self, report, image_dir=""):
        self.report = report
        self.image_dir = image_dir

    def _image_path(self, name):
        if self.image_dir:
            return os.path.join(self.image_dir, name)
        return name

    def generate(
            self,
            filename="mission_report.pdf"
    ):

        doc = SimpleDocTemplate(
            filename
        )

        styles = getSampleStyleSheet()

        elements = []

        elements.append(
            Paragraph(
                "OMJET GNSS ANALYZER",
                styles["Title"]
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        elements.append(
            Paragraph(
                "MISSION REPORT",
                styles["Heading1"]
            )
        )
        elements.append(
            Paragraph(
                f"Flight Duration: "
                f"{self.report['flight_duration_min']:.1f} min",
                styles["Normal"]
            )
        )

        elements.append(
            Paragraph(
                f"Photo Count: "
                f"{self.report['photo_count']}",
                styles["Normal"]
            )
        )

        elements.append(
            Paragraph(
                f"Unique Satellites: "
                f"{self.report['unique_satellites']}",
                styles["Normal"]
            )
        )

        elements.append(
            Spacer(1, 15)
        )
        elements.append(
            Paragraph(
                f"Photo Quality: {self.report['photo_quality']}",
                styles["Normal"]
            )
        )

        elements.append(
            Paragraph(
                f"GNSS Quality: {self.report['gnss_quality']}",
                styles["Normal"]
            )
        )

        elements.append(
            Paragraph(
                f"Good Photos: {self.report['good_percent']:.1f}%",
                styles["Normal"]
            )
        )
        elements.append(
            Paragraph(
                f"Final Score: {self.report['final_score']}",
                styles["Normal"]
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        elements.append(
            Paragraph(
                f"<b>MISSION GRADE: "
                f"{self.report['final_score']}</b>",
                styles["Title"]
            )
        )

        elements.append(
            Spacer(1, 20)
        )
        elements.append(
            Spacer(1, 20)
        )

        for heading, image_name in (
            ("Satellite Count", "satellites.png"),
            ("Photo Intervals", "photo_intervals.png"),
            ("Photo Interval Histogram", "photo_histogram.png"),
        ):
            image_path = self._image_path(image_name)

            if not os.path.exists(image_path):
                continue

            elements.append(
                Spacer(1, 20)
            )

            elements.append(
                Paragraph(
                    heading,
                    styles["Heading2"]
                )
            )

            elements.append(
                Image(
                    image_path,
                    width=500,
                    height=250
                )
            )

        doc.build(
            elements
        )