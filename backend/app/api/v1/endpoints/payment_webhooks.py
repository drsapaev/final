"""
API endpoints для обработки webhook от платежных провайдеров
"""

import json
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.services.notifications import notification_sender_service
from app.services.provider_webhook_service import ProviderWebhookService

router = APIRouter()

MAX_PAYMENT_WEBHOOK_BODY_BYTES = 256 * 1024


async def _read_payment_webhook_json(request: Request) -> dict[str, Any]:
    chunks: list[bytes] = []
    total_size = 0

    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > MAX_PAYMENT_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Payment webhook payload is too large",
            )
        chunks.append(chunk)

    try:
        payload = json.loads(b"".join(chunks).decode("utf-8") or "{}")
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment webhook JSON",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment webhook JSON must be an object",
        )

    return payload


async def _emit_payment_notification_from_webhook_result(
    *,
    db: Session,
    result: dict[str, Any],
    webhook_kind: str,
) -> None:
    payment_id = result.get("payment_id")
    payment_status = str(result.get("payment_status") or "").strip().lower()
    provider = str(result.get("payment_provider") or webhook_kind).strip().lower()

    if not payment_id or payment_status not in {"paid", "failed", "cancelled", "refunded"}:
        return

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment or not payment.visit_id:
        return

    visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
    if not visit:
        return

    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    if not patient or not patient.user_id:
        return

    recipient = (
        db.query(User)
        .filter(User.id == patient.user_id, User.is_active.is_(True))
        .first()
    )
    if not recipient:
        return

    change_type_map = {
        "paid": "paid",
        "failed": "failed",
        "cancelled": "cancelled",
        "refunded": "full_refund",
    }
    title_map = {
        "paid": "Оплата подтверждена",
        "failed": "Платеж не выполнен",
        "cancelled": "Платеж отменен",
        "refunded": "Возврат выполнен",
    }
    message_map = {
        "paid": "Онлайн-платеж успешно обработан.",
        "failed": "Онлайн-платеж не был завершен.",
        "cancelled": "Онлайн-платеж был отменен.",
        "refunded": "По вашему платежу выполнен возврат.",
    }

    await notification_sender_service.send_canonical_notification_to_user(
        db=db,
        recipient=recipient,
        event_type="payment_notification",
        title=title_map[payment_status],
        message=message_map[payment_status],
        source_module="payments_webhook",
        metadata={
            "payment_id": payment.id,
            "visit_id": payment.visit_id,
            "patient_id": patient.id,
            "payment_status": payment_status,
            "change_type": change_type_map[payment_status],
            "provider": provider,
            "webhook_kind": webhook_kind,
        },
        deep_link="/patient",
        severity="warning" if payment_status in {"failed", "cancelled", "refunded"} else "info",
        priority="high" if payment_status in {"failed", "cancelled", "refunded"} else "normal",
        entity_type="payment",
        entity_id=str(payment.id),
    )


def _strip_internal_payment_fields(result: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(result or {})
    sanitized.pop("payment_id", None)
    sanitized.pop("payment_status", None)
    sanitized.pop("payment_provider", None)
    return sanitized


@router.post("/click", response_model=dict[str, Any])
async def click_webhook(
    request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Webhook для Click платежной системы"""
    webhook_data = await _read_payment_webhook_json(request)
    result = ProviderWebhookService(db).process_click_webhook(webhook_data)
    await _emit_payment_notification_from_webhook_result(
        db=db,
        result=result,
        webhook_kind="click",
    )
    return _strip_internal_payment_fields(result)


@router.post("/payme", response_model=dict[str, Any])
async def payme_webhook(
    request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Webhook для Payme платежной системы (JSON-RPC)"""
    webhook_data = await _read_payment_webhook_json(request)
    auth_header = request.headers.get("Authorization")
    result = ProviderWebhookService(db).process_payme_webhook(webhook_data, auth_header)
    await _emit_payment_notification_from_webhook_result(
        db=db,
        result=result,
        webhook_kind="payme",
    )
    return _strip_internal_payment_fields(result)


@router.post("/kaspi", response_model=dict[str, Any])
async def kaspi_webhook(
    request: Request, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Webhook для Kaspi Pay платежной системы"""
    webhook_data = await _read_payment_webhook_json(request)
    result = ProviderWebhookService(db).process_kaspi_webhook(webhook_data)
    await _emit_payment_notification_from_webhook_result(
        db=db,
        result=result,
        webhook_kind="kaspi",
    )
    return _strip_internal_payment_fields(result)
