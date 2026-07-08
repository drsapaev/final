"""Rendering mixin for PrintService.

Split from print_service.py.
"""
from __future__ import annotations

from app.services.print_svc._base import *  # noqa: F401, F403
from app.services.print_svc._base import PrintServiceMixinBase


class RenderingMixin(PrintServiceMixinBase):
    """Rendering methods."""

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


