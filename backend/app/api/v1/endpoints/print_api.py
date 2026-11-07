"""
API endpoints для печати документов
Основа: detail.md стр. 3721-3888, passport.md стр. 1925-2063
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import print_config as crud_print
from app.models.user import User
from app.schemas.print_config import (
    PrintCertificateRequest,
    PrintLabResultsRequest,
    PrintPrescriptionRequest,
    PrintReceiptRequest,
    PrintResponse,
    PrintTicketRequest,
    QuickReceiptRequest,
    QuickTicketRequest,
)
from app.services.print_service import PrintService, get_print_service

router = APIRouter()
logger = logging.getLogger(__name__)

# ===================== ПЕЧАТЬ ДОКУМЕНТОВ =====================


@router.post("/ticket", response_model=PrintResponse)
async def print_queue_ticket(
    request: PrintTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Печать талона очереди (использует SSOT)
    """
    try:
        # Используем SSOT для генерации талона
        result = await print_service.generate_ticket(
            queue_entry_id=(
                request.queue_entry_id if hasattr(request, 'queue_entry_id') else None
            ),
            visit_id=request.visit_id if hasattr(request, 'visit_id') else None,
            ticket_data=request.dict(),
            printer_name=request.printer_name,
            user=current_user,
        )

        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/prescription", response_model=PrintResponse)
