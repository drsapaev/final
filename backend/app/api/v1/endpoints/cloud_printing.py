"""
API endpoints для облачной печати
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.core.roles import Roles
from app.models.user import User
from app.services.cloud_printing_service import (
    CloudPrintingService,
    DocumentFormat,
    get_cloud_printing_service,
    PrinterStatus,
    PrintJobStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic Models for Requests and Responses
class PrinterResponse(BaseModel):
    """Ответ с информацией о принтере"""

    id: str
    name: str
    description: str
    status: str
    location: str
    capabilities: Dict[str, Any]
    provider: str


class PrintJobRequest(BaseModel):
    """Запрос на печать"""

    provider_name: str = Field(..., description="Имя провайдера печати")
    printer_id: str = Field(..., description="ID принтера")
    title: str = Field(..., description="Название документа")
    content: str = Field(..., description="Содержимое документа")
    format: str = Field(default="html", pattern="^(pdf|html|text|image)$")
    copies: int = Field(default=1, ge=1, le=10)
    color: bool = Field(default=False, description="Цветная печать")
    duplex: bool = Field(default=False, description="Двусторонняя печать")


class MedicalDocumentRequest(BaseModel):
    """Запрос на печать медицинского документа"""

    provider_name: str = Field(..., description="Имя провайдера печати")
    printer_id: str = Field(..., description="ID принтера")
    document_type: str = Field(..., pattern="^(prescription|receipt|ticket|report)$")
    patient_data: Dict[str, Any] = Field(..., description="Данные пациента")
    template_data: Optional[Dict[str, Any]] = Field(None, description="Данные шаблона")


class PrintJobResponse(BaseModel):
    """Ответ с информацией о задании печати"""

    success: bool
    job_id: Optional[str] = None
    message: str
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Ответ со статусом задания"""

    job_id: str
    status: str
    provider_name: str


# ===================== ПРИНТЕРЫ =====================


