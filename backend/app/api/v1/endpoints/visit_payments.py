# app/api/v1/endpoints/visit_payments.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.visit_payment_integration import VisitPaymentIntegrationService

router = APIRouter()


@router.get("/visit-payments/{visit_id}", summary="Информация о платеже для визита")
def get_visit_payment_info(
    visit_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Получение информации о платеже для конкретного визита"""
    try:
        success, message, payment_info = (
            VisitPaymentIntegrationService.get_visit_payment_info(db, visit_id)
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

        return {"success": True, "message": message, "payment_info": payment_info}

    except HTTPException:
        raise
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
    try:
        success, message, visits = (
            VisitPaymentIntegrationService.get_visits_by_payment_status(
                db, payment_status, limit, offset
            )
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return {
            "success": True,
            "message": message,
            "payment_status": payment_status,
            "visits": visits,
            "total": len(visits),
            "limit": limit,
            "offset": offset,
        }

    except HTTPException:
        raise
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
    try:
        # Валидация статуса
        valid_statuses = ["unpaid", "pending", "paid", "failed", "refunded"]
        if payment_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неверный статус платежа. Допустимые значения: {', '.join(valid_statuses)}",
            )

        success, message = VisitPaymentIntegrationService.update_visit_payment_status(
            db, visit_id, payment_status
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return {
            "success": True,
            "message": message,
            "visit_id": visit_id,
            "new_payment_status": payment_status,
        }

    except HTTPException:
        raise
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
    try:
        # Получаем статистику по разным статусам
        statuses = ["unpaid", "pending", "paid", "failed", "refunded"]
        summary = {}

        for status in statuses:
            success, message, visits = (
                VisitPaymentIntegrationService.get_visits_by_payment_status(
                    db, status, limit=1000, offset=0
                )
            )

            if success:
                summary[status] = {
                    "count": len(visits),
                    "total_amount": sum(
                        float(v.get("payment_amount", 0))
                        for v in visits
                        if v.get("payment_amount")
                    ),
                }
            else:
                summary[status] = {"count": 0, "total_amount": 0}

        # Общая статистика
        total_visits = sum(summary[s]["count"] for s in summary)
        total_paid_amount = summary.get("paid", {}).get("total_amount", 0)
        total_pending_amount = summary.get("pending", {}).get("total_amount", 0)

        return {
            "success": True,
            "summary": summary,
            "total_visits": total_visits,
            "total_paid_amount": total_paid_amount,
            "total_pending_amount": total_pending_amount,
            "payment_success_rate": (
                summary.get("paid", {}).get("count", 0) / max(total_visits, 1)
            )
            * 100,
        }

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
    try:
        # Получаем вебхук по ID визита (если есть)
        # Здесь нужно будет добавить логику поиска вебхука
        # Пока что создаём визит без вебхука

        # Создаём базовые данные для визита
        visit_data = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "notes": notes or "Визит создан вручную",
            "payment_status": "paid",
        }

        # Обновляем статус платежа для существующего визита
        success, message = VisitPaymentIntegrationService.update_visit_payment_status(
            db, visit_id, "paid", additional_data=visit_data
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return {"success": True, "message": message, "visit_id": visit_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания визита: {str(e)}",
        )
