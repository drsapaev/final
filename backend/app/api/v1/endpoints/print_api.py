"""
API endpoints для печати документов
Основа: detail.md стр. 3721-3888, passport.md стр. 1925-2063
"""
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.print_service import get_print_service, PrintService
from app.schemas.print_config import (
    PrintTicketRequest, PrintPrescriptionRequest, PrintCertificateRequest,
    PrintReceiptRequest, PrintLabResultsRequest, PrintResponse,
    QuickTicketRequest, QuickReceiptRequest, PrinterStatusResponse,
    PrintersListResponse, TestPrintResponse
)

router = APIRouter()

# ===================== ПЕЧАТЬ ДОКУМЕНТОВ =====================

@router.post("/ticket", response_model=PrintResponse)
async def print_queue_ticket(
    request: PrintTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Печать талона очереди
    """
    try:
        # Дополняем данные талона
        ticket_data = request.dict()
        ticket_data.update({
            "date": datetime.now(),
            "time": datetime.now(),
            "issued_by": current_user.full_name
        })
        
        result = await print_service.print_document(
            document_type="ticket",
            document_data=ticket_data,
            printer_name=request.printer_name,
            user=current_user
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка печати талона: {str(e)}"
        )


@router.post("/prescription", response_model=PrintResponse)
async def print_prescription(
    request: PrintPrescriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Печать рецепта
    """
    try:
        # Дополняем данные рецепта
        prescription_data = request.dict()
        prescription_data.update({
            "prescription": {
                **prescription_data.get("prescription", {}),
                "date": datetime.now(),
                "time": datetime.now(),
                "number": prescription_data.get("prescription", {}).get("number") or f"RX-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            },
            "doctor": {
                "full_name": current_user.full_name,
                "specialty_name": "Врач",  # Получать из профиля врача
                "license_number": "Лицензия"  # Получать из профиля врача
            }
        })
        
        result = await print_service.print_document(
            document_type="prescription",
            document_data=prescription_data,
            printer_name=request.printer_name,
            user=current_user
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка печати рецепта: {str(e)}"
        )


@router.post("/certificate", response_model=PrintResponse)
async def print_medical_certificate(
    request: PrintCertificateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Печать медицинской справки
    """
    try:
        # Дополняем данные справки
        certificate_data = request.dict()
        certificate_data.update({
            "certificate": {
                **certificate_data.get("certificate", {}),
                "issue_date": datetime.now(),
                "number": certificate_data.get("certificate", {}).get("number") or f"CERT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            },
            "doctor": {
                "full_name": current_user.full_name,
                "specialty_name": "Врач",  # Получать из профиля врача
                "license_number": "Лицензия"  # Получать из профиля врача
            }
        })
        
        result = await print_service.print_document(
            document_type="medical_certificate",
            document_data=certificate_data,
            printer_name=request.printer_name,
            user=current_user
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка печати справки: {str(e)}"
        )


@router.post("/receipt", response_model=PrintResponse)
async def print_payment_receipt(
    request: PrintReceiptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Печать чека об оплате
    """
    try:
        # Дополняем данные чека
        payment_data = request.dict()
        payment_data.update({
            "payment": {
                **payment_data.get("payment", {}),
                "date": datetime.now(),
                "time": datetime.now(),
                "number": payment_data.get("payment", {}).get("number") or f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            },
            "cashier": {
                "full_name": current_user.full_name
            }
        })
        
        result = await print_service.print_document(
            document_type="payment_receipt",
            document_data=payment_data,
            printer_name=request.printer_name,
            user=current_user
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка печати чека: {str(e)}"
        )


@router.post("/lab-results", response_model=PrintResponse)
async def print_lab_results(
    request: PrintLabResultsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Печать результатов лабораторных анализов
    """
    try:
        lab_data = request.dict()
        result = await print_service.print_document(
            document_type="lab_results",
            document_data=lab_data,
            printer_name=request.printer_name,
            user=current_user
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка печати результатов анализов: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ ПРИНТЕРАМИ =====================

@router.get("/printers")
def get_printers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Получить список доступных принтеров
    """
    try:
        from app.crud import print_config as crud_print
        
        printers = crud_print.get_printer_configs(db, active_only=True)
        
        # Добавляем статус каждого принтера
        printers_with_status = []
        for printer in printers:
            status = print_service.get_printer_status(printer.name)
            printers_with_status.append({
                "id": printer.id,
                "name": printer.name,
                "display_name": printer.display_name,
                "printer_type": printer.printer_type,
                "connection_type": printer.connection_type,
                "is_default": printer.is_default,
                "status": status
            })
        
        return {
            "printers": printers_with_status,
            "total": len(printers_with_status)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка принтеров: {str(e)}"
        )


@router.get("/printers/{printer_name}/status")
def get_printer_status(
    printer_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Проверить статус принтера
    """
    try:
        status = print_service.get_printer_status(printer_name)
        
        return {
            "printer_name": printer_name,
            "timestamp": datetime.now().isoformat(),
            **status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки статуса принтера: {str(e)}"
        )


@router.post("/printers/{printer_name}/test")
def test_printer(
    printer_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service)
):
    """
    Тестовая печать
    """
    try:
        result = print_service.test_print(printer_name)
        
        return {
            "printer_name": printer_name,
            "test_time": datetime.now().isoformat(),
            **result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестовой печати: {str(e)}"
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================

@router.post("/quick/queue-ticket", response_model=PrintResponse)
async def quick_print_ticket(
    request: QuickTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service)
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
        time_window="07:00 - 18:00"  # Получать из настроек очереди
    )
    
    return await print_queue_ticket(ticket_request, db, current_user, print_service)


@router.post("/quick/payment-receipt", response_model=PrintResponse)
async def quick_print_receipt(
    request: QuickReceiptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    print_service: PrintService = Depends(get_print_service)
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
                "click": "Click"
            }.get(request.payment_method, request.payment_method),
            "status": "completed"
        },
        services=request.services
    )
    
    return await print_payment_receipt(receipt_request, db, current_user, print_service)