@router.get("/printers")
async def get_all_printers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Получить список всех доступных принтеров"""
    try:
        printing_service = get_cloud_printing_service(db)
        all_printers = await printing_service.get_all_printers()

        # Преобразуем в плоский список с указанием провайдера
        printers_list = []
        for provider_name, printers in all_printers.items():
            for printer in printers:
                printer_response = PrinterResponse(
                    id=printer.id,
                    name=printer.name,
                    description=printer.description,
                    status=printer.status.value,
                    location=printer.location,
                    capabilities=printer.capabilities,
                    provider=provider_name,
                )
                printers_list.append(printer_response)

        return {
            "success": True,
            "printers": printers_list,
            "total_count": len(printers_list),
            "providers": list(all_printers.keys()),
        }
    except Exception as e:
        logger.error(f"Ошибка получения принтеров: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/printers/{provider_name}")
async def get_printers_by_provider(
    provider_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Получить принтеры конкретного провайдера"""
    try:
        printing_service = get_cloud_printing_service(db)
        all_printers = await printing_service.get_all_printers()

        if provider_name not in all_printers:
            raise HTTPException(
                status_code=404, detail=f"Провайдер {provider_name} не найден"
            )

        printers = all_printers[provider_name]
        printers_list = []

        for printer in printers:
            printer_response = PrinterResponse(
                id=printer.id,
                name=printer.name,
                description=printer.description,
                status=printer.status.value,
                location=printer.location,
                capabilities=printer.capabilities,
                provider=provider_name,
            )
            printers_list.append(printer_response)

        return {
            "success": True,
            "provider": provider_name,
            "printers": printers_list,
            "count": len(printers_list),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения принтеров провайдера {provider_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/printers/{provider_name}/{printer_id}")
async def get_printer_info(
    provider_name: str,
    printer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Получить информацию о конкретном принтере"""
    try:
        printing_service = get_cloud_printing_service(db)
        printer = await printing_service.get_printer_by_id(provider_name, printer_id)

        if not printer:
            raise HTTPException(status_code=404, detail="Принтер не найден")

        return {
            "success": True,
            "printer": PrinterResponse(
                id=printer.id,
                name=printer.name,
                description=printer.description,
                status=printer.status.value,
                location=printer.location,
                capabilities=printer.capabilities,
                provider=provider_name,
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о принтере {printer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== ПЕЧАТЬ =====================


@router.post("/print", response_model=PrintJobResponse)
async def print_document(
    request: PrintJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Печать документа"""
    try:
        printing_service = get_cloud_printing_service(db)

        # Проверяем существование принтера
        printer = await printing_service.get_printer_by_id(
            request.provider_name, request.printer_id
        )
        if not printer:
            return PrintJobResponse(
                success=False,
                message="Принтер не найден",
                error="Указанный принтер не существует или недоступен",
            )

        # Отправляем задание на печать
        job_id = await printing_service.print_document(
            provider_name=request.provider_name,
            printer_id=request.printer_id,
            title=request.title,
            content=request.content,
            format=DocumentFormat(request.format),
            copies=request.copies,
            color=request.color,
            duplex=request.duplex,
        )

        if job_id:
            logger.info(
                f"Пользователь {current_user.email} отправил документ '{request.title}' на печать"
            )
            return PrintJobResponse(
                success=True, job_id=job_id, message="Документ отправлен на печать"
            )
        else:
            return PrintJobResponse(
                success=False,
                message="Не удалось отправить документ на печать",
                error="Ошибка при создании задания печати",
            )
    except Exception as e:
        logger.error(f"Ошибка печати документа: {e}")
        return PrintJobResponse(success=False, message="Ошибка печати", error=str(e))


@router.post("/print/medical", response_model=PrintJobResponse)
async def print_medical_document(
    request: MedicalDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Печать медицинского документа"""
    try:
        printing_service = get_cloud_printing_service(db)

        # Проверяем существование принтера
        printer = await printing_service.get_printer_by_id(
            request.provider_name, request.printer_id
        )
        if not printer:
            return PrintJobResponse(
                success=False,
                message="Принтер не найден",
                error="Указанный принтер не существует или недоступен",
            )

        # Отправляем медицинский документ на печать
        job_id = await printing_service.print_medical_document(
            provider_name=request.provider_name,
            printer_id=request.printer_id,
            document_type=request.document_type,
            patient_data=request.patient_data,
            template_data=request.template_data,
        )

        if job_id:
            logger.info(
                f"Пользователь {current_user.email} отправил медицинский документ '{request.document_type}' на печать"
            )
            return PrintJobResponse(
                success=True,
                job_id=job_id,
                message=f"Медицинский документ '{request.document_type}' отправлен на печать",
            )
        else:
            return PrintJobResponse(
                success=False,
                message="Не удалось отправить медицинский документ на печать",
                error="Ошибка при создании задания печати",
            )
    except Exception as e:
        logger.error(f"Ошибка печати медицинского документа: {e}")
        return PrintJobResponse(
            success=False, message="Ошибка печати медицинского документа", error=str(e)
        )


# ===================== УПРАВЛЕНИЕ ЗАДАНИЯМИ =====================


@router.get("/jobs/{provider_name}/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    provider_name: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Получить статус задания печати"""
    try:
        printing_service = get_cloud_printing_service(db)
        status = await printing_service.get_job_status(provider_name, job_id)

        if status is None:
            raise HTTPException(status_code=404, detail="Задание не найдено")

        return JobStatusResponse(
            job_id=job_id, status=status.value, provider_name=provider_name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статуса задания {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{provider_name}/{job_id}/cancel")
async def cancel_job(
    provider_name: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.DOCTOR])),
):
    """Отменить задание печати"""
    try:
        printing_service = get_cloud_printing_service(db)
        success = await printing_service.cancel_job(provider_name, job_id)

        if success:
            logger.info(
                f"Пользователь {current_user.email} отменил задание печати {job_id}"
            )
            return {
                "success": True,
                "message": "Задание печати отменено",
                "job_id": job_id,
            }
        else:
            return {
                "success": False,
                "message": "Не удалось отменить задание печати",
                "job_id": job_id,
            }
    except Exception as e:
        logger.error(f"Ошибка отмены задания {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick-print/prescription")
async def quick_print_prescription(
    provider_name: str,
    printer_id: str,
    patient_name: str,
    diagnosis: str,
    prescription_text: str,
    doctor_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.DOCTOR])),
):
    """Быстрая печать рецепта"""
    try:
        printing_service = get_cloud_printing_service(db)

        patient_data = {"patient_name": patient_name}
        template_data = {
            "diagnosis": diagnosis,
            "prescription_text": prescription_text,
            "doctor_name": doctor_name,
        }

        job_id = await printing_service.print_medical_document(
            provider_name=provider_name,
            printer_id=printer_id,
            document_type="prescription",
            patient_data=patient_data,
            template_data=template_data,
        )

        if job_id:
            return {
                "success": True,
                "job_id": job_id,
                "message": "Рецепт отправлен на печать",
            }
        else:
            return {"success": False, "message": "Не удалось напечатать рецепт"}
    except Exception as e:
        logger.error(f"Ошибка быстрой печати рецепта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-print/ticket")