async def print_prescription(
    request: PrintPrescriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Печать рецепта
    """
    try:
        # Дополняем данные рецепта
        prescription_data = request.dict()
        prescription_data.update(
            {
                "prescription": {
                    **prescription_data.get("prescription", {}),
                    "date": datetime.now(),
                    "time": datetime.now(),
                    "number": prescription_data.get("prescription", {}).get("number")
                    or f"RX-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                },
                "doctor": {
                    "full_name": current_user.full_name,
                    "specialty_name": "Врач",  # Получать из профиля врача
                    "license_number": "Лицензия",  # Получать из профиля врача
                },
            }
        )

        result = await print_service.print_document(
            document_type="prescription",
            document_data=prescription_data,
            printer_name=request.printer_name,
            user=current_user,
        )

        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/certificate", response_model=PrintResponse)
async def print_medical_certificate(
    request: PrintCertificateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Печать медицинской справки
    """
    try:
        # Дополняем данные справки
        certificate_data = request.dict()
        certificate_data.update(
            {
                "certificate": {
                    **certificate_data.get("certificate", {}),
                    "issue_date": datetime.now(),
                    "number": certificate_data.get("certificate", {}).get("number")
                    or f"CERT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                },
                "doctor": {
                    "full_name": current_user.full_name,
                    "specialty_name": "Врач",  # Получать из профиля врача
                    "license_number": "Лицензия",  # Получать из профиля врача
                },
            }
        )

        result = await print_service.print_document(
            document_type="medical_certificate",
            document_data=certificate_data,
            printer_name=request.printer_name,
            user=current_user,
        )

        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/receipt", response_model=PrintResponse)
async def print_payment_receipt(
    request: PrintReceiptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Печать чека об оплате (использует SSOT)
    """
    try:
        # Используем SSOT для генерации чека
        result = await print_service.generate_receipt(
            payment_id=request.payment_id if hasattr(request, 'payment_id') else None,
            visit_id=request.visit_id if hasattr(request, 'visit_id') else None,
            payment_data=request.dict(),
            printer_name=request.printer_name,
            user=current_user,
        )

        return result

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


@router.post("/lab-results", response_model=PrintResponse)
async def print_lab_results(
    request: PrintLabResultsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
    print_service: PrintService = Depends(get_print_service),
):
    """Печать лабораторного бланка по авторизованному отчёту.

    LABPRINT-FE-001 (audit 3886, round 14): раньше роут принимал СВОБОДНЫЕ
    клиентские данные (результаты/флаги/снапшоты пациента) и рендерил их
    как «лабораторный бланк» без какой-либо сверки с LabReportInstance —
    доверенная роль могла распечатать несохранённые/изменённые/чужие
    значения, а UI после этого помечал *другой* канонический инстанс как
    PRINTED. Теперь фронт отправляет ТОЛЬКО report_instance_id (+ опцию
    принтера); сервер загружает инстанс, проверяет право чтения Doctor
    (тот же guard, что у /lab/report-instances/{id}/pdf), требует статус
    FINALIZED/PRINTED и материализует бланк из БД тем же пайплайном
    (materialize_instance + снапшоты), что и канонический PDF.
    """
    from app.api.v1.endpoints.lab_reporting import (
        LabReportingDomainError,
        LabReportingService,
        _ensure_doctor_can_read_lab_instance,
    )

    try:
        lab_service = LabReportingService(db)
        instance = lab_service.get_instance(request.report_instance_id)
        _ensure_doctor_can_read_lab_instance(db, instance, current_user)
        if instance.status not in {"FINALIZED", "PRINTED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only finalized reports can be printed",
            )

        materialized_sections = lab_service.materialize_instance(instance)
        critical_findings = lab_service.summarize_critical_findings(materialized_sections)
        patient_snapshot = instance.patient_snapshot or {}
        branding = instance.branding_snapshot or {}
        patient_full_name = (
            patient_snapshot.get("full_name")
            or f"Patient #{instance.patient_id}"
        )
        template_name = instance.template.name if instance.template else None
        report_date = (
            instance.finalized_at or instance.created_at or datetime.now(UTC)
        )

        # Тот же формат документа, что раньше собирал браузер
        # (buildLabPrintPayload), — но каждое значение теперь читается из
        # персистентного состояния инстанса, а не из запроса клиента.
        document_data = {
            "lab_order": {
                "id": instance.id,
                "visit_id": instance.visit_id,
                "patient_id": instance.patient_id,
                "template_id": instance.template_id,
                "template_name": template_name,
                "status": instance.status,
                "created_at": _iso(instance.created_at),
                "finalized_at": _iso(instance.finalized_at),
                "printed_at": _iso(instance.printed_at),
            },
            "lab_results": [
                {
                    "section_key": section.get("key"),
                    "section_title": section.get("title"),
                    "field_key": field.get("field_key"),
                    "label": field.get("label"),
                    "value_numeric": field.get("value_numeric"),
                    "value_text": field.get("value_text"),
                    "reference_text": field.get("reference_text"),
                    "unit": field.get("unit"),
                    "resolved_flag": field.get("resolved_flag"),
                    "resolved_flag_severity": field.get("resolved_flag_severity"),
                }
                for section in materialized_sections
                for field in section.get("fields", [])
            ],
            "patient": {
                "full_name": patient_full_name,
                "birth_date": patient_snapshot.get("birth_date") or "",
                "address": patient_snapshot.get("address") or "",
                "phone": patient_snapshot.get("phone") or "",
                "sex": patient_snapshot.get("sex") or "",
            },
            "clinic": {
                "name": branding.get("name") or branding.get("clinic_name") or "",
                "address": branding.get("address") or "",
                "phone": branding.get("phone") or "",
                "website": branding.get("website") or "",
                "license_number": branding.get("license_number") or "",
            },
            "branding": {
                "clinic_name": branding.get("name") or branding.get("clinic_name") or "",
                "address": branding.get("address") or "",
                "phone": branding.get("phone") or "",
                "document_title": template_name or "",
                "document_subtitle": (getattr(instance.template, "subtitle", "") if instance.template else "") or "",
            },
            "signers": instance.signer_snapshot or {},
            "sections": materialized_sections,
            "template_name": template_name,
            "report_date": _iso(report_date),
            "footer_notes": (instance.template_version.footer_notes if instance.template_version else "") or "",
            "critical_findings": critical_findings,
        }

        result = await print_service.print_document(
            document_type="lab_results",
            document_data=document_data,
            printer_name=request.printer_name,
            user=current_user,
        )
        return result

    except LabReportingDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except HTTPException:
        raise
    except Exception:
        logger.exception("print_lab_results failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ ПРИНТЕРАМИ =====================


@router.get("/printers", response_model=dict[str, Any])
def get_printers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Получить список доступных принтеров
    """
    try:
        # Сначала синхронизируем локальные системные принтеры, чтобы UI видел
        # реальные установленные устройства, а не только seed/mock записи.
        synced_printers = asyncio.run(print_service.sync_system_printers())
        printers = crud_print.get_printer_configs(db, active_only=True)
        local_printer_types = {
            printer.printer_type
            for printer in printers
            if printer.connection_type != "mock"
        }
        if local_printer_types:
            printers = [
                printer
                for printer in printers
                if printer.connection_type != "mock"
                or printer.printer_type not in local_printer_types
            ]
        printer_items = []

        for printer in printers:
            status_data = print_service.get_printer_status(printer.name)
            printer_items.append(
                {
                    "id": printer.id,
                    "name": printer.name,
                    "display_name": printer.display_name,
                    "printer_type": printer.printer_type,
                    "connection_type": printer.connection_type,
                    "is_default": printer.is_default,
                    "status": status_data.get("status", "unknown"),
                }
            )

        logger.info(
            "[FIX] Loaded %s printers from database (%s synced local printers)",
            len(printer_items),
            len(synced_printers),
        )
        return {"printers": printer_items, "total": len(printer_items)}

    except Exception as e:
        logger.error("[FIX] Failed to load printers from database: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/printers/{printer_name}/status", response_model=dict[str, Any])
def get_printer_status(
    printer_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Проверить статус принтера
    """
    try:
        status = print_service.get_printer_status(printer_name)

        return {
            "printer_name": printer_name,
            "timestamp": datetime.now().isoformat(),
            **status,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/printers/{printer_name}/test", response_model=dict[str, Any])
def test_printer(
    printer_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Тестовая печать
    """
    try:
        result = print_service.test_print(printer_name)

        return {
            "printer_name": printer_name,
            "test_time": datetime.now().isoformat(),
            **result,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/queue-ticket", response_model=PrintResponse)
async def quick_print_ticket(
    request: QuickTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Быстрая печать талона очереди
    """
    ticket_request = PrintTicketRequest(
        clinic_name="МЕДИЦИНСКАЯ КЛИНИКА",  # Получать из настроек
        queue_number=request.queue_number,
        doctor_name=request.doctor_name,
        specialty_name=request.specialty,
        cabinet=request.cabinet,
        patient_name=request.patient_name,
        source=request.source,
        time_window="07:00 - 18:00",  # Получать из настроек очереди
    )

    return await print_queue_ticket(ticket_request, db, current_user, print_service)


@router.post("/quick/payment-receipt", response_model=PrintResponse)
async def quick_print_receipt(
    request: QuickReceiptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service),
):
    """
    Быстрая печать чека об оплате
    """
    receipt_request = PrintReceiptRequest(
        clinic={"name": "МЕДИЦИНСКАЯ КЛИНИКА"},
        patient={"full_name": request.patient_name},
        payment={
            "total": request.total_amount,
            "method": request.payment_method,
            "method_name": {
                "cash": "Наличные",
                "card": "Банковская карта",
                "payme": "PayMe",
                "click": "Click",
            }.get(request.payment_method, request.payment_method),
            "status": "completed",
        },
        services=request.services,
    )

    return await print_payment_receipt(receipt_request, db, current_user, print_service)
