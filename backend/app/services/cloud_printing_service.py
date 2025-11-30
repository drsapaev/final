"""
Сервис для интеграции с облачной печатью
Поддерживает различные провайдеры облачной печати
"""

import asyncio
import base64
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import requests
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class PrinterStatus(str, Enum):
    """Статусы принтера"""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    BUSY = "busy"
    OUT_OF_PAPER = "out_of_paper"
    OUT_OF_INK = "out_of_ink"


class PrintJobStatus(str, Enum):
    """Статусы задания печати"""

    PENDING = "pending"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentFormat(str, Enum):
    """Форматы документов"""

    PDF = "pdf"
    HTML = "html"
    TEXT = "text"
    IMAGE = "image"


@dataclass
class PrintJob:
    """Задание печати"""

    id: str
    title: str
    content: Union[str, bytes]
    format: DocumentFormat
    printer_id: str
    copies: int = 1
    color: bool = False
    duplex: bool = False
    status: PrintJobStatus = PrintJobStatus.PENDING
    created_at: datetime = None
    completed_at: datetime = None
    error_message: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Printer:
    """Информация о принтере"""

    id: str
    name: str
    description: str
    status: PrinterStatus
    location: str = ""
    capabilities: Dict[str, Any] = None
    last_seen: datetime = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = {}
        if self.last_seen is None:
            self.last_seen = datetime.now()


class BasePrintProvider(ABC):
    """Базовый класс для провайдеров облачной печати"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    async def get_printers(self) -> List[Printer]:
        """Получить список доступных принтеров"""
        pass

    @abstractmethod
    async def get_printer_status(self, printer_id: str) -> PrinterStatus:
        """Получить статус принтера"""
        pass

    @abstractmethod
    async def submit_print_job(self, job: PrintJob) -> str:
        """Отправить задание на печать"""
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> PrintJobStatus:
        """Получить статус задания печати"""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Отменить задание печати"""
        pass