async def quick_print_ticket(
    provider_name: str,
    printer_id: str,
    patient_name: str,
    queue_number: str,
    doctor_name: str,
    cabinet: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR])),
):
    """Быстрая печать талона"""
    try:
        printing_service = get_cloud_printing_service(db)

        patient_data = {"patient_name": patient_name}
        template_data = {
            "queue_number": queue_number,
            "doctor_name": doctor_name,
            "cabinet": cabinet,
        }

        job_id = await printing_service.print_medical_document(
            provider_name=provider_name,
            printer_id=printer_id,
            document_type="ticket",
            patient_data=patient_data,
            template_data=template_data,
        )

        if job_id:
            return {
                "success": True,
                "job_id": job_id,
                "message": "Талон отправлен на печать",
            }
        else:
            return {"success": False, "message": "Не удалось напечатать талон"}
    except Exception as e:
        logger.error(f"Ошибка быстрой печати талона: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== ТЕСТИРОВАНИЕ =====================


@router.post("/test/{provider_name}/{printer_id}")
async def test_printer(
    provider_name: str,
    printer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Тестовая печать"""
    try:
        printing_service = get_cloud_printing_service(db)

        test_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Тестовая печать</title>
        </head>
        <body>
            <h2>ТЕСТОВАЯ ПЕЧАТЬ</h2>
            <p>Дата и время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            <p>Провайдер: {provider_name}</p>
            <p>Принтер: {printer_id}</p>
            <p>Пользователь: {current_user.email}</p>
            <p>Этот документ был напечатан для проверки работы принтера.</p>
        </body>
        </html>
        """

        job_id = await printing_service.print_document(
            provider_name=provider_name,
            printer_id=printer_id,
            title="Тестовая печать",
            content=test_content,
            format=DocumentFormat.HTML,
            copies=1,
        )

        if job_id:
            return {
                "success": True,
                "job_id": job_id,
                "message": "Тестовая печать отправлена",
            }
        else:
            return {"success": False, "message": "Не удалось выполнить тестовую печать"}
    except Exception as e:
        logger.error(f"Ошибка тестовой печати: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== СТАТИСТИКА =====================


@router.get("/statistics")
async def get_printing_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получить статистику печати"""
    try:
        printing_service = get_cloud_printing_service(db)
        all_printers = await printing_service.get_all_printers()

        # Подсчет статистики
        total_printers = sum(len(printers) for printers in all_printers.values())
        online_printers = 0
        offline_printers = 0

        for printers in all_printers.values():
            for printer in printers:
                if printer.status == PrinterStatus.ONLINE:
                    online_printers += 1
                else:
                    offline_printers += 1

        return {
            "success": True,
            "statistics": {
                "total_printers": total_printers,
                "online_printers": online_printers,
                "offline_printers": offline_printers,
                "providers_count": len(all_printers),
                "providers": list(all_printers.keys()),
            },
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики печати: {e}")
        raise HTTPException(status_code=500, detail=str(e))
