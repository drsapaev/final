"""Reportlab mixin for LabReportPDFService.

Split from lab_report_pdf_service.py.
"""
from __future__ import annotations

from app.services.lab_report_pdf._base import *  # noqa: F401, F403
from app.services.lab_report_pdf._base import LabReportPDFServiceMixinBase


class ReportlabMixin(LabReportPDFServiceMixinBase):
    """Reportlab methods."""

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


