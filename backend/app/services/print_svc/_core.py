"""Core mixin for PrintService.

Split from print_service.py.
"""
from __future__ import annotations

from app.services.print_svc._base import *  # noqa: F401, F403
from app.services.print_svc._base import PrintServiceMixinBase


class CoreMixin(PrintServiceMixinBase):
    """Core methods."""

    def __init__(self, db: Session):
        self.db = db
        self.templates_dir = Path(__file__).parent.parent / "templates" / "print"

        # Настройка Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
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


    async def print_document(
        self,
        document_type: str,
        document_data: dict[str, Any],
        printer_name: str | None = None,
        template_id: int | None = None,
        user: User | None = None,
    ) -> dict[str, Any]:
        """
        Основной метод печати документа
        """
        try:
            logger.info(
                "[FIX] print_document start document_type=%s printer_name=%s",
                document_type,
                printer_name,
            )
            if document_type == "lab_results":
                document_data = self._normalize_lab_results_data(document_data, user)
            # Находим принтер
            printer = self._get_printer(printer_name, document_type)
            if not printer:
                raise Exception(f"Принтер для типа '{document_type}' не найден")

            # Находим шаблон
            template = self._get_template(template_id, document_type, printer.id)
            if not template:
                raise Exception(f"Шаблон для типа '{document_type}' не найден")

            # Создаем задание печати
            print_job = self._create_print_job(
                user_id=user.id if user else None,
                printer_id=printer.id,
                template_id=template.id,
                document_type=document_type,
                document_data=document_data,
            )

            try:
                # Рендерим шаблон
                rendered_content = self._render_template(template, document_data)

                # Печатаем в зависимости от типа принтера
                if printer.printer_type == "ESC/POS":
                    result = await self._print_escpos(printer, rendered_content)
                elif printer.printer_type in ["A4", "A5"]:
                    result = await self._print_pdf(
                        printer, rendered_content, printer.printer_type
                    )
                else:
                    raise Exception(
                        f"Неподдерживаемый тип принтера: {printer.printer_type}"
                    )

                # Обновляем статус задания
                self._update_print_job(print_job.id, "completed")
                logger.info(
                    "[FIX] print_document completed document_type=%s printer=%s job_id=%s",
                    document_type,
                    printer.name,
                    print_job.id,
                )

                return {
                    "success": True,
                    "job_id": print_job.id,
                    "message": "Документ отправлен на печать",
                    "printer": printer.display_name,
                    "result": result,
                }

            except Exception as e:
                # Обновляем статус задания с ошибкой
                self._update_print_job(print_job.id, "failed", str(e))
                logger.error(
                    "[FIX] print_document failed document_type=%s printer=%s error=%s",
                    document_type,
                    printer.name,
                    e,
                )
                raise

        except Exception as e:
            logger.error(
                "[FIX] print_document error document_type=%s printer_name=%s error=%s",
                document_type,
                printer_name,
                e,
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Внутренняя ошибка",
            }


    def _get_printer(
        self, printer_name: str | None, document_type: str
    ) -> PrinterConfig | None:
        """Найти принтер по имени или типу документа"""
        if printer_name:
            printer = crud_print.get_printer_by_name(self.db, printer_name)
            if printer:
                logger.info(
                    "[FIX] Using requested printer name=%s type=%s connection=%s",
                    printer.name,
                    printer.printer_type,
                    printer.connection_type,
                )
                return printer

            synced_printer = self._sync_discovered_printer_by_name(printer_name)
            if synced_printer:
                logger.info(
                    "[FIX] Synced discovered printer name=%s type=%s connection=%s",
                    synced_printer.name,
                    synced_printer.printer_type,
                    synced_printer.connection_type,
                )
                return synced_printer

            logger.warning(
                "[FIX] Requested printer name=%s not found, falling back to document_type=%s",
                printer_name,
                document_type,
            )

        printer = crud_print.get_default_printer_for_type(self.db, document_type)
        if printer:
            logger.info(
                "[FIX] Using default printer name=%s type=%s connection=%s for document_type=%s",
                printer.name,
                printer.printer_type,
                printer.connection_type,
                document_type,
            )
        return printer


    def _sync_discovered_printer_by_name(
        self, printer_name: str
    ) -> PrinterConfig | None:
        """Синхронизировать один принтер из системного списка и вернуть его."""
        discovered = self._discover_system_printers_sync()
        for printer_data in discovered:
            if printer_data["name"] != printer_name and printer_data["display_name"] != printer_name:
                continue
            return self._upsert_discovered_printer(printer_data)

        return None


    def _get_template(
        self, template_id: int | None, document_type: str, printer_id: int
    ) -> PrintTemplate | None:
        """Найти шаблон по ID или типу документа"""
        if template_id:
            return crud_print.get_print_template(self.db, template_id)
        else:
            return crud_print.get_template_by_type_and_printer(
                self.db, document_type, printer_id
            )


    def _render_template(self, template: PrintTemplate, data: dict[str, Any]) -> str:
        """Рендерить шаблон с данными"""
        try:
            template_source = LEGACY_COMMENT_BLOCK_RE.sub("", template.template_content)
            jinja_template = self.jinja_env.from_string(template_source)
            return jinja_template.render(**data)
        except Exception as e:
            raise Exception("Внутренняя ошибка")


    def _normalize_lab_results_data(
        self, lab_data: dict[str, Any], user: User | None = None
    ) -> dict[str, Any]:
        """Нормализовать данные для печати лабораторного отчета."""
        from app.core.config import settings

        normalized = lab_data.copy()
        clinic_data = normalized.get("clinic") or {}
        patient_data = normalized.get("patient") or {}

        referring_doctor = normalized.get("referring_doctor")
        if not isinstance(referring_doctor, dict):
            referring_doctor = {}

        lab_doctor = normalized.get("lab_doctor")
        if not isinstance(lab_doctor, dict):
            lab_doctor = {}

        lab_head = normalized.get("lab_head")
        if not isinstance(lab_head, dict):
            lab_head = {}

        normalized["clinic"] = {
            "name": clinic_data.get("name") or settings.APP_NAME,
            "license_number": clinic_data.get("license_number") or "",
            "address": clinic_data.get("address") or "",
            "phone": clinic_data.get("phone") or "",
            "email": clinic_data.get("email") or "",
        }
        normalized["referring_doctor"] = {
            "full_name": referring_doctor.get("full_name")
            or patient_data.get("referring_doctor_name")
            or normalized.get("referring_doctor_name")
            or "Не указано",
            "specialty_name": referring_doctor.get("specialty_name")
            or normalized.get("referring_specialty")
            or "",
        }
        normalized["lab_doctor"] = {
            "full_name": lab_doctor.get("full_name")
            or (user.full_name if user else None)
            or normalized.get("lab_doctor_name")
            or "Лаборант",
            "specialty_name": lab_doctor.get("specialty_name") or "Лаборант",
            "license_number": lab_doctor.get("license_number") or "",
        }
        normalized["lab_head"] = {
            "full_name": lab_head.get("full_name")
            or normalized.get("lab_head_name")
            or "Заведующий лабораторией",
            "specialty_name": lab_head.get("specialty_name") or "",
        }

        return normalized


    def _create_print_job(
        self,
        user_id: int | None,
        printer_id: int,
        template_id: int,
        document_type: str,
        document_data: dict[str, Any],
    ) -> PrintJob:
        """Создать задание печати"""
        job_data = {
            "user_id": user_id,
            "printer_id": printer_id,
            "template_id": template_id,
            "document_type": document_type,
            "document_id": document_data.get("id", ""),
            "status": "pending",
            "print_data": document_data,
        }

        return crud_print.create_print_job(self.db, job_data)


    def _update_print_job(
        self, job_id: int, status: str, error_message: str | None = None
    ):
        """Обновить статус задания печати"""
        update_data = {
            "status": status,
            "completed_at": (
                datetime.now(UTC) if status in ["completed", "failed"] else None
            ),
        }

        if error_message:
            update_data["error_message"] = error_message

        crud_print.update_print_job(self.db, job_id, update_data)