class MicrosoftUniversalPrintProvider(BasePrintProvider):
    """Провайдер Microsoft Universal Print"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.tenant_id = config.get("tenant_id")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.access_token = None
        self.token_expires_at = None

    async def _get_access_token(self) -> str:
        """Получить токен доступа"""
        if (
            self.access_token
            and self.token_expires_at
            and datetime.now() < self.token_expires_at
        ):
            return self.access_token

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            token_data = response.json()

            self.access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

            return self.access_token
        except Exception as e:
            logger.error(f"Ошибка получения токена Microsoft Universal Print: {e}")
            raise

    async def get_printers(self) -> List[Printer]:
        """Получить список принтеров"""
        try:
            token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            url = "https://graph.microsoft.com/v1.0/print/printers"
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            printers = []

            for printer_data in data.get("value", []):
                printer = Printer(
                    id=printer_data["id"],
                    name=printer_data["displayName"],
                    description=printer_data.get("description", ""),
                    status=self._map_printer_status(
                        printer_data.get("status", {}).get("state")
                    ),
                    location=printer_data.get("location", {}).get("displayName", ""),
                    capabilities=printer_data.get("capabilities", {}),
                )
                printers.append(printer)

            return printers
        except Exception as e:
            logger.error(f"Ошибка получения принтеров Microsoft Universal Print: {e}")
            return []

    async def get_printer_status(self, printer_id: str) -> PrinterStatus:
        """Получить статус принтера"""
        try:
            token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            url = f"https://graph.microsoft.com/v1.0/print/printers/{printer_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            status_data = data.get("status", {})
            return self._map_printer_status(status_data.get("state"))
        except Exception as e:
            logger.error(f"Ошибка получения статуса принтера {printer_id}: {e}")
            return PrinterStatus.ERROR

    async def submit_print_job(self, job: PrintJob) -> str:
        """Отправить задание на печать"""
        try:
            token = await self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Подготовка документа
            if job.format == DocumentFormat.PDF:
                content_type = "application/pdf"
            elif job.format == DocumentFormat.HTML:
                content_type = "text/html"
            elif job.format == DocumentFormat.TEXT:
                content_type = "text/plain"
            else:
                content_type = "application/octet-stream"

            # Кодирование содержимого
            if isinstance(job.content, str):
                content_bytes = job.content.encode('utf-8')
            else:
                content_bytes = job.content

            content_base64 = base64.b64encode(content_bytes).decode('utf-8')

            # Создание задания печати
            job_data = {
                "displayName": job.title,
                "configuration": {
                    "copies": job.copies,
                    "colorMode": "color" if job.color else "monochrome",
                    "duplex": "twoSidedLongEdge" if job.duplex else "oneSided",
                },
                "documents": [
                    {
                        "displayName": job.title,
                        "contentType": content_type,
                        "size": len(content_bytes),
                        "content": content_base64,
                    }
                ],
            }

            url = (
                f"https://graph.microsoft.com/v1.0/print/printers/{job.printer_id}/jobs"
            )
            response = requests.post(url, headers=headers, json=job_data)
            response.raise_for_status()

            result = response.json()
            return result["id"]
        except Exception as e:
            logger.error(f"Ошибка отправки задания печати: {e}")
            raise

    async def get_job_status(self, job_id: str) -> PrintJobStatus:
        """Получить статус задания печати"""
        try:
            token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            url = f"https://graph.microsoft.com/v1.0/print/jobs/{job_id}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            status = data.get("status", {}).get("state")
            return self._map_job_status(status)
        except Exception as e:
            logger.error(f"Ошибка получения статуса задания {job_id}: {e}")
            return PrintJobStatus.FAILED

    async def cancel_job(self, job_id: str) -> bool:
        """Отменить задание печати"""
        try:
            token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            url = f"https://graph.microsoft.com/v1.0/print/jobs/{job_id}/cancel"
            response = requests.post(url, headers=headers)
            response.raise_for_status()

            return True
        except Exception as e:
            logger.error(f"Ошибка отмены задания {job_id}: {e}")
            return False

    def _map_printer_status(self, status: str) -> PrinterStatus:
        """Маппинг статуса принтера"""
        mapping = {
            "idle": PrinterStatus.ONLINE,
            "processing": PrinterStatus.BUSY,
            "stopped": PrinterStatus.ERROR,
            "offline": PrinterStatus.OFFLINE,
        }
        return mapping.get(status, PrinterStatus.ERROR)

    def _map_job_status(self, status: str) -> PrintJobStatus:
        """Маппинг статуса задания"""
        mapping = {
            "pending": PrintJobStatus.PENDING,
            "processing": PrintJobStatus.PRINTING,
            "completed": PrintJobStatus.COMPLETED,
            "aborted": PrintJobStatus.CANCELLED,
            "failed": PrintJobStatus.FAILED,
        }
        return mapping.get(status, PrintJobStatus.FAILED)


class GoogleCloudPrintProvider(BasePrintProvider):
    """Провайдер Google Cloud Print (Legacy - для совместимости)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        logger.warning(
            "Google Cloud Print был закрыт в 2021 году. Используйте альтернативные провайдеры."
        )

    async def get_printers(self) -> List[Printer]:
        return []

    async def get_printer_status(self, printer_id: str) -> PrinterStatus:
        return PrinterStatus.OFFLINE

    async def submit_print_job(self, job: PrintJob) -> str:
        raise NotImplementedError("Google Cloud Print больше не поддерживается")

    async def get_job_status(self, job_id: str) -> PrintJobStatus:
        return PrintJobStatus.FAILED

    async def cancel_job(self, job_id: str) -> bool:
        return False


