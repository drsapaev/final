"""
Сервис для печати документов
Основа: detail.md стр. 3721-3888, passport.md стр. 1925-2063
"""

import asyncio
import json
import logging
import os
import platform
import re
import socket
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import serial
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.crud import print_config as crud_print
from app.models.print_config import PrinterConfig, PrintJob, PrintTemplate
from app.models.user import User

logger = logging.getLogger(__name__)
LEGACY_COMMENT_BLOCK_RE = re.compile(r"{% comment %}.*?{% endcomment %}", re.S)
THERMAL_PRINTER_KEYWORDS = (
    "thermal",
    "therm",
    "ticket",
    "receipt",
    "pos",
    "escpos",
    "receipt printer",
    "ticket printer",
    "xprinter",
    "epson",
    "star",
    "bixolon",
    "pos58",
    "80mm",
    "58mm",
)
LAB_PRINTER_KEYWORDS = (
    "laser",
    "laserjet",
    "office",
    "canon",
    "brother",
    "xerox",
    "hp",
    "mfp",
    "a4",
    "pdf",
)
PRESCRIPTION_PRINTER_KEYWORDS = (
    "prescription",
    "rx",
    "a5",
)


class PrintService:
    """Сервис для печати документов"""

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

    async def _print_escpos(
        self, printer: PrinterConfig, content: str
    ) -> dict[str, Any]:
        """
        Печать на ESC/POS принтере (термопринтер)
        """
        try:
            if printer.connection_type == "mock":
                encoded_content = content.encode(printer.encoding or "utf-8")
                logger.info(
                    "[FIX] Mock ESC/POS print for printer=%s bytes_sent=%s",
                    printer.name,
                    len(encoded_content),
                )
                return {
                    "method": "mock",
                    "printer": printer.display_name,
                    "bytes_sent": len(encoded_content),
                }

            if printer.connection_type == "local":
                return await self._print_local_escpos(printer, content)

            if printer.connection_type == "network":
                return await self._print_network_escpos(printer, content)
            elif printer.connection_type == "usb":
                return await self._print_usb_escpos(printer, content)
            elif printer.connection_type == "serial":
                return await self._print_serial_escpos(printer, content)
            else:
                raise Exception(
                    f"Неподдерживаемый тип подключения: {printer.connection_type}"
                )

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    async def _print_local_escpos(
        self, printer: PrinterConfig, content: str
    ) -> dict[str, Any]:
        """Печать ESC/POS содержимого на локальный системный принтер."""
        try:
            import tempfile

            safe_device = printer.device_path or printer.display_name or printer.name
            if not safe_device:
                raise Exception("Не указан локальный принтер")

            encoded_content = content.encode(printer.encoding or "utf-8")
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=printer.encoding or "utf-8",
                suffix=".txt",
                delete=False,
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                if platform.system() == "Windows":
                    cmd = ["print", f"/D:{safe_device}", temp_file_path]
                else:
                    cmd = ["lp", "-d", safe_device, temp_file_path]

                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    return {
                        "method": "local",
                        "device_path": safe_device,
                        "bytes_sent": len(encoded_content),
                    }

                raise Exception(f"Ошибка локальной печати: {stderr.decode()}")
            finally:
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    async def _print_network_escpos(
        self, printer: PrinterConfig, content: str
    ) -> dict[str, Any]:
        """Печать через сеть (TCP/IP)"""
        try:
            # Кодируем контент
            encoded_content = content.encode(printer.encoding or 'utf-8')

            # Подключаемся к принтеру
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # 10 секунд таймаут

            await asyncio.get_event_loop().run_in_executor(
                None, lambda: sock.connect((printer.ip_address, printer.port or 9100))
            )

            # Отправляем данные
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: sock.send(encoded_content)
            )

            sock.close()

            return {
                "method": "network",
                "address": f"{printer.ip_address}:{printer.port}",
                "bytes_sent": len(encoded_content),
            }

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    async def _print_usb_escpos(
        self, printer: PrinterConfig, content: str
    ) -> dict[str, Any]:
        """Печать через USB"""
        try:
            if not printer.device_path:
                raise Exception("Не указан путь к USB устройству")

            encoded_content = content.encode(printer.encoding or 'utf-8')

            # Записываем в устройство
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._write_to_device(printer.device_path, encoded_content),
            )

            return {
                "method": "usb",
                "device_path": printer.device_path,
                "bytes_sent": len(encoded_content),
            }

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    def _write_to_device(self, device_path: str, content: bytes):
        """Записать данные в устройство"""
        with open(device_path, 'wb') as device:
            device.write(content)
            device.flush()

    async def _print_serial_escpos(
        self, printer: PrinterConfig, content: str
    ) -> dict[str, Any]:
        """Печать через последовательный порт"""
        try:
            if not printer.device_path:
                raise Exception("Не указан путь к последовательному порту")

            encoded_content = content.encode(printer.encoding or 'utf-8')

            # Открываем последовательный порт
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._write_to_serial(printer.device_path, encoded_content),
            )

            return {
                "method": "serial",
                "device_path": printer.device_path,
                "bytes_sent": len(encoded_content),
            }

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    def _write_to_serial(self, device_path: str, content: bytes):
        """Записать данные в последовательный порт"""
        with serial.Serial(device_path, 9600, timeout=1) as ser:
            ser.write(content)
            ser.flush()

    async def _print_pdf(
        self, printer: PrinterConfig, content: str, paper_size: str
    ) -> dict[str, Any]:
        """
        Печать PDF документов (A4/A5)
        """
        try:
            if printer.connection_type == "mock":
                logger.info(
                    "[FIX] Mock PDF print for printer=%s paper_size=%s content_chars=%s",
                    printer.name,
                    paper_size,
                    len(content),
                )
                return {
                    "method": "mock",
                    "paper_size": paper_size,
                    "printer": printer.display_name,
                    "status": "queued",
                    "file_size": len(content.encode("utf-8")),
                }

            import tempfile

            from app.services.pdf_service import _load_weasyprint_components

            # Если контент это HTML шаблон, генерируем PDF напрямую из строки.
            if content.strip().startswith(
                '<!DOCTYPE html'
            ) or content.strip().startswith('<html'):
                weasy_css, weasy_html = _load_weasyprint_components()
                css_content = (
                    """
                        @page {
                            size: A5;
                            margin: 15mm;
                        }
                        body { font-family: 'Times New Roman', serif; }
                    """
                    if paper_size == "A5"
                    else """
                        @page {
                            size: A4;
                            margin: 20mm;
                        }
                        body { font-family: 'Times New Roman', serif; }
                    """
                )
                html_doc = weasy_html(string=content, base_url=str(self.templates_dir))
                css_doc = weasy_css(string=css_content)
                pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
            else:
                # Контент уже готовый, используем как есть
                pdf_bytes = content.encode('utf-8')

            # Сохраняем PDF во временный файл
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_bytes)
                temp_file_path = temp_file.name

            try:
                # Отправляем на печать в зависимости от типа подключения
                if printer.connection_type == "network":
                    # Для сетевой печати используем lp или другую утилиту
                    result = await self._print_pdf_network(printer, temp_file_path)
                else:
                    # Для локальной печати используем системную команду
                    result = await self._print_pdf_local(printer, temp_file_path)

                return {
                    "method": "pdf",
                    "paper_size": paper_size,
                    "printer": printer.display_name,
                    "file_size": len(pdf_bytes),
                    **result,
                }

            finally:
                # Удаляем временный файл
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    async def _print_pdf_network(
        self, printer: PrinterConfig, file_path: str
    ) -> dict[str, Any]:
        """Печать PDF через сеть"""
        try:
            # Валидация пути к файлу (только безопасные символы)
            if not all(
                c.isprintable()
                and c not in [';', '&', '|', '`', '$', '(', ')', '<', '>']
                for c in file_path
            ):
                raise ValueError("Недопустимый путь к файлу")

            # Валидация IP адреса (базовая проверка)
            ip_address = printer.ip_address or "127.0.0.1"
            # Проверяем, является ли это IP адресом (4 числа через точку)
            if ip_address.count('.') == 3:
                # Проверяем каждую часть IP адреса
                parts = ip_address.split('.')
                if len(parts) == 4 and all(
                    part.isdigit() and 0 <= int(part) <= 255 for part in parts
                ):
                    pass  # Валидный IP адрес
                else:
                    raise ValueError("Недопустимый IP адрес")
            else:
                # Если не IP, проверяем как hostname (только буквы, цифры, точки, дефисы)
                if not all(c.isalnum() or c in ['.', '-'] for c in ip_address):
                    raise ValueError("Недопустимый IP адрес или hostname")

            port = printer.port or 631
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError("Недопустимый порт")

            # Используем lp команду для отправки на сетевой принтер
            cmd = [
                "lp",
                "-d",
                f"ipp://{ip_address}:{port}/printers/default",
                "-o",
                f"media={printer.printer_type or 'A4'}",
                file_path,
            ]

            # Безопасно: используем subprocess_exec с предопределенными командами
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {"status": "sent", "message": "PDF отправлен на сетевой принтер"}
            else:
                raise Exception(f"Ошибка lp команды: {stderr.decode()}")

        except Exception:
            # Fallback: копируем файл в сетевую папку принтера
            return await self._print_pdf_fallback(printer, file_path)

    async def _print_pdf_local(
        self, printer: PrinterConfig, file_path: str
    ) -> dict[str, Any]:
        """Печать PDF на локальном принтере"""
        try:
            import platform

            # Валидация пути к файлу (только безопасные символы)
            if not all(
                c.isprintable()
                and c not in [';', '&', '|', '`', '$', '(', ')', '<', '>']
                for c in file_path
            ):
                raise ValueError("Недопустимый путь к файлу")

            device_path = printer.device_path or (
                'LPT1' if platform.system() == "Windows" else "default"
            )
            # Валидация пути к устройству (только безопасные символы)
            if not all(
                c.isprintable()
                and c not in [';', '&', '|', '`', '$', '(', ')', '<', '>']
                for c in device_path
            ):
                raise ValueError("Недопустимый путь к устройству")

            if platform.system() == "Windows":
                # Windows: используем команду print
                cmd = ["print", f"/D:{device_path}", file_path]
            else:
                # Linux/Unix: используем lp
                cmd = ["lp", "-d", device_path, file_path]

            # Безопасно: используем subprocess_exec с предопределенными командами
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return {
                    "status": "printed",
                    "message": "PDF отправлен на локальный принтер",
                }
            else:
                raise Exception(f"Ошибка печати: {stderr.decode()}")

        except Exception as e:
            raise Exception("Внутренняя ошибка")

    async def _print_pdf_fallback(
        self, printer: PrinterConfig, file_path: str
    ) -> dict[str, Any]:
        """Fallback метод для PDF печати"""
        return {
            "status": "queued",
            "message": f"PDF файл готов для печати на {printer.display_name}",
            "note": "Требуется ручная отправка на принтер",
        }

    # ===================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====================

    def get_printer_status(self, printer_name: str) -> dict[str, Any]:
        """Получить статус принтера"""
        printer = crud_print.get_printer_by_name(self.db, printer_name)

        if not printer:
            return {"status": "not_found", "message": "Принтер не найден"}

        if not printer.active:
            return {"status": "disabled", "message": "Принтер отключен"}

        if printer.connection_type == "mock":
            return {"status": "online", "message": "Mock printer available"}

        if printer.connection_type == "local":
            if printer.device_path:
                return {"status": "online", "message": "Локальный принтер доступен"}
            return {"status": "offline", "message": "Не указан локальный принтер"}

        # Проверяем доступность принтера
        try:
            if printer.connection_type == "network":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((printer.ip_address, printer.port or 9100))
                sock.close()

                if result == 0:
                    return {"status": "online", "message": "Принтер доступен"}
                else:
                    return {"status": "offline", "message": "Принтер недоступен"}
            else:
                # Для USB/Serial проверяем наличие устройства
                if printer.device_path and Path(printer.device_path).exists():
                    return {"status": "online", "message": "Устройство найдено"}
                else:
                    return {"status": "offline", "message": "Устройство не найдено"}

        except Exception as e:
            return {"status": "error", "message": "Внутренняя ошибка"}

    async def discover_system_printers(self) -> list[dict[str, Any]]:
        """Получить список локально установленных принтеров ОС."""
        try:
            system_name = platform.system()
            if system_name == "Windows":
                return await asyncio.to_thread(self._discover_windows_printers_sync)
            if system_name in {"Linux", "Darwin"}:
                return await asyncio.to_thread(self._discover_unix_printers_sync)
            return []
        except Exception as e:
            logger.warning("[FIX] System printer discovery failed: %s", e)
            return []

    async def sync_system_printers(self) -> list[PrinterConfig]:
        """Синхронизировать локальные системные принтеры в БД."""
        discovered = await self.discover_system_printers()
        synced: list[PrinterConfig] = []

        for printer_data in discovered:
            try:
                synced.append(self._upsert_discovered_printer(printer_data))
            except Exception as e:
                logger.warning(
                    "[FIX] Failed to sync discovered printer %s: %s",
                    printer_data.get("name"),
                    e,
                )

        if synced:
            logger.info("[FIX] Synced %s system printers", len(synced))

        return synced

    def _discover_windows_printers_sync(self) -> list[dict[str, Any]]:
        """Обнаружить локальные принтеры в Windows через PowerShell."""
        command = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-Printer | "
                "Select-Object Name,DriverName,PortName,Shared,Default,PrinterStatus,Comment,Location,WorkOffline | "
                "ConvertTo-Json -Depth 4"
            ),
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        raw_output = completed.stdout.strip()
        if not raw_output:
            return []

        payload = json.loads(raw_output)
        items = payload if isinstance(payload, list) else [payload]

        discovered: list[dict[str, Any]] = []
        for item in items:
            normalized = self._normalize_discovered_printer(item, system_name="Windows")
            if normalized:
                discovered.append(normalized)

        return discovered

    def _discover_unix_printers_sync(self) -> list[dict[str, Any]]:
        """Обнаружить локальные принтеры в Unix-подобных системах."""
        command = ["lpstat", "-p"]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except FileNotFoundError:
            return []

        discovered: list[dict[str, Any]] = []
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("printer "):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            name = parts[1]
            discovered.append(
                self._normalize_discovered_printer(
                    {
                        "Name": name,
                        "DriverName": name,
                        "PortName": name,
                        "Shared": False,
                        "Default": False,
                        "PrinterStatus": 0,
                        "Comment": "",
                        "Location": "",
                        "WorkOffline": False,
                    },
                    system_name="Unix",
                )
            )

        return [item for item in discovered if item]

    def _normalize_discovered_printer(
        self, raw: dict[str, Any], *, system_name: str
    ) -> dict[str, Any] | None:
        """Свести системные данные принтера к нашему внутреннему формату."""
        name = str(
            raw.get("Name")
            or raw.get("name")
            or raw.get("PrinterName")
            or raw.get("displayName")
            or ""
        ).strip()
        if not name:
            return None

        driver_name = str(raw.get("DriverName") or raw.get("driverName") or name).strip()
        port_name = str(raw.get("PortName") or raw.get("portName") or name).strip()
        comment = str(raw.get("Comment") or raw.get("comment") or "").strip()
        location = str(raw.get("Location") or raw.get("location") or "").strip()
        display_name = comment or location or name
        printer_type = self._infer_printer_type(name, driver_name)
        paper_width, paper_height = self._infer_paper_size(printer_type)
        is_default = bool(raw.get("Default") or raw.get("default") or raw.get("isDefault"))
        status = self._infer_printer_status(raw)

        return {
            "name": name,
            "display_name": display_name,
            "printer_type": printer_type,
            "connection_type": "local",
            "device_path": name if system_name == "Windows" else port_name,
            "paper_width": paper_width,
            "paper_height": paper_height,
            "margins": None,
            "encoding": "utf-8",
            "active": True,
            "is_default": is_default,
            "status": status,
            "driver_name": driver_name,
            "location": location,
        }

    def _infer_printer_type(self, name: str, driver_name: str) -> str:
        haystack = f"{name} {driver_name}".lower()

        if any(keyword in haystack for keyword in THERMAL_PRINTER_KEYWORDS):
            return "ESC/POS"

        if any(keyword in haystack for keyword in PRESCRIPTION_PRINTER_KEYWORDS):
            return "A5"

        if any(keyword in haystack for keyword in LAB_PRINTER_KEYWORDS):
            return "A4"

        return "A4"

    def _infer_paper_size(self, printer_type: str) -> tuple[int | None, int | None]:
        if printer_type == "ESC/POS":
            return 58, None
        if printer_type == "A5":
            return 148, 210
        return 210, 297

    def _infer_printer_status(self, raw: dict[str, Any]) -> str:
        if raw.get("WorkOffline") or raw.get("workOffline"):
            return "offline"

        status_value = raw.get("PrinterStatus") or raw.get("printerStatus")
        if isinstance(status_value, str):
            lowered = status_value.lower()
            if lowered in {"offline", "error", "disabled"}:
                return "offline"
            return "online"

        if status_value in {1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}:
            return "offline"

        return "online"

    def _upsert_discovered_printer(
        self, printer_data: dict[str, Any]
    ) -> PrinterConfig:
        """Создать или обновить конфигурацию принтера из системного инвентаря."""
        printer = crud_print.get_printer_by_name(self.db, printer_data["name"])
        if not printer:
            printer = PrinterConfig(
                name=printer_data["name"],
                display_name=printer_data["display_name"],
                printer_type=printer_data["printer_type"],
                connection_type=printer_data["connection_type"],
                device_path=printer_data["device_path"],
                paper_width=printer_data["paper_width"],
                paper_height=printer_data["paper_height"],
                margins=printer_data["margins"],
                encoding=printer_data["encoding"],
                active=printer_data["active"],
                is_default=printer_data["is_default"],
            )
            self.db.add(printer)
        else:
            printer.display_name = printer_data["display_name"]
            printer.printer_type = printer_data["printer_type"]
            printer.connection_type = printer_data["connection_type"]
            printer.device_path = printer_data["device_path"]
            printer.paper_width = printer_data["paper_width"]
            printer.paper_height = printer_data["paper_height"]
            printer.margins = printer_data["margins"]
            printer.encoding = printer_data["encoding"]
            printer.active = True
            printer.is_default = printer_data["is_default"] or printer.is_default

        self.db.commit()
        self.db.refresh(printer)
        return printer

    async def generate_receipt(
        self,
        payment_id: int | None = None,
        visit_id: int | None = None,
        payment_data: dict[str, Any] | None = None,
        printer_name: str | None = None,
        user: User | None = None,
    ) -> dict[str, Any]:
        """
        Генерация чека (SSOT).

        Args:
            payment_id: ID платежа
            visit_id: ID визита
            payment_data: Данные платежа (если нет payment_id/visit_id)
            printer_name: Имя принтера
            user: Пользователь, выполняющий печать

        Returns:
            Dict с результатом печати
        """
        from app.core.config import settings
        from app.models.payment import Payment
        from app.models.visit import Visit
        from app.services.queue_service import queue_service

        # Получаем данные платежа
        if payment_id:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise ValueError(f"Платеж {payment_id} не найден")
            visit_id = payment.visit_id
        elif visit_id:
            payment = (
                self.db.query(Payment)
                .filter(Payment.visit_id == visit_id, Payment.status == "paid")
                .order_by(Payment.created_at.desc())
                .first()
            )
        else:
            payment = None

        # Получаем данные визита
        if visit_id:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Визит {visit_id} не найден")
        else:
            visit = None

        # Формируем данные для чека
        if payment_data:
            receipt_data = payment_data.copy()
        else:
            receipt_data = {}

        clinic_data = receipt_data.get("clinic") or {}
        receipt_data.setdefault(
            "clinic_name",
            receipt_data.get("clinic_name")
            or clinic_data.get("name")
            or settings.APP_NAME,
        )
        receipt_data.setdefault(
            "clinic_phone",
            receipt_data.get("clinic_phone")
            or clinic_data.get("phone")
            or "",
        )
        receipt_data.setdefault(
            "clinic_address",
            receipt_data.get("clinic_address")
            or clinic_data.get("address")
            or "",
        )
        receipt_data.setdefault(
            "clinic_website",
            receipt_data.get("clinic_website")
            or clinic_data.get("website")
            or "",
        )
        receipt_data.setdefault(
            "cashier",
            receipt_data.get("cashier")
            or {"full_name": user.full_name if user else "Система"},
        )
        receipt_data.setdefault(
            "doctor",
            receipt_data.get("doctor")
            or {"full_name": user.full_name if user else "Врач", "specialty_name": "", "cabinet": ""},
        )

        # Дополняем данными из БД
        if payment:
            receipt_data.update(
                {
                    "payment_id": payment.id,
                    "amount": float(payment.amount),
                    "currency": payment.currency or "UZS",
                    "method": payment.method or "cash",
                    "status": payment.status,
                    "receipt_no": payment.receipt_no or f"RCP-{payment.id}",
                    "paid_at": (
                        payment.paid_at.isoformat()
                        if payment.paid_at
                        else queue_service.get_local_timestamp(self.db).isoformat()
                    ),
                    "note": payment.note,
                }
            )

        if visit:
            receipt_data.update(
                {
                    "visit_id": visit.id,
                    "patient_name": getattr(visit, 'patient_name', None)
                    or "Не указано",
                    "patient_phone": getattr(visit, 'patient_phone', None),
                }
            )

        payment_block = receipt_data.setdefault("payment", {})
        if isinstance(payment_block, dict):
            payment_block["services"] = payment_block.get("services") or receipt_data.get("services", [])
            payment_block["method_name"] = payment_block.get("method_name") or "cash"
            payment_block["total"] = payment_block.get("total", receipt_data.get("amount", 0))
            payment_block["subtotal"] = payment_block.get("subtotal", payment_block.get("total", 0))
            payment_block["discount"] = payment_block.get("discount", 0)
            payment_block["paid_amount"] = payment_block.get("paid_amount", payment_block.get("total", 0))
            payment_block["change"] = payment_block.get("change", 0)

        # Добавляем метаданные
        now = queue_service.get_local_timestamp(self.db).isoformat()
        receipt_data.update(
            {
                "date": now,
                "time": now,
                "issued_by": user.full_name if user else "Система",
            }
        )

        # Печатаем чек
        return await self.print_document(
            document_type="receipt",
            document_data=receipt_data,
            printer_name=printer_name,
            user=user,
        )

    async def generate_ticket(
        self,
        queue_entry_id: int | None = None,
        visit_id: int | None = None,
        ticket_data: dict[str, Any] | None = None,
        printer_name: str | None = None,
        user: User | None = None,
    ) -> dict[str, Any]:
        """
        Генерация талона очереди (SSOT).

        Args:
            queue_entry_id: ID записи в очереди
            visit_id: ID визита
            ticket_data: Данные талона (если нет queue_entry_id/visit_id)
            printer_name: Имя принтера
            user: Пользователь, выполняющий печать

        Returns:
            Dict с результатом печати
        """
        from app.core.config import settings
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit
        from app.services.queue_service import queue_service

        # Получаем данные из очереди
        if queue_entry_id:
            queue_entry = (
                self.db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id == queue_entry_id)
                .first()
            )
            if not queue_entry:
                raise ValueError(f"Запись очереди {queue_entry_id} не найдена")
        else:
            queue_entry = None

        # Получаем данные визита
        if visit_id:
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Визит {visit_id} не найден")
        else:
            visit = None

        # Формируем данные для талона
        if ticket_data:
            ticket_data_final = ticket_data.copy()
        else:
            ticket_data_final = {}

        ticket_data_final.setdefault("clinic_name", settings.APP_NAME)
        ticket_data_final.setdefault("clinic_phone", "")
        ticket_data_final.setdefault("clinic_address", "")

        # Дополняем данными из БД
        if queue_entry:
            ticket_data_final.update(
                {
                    "queue_number": queue_entry.number,
                    "queue_id": queue_entry.queue_id,
                    "patient_name": queue_entry.patient_name or "Не указано",
                    "patient_phone": queue_entry.phone,
                    "doctor_name": getattr(queue_entry, 'doctor_name', None),
                    "specialty_name": getattr(queue_entry, 'specialty_name', None),
                    "source": queue_entry.source or "manual",
                }
            )

        if visit:
            ticket_data_final.update(
                {
                    "visit_id": visit.id,
                    "patient_name": getattr(visit, 'patient_name', None)
                    or ticket_data_final.get("patient_name", "Не указано"),
                    "patient_phone": getattr(visit, 'patient_phone', None)
                    or ticket_data_final.get("patient_phone"),
                }
            )

        # Добавляем метаданные
        now = queue_service.get_local_timestamp(self.db).isoformat()
        ticket_data_final.update(
            {
                "date": now,
                "time": now,
                "issued_by": user.full_name if user else "Система",
            }
        )

        # Печатаем талон
        return await self.print_document(
            document_type="ticket",
            document_data=ticket_data_final,
            printer_name=printer_name,
            user=user,
        )

    def get_print_template(
        self,
        document_type: str,
        printer_id: int | None = None,
        template_id: int | None = None,
        language: str = "ru",
    ) -> dict[str, Any] | None:
        """
        Получить шаблон печати (SSOT).

        Args:
            document_type: Тип документа (receipt, ticket, prescription, etc.)
            printer_id: ID принтера
            template_id: ID шаблона (если указан, используется он)
            language: Язык шаблона

        Returns:
            Dict с данными шаблона или None
        """
        # Находим шаблон
        template = self._get_template(template_id, document_type, printer_id or 0)

        if not template:
            return None

        return {
            "id": template.id,
            "name": template.name,
            "document_type": template.template_type,
            "printer_id": template.printer_id,
            "template_content": template.template_content,
            "language": template.language or language,
            "is_active": template.active,
            "created_at": (
                template.created_at.isoformat() if template.created_at else None
            ),
            "updated_at": (
                template.updated_at.isoformat() if template.updated_at else None
            ),
        }

    def test_print(self, printer_name: str) -> dict[str, Any]:
        """Тестовая печать"""
        test_data = {
            "clinic_name": "ТЕСТОВАЯ КЛИНИКА",
            "date": datetime.now(),
            "time": datetime.now(),
            "queue_number": "TEST",
            "doctor_name": "Тестовый врач",
            "specialty_name": "Терапия",
            "source": "test",
        }

        return asyncio.run(
            self.print_document(
                document_type="ticket",
                document_data=test_data,
                printer_name=printer_name,
            )
        )


# Глобальный экземпляр сервиса (будет инициализирован в зависимостях)
print_service: PrintService | None = None


def get_print_service() -> PrintService:
    """Получить экземпляр сервиса печати"""
    from app.db.session import SessionLocal

    db = SessionLocal()
    return PrintService(db)
