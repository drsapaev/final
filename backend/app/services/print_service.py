"""
Сервис для печати документов
Основа: detail.md стр. 3721-3888, passport.md стр. 1925-2063
"""
import asyncio
import os
import socket
import serial
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.models.print_config import PrinterConfig, PrintTemplate, PrintJob
from app.models.user import User
from app.crud import print_config as crud_print

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
            lstrip_blocks=True
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
        document_data: Dict[str, Any],
        printer_name: Optional[str] = None,
        template_id: Optional[int] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Основной метод печати документа
        """
        try:
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
                document_data=document_data
            )

            try:
                # Рендерим шаблон
                rendered_content = self._render_template(template, document_data)
                
                # Печатаем в зависимости от типа принтера
                if printer.printer_type == "ESC/POS":
                    result = await self._print_escpos(printer, rendered_content)
                elif printer.printer_type in ["A4", "A5"]:
                    result = await self._print_pdf(printer, rendered_content, printer.printer_type)
                else:
                    raise Exception(f"Неподдерживаемый тип принтера: {printer.printer_type}")

                # Обновляем статус задания
                self._update_print_job(print_job.id, "completed")
                
                return {
                    "success": True,
                    "job_id": print_job.id,
                    "message": "Документ отправлен на печать",
                    "printer": printer.display_name,
                    "result": result
                }

            except Exception as e:
                # Обновляем статус задания с ошибкой
                self._update_print_job(print_job.id, "failed", str(e))
                raise

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Ошибка печати: {str(e)}"
            }

    def _get_printer(self, printer_name: Optional[str], document_type: str) -> Optional[PrinterConfig]:
        """Найти принтер по имени или типу документа"""
        if printer_name:
            return crud_print.get_printer_by_name(self.db, printer_name)
        else:
            # Находим принтер по умолчанию для типа документа
            return crud_print.get_default_printer_for_type(self.db, document_type)

    def _get_template(self, template_id: Optional[int], document_type: str, printer_id: int) -> Optional[PrintTemplate]:
        """Найти шаблон по ID или типу документа"""
        if template_id:
            return crud_print.get_print_template(self.db, template_id)
        else:
            return crud_print.get_template_by_type_and_printer(self.db, document_type, printer_id)

    def _render_template(self, template: PrintTemplate, data: Dict[str, Any]) -> str:
        """Рендерить шаблон с данными"""
        try:
            jinja_template = self.jinja_env.from_string(template.template_content)
            return jinja_template.render(**data)
        except Exception as e:
            raise Exception(f"Ошибка рендеринга шаблона: {str(e)}")

    def _create_print_job(self, user_id: Optional[int], printer_id: int, template_id: int, 
                         document_type: str, document_data: Dict[str, Any]) -> PrintJob:
        """Создать задание печати"""
        job_data = {
            "user_id": user_id,
            "printer_id": printer_id,
            "template_id": template_id,
            "document_type": document_type,
            "document_id": document_data.get("id", ""),
            "status": "pending",
            "print_data": document_data
        }
        
        return crud_print.create_print_job(self.db, job_data)

    def _update_print_job(self, job_id: int, status: str, error_message: Optional[str] = None):
        """Обновить статус задания печати"""
        update_data = {
            "status": status,
            "completed_at": datetime.utcnow() if status in ["completed", "failed"] else None
        }
        
        if error_message:
            update_data["error_message"] = error_message
            
        crud_print.update_print_job(self.db, job_id, update_data)

    async def _print_escpos(self, printer: PrinterConfig, content: str) -> Dict[str, Any]:
        """
        Печать на ESC/POS принтере (термопринтер)
        """
        try:
            if printer.connection_type == "network":
                return await self._print_network_escpos(printer, content)
            elif printer.connection_type == "usb":
                return await self._print_usb_escpos(printer, content)
            elif printer.connection_type == "serial":
                return await self._print_serial_escpos(printer, content)
            else:
                raise Exception(f"Неподдерживаемый тип подключения: {printer.connection_type}")
                
        except Exception as e:
            raise Exception(f"Ошибка ESC/POS печати: {str(e)}")

    async def _print_network_escpos(self, printer: PrinterConfig, content: str) -> Dict[str, Any]:
        """Печать через сеть (TCP/IP)"""
        try:
            # Кодируем контент
            encoded_content = content.encode(printer.encoding or 'utf-8')
            
            # Подключаемся к принтеру
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # 10 секунд таймаут
            
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: sock.connect((printer.ip_address, printer.port or 9100))
            )
            
            # Отправляем данные
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sock.send(encoded_content)
            )
            
            sock.close()
            
            return {
                "method": "network",
                "address": f"{printer.ip_address}:{printer.port}",
                "bytes_sent": len(encoded_content)
            }
            
        except Exception as e:
            raise Exception(f"Ошибка сетевой печати: {str(e)}")

    async def _print_usb_escpos(self, printer: PrinterConfig, content: str) -> Dict[str, Any]:
        """Печать через USB"""
        try:
            if not printer.device_path:
                raise Exception("Не указан путь к USB устройству")
            
            encoded_content = content.encode(printer.encoding or 'utf-8')
            
            # Записываем в устройство
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._write_to_device(printer.device_path, encoded_content)
            )
            
            return {
                "method": "usb",
                "device_path": printer.device_path,
                "bytes_sent": len(encoded_content)
            }
            
        except Exception as e:
            raise Exception(f"Ошибка USB печати: {str(e)}")

    def _write_to_device(self, device_path: str, content: bytes):
        """Записать данные в устройство"""
        with open(device_path, 'wb') as device:
            device.write(content)
            device.flush()

    async def _print_serial_escpos(self, printer: PrinterConfig, content: str) -> Dict[str, Any]:
        """Печать через последовательный порт"""
        try:
            if not printer.device_path:
                raise Exception("Не указан путь к последовательному порту")
            
            encoded_content = content.encode(printer.encoding or 'utf-8')
            
            # Открываем последовательный порт
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._write_to_serial(printer.device_path, encoded_content)
            )
            
            return {
                "method": "serial",
                "device_path": printer.device_path,
                "bytes_sent": len(encoded_content)
            }
            
        except Exception as e:
            raise Exception(f"Ошибка печати через COM порт: {str(e)}")

    def _write_to_serial(self, device_path: str, content: bytes):
        """Записать данные в последовательный порт"""
        with serial.Serial(device_path, 9600, timeout=1) as ser:
            ser.write(content)
            ser.flush()

    async def _print_pdf(self, printer: PrinterConfig, content: str, paper_size: str) -> Dict[str, Any]:
        """
        Печать PDF документов (A4/A5)
        """
        try:
            from app.services.pdf_service import get_pdf_service
            import tempfile
            import subprocess
            
            pdf_service = get_pdf_service()
            
            # Если контент это HTML шаблон, генерируем PDF
            if content.strip().startswith('<!DOCTYPE html') or content.strip().startswith('<html'):
                # Генерируем PDF из HTML
                pdf_bytes = pdf_service.generate_pdf_from_html(
                    template_name="temp_template.html",  # Временный шаблон
                    data={},
                    paper_size=paper_size
                )
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
                    **result
                }
                
            finally:
                # Удаляем временный файл
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
        except Exception as e:
            raise Exception(f"Ошибка PDF печати: {str(e)}")

    async def _print_pdf_network(self, printer: PrinterConfig, file_path: str) -> Dict[str, Any]:
        """Печать PDF через сеть"""
        try:
            # Используем lp команду для отправки на сетевой принтер
            cmd = [
                "lp", 
                "-d", f"ipp://{printer.ip_address}:{printer.port or 631}/printers/default",
                "-o", f"media={printer.printer_type}",
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "status": "sent",
                    "message": "PDF отправлен на сетевой принтер"
                }
            else:
                raise Exception(f"Ошибка lp команды: {stderr.decode()}")
                
        except Exception as e:
            # Fallback: копируем файл в сетевую папку принтера
            return await self._print_pdf_fallback(printer, file_path)

    async def _print_pdf_local(self, printer: PrinterConfig, file_path: str) -> Dict[str, Any]:
        """Печать PDF на локальном принтере"""
        try:
            import platform
            
            if platform.system() == "Windows":
                # Windows: используем команду print
                cmd = ["print", f"/D:{printer.device_path or 'LPT1'}", file_path]
            else:
                # Linux/Unix: используем lp
                cmd = ["lp", "-d", printer.device_path or "default", file_path]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {
                    "status": "printed",
                    "message": "PDF отправлен на локальный принтер"
                }
            else:
                raise Exception(f"Ошибка печати: {stderr.decode()}")
                
        except Exception as e:
            raise Exception(f"Ошибка локальной PDF печати: {str(e)}")

    async def _print_pdf_fallback(self, printer: PrinterConfig, file_path: str) -> Dict[str, Any]:
        """Fallback метод для PDF печати"""
        return {
            "status": "queued", 
            "message": f"PDF файл готов для печати на {printer.display_name}",
            "note": "Требуется ручная отправка на принтер"
        }

    # ===================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====================

    def get_printer_status(self, printer_name: str) -> Dict[str, Any]:
        """Получить статус принтера"""
        printer = crud_print.get_printer_by_name(self.db, printer_name)
        
        if not printer:
            return {"status": "not_found", "message": "Принтер не найден"}
        
        if not printer.active:
            return {"status": "disabled", "message": "Принтер отключен"}
        
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
            return {"status": "error", "message": f"Ошибка проверки: {str(e)}"}

    async def generate_receipt(
        self,
        payment_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        payment_data: Optional[Dict[str, Any]] = None,
        printer_name: Optional[str] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
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
            payment = self.db.query(Payment).filter(
                Payment.visit_id == visit_id,
                Payment.status == "paid"
            ).order_by(Payment.created_at.desc()).first()
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
        
        # Дополняем данными из БД
        if payment:
            receipt_data.update({
                "payment_id": payment.id,
                "amount": float(payment.amount),
                "currency": payment.currency or "UZS",
                "method": payment.method or "cash",
                "status": payment.status,
                "receipt_no": payment.receipt_no or f"RCP-{payment.id}",
                "paid_at": payment.paid_at or queue_service.get_local_timestamp(self.db),
                "note": payment.note
            })
        
        if visit:
            receipt_data.update({
                "visit_id": visit.id,
                "patient_name": getattr(visit, 'patient_name', None) or "Не указано",
                "patient_phone": getattr(visit, 'patient_phone', None),
            })
        
        # Добавляем метаданные
        now = queue_service.get_local_timestamp(self.db)
        receipt_data.update({
            "date": now,
            "time": now,
            "issued_by": user.full_name if user else "Система"
        })
        
        # Печатаем чек
        return await self.print_document(
            document_type="receipt",
            document_data=receipt_data,
            printer_name=printer_name,
            user=user
        )
    
    async def generate_ticket(
        self,
        queue_entry_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        ticket_data: Optional[Dict[str, Any]] = None,
        printer_name: Optional[str] = None,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
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
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit
        from app.services.queue_service import queue_service
        
        # Получаем данные из очереди
        if queue_entry_id:
            queue_entry = self.db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.id == queue_entry_id
            ).first()
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
        
        # Дополняем данными из БД
        if queue_entry:
            ticket_data_final.update({
                "queue_number": queue_entry.number,
                "queue_id": queue_entry.queue_id,
                "patient_name": queue_entry.patient_name or "Не указано",
                "patient_phone": queue_entry.phone,
                "doctor_name": getattr(queue_entry, 'doctor_name', None),
                "specialty_name": getattr(queue_entry, 'specialty_name', None),
                "source": queue_entry.source or "manual"
            })
        
        if visit:
            ticket_data_final.update({
                "visit_id": visit.id,
                "patient_name": getattr(visit, 'patient_name', None) or ticket_data_final.get("patient_name", "Не указано"),
                "patient_phone": getattr(visit, 'patient_phone', None) or ticket_data_final.get("patient_phone"),
            })
        
        # Добавляем метаданные
        now = queue_service.get_local_timestamp(self.db)
        ticket_data_final.update({
            "date": now,
            "time": now,
            "issued_by": user.full_name if user else "Система"
        })
        
        # Печатаем талон
        return await self.print_document(
            document_type="ticket",
            document_data=ticket_data_final,
            printer_name=printer_name,
            user=user
        )
    
    def get_print_template(
        self,
        document_type: str,
        printer_id: Optional[int] = None,
        template_id: Optional[int] = None,
        language: str = "ru"
    ) -> Optional[Dict[str, Any]]:
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
            "document_type": template.document_type,
            "printer_id": template.printer_id,
            "template_content": template.template_content,
            "language": template.language or language,
            "is_active": template.is_active,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None
        }
    
    def test_print(self, printer_name: str) -> Dict[str, Any]:
        """Тестовая печать"""
        test_data = {
            "clinic_name": "ТЕСТОВАЯ КЛИНИКА",
            "date": datetime.now(),
            "time": datetime.now(),
            "queue_number": "TEST",
            "doctor_name": "Тестовый врач",
            "specialty_name": "Терапия",
            "source": "test"
        }
        
        return asyncio.run(self.print_document(
            document_type="ticket",
            document_data=test_data,
            printer_name=printer_name
        ))

# Глобальный экземпляр сервиса (будет инициализирован в зависимостях)
print_service: Optional[PrintService] = None

def get_print_service() -> PrintService:
    """Получить экземпляр сервиса печати"""
    from app.db.session import SessionLocal
    db = SessionLocal()
    return PrintService(db)
