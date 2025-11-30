"""
Сервис для генерации PDF документов
Основа: passport.md стр. 1925-2063
"""

import base64
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import qrcode
from jinja2 import Environment, FileSystemLoader

try:
    from weasyprint import CSS, HTML

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, A5
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFService:
    """Сервис для генерации PDF документов"""

    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent / "templates" / "print"

        # Настройка Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Добавляем фильтры
        self.jinja_env.filters['strftime'] = self._strftime_filter
        self.jinja_env.filters['number_format'] = self._number_format_filter
        self.jinja_env.filters['nl2br'] = self._nl2br_filter

    def _strftime_filter(self, date, fmt='%d.%m.%Y'):
        """Фильтр для форматирования дат"""
        if date is None:
            return ''
        if isinstance(date, str):
            return date
        return date.strftime(fmt)

    def _number_format_filter(self, number, decimals=0):
        """Фильтр для форматирования чисел"""
        if number is None:
            return '0'
        return f"{number:,.{decimals}f}".replace(',', ' ')

    def _nl2br_filter(self, text):
        """Фильтр для замены переносов строк на <br>"""
        if not text:
            return ''
        return text.replace('\n', '<br>')

    def generate_pdf_from_html(
        self, template_name: str, data: Dict[str, Any], paper_size: str = "A4"
    ) -> bytes:
        """
        Генерация PDF из HTML шаблона с помощью WeasyPrint
        """
        if not WEASYPRINT_AVAILABLE:
            raise Exception(
                "WeasyPrint не установлен. Используйте: pip install weasyprint"
            )

        try:
            # Генерируем QR код если нужен
            if data.get("generate_qr"):
                qr_code_url = self._generate_qr_code(data.get("qr_data", ""))
                data["qr_code_url"] = qr_code_url

            # Рендерим HTML шаблон
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**data)

            # Создаем CSS для размера бумаги
            css_content = self._get_page_css(paper_size)

            # Генерируем PDF
            html_doc = HTML(string=html_content, base_url=str(self.templates_dir))
            css_doc = CSS(string=css_content)

            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])

            return pdf_bytes

        except Exception as e:
            raise Exception(f"Ошибка генерации PDF: {str(e)}")

    def generate_pdf_with_reportlab(
        self, document_type: str, data: Dict[str, Any], paper_size: str = "A4"
    ) -> bytes:
        """
        Генерация PDF с помощью ReportLab
        """
        if not REPORTLAB_AVAILABLE:
            raise Exception(
                "ReportLab не установлен. Используйте: pip install reportlab"
            )

        try:
            buffer = io.BytesIO()

            # Определяем размер страницы
            page_size = A4 if paper_size == "A4" else A5

            # Создаем документ
            doc = SimpleDocTemplate(
                buffer,
                pagesize=page_size,
                rightMargin=20 * mm,
                leftMargin=20 * mm,
                topMargin=20 * mm,
                bottomMargin=20 * mm,
            )

            # Генерируем содержимое в зависимости от типа
            if document_type == "prescription":
                story = self._build_prescription_reportlab(data)
            elif document_type == "medical_certificate":
                story = self._build_certificate_reportlab(data)
            elif document_type == "lab_results":
                story = self._build_lab_results_reportlab(data)
            else:
                raise Exception(f"Неподдерживаемый тип документа: {document_type}")

            # Генерируем PDF
            doc.build(story)

            pdf_bytes = buffer.getvalue()
            buffer.close()

            return pdf_bytes

        except Exception as e:
            raise Exception(f"Ошибка генерации PDF с ReportLab: {str(e)}")

    def _get_page_css(self, paper_size: str) -> str:
        """Получить CSS для размера страницы"""
        if paper_size == "A5":
            return """
                @page {
                    size: A5;
                    margin: 15mm;
                }
                body { font-family: 'Times New Roman', serif; }
            """
        else:  # A4
            return """
                @page {
                    size: A4;
                    margin: 20mm;
                }
                body { font-family: 'Times New Roman', serif; }
            """

    def _generate_qr_code(self, data: str) -> str:
        """Генерация QR кода и возврат в виде data URL"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)

            # Создаем изображение
            img = qr.make_image(fill_color="black", back_color="white")

            # Конвертируем в base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/png;base64,{img_str}"

        except Exception as e:
            raise Exception(f"Ошибка генерации QR кода: {str(e)}")

    def _build_prescription_reportlab(self, data: Dict[str, Any]) -> list:
        """Построить рецепт с помощью ReportLab"""
        story = []
        styles = getSampleStyleSheet()

        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        clinic_name = data.get("clinic", {}).get("name", "МЕДИЦИНСКАЯ КЛИНИКА")
        prescription_number = data.get("prescription", {}).get("number", "RX-001")

        story.append(Paragraph(clinic_name, title_style))
        story.append(Paragraph(f"РЕЦЕПТ № {prescription_number}", title_style))
        story.append(Spacer(1, 20))

        # Информация о пациенте
        patient = data.get("patient", {})
        patient_info = [
            ["Пациент:", patient.get("full_name", "")],
            ["Дата рождения:", patient.get("birth_date", "")],
            ["Телефон:", patient.get("phone", "")],
        ]

        patient_table = Table(patient_info, colWidths=[4 * cm, 10 * cm])
        patient_table.setStyle(
            TableStyle(
                [
                    ('FONTNAME', (0, 0), (-1, -1), 'Times-Roman'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ]
            )
        )

        story.append(patient_table)
        story.append(Spacer(1, 20))

        # Медикаменты
        medications = data.get("prescription", {}).get("medications", [])
        if medications:
            story.append(Paragraph("НАЗНАЧЕНИЯ:", styles['Heading2']))
            story.append(Spacer(1, 10))

            for i, med in enumerate(medications, 1):
                med_text = f"{i}. <b>{med.get('name', '')}</b>"
                if med.get('dosage'):
                    med_text += f" - {med.get('dosage')}"

                story.append(Paragraph(med_text, styles['Normal']))

                if med.get('instructions'):
                    story.append(
                        Paragraph(
                            f"Способ применения: {med.get('instructions')}",
                            styles['Normal'],
                        )
                    )

                story.append(Spacer(1, 10))

        # Подпись врача
        story.append(Spacer(1, 40))
        doctor = data.get("doctor", {})
        signature_data = [
            ["Врач:", doctor.get("full_name", "")],
            ["Подпись:", "_" * 30],
            ["Дата:", datetime.now().strftime("%d.%m.%Y")],
        ]

        signature_table = Table(signature_data, colWidths=[3 * cm, 8 * cm])
        signature_table.setStyle(
            TableStyle(
                [
                    ('FONTNAME', (0, 0), (-1, -1), 'Times-Roman'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),
                ]
            )
        )

        story.append(signature_table)

        return story

    def _build_certificate_reportlab(self, data: Dict[str, Any]) -> list:
        """Построить медицинскую справку с помощью ReportLab"""
        story = []
        styles = getSampleStyleSheet()

        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        clinic_name = data.get("clinic", {}).get("name", "МЕДИЦИНСКАЯ КЛИНИКА")
        cert_number = data.get("certificate", {}).get("number", "CERT-001")

        story.append(Paragraph(clinic_name, title_style))
        story.append(Paragraph("МЕДИЦИНСКАЯ СПРАВКА", title_style))
        story.append(Paragraph(f"№ {cert_number}", styles['Normal']))
        story.append(Spacer(1, 30))

        # Информация о пациенте
        patient = data.get("patient", {})
        patient_info = f"""
        Настоящая справка выдана в том, что <b>{patient.get("full_name", "")}</b>,
        {patient.get("birth_date", "")} года рождения, действительно обращался(лась)
        за медицинской помощью и по состоянию здоровья может/не может выполнять
        определенные виды деятельности.
        """

        story.append(Paragraph(patient_info, styles['Normal']))
        story.append(Spacer(1, 30))

        # Диагноз
        visit = data.get("visit", {})
        if visit.get("diagnosis"):
            story.append(
                Paragraph(f"<b>Диагноз:</b> {visit.get('diagnosis')}", styles['Normal'])
            )
            if visit.get("icd10"):
                story.append(
                    Paragraph(f"<b>МКБ-10:</b> {visit.get('icd10')}", styles['Normal'])
                )
            story.append(Spacer(1, 20))

        # Подпись
        story.append(Spacer(1, 50))
        doctor = data.get("doctor", {})
        story.append(
            Paragraph(f"Врач: {doctor.get('full_name', '')}", styles['Normal'])
        )
        story.append(Paragraph("Подпись: _" * 30, styles['Normal']))
        story.append(
            Paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y')}", styles['Normal'])
        )

        return story

    def _build_lab_results_reportlab(self, data: Dict[str, Any]) -> list:
        """Построить результаты анализов с помощью ReportLab"""
        story = []
        styles = getSampleStyleSheet()

        # Заголовок
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        clinic_name = data.get("clinic", {}).get("name", "МЕДИЦИНСКАЯ КЛИНИКА")
        order_number = data.get("lab_order", {}).get("number", "LAB-001")

        story.append(Paragraph(clinic_name, title_style))
        story.append(Paragraph("РЕЗУЛЬТАТЫ ЛАБОРАТОРНЫХ ИССЛЕДОВАНИЙ", title_style))
        story.append(Paragraph(f"№ заказа: {order_number}", styles['Normal']))
        story.append(Spacer(1, 20))

        # Информация о пациенте
        patient = data.get("patient", {})
        patient_data = [
            ["Пациент:", patient.get("full_name", "")],
            ["Дата рождения:", patient.get("birth_date", "")],
            ["Пол:", patient.get("gender_name", "")],
        ]

        patient_table = Table(patient_data, colWidths=[4 * cm, 10 * cm])
        patient_table.setStyle(
            TableStyle(
                [
                    ('FONTNAME', (0, 0), (-1, -1), 'Times-Roman'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        story.append(patient_table)
        story.append(Spacer(1, 20))

        # Результаты
        lab_results = data.get("lab_results", [])
        if lab_results:
            # Заголовки таблицы
            results_data = [["Показатель", "Результат", "Единицы", "Норма"]]

            for result in lab_results:
                results_data.append(
                    [
                        result.get("parameter_name", ""),
                        result.get("value", ""),
                        result.get("unit", ""),
                        result.get("reference_range", ""),
                    ]
                )

            results_table = Table(
                results_data, colWidths=[6 * cm, 3 * cm, 2 * cm, 4 * cm]
            )
            results_table.setStyle(
                TableStyle(
                    [
                        ('FONTNAME', (0, 0), (-1, -1), 'Times-Roman'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]
                )
            )

            story.append(results_table)

        return story


# Глобальный экземпляр сервиса
pdf_service = PDFService()


def get_pdf_service() -> PDFService:
    """Получить экземпляр PDF сервиса"""
    return pdf_service