class MockPrintProvider(BasePrintProvider):
    """Мок-провайдер для тестирования"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.printers = [
            Printer(
                id="mock-printer-1",
                name="Тестовый принтер 1",
                description="Виртуальный принтер для тестирования",
                status=PrinterStatus.ONLINE,
                location="Тестовая локация",
            ),
            Printer(
                id="mock-printer-2",
                name="Тестовый принтер 2",
                description="Второй виртуальный принтер",
                status=PrinterStatus.BUSY,
                location="Другая локация",
            ),
        ]
        self.jobs = {}

    async def get_printers(self) -> List[Printer]:
        return self.printers

    async def get_printer_status(self, printer_id: str) -> PrinterStatus:
        for printer in self.printers:
            if printer.id == printer_id:
                return printer.status
        return PrinterStatus.ERROR

    async def submit_print_job(self, job: PrintJob) -> str:
        job_id = f"mock-job-{len(self.jobs) + 1}"
        self.jobs[job_id] = job
        job.status = PrintJobStatus.PENDING

        # Симуляция обработки задания
        await asyncio.sleep(0.1)
        job.status = PrintJobStatus.PRINTING

        await asyncio.sleep(0.1)
        job.status = PrintJobStatus.COMPLETED
        job.completed_at = datetime.now()

        return job_id

    async def get_job_status(self, job_id: str) -> PrintJobStatus:
        job = self.jobs.get(job_id)
        return job.status if job else PrintJobStatus.FAILED

    async def cancel_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            self.jobs[job_id].status = PrintJobStatus.CANCELLED
            return True
        return False


class CloudPrintingService:
    """Основной сервис облачной печати"""

    def __init__(self, db: Session):
        self.db = db
        self.providers = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Инициализация провайдеров"""
        # Microsoft Universal Print
        if hasattr(settings, 'MICROSOFT_PRINT_TENANT_ID'):
            microsoft_config = {
                "tenant_id": getattr(settings, 'MICROSOFT_PRINT_TENANT_ID', ''),
                "client_id": getattr(settings, 'MICROSOFT_PRINT_CLIENT_ID', ''),
                "client_secret": getattr(settings, 'MICROSOFT_PRINT_CLIENT_SECRET', ''),
            }
            if all(microsoft_config.values()):
                self.providers["microsoft"] = MicrosoftUniversalPrintProvider(
                    microsoft_config
                )

        # Mock провайдер для тестирования
        self.providers["mock"] = MockPrintProvider({})

        logger.info(
            f"Инициализированы провайдеры печати: {list(self.providers.keys())}"
        )

    async def get_all_printers(self) -> Dict[str, List[Printer]]:
        """Получить принтеры от всех провайдеров"""
        all_printers = {}

        for provider_name, provider in self.providers.items():
            try:
                printers = await provider.get_printers()
                all_printers[provider_name] = printers
                logger.info(f"Получено {len(printers)} принтеров от {provider_name}")
            except Exception as e:
                logger.error(f"Ошибка получения принтеров от {provider_name}: {e}")
                all_printers[provider_name] = []

        return all_printers

    async def get_printer_by_id(
        self, provider_name: str, printer_id: str
    ) -> Optional[Printer]:
        """Получить принтер по ID"""
        if provider_name not in self.providers:
            return None

        try:
            printers = await self.providers[provider_name].get_printers()
            for printer in printers:
                if printer.id == printer_id:
                    return printer
        except Exception as e:
            logger.error(f"Ошибка получения принтера {printer_id}: {e}")

        return None

    async def print_document(
        self,
        provider_name: str,
        printer_id: str,
        title: str,
        content: Union[str, bytes],
        format: DocumentFormat,
        copies: int = 1,
        color: bool = False,
        duplex: bool = False,
    ) -> Optional[str]:
        """Печать документа"""
        if provider_name not in self.providers:
            logger.error(f"Провайдер {provider_name} не найден")
            return None

        try:
            job = PrintJob(
                id="",
                title=title,
                content=content,
                format=format,
                printer_id=printer_id,
                copies=copies,
                color=color,
                duplex=duplex,
            )

            provider = self.providers[provider_name]
            job_id = await provider.submit_print_job(job)

            logger.info(f"Задание печати {job_id} отправлено на принтер {printer_id}")
            return job_id
        except Exception as e:
            logger.error(f"Ошибка печати документа: {e}")
            return None

    async def get_job_status(
        self, provider_name: str, job_id: str
    ) -> Optional[PrintJobStatus]:
        """Получить статус задания печати"""
        if provider_name not in self.providers:
            return None

        try:
            provider = self.providers[provider_name]
            return await provider.get_job_status(job_id)
        except Exception as e:
            logger.error(f"Ошибка получения статуса задания {job_id}: {e}")
            return None

    async def cancel_job(self, provider_name: str, job_id: str) -> bool:
        """Отменить задание печати"""
        if provider_name not in self.providers:
            return False

        try:
            provider = self.providers[provider_name]
            return await provider.cancel_job(job_id)
        except Exception as e:
            logger.error(f"Ошибка отмены задания {job_id}: {e}")
            return False

    async def print_medical_document(
        self,
        provider_name: str,
        printer_id: str,
        document_type: str,
        patient_data: Dict[str, Any],
        template_data: Dict[str, Any] = None,
    ) -> Optional[str]:
        """Печать медицинского документа"""
        try:
            # Генерация содержимого документа на основе типа
            if document_type == "prescription":
                content = self._generate_prescription(patient_data, template_data or {})
            elif document_type == "receipt":
                content = self._generate_receipt(patient_data, template_data or {})
            elif document_type == "ticket":
                content = self._generate_ticket(patient_data, template_data or {})
            elif document_type == "report":
                content = self._generate_report(patient_data, template_data or {})
            else:
                logger.error(f"Неизвестный тип документа: {document_type}")
                return None

            title = f"{document_type}_{patient_data.get('patient_name', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            return await self.print_document(
                provider_name=provider_name,
                printer_id=printer_id,
                title=title,
                content=content,
                format=DocumentFormat.HTML,
                copies=1,
            )
        except Exception as e:
            logger.error(f"Ошибка печати медицинского документа: {e}")
            return None

    def _generate_prescription(
        self, patient_data: Dict[str, Any], template_data: Dict[str, Any]
    ) -> str:
        """Генерация рецепта"""
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Рецепт</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; }}
                .patient-info {{ margin-bottom: 15px; }}
                .prescription {{ border: 1px solid #000; padding: 10px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>РЕЦЕПТ</h2>
                <p>Дата: {datetime.now().strftime('%d.%m.%Y')}</p>
            </div>
            <div class="patient-info">
                <p><strong>Пациент:</strong> {patient_data.get('patient_name', 'Не указано')}</p>
                <p><strong>Возраст:</strong> {patient_data.get('age', 'Не указано')}</p>
                <p><strong>Диагноз:</strong> {template_data.get('diagnosis', 'Не указано')}</p>
            </div>
            <div class="prescription">
                <p><strong>Назначение:</strong></p>
                <p>{template_data.get('prescription_text', 'Назначение не указано')}</p>
            </div>
            <div style="margin-top: 30px;">
                <p>Врач: {template_data.get('doctor_name', 'Не указано')}</p>
                <p>Подпись: ________________</p>
            </div>
        </body>
        </html>
        """

    def _generate_receipt(
        self, patient_data: Dict[str, Any], template_data: Dict[str, Any]
    ) -> str:
        """Генерация чека"""
        services = template_data.get('services', [])
        total = sum(service.get('price', 0) for service in services)

        services_html = ""
        for service in services:
            services_html += f"""
            <tr>
                <td>{service.get('name', 'Услуга')}</td>
                <td>{service.get('price', 0)} сум</td>
            </tr>
            """

        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Чек</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .total {{ font-weight: bold; }}
            </style>
        </head>
        <body>
            <h2>ЧЕК</h2>
            <p>Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            <p>Пациент: {patient_data.get('patient_name', 'Не указано')}</p>
            
            <table>
                <tr>
                    <th>Услуга</th>
                    <th>Стоимость</th>
                </tr>
                {services_html}
                <tr class="total">
                    <td>ИТОГО:</td>
                    <td>{total} сум</td>
                </tr>
            </table>
            
            <p style="margin-top: 20px;">Спасибо за обращение!</p>
        </body>
        </html>
        """

    def _generate_ticket(
        self, patient_data: Dict[str, Any], template_data: Dict[str, Any]
    ) -> str:
        """Генерация талона"""
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Талон</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 10px; text-align: center; }}
                .ticket {{ border: 2px solid #000; padding: 15px; margin: 10px; }}
                .queue-number {{ font-size: 48px; font-weight: bold; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="ticket">
                <h2>ТАЛОН ОЧЕРЕДИ</h2>
                <div class="queue-number">{template_data.get('queue_number', '???')}</div>
                <p><strong>Врач:</strong> {template_data.get('doctor_name', 'Не указано')}</p>
                <p><strong>Кабинет:</strong> {template_data.get('cabinet', 'Не указано')}</p>
                <p><strong>Время:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                <p><strong>Пациент:</strong> {patient_data.get('patient_name', 'Не указано')}</p>
            </div>
        </body>
        </html>
        """

    def _generate_report(
        self, patient_data: Dict[str, Any], template_data: Dict[str, Any]
    ) -> str:
        """Генерация отчета"""
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Медицинский отчет</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .section {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>МЕДИЦИНСКИЙ ОТЧЕТ</h1>
                <p>Дата: {datetime.now().strftime('%d.%m.%Y')}</p>
            </div>
            
            <div class="section">
                <h3>Информация о пациенте</h3>
                <p><strong>ФИО:</strong> {patient_data.get('patient_name', 'Не указано')}</p>
                <p><strong>Возраст:</strong> {patient_data.get('age', 'Не указано')}</p>
                <p><strong>Телефон:</strong> {patient_data.get('phone', 'Не указано')}</p>
            </div>
            
            <div class="section">
                <h3>Результаты обследования</h3>
                <p>{template_data.get('examination_results', 'Результаты не указаны')}</p>
            </div>
            
            <div class="section">
                <h3>Заключение</h3>
                <p>{template_data.get('conclusion', 'Заключение не указано')}</p>
            </div>
            
            <div style="margin-top: 50px;">
                <p>Врач: {template_data.get('doctor_name', 'Не указано')}</p>
                <p>Подпись: ________________</p>
            </div>
        </body>
        </html>
        """


def get_cloud_printing_service(db: Session) -> CloudPrintingService:
    """Получить экземпляр сервиса облачной печати"""
    return CloudPrintingService(db)
