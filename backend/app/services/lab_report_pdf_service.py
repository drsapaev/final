"""Dedicated PDF renderer for structured laboratory reports."""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime, UTC
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jinja2 import Environment, FileSystemLoader

from app.services.pdf_service import REPORTLAB_AVAILABLE, _load_weasyprint_components

logger = logging.getLogger(__name__)


class LabReportPDFService:
    """Renders fixed-layout laboratory templates to PDF."""

    def __init__(self) -> None:
        self.backend_root = Path(__file__).resolve().parents[2]
        self.templates_dir = self.backend_root / "app" / "templates" / "print"
        self.jinja_env = Environment(autoescape=True,
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_report(self, context: dict[str, Any]) -> bytes:
        layout_preset = context.get("layout_preset") or "lab_table_classic_v1"
        page_settings = context.get("page_settings") or {}
        context = dict(context)
        context["generated_at"] = datetime.now(UTC)
        context["oam_docx_mode"] = self._is_oam_docx_template(context)
        context["smear_matrix_mode"] = self._is_smear_matrix_template(context)
        context["docx_three_column_mode"] = self._is_docx_three_column_template(context)
        context["copy_count"] = self._resolve_copy_count(context)
        context["branding"] = dict(context.get("branding") or {})
        context["branding"]["logo_file_url"] = self._resolve_logo_url(
            context["branding"].get("logo_url")
        )
        logger.info(
            "[LAB][PDF] render_report layout_preset=%s page_settings=%s",
            layout_preset,
            page_settings,
        )
        try:
            weasy_css, weasy_html = _load_weasyprint_components()
        except (ImportError, OSError) as exc:
            if REPORTLAB_AVAILABLE:
                logger.warning("[LAB][PDF] falling back to ReportLab renderer: %s", exc)
                return self._render_reportlab(context)
            raise

        template = self.jinja_env.get_template("lab_report_fixed.j2")
        html_content = template.render(**context)
        css_content = self._build_css(layout_preset=layout_preset, page_settings=page_settings)
        html_doc = weasy_html(string=html_content, base_url=str(self.backend_root))
        css_doc = weasy_css(string=css_content)
        return html_doc.write_pdf(stylesheets=[css_doc])

    def _resolve_copy_count(self, context: dict[str, Any]) -> int:
        if self._is_docx_three_column_template(context):
            return 1
        if self._is_smear_matrix_template(context):
            return 2
        sections = context.get("sections") or []
        for section in sections:
            section_style = section.get("section_style") or {}
            copy_count = section_style.get("copy_count")
            if copy_count is not None:
                try:
                    value = int(copy_count)
                    if value > 0:
                        return value
                except (TypeError, ValueError):
                    continue
        return 1

    def _is_smear_matrix_template(self, context: dict[str, Any]) -> bool:
        if str(context.get("template_name") or "").strip() == "Мазок":
            return True
        for section in context.get("sections") or []:
            section_style = section.get("section_style") or {}
            if str(section_style.get("render") or "").strip() == "smear_matrix":
                return True
        return False

    def _is_oam_docx_template(self, context: dict[str, Any]) -> bool:
        if str(context.get("template_name") or "").strip() == "ОАМ":
            return True
        for section in context.get("sections") or []:
            section_style = section.get("section_style") or {}
            if str(section_style.get("render") or "").strip() == "oam_docx":
                return True
        return False

    def _is_docx_three_column_template(self, context: dict[str, Any]) -> bool:
        template_name = str(context.get("template_name") or "").strip()
        if template_name in {"ОАК", "Биохимия"}:
            return True
        for section in context.get("sections") or []:
            section_style = section.get("section_style") or {}
            if str(section_style.get("render") or "").strip() == "docx_three_column":
                return True
        return False

    def _render_reportlab(self, context: dict[str, Any]) -> bytes:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "Neither WeasyPrint nor ReportLab is available for PDF rendering"
            )

        from reportlab.lib import colors  # noqa: I001
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        context = dict(context)
        branding = dict(context.get("branding") or {})
        patient = dict(context.get("patient") or {})
        signers = dict(context.get("signers") or {})
        sections = context.get("sections") or []
        critical_findings = context.get("critical_findings") or []
        if context.get("oam_docx_mode"):
            return self._render_oam_docx_reportlab(context)
        if context.get("docx_three_column_mode"):
            return self._render_docx_three_column_reportlab(context)
        if context.get("smear_matrix_mode"):
            return self._render_smear_matrix_reportlab(context)
        font_regular, font_bold = self._register_reportlab_fonts()

        page_settings = context.get("page_settings") or {}
        paper_size = str(page_settings.get("paper_size") or "A4").upper()
        orientation = str(page_settings.get("orientation") or "portrait").lower()
        page_size = A4
        if orientation == "landscape":
            page_size = landscape(A4)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=10 * mm,
            bottomMargin=12 * mm,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                "LabHeader",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=16,
                leading=18,
                alignment=TA_LEFT,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabSubHeader",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=10,
                leading=12,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#4b5563"),
            )
        )
        styles.add(
            ParagraphStyle(
                "LabSection",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=12,
                leading=14,
                alignment=TA_LEFT,
                spaceBefore=8,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabCell",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.2 if paper_size == "A4" else 8.6,
                leading=10,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabCenter",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.2 if paper_size == "A4" else 8.6,
                leading=10,
                alignment=TA_CENTER,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabTiny",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=8.5,
                leading=9.5,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#4b5563"),
            )
        )

        def para(value: Any, style_name: str = "LabCell") -> Paragraph:
            text = "" if value is None else str(value)
            text = escape(text).replace("\n", "<br/>")
            return Paragraph(text, styles[style_name])

        story: list[Any] = []

        logo_flowable = self._reportlab_logo_flowable(branding.get("logo_file_url"))
        header_lines = [
            branding.get("clinic_name") or "Doktor Laboratoriyasi",
            f"Манзил: {branding.get('address')}" if branding.get("address") else "",
            (
                "Мўлжал: "
                + (branding.get("document_subtitle") or "")
                + (
                    f"                                                                             Телефон:   {branding.get('phone')}"
                    if branding.get("phone")
                    else ""
                )
            ).strip(),
        ]
        header_text = "<br/>".join(
            escape(line) for line in header_lines if line
        )
        header_table = Table(
            [[logo_flowable or Spacer(1, 1), Paragraph(header_text, styles["LabHeader"])]],
            colWidths=[2.6 * cm, doc.width - 2.6 * cm],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
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
                [para("ФИО / ФИШ", "LabCell"), para(patient.get("full_name") or "", "LabCell"),
                 para("Дата", "LabCell"), para(context.get("report_date") or "", "LabCell")],
                [para("Дата рождения", "LabCell"), para(patient.get("birth_date") or "", "LabCell"),
                 para("Пол", "LabCell"), para(patient.get("sex") or "", "LabCell")],
                [para("Телефон", "LabCell"), para(patient.get("phone") or "", "LabCell"),
                 para("Адрес", "LabCell"), para(patient.get("address") or "", "LabCell")],
            ],
            colWidths=[3.2 * cm, 6.8 * cm, 3.0 * cm, doc.width - 13.0 * cm],
        )
        patient_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#111827")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
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

        if critical_findings:
            story.append(Paragraph("Critical Findings", styles["LabSection"]))
            critical_rows = [[
                para("Показатель", "LabCenter"),
                para("Результат", "LabCenter"),
                para("Норма", "LabCenter"),
                para("Порог", "LabCenter"),
                para("Флаг", "LabCenter"),
            ]]
            for finding in critical_findings:
                critical_rows.append(
                    [
                        para(finding.get("label"), "LabCell"),
                        para(
                            f"{finding.get('value_display')}{' ' + str(finding.get('unit')) if finding.get('unit') else ''}",
                            "LabCell",
                        ),
                        para(finding.get("reference_text") or "", "LabCell"),
                        para(finding.get("threshold_display") or "", "LabCell"),
                        para(finding.get("resolved_flag") or "", "LabCenter"),
                    ]
                )
            critical_table = Table(
                critical_rows,
                colWidths=[5.0 * cm, 3.0 * cm, 4.0 * cm, 3.0 * cm, doc.width - 15.0 * cm],
                repeatRows=1,
            )
            critical_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#b91c1c")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#7f1d1d")),
                        ("FONTNAME", (0, 0), (-1, -1), font_regular),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(critical_table)
            story.append(Spacer(1, 8))

        for section in sections:
            story.append(Paragraph(section.get("title") or section.get("key") or "", styles["LabSection"]))
            rows = [[
                para("Показатель", "LabCenter"),
                para("Результат", "LabCenter"),
                para("Ед.", "LabCenter"),
                para("Норма", "LabCenter"),
                para("Флаг", "LabCenter"),
            ]]
            for row in section.get("fields") or []:
                value_display = row.get("value_text") or ""
                if row.get("value_numeric") is not None:
                    value_display = row.get("value_numeric")
                rows.append(
                    [
                        para(row.get("label"), "LabCell"),
                        para(value_display, "LabCell"),
                        para(row.get("unit") or "", "LabCenter"),
                        para(row.get("reference_text") or "", "LabCell"),
                        para(row.get("resolved_flag") or "", "LabCenter"),
                    ]
                )
            section_table = Table(
                rows,
                colWidths=[6.0 * cm, 3.2 * cm, 1.8 * cm, 5.4 * cm, doc.width - 16.4 * cm],
                repeatRows=1,
            )
            section_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#111827")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                        ("FONTNAME", (0, 0), (-1, -1), font_regular),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.6 if paper_size == "A4" else 8.1),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(KeepTogether([section_table]))
            story.append(Spacer(1, 6))

        footer_notes = context.get("footer_notes")
        if footer_notes:
            story.append(Paragraph(str(footer_notes), styles["LabTiny"]))
            story.append(Spacer(1, 8))

        signature_table = Table(
            [
                [
                    para(signers.get("lab_technician_label") or "Лаборант", "LabCell"),
                    para(signers.get("approver_label") or "Подпись", "LabCell"),
                ],
                [
                    para(signers.get("lab_technician_name") or "________________", "LabCell"),
                    para(signers.get("approver_name") or "________________", "LabCell"),
                ],
            ],
            colWidths=[doc.width / 2, doc.width / 2],
        )
        signature_table.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#111827")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(signature_table)

        doc.build(story)
        return buffer.getvalue()

    def _render_docx_three_column_reportlab(self, context: dict[str, Any]) -> bytes:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "Neither WeasyPrint nor ReportLab is available for PDF rendering"
            )

        from reportlab.lib import colors  # noqa: I001
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        font_regular, font_bold = self._register_reportlab_fonts()

        branding = dict(context.get("branding") or {})
        patient = dict(context.get("patient") or {})
        signers = dict(context.get("signers") or {})
        sections = context.get("sections") or []
        first_section = sections[0] if sections else None
        if not first_section:
            buffer = io.BytesIO()
            SimpleDocTemplate(buffer, pagesize=A4).build([])
            return buffer.getvalue()

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
                "LabDocxHeader",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=16,
                leading=18,
                alignment=TA_LEFT,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabDocxTitle",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=14.2,
                leading=15.2,
                alignment=TA_CENTER,
                spaceBefore=4,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabDocxCell",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.0,
                leading=10,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabDocxCenter",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.0,
                leading=10,
                alignment=TA_CENTER,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabDocxTiny",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=8.5,
                leading=9.5,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#4b5563"),
            )
        )

        def para(value: Any, style_name: str = "LabDocxCell") -> Paragraph:
            text = "" if value is None else str(value)
            text = escape(text).replace("\n", "<br/>")
            return Paragraph(text, styles[style_name])

        patient_full_name = patient.get("full_name") or "________________________________________________"
        patient_birth_date = patient.get("birth_date") or "____________________"
        patient_address = patient.get("address") or "________________________________________________"
        year_text = ""
        report_date = str(context.get("report_date") or "")
        if report_date:
            year_text = report_date[-4:]

        header_lines = [
            branding.get("clinic_name") or "Doktor Laboratoriyasi",
            f"Манзил: {branding.get('address')}" if branding.get("address") else "",
            (
                "Мўлжал: "
                + (branding.get("document_subtitle") or "")
                + (f"                                                                             Телефон:   {branding.get('phone')}" if branding.get("phone") else "")
            ).strip(),
        ]
        header_text = "<br/>".join(escape(line) for line in header_lines if line)
        story: list[Any] = [
            Paragraph(header_text, styles["LabDocxHeader"]),
            Spacer(1, 4),
            Table(
                [
                    [para("ФИШ"), para(patient_full_name)],
                    [para("Туғилган йили"), para(patient_birth_date)],
                    [para("Манзили"), para(patient_address)],
                    [para("Текширув санаси"), para(f"«___» ____________________{year_text}   й")],
                ],
                colWidths=[4.0 * cm, doc.width - 4.0 * cm],
            ),
            Spacer(1, 8),
            Paragraph(
                str(branding.get("document_title") or context.get("template_name") or "").upper(),
                styles["LabDocxTitle"],
            ),
        ]

        patient_table = story[2]
        if isinstance(patient_table, Table):
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

        rows = [[
            para("Тахлил номи", "LabDocxCenter"),
            para("Натижа", "LabDocxCenter"),
            para("Норма", "LabDocxCenter"),
        ]]
        for row in first_section.get("fields") or []:
            value_display = row.get("value_text") or ""
            if row.get("value_numeric") is not None:
                value_display = row.get("value_numeric")
            rows.append(
                [
                    para(row.get("label") or "", "LabDocxCell"),
                    para(value_display if value_display is not None else "", "LabDocxCell"),
                    para(row.get("reference_text") or "", "LabDocxCell"),
                ]
            )

        table = Table(
            rows,
            colWidths=[7.6 * cm, 3.8 * cm, doc.width - 11.4 * cm],
            repeatRows=1,
        )
        table.setStyle(
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
        story.append(table)
        story.append(Spacer(1, 8))

        footer_notes = context.get("footer_notes")
        if footer_notes:
            story.append(Paragraph(str(footer_notes), styles["LabDocxTiny"]))
            story.append(Spacer(1, 6))

        story.append(
            Paragraph(
                f"{signers.get('lab_technician_label') or 'Врач лаборант'}:________{signers.get('lab_technician_name') or ''}",
                styles["LabDocxCell"],
            )
        )

        doc.build(story)
        return buffer.getvalue()

    def _render_oam_docx_reportlab(self, context: dict[str, Any]) -> bytes:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "Neither WeasyPrint nor ReportLab is available for PDF rendering"
            )

        from reportlab.lib import colors  # noqa: I001
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        font_regular, font_bold = self._register_reportlab_fonts()

        branding = dict(context.get("branding") or {})
        patient = dict(context.get("patient") or {})
        signers = dict(context.get("signers") or {})
        sections = context.get("sections") or []
        physical_section = sections[0] if sections else None
        sediment_section = sections[1] if len(sections) > 1 else None
        if not physical_section:
            buffer = io.BytesIO()
            SimpleDocTemplate(buffer, pagesize=A4).build([])
            return buffer.getvalue()

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
                "LabOamHeader",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=16,
                leading=18,
                alignment=TA_LEFT,
                spaceAfter=2,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabOamTitle",
                parent=styles["Normal"],
                fontName=font_bold,
                fontSize=14.2,
                leading=15.2,
                alignment=TA_CENTER,
                spaceBefore=4,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabOamCell",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.0,
                leading=10,
                alignment=TA_LEFT,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabOamCenter",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=9.0,
                leading=10,
                alignment=TA_CENTER,
            )
        )
        styles.add(
            ParagraphStyle(
                "LabOamTiny",
                parent=styles["Normal"],
                fontName=font_regular,
                fontSize=8.5,
                leading=9.5,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#4b5563"),
            )
        )

        def para(value: Any, style_name: str = "LabOamCell") -> Paragraph:
            text = "" if value is None else str(value)
            text = escape(text).replace("\n", "<br/>")
            return Paragraph(text, styles[style_name])

        patient_full_name = patient.get("full_name") or "________________________________________________"
        patient_birth_date = patient.get("birth_date") or "____________________"
        patient_address = patient.get("address") or "________________________________________________"
        year_text = ""
        report_date = str(context.get("report_date") or "")
        if report_date:
            year_text = report_date[-4:]

        header_lines = [
            branding.get("clinic_name") or "Doktor Laboratoriyasi",
            f"Манзил: {branding.get('address')}" if branding.get("address") else "",
            (
                "Мўлжал: "
                + (branding.get("document_subtitle") or "")
                + (f"                                                                             Телефон:   {branding.get('phone')}" if branding.get("phone") else "")
            ).strip(),
        ]
        header_text = "<br/>".join(escape(line) for line in header_lines if line)
        story: list[Any] = [
            Paragraph(header_text, styles["LabOamHeader"]),
            Spacer(1, 4),
            Table(
                [
                    [para("ФИШ"), para(patient_full_name)],
                    [para("Туғилган йили"), para(patient_birth_date)],
                    [para("Манзили"), para(patient_address)],
                    [para("Текширув санаси"), para(f"«___» ____________________{year_text}   й")],
                ],
                colWidths=[4.0 * cm, doc.width - 4.0 * cm],
            ),
            Spacer(1, 8),
            Paragraph(
                str(branding.get("document_title") or context.get("template_name") or "").upper(),
                styles["LabOamTitle"],
            ),
        ]

        patient_table = story[2]
        if isinstance(patient_table, Table):
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

        rows: list[list[Any]] = [
            [
                para("Кўрсаткич", "LabOamCenter"),
                para("Натижа", "LabOamCenter"),
                para("Норма", "LabOamCenter"),
            ]
        ]
        for row in physical_section.get("fields") or []:
            value_display = row.get("value_text") or ""
            if row.get("value_numeric") is not None:
                value_display = row.get("value_numeric")
            rows.append(
                [
                    para(row.get("label") or "", "LabOamCell"),
                    para(value_display if value_display is not None else "", "LabOamCell"),
                    para(row.get("reference_text") or "", "LabOamCell"),
                ]
            )

        section_title_row_index: int | None = None
        if sediment_section:
            section_title_row_index = len(rows)
            rows.append(
                [
                    para(str(sediment_section.get("title") or "ЧЎКМА МИКРОСКОПИЯСИ").upper(), "LabOamCenter"),
                    "",
                    "",
                ]
            )
            for row in sediment_section.get("fields") or []:
                value_display = row.get("value_text") or ""
                if row.get("value_numeric") is not None:
                    value_display = row.get("value_numeric")
                rows.append(
                    [
                        para(row.get("label") or "", "LabOamCell"),
                        para(value_display if value_display is not None else "", "LabOamCell"),
                        para(row.get("reference_text") or "", "LabOamCell"),
                    ]
                )

        table = Table(
            rows,
            colWidths=[7.6 * cm, 3.8 * cm, doc.width - 11.4 * cm],
            repeatRows=1,
        )
        table_style_commands = [
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
        if section_title_row_index is not None:
            table_style_commands.extend(
                [
                    ("SPAN", (0, section_title_row_index), (-1, section_title_row_index)),
                    ("ALIGN", (0, section_title_row_index), (-1, section_title_row_index), "CENTER"),
                    ("BACKGROUND", (0, section_title_row_index), (-1, section_title_row_index), colors.HexColor("#f3f4f6")),
                    ("FONTNAME", (0, section_title_row_index), (-1, section_title_row_index), font_bold),
                    ("FONTSIZE", (0, section_title_row_index), (-1, section_title_row_index), 9.2),
                    ("TOPPADDING", (0, section_title_row_index), (-1, section_title_row_index), 4),
                    ("BOTTOMPADDING", (0, section_title_row_index), (-1, section_title_row_index), 4),
                ]
            )
        table.setStyle(TableStyle(table_style_commands))
        story.append(table)
        story.append(Spacer(1, 8))

        footer_notes = context.get("footer_notes")
        if footer_notes:
            story.append(Paragraph(str(footer_notes), styles["LabOamTiny"]))
            story.append(Spacer(1, 6))

        story.append(
            Paragraph(
                f"{signers.get('lab_technician_label') or 'Врач лаборант'}:________{signers.get('lab_technician_name') or ''}",
                styles["LabOamCell"],
            )
        )

        doc.build(story)
        return buffer.getvalue()

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


lab_report_pdf_service = LabReportPDFService()
