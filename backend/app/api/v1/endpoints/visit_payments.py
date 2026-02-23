# app/api/v1/endpoints/visit_payments.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.visit_payment_api_service import (
    VisitPaymentApiDomainError,
    VisitPaymentApiService,
)

router = APIRouter()


@router.get("/visit-payments/{visit_id}", summary="Информация о платеже для визита")
def get_visit_payment_info(
    visit_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Получение информации о платеже для конкретного визита"""
    service = VisitPaymentApiService(db)
    try:
        return service.get_visit_payment_info(visit_id=visit_id)
    except VisitPaymentApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о платеже: {str(e)}",
        )


@router.get(
    "/visit-payments/by-status/{payment_status}", summary="Визиты по статусу платежа"
)
def get_visits_by_payment_status(
    payment_status: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin", "Registrar")),
):
    """Получение списка визитов по статусу платежа"""
    service = VisitPaymentApiService(db)
    try:
        return service.get_visits_by_payment_status(
            payment_status=payment_status,
            limit=limit,
            offset=offset,
        )
    except VisitPaymentApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения визитов: {str(e)}",
        )


@router.post(
    "/visit-payments/{visit_id}/update-status", summary="Обновление статуса платежа"
)
def update_visit_payment_status(
    visit_id: int,
    payment_status: str = Query(..., description="Новый статус платежа"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin", "Registrar")),
):
    """Обновление статуса платежа для визита"""
    service = VisitPaymentApiService(db)
    try:
        return service.update_visit_payment_status(
            visit_id=visit_id,
            payment_status=payment_status,
        )
    except VisitPaymentApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления статуса платежа: {str(e)}",
        )


@router.get("/visit-payments/summary", summary="Сводка по платежам визитов")
def get_visit_payments_summary(
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin", "Registrar")),
):
    """Получение сводки по платежам визитов"""
    service = VisitPaymentApiService(db)
    try:
        return service.get_visit_payments_summary()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сводки: {str(e)}",
        )


@router.post(
    "/visit-payments/{visit_id}/create-from-payment",
    summary="Создание визита из платежа",
)
def create_visit_from_payment(
    visit_id: int,
    patient_id: Optional[int] = Query(None, description="ID пациента"),
    doctor_id: Optional[int] = Query(None, description="ID врача"),
    notes: Optional[str] = Query(None, description="Заметки к визиту"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin", "Registrar")),
):
    """Создание визита на основе существующего платежа"""
    service = VisitPaymentApiService(db)
    try:
        return service.create_visit_from_payment(
            visit_id=visit_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            notes=notes,
        )
    except VisitPaymentApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания визита: {str(e)}",
        )
