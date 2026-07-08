"""Docx mixin for LabReportPDFService.

Split from lab_report_pdf_service.py.
"""
from __future__ import annotations

from app.services.lab_report_pdf._base import *  # noqa: F401, F403
from app.services.lab_report_pdf._base import LabReportPDFServiceMixinBase


class DocxMixin(LabReportPDFServiceMixinBase):
    """Docx methods."""

    def _render_smear_matrix_reportlab(self, context: dict[str, Any]) -> bytes:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "Neither WeasyPrint nor ReportLab is available for PDF rendering"
            )

        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        font_regular, font_bold = self._register_reportlab_fonts()

        branding = dict(context.get("branding") or {})
        patient = dict(context.get("patient") or {})
        signers = dict(context.get("signers") or {})
        sections = context.get("sections") or []
        first_section = sections[0] if sections else None
        copy_total = max(1, int(context.get("copy_count") or 1))
        report_date = context.get("report_date") or ""

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=10 * mm,
            bottomMargin=12 * mm,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                "LabSmearHeader",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=15,
                leading=17,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabSmearCell",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.2,
                leading=10,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabSmearTitle",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=12.5,
                leading=14,
                alignment=TA_CENTER,
                spaceBefore=8,
                spaceAfter=6,
            )
        )

        def para(value: Any, style_name: str = "LabSmearCell") -> Paragraph:
            text = "" if value is None else str(value)
            text = escape(text).replace("\n", "<br/>")
            return Paragraph(text, styles[style_name])

        story: list[Any] = []
        if not first_section:
            doc.build([])
            return buffer.getvalue()

        row_count = len(first_section.get("fields") or [])
        for copy_index in range(copy_total):
            header_lines = [
                branding.get("clinic_name") or "Doktor Laboratoriyasi",
                f"Манзил: {branding.get('address')}" if branding.get("address") else "",
                f"Телефон: {branding.get('phone')}" if branding.get("phone") else "",
            ]
            header_text = "<br/>".join(escape(line) for line in header_lines if line)
            header_table = Table(
                [[Paragraph(header_text, styles["LabSmearHeader"])]],
                colWidths=[doc.width],
            )
            header_table.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(header_table)
            story.append(Spacer(1, 6))

            patient_table = Table(
                [
                    [para("ФИШ"), para(patient.get("full_name") or "")],
                    [para("Туғилган йили"), para(patient.get("birth_date") or "")],
                    [para("Манзили"), para(patient.get("address") or "")],
                    [para("Текширув санаси"), para(f"«      » ________________ {report_date[-4:]}й" if report_date else "")],
                ],
                colWidths=[4.0 * cm, doc.width - 4.0 * cm],
            )
            patient_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#111827")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("FONTNAME", (0, 0), (-1, -1), font_regular),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(patient_table)
            story.append(Spacer(1, 8))

            story.append(
                Paragraph(
                    "СУРТМА ТАХЛИЛИ (степень чистоты)",
                    styles["LabSmearTitle"],
                )
            )

            matrix_rows: list[list[Any]] = [[
                para("Кўрсатгичлар", "LabSmearCell"),
                *[
                    para(section.get("title") or section.get("key") or "", "LabSmearCell")
                    for section in sections
                ],
            ]]
            for row_index in range(row_count):
                matrix_row = [para(first_section["fields"][row_index].get("label") or "", "LabSmearCell")]
                for section in sections:
                    row = (section.get("fields") or [])[row_index]
                    value_display = row.get("value_text") or ""
                    if row.get("value_numeric") is not None:
                        value_display = row.get("value_numeric")
                    matrix_row.append(
                        para(value_display if value_display is not None else "", "LabSmearCell")
                    )
                matrix_rows.append(matrix_row)

            matrix_table = Table(
                matrix_rows,
                colWidths=[5.0 * cm] + [(doc.width - 5.0 * cm) / max(1, len(sections))] * len(sections),
                repeatRows=1,
            )
            matrix_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#111827")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                        ("FONTNAME", (0, 0), (-1, -1), font_regular),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(matrix_table)
            story.append(Spacer(1, 10))

            signature_text = f"{signers.get('lab_technician_label') or 'Врач лаборант'}:________{signers.get('lab_technician_name') or ''}"
            story.append(Paragraph(signature_text, styles["LabSmearCell"]))

            if copy_index < copy_total - 1:
                story.append(PageBreak())

        doc.build(story)
        return buffer.getvalue()


    def _register_reportlab_fonts(self) -> tuple[str, str]:
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            return "Helvetica", "Helvetica-Bold"

        candidate_pairs = [
            (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
            (Path("C:/Windows/Fonts/arialuni.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
            (Path("C:/Windows/Fonts/times.ttf"), Path("C:/Windows/Fonts/timesbd.ttf")),
            (
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ),
            (
                Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
                Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
            ),
        ]

        for regular_path, bold_path in candidate_pairs:
            if not regular_path.exists():
                continue

            regular_name = f"LabFont-{regular_path.stem}"
            bold_name = f"{regular_name}-Bold"
            if regular_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
            if bold_path.exists():
                if bold_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                return regular_name, bold_name
            return regular_name, regular_name

        logger.warning(
            "[LAB][PDF] no Unicode TTF font found for ReportLab fallback, using Helvetica"
        )
        return "Helvetica", "Helvetica-Bold"


    def _resolve_logo_url(self, logo_url: str | None) -> str | None:
        if not logo_url:
            return None
        if logo_url.startswith(("http://", "https://", "data:")):
            return logo_url
        if logo_url.startswith("/"):
            candidate = self.backend_root / logo_url.lstrip("/")
            if candidate.exists():
                return candidate.resolve().as_uri()
        candidate = Path(logo_url)
        if candidate.exists():
            return candidate.resolve().as_uri()
        logger.warning("[LAB][PDF] logo asset not found for %s", logo_url)
        return None


    def _reportlab_logo_flowable(self, logo_url: str | None):
        if not logo_url:
            return None

        try:
            from reportlab.lib.units import cm
            from reportlab.platypus import Image
        except ImportError:
            return None

        if logo_url.startswith("data:"):
            try:
                header, encoded = logo_url.split(",", 1)
                image_data = base64.b64decode(encoded)
                return Image(io.BytesIO(image_data), width=2.0 * cm, height=2.0 * cm)
            except Exception:
                return None

        parsed = urlparse(logo_url)
        candidate_path = None
        if parsed.scheme == "file":
            candidate_path = Path(unquote(parsed.path))
        elif logo_url.startswith("/"):
            candidate_path = self.backend_root / logo_url.lstrip("/")
        else:
            candidate_path = Path(logo_url)

        if candidate_path and candidate_path.exists():
            try:
                return Image(str(candidate_path), width=2.0 * cm, height=2.0 * cm)
            except Exception:
                return None
        return None


    def _build_css(self, *, layout_preset: str, page_settings: dict[str, Any]) -> str:
        paper_size = page_settings.get("paper_size", "A4")
        orientation = page_settings.get("orientation", "portrait")
        page_margin = "10mm 12mm 12mm 12mm"
        row_padding = "5px 6px"
        header_font = "13px"
        body_font = "11px"
        if layout_preset == "lab_table_compact_v1":
            page_margin = "8mm 10mm 10mm 10mm"
            row_padding = "4px 5px"
            header_font = "12px"
            body_font = "10px"

        return f"""
@page {{
  size: {paper_size} {orientation};
  margin: {page_margin};
}}
body {{
  font-family: 'Times New Roman', serif;
  font-size: {body_font};
  color: #111827;
  line-height: 1.15;
}}
.page {{
  width: 100%;
}}
.header-table,
.patient-table,
.lab-table,
.critical-table,
.footer-table {{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}}
.header-table td {{
  vertical-align: top;
}}
.logo-cell {{
  width: 92px;
}}
.logo {{
  width: 84px;
  max-height: 84px;
  object-fit: contain;
}}
.branding-title {{
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 2px;
}}
.branding-subtitle {{
  font-size: {header_font};
  margin-bottom: 4px;
}}
.muted {{
  color: #4b5563;
}}
.patient-table td {{
  border: 1px solid #1f2937;
  padding: 4px 6px;
  overflow-wrap: anywhere;
  word-break: break-word;
}}
.section-title {{
  margin-top: 12px;
  margin-bottom: 4px;
  font-size: {header_font};
  font-weight: 700;
  text-transform: uppercase;
  break-after: avoid;
}}
.oam-title {{
  margin-top: 10px;
  margin-bottom: 6px;
  font-size: {header_font};
  font-weight: 700;
  text-align: center;
  text-transform: uppercase;
}}
.oam-table .oam-section-row td {{
  background: #f3f4f6;
  font-weight: 700;
  text-align: center;
}}
.lab-table th,
.lab-table td {{
  border: 1px solid #111827;
  padding: {row_padding};
  overflow-wrap: anywhere;
  word-break: break-word;
}}
.lab-table th {{
  background: #e5e7eb;
  text-align: left;
}}
.lab-table .col-result,
.lab-table .col-unit,
.lab-table .col-flag {{
  text-align: center;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}}
.lab-table tr {{
  break-inside: avoid;
}}
.flag-high,
.flag-low,
.flag-warning,
.flag-abnormal,
.flag-critical {{
  font-weight: 700;
}}
.flag-warning,
.flag-abnormal {{
  color: #92400e;
}}
.flag-high {{
  color: #991b1b;
}}
.flag-low {{
  color: #1d4ed8;
}}
.flag-critical {{
  color: #7f1d1d;
}}
.critical-block {{
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid #7f1d1d;
  background: #fef2f2;
}}
.critical-title {{
  font-size: {header_font};
  font-weight: 700;
  color: #7f1d1d;
  margin-bottom: 6px;
}}
.critical-table th,
.critical-table td {{
  border: 1px solid #b91c1c;
  padding: {row_padding};
  overflow-wrap: anywhere;
  word-break: break-word;
}}
.critical-table th {{
  background: #fee2e2;
  text-align: left;
}}
.critical-table .col-result,
.critical-table .col-flag {{
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}}
.critical-table tr {{
  break-inside: avoid;
}}
.footer-table td {{
  padding-top: 12px;
  vertical-align: top;
}}
.smear-title {{
  margin-top: 10px;
  margin-bottom: 6px;
  font-size: {header_font};
  font-weight: 700;
  text-align: center;
  text-transform: uppercase;
}}
.smear-matrix-table .smear-site-cell {{
  text-align: center;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}}
.smear-signature {{
  margin-top: 10px;
  font-weight: 700;
}}
.smear-copy {{
  break-after: page;
}}
"""




