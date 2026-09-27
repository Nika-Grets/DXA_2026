from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.exceptions import AppError
from app.schemas.report import ReportResponse
from app.services.storage import StorageService


class ReportService:
    def __init__(
        self,
        storage: StorageService,
        template_dir: Path,
        template_name: str,
        renderer: Callable[[str, str], bytes] | None = None,
    ) -> None:
        self.storage = storage
        self.template_name = template_name
        self.environment = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html"]),
        )
        # The optional renderer is kept for tests/integration overrides.
        # The production default uses ReportLab, which is already a pinned
        # pure-Python dependency and does not require native Cairo/Pango libs.
        self.renderer = renderer

    @staticmethod
    def _reportlab_pdf(
        *,
        study_id: UUID,
        generated_at: datetime,
        manifest: dict,
        metadata: dict,
        prediction: dict,
        preview_bytes: dict[str, bytes],
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"DXA quality report — {study_id}",
            author="DXA Quality Control",
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "DXATitle",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            spaceAfter=6 * mm,
            textColor=colors.HexColor("#2357a5"),
        )
        heading = ParagraphStyle(
            "DXAHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            spaceBefore=5 * mm,
            spaceAfter=3 * mm,
            textColor=colors.HexColor("#314665"),
        )
        body = ParagraphStyle(
            "DXABody",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=2 * mm,
        )
        small = ParagraphStyle(
            "DXASmall",
            parent=body,
            fontSize=7.5,
            leading=10,
        )
        notice = ParagraphStyle(
            "DXANotice",
            parent=body,
            fontSize=8,
            leading=11,
            backColor=colors.HexColor("#fff5d9"),
            borderColor=colors.HexColor("#d49b00"),
            borderWidth=0.6,
            borderPadding=5,
        )
        story = [
            Paragraph("DICOM quality report", title),
            Paragraph(f"<b>Study:</b> {study_id}", body),
            Paragraph(f"<b>Generated:</b> {generated_at.isoformat()}", body),
            Paragraph(
                f"<b>Quality:</b> {prediction.get('quality_status', 'unknown')}"
                + (
                    f" ({float(prediction['quality_score']):.2f})"
                    if prediction.get("quality_score") is not None
                    else ""
                ),
                body,
            ),
            Paragraph(
                f"<b>Model:</b> {prediction.get('model', {}).get('name', 'unknown')} "
                f"{prediction.get('model', {}).get('version', '')}",
                body,
            ),
        ]

        story.append(Paragraph("Images", heading))
        for image in manifest.get("images", []):
            image_id = str(image.get("image_id"))
            story.append(Paragraph(f"Image {image_id}", body))
            raw = preview_bytes.get(image_id)
            if raw:
                try:
                    img = Image(BytesIO(raw))
                    max_width = 170 * mm
                    max_height = 105 * mm
                    scale = min(
                        max_width / max(img.imageWidth, 1),
                        max_height / max(img.imageHeight, 1),
                        1.0,
                    )
                    img.drawWidth = img.imageWidth * scale
                    img.drawHeight = img.imageHeight * scale
                    story.extend([img, Spacer(1, 3 * mm)])
                except Exception:
                    story.append(Paragraph("Preview could not be embedded.", small))

        story.append(Paragraph("Safe technical metadata", heading))
        for image_id, values in metadata.get("images", {}).items():
            story.append(Paragraph(f"Image {image_id}", body))
            rows = [[Paragraph("<b>Field</b>", small), Paragraph("<b>Value</b>", small)]]
            for key, value in values.items():
                rows.append([Paragraph(str(key), small), Paragraph(str(value), small)])
            table = Table(rows, colWidths=[48 * mm, 122 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7deea")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3fa")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.extend([table, Spacer(1, 2 * mm)])

        story.append(Paragraph("Detected defects", heading))
        defects = prediction.get("defects") or []
        if defects:
            rows = [[
                Paragraph("<b>Image</b>", small),
                Paragraph("<b>Type</b>", small),
                Paragraph("<b>Label</b>", small),
                Paragraph("<b>Confidence</b>", small),
                Paragraph("<b>ROI</b>", small),
            ]]
            for defect in defects:
                rows.append([
                    Paragraph(str(defect.get("image_id", "")), small),
                    Paragraph(str(defect.get("type", "")), small),
                    Paragraph(str(defect.get("label", "")), small),
                    Paragraph(str(defect.get("confidence", "")), small),
                    Paragraph(str(defect.get("roi", "")), small),
                ])
            table = Table(rows, colWidths=[32 * mm, 30 * mm, 38 * mm, 25 * mm, 45 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7deea")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3fa")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]))
            story.append(table)
        else:
            story.append(Paragraph("No defects were returned by the model.", body))

        story.extend([
            Spacer(1, 8 * mm),
            Paragraph(
                "This result was produced by software and is not an independent medical diagnosis "
                "or clinical conclusion.",
                notice,
            ),
        ])

        def footer(canvas, doc_obj):
            canvas.saveState()
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.grey)
            canvas.drawCentredString(
                A4[0] / 2,
                8 * mm,
                f"DXA Quality Control • page {doc_obj.page}",
            )
            canvas.restoreState()

        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        return output.getvalue()

    def generate(self, study_id: UUID) -> ReportResponse:
        path = self.storage.require_study(study_id)
        manifest = self.storage.read_json(path / "manifest.json")
        metadata = self.storage.read_json(path / "metadata.json")
        if not (path / "prediction.json").is_file():
            raise AppError("INVALID_STUDY_STATE", "Prediction is required before report generation", 409)
        prediction = self.storage.read_json(path / "prediction.json")
        generated_at = datetime.now(UTC)
        try:
            preview_bytes: dict[str, bytes] = {}
            for image in manifest["images"]:
                preview_path = path / image["preview_path"]
                preview_bytes[str(image["image_id"])] = self.storage.read_bytes(preview_path)

            if self.renderer is not None:
                # Custom renderer path retained for tests or deployments that
                # explicitly provide their own HTML-to-PDF implementation.
                template = self.environment.get_template(self.template_name)
                previews = {
                    image_id: "data:image/png;base64," + __import__("base64").b64encode(raw).decode("ascii")
                    for image_id, raw in preview_bytes.items()
                }
                html = template.render(
                    study_id=study_id,
                    generated_at=generated_at.isoformat(),
                    manifest=manifest,
                    metadata=metadata,
                    prediction=prediction,
                    previews=previews,
                    study_path=path.as_uri(),
                )
                pdf = self.renderer(html, str(path))
            else:
                pdf = self._reportlab_pdf(
                    study_id=study_id,
                    generated_at=generated_at,
                    manifest=manifest,
                    metadata=metadata,
                    prediction=prediction,
                    preview_bytes=preview_bytes,
                )
        except Exception as exc:
            raise AppError("REPORT_GENERATION_FAILED", "PDF report could not be generated", 500) from exc
        self.storage.write_bytes_atomic(path / "report" / "report.pdf", pdf)
        manifest["status"] = "report_ready"
        self.storage.write_json_atomic(path / "manifest.json", manifest)
        return ReportResponse(
            study_id=study_id,
            report_url=f"/api/v1/studies/{study_id}/report",
            generated_at=generated_at,
        )
