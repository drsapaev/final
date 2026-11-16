"""
API endpoints для SMS/Email двухфакторной аутентификации
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service

router = APIRouter()
logger = logging.getLogger(__name__)


def raise_two_factor_sms_internal_error(
    action: str, public_detail: str, exc: Exception
) -> NoReturn:
    logger.warning(
        "2FA SMS/email endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=public_detail,
    )


class VerificationMethodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["sms", "email"]


class VerifyCodeRequest(VerificationMethodRequest):
    """TWOFACTOR-BE-004 (#4063): the six-digit code rides the BODY, not URL Query.
    This completes the AUTH-REAUDIT-28
    remediation (totp_code/recovery_token moved to body two endpoints over
    in two_factor_auth.py). Query transport put a replayable code and PII
    contacts into intermediary/server logs for the full 300-second validity
    window."""

    code: str = Field(..., pattern=r"^[0-9]{6}$")


async def _send_and_store_code(
    service: Any,
    db: Session,
    user: User,
    method: Literal["sms", "email"],
) -> dict[str, Any]:
    """Deliver to the configured contact, then store only a keyed code hash."""
    contact = service.get_recovery_contact(db=db, user_id=user.id, method=method)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для этого метода не настроен контакт восстановления",
        )
    result = await service.send_verification_code(
        method=method,
        contact=contact,
        user_name=user.username,
    )
    if not result.get("success") or not result.get("code"):
        logger.warning("2FA SMS/email provider send failed method=%s", method)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка отправки {method.upper()}",
        )

    service.save_verification_code(
        db=db,
        user_id=user.id,
        method=method,
        code=result["code"],
        contact=contact,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    masked_contact = _mask_recovery_contact(method, contact)
    return {
        "success": True,
        "message": "Код отправлен на настроенный контакт",
        "method": method,
        "destination": masked_contact,
        "expires_in": 300,
    }


def _mask_recovery_contact(method: str, contact: str) -> str:
    if method == "sms":
        digits = "".join(character for character in contact if character.isdigit())
        return f"••••{digits[-4:]}" if len(digits) >= 4 else "••••"
    local_part, separator, domain = contact.rpartition("@")
    if not separator or not local_part or not domain:
        return "••••"
    return f"{local_part[0]}•••@{domain}"


@router.post("/send-code", response_model=dict[str, Any])
@limiter.limit("5/minute")
async def send_verification_code(
    request: Request,
    request_data: VerificationMethodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a code only to the recovery contact configured for the account."""
    try:
        service = get_two_factor_service()
        if not service.get_recovery_contact(db, current_user.id, request_data.method):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для этого метода не настроен контакт восстановления",
            )
        if not service.can_send_code(db, current_user.id, request_data.method):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Запросите новый код через минуту",
            )
        return await _send_and_store_code(service, db, current_user, request_data.method)
    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_sms_internal_error("send-code", "Ошибка отправки кода", e)


@router.post("/verify-code", response_model=dict[str, Any])
@limiter.limit("10/minute")
async def verify_verification_code(
    request: Request,
    request_data: VerifyCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверить код подтверждения"""
    try:
        service = get_two_factor_service()
        method = request_data.method

        # Проверяем код
        is_valid = service.verify_code(
            db=db, user_id=current_user.id, method=method, code=request_data.code
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный или истекший код",
            )

        return {
            "success": True,
            "message": "Код подтвержден успешно",
            "method": method,
            "verified": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_sms_internal_error("verify-code", "Ошибка проверки кода", e)


@router.get("/verification-status", response_model=dict[str, Any])
async def get_verification_status(
    method: Literal["sms", "email"] = Query(..., description="Метод: sms или email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить статус верификации для метода"""
    try:
        service = get_two_factor_service()

        status = service.get_verification_status(
            db=db, user_id=current_user.id, method=method
        )

        return status

    except Exception as e:
        raise_two_factor_sms_internal_error(
            "verification-status", "Ошибка получения статуса", e
        )


@router.post("/resend-code", response_model=dict[str, Any])
@limiter.limit("3/minute")
async def resend_verification_code(
    request: Request,
    request_data: VerificationMethodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Повторно отправить код подтверждения"""
    try:
        service = get_two_factor_service()
        method = request_data.method
        if not service.get_recovery_contact(db, current_user.id, method):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для этого метода не настроен контакт восстановления",
            )

        # Проверяем, можно ли отправить повторно
        can_resend = service.can_resend_code(
            db=db, user_id=current_user.id, method=method
        )

        if not can_resend:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте позже.",
            )

        return await _send_and_store_code(service, db, current_user, method)

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_sms_internal_error(
            "resend-code", "Ошибка повторной отправки", e
        )


@router.get("/supported-methods", response_model=dict[str, Any])
async def get_supported_methods():
    """Получить список поддерживаемых методов 2FA"""
    return {
        "methods": [
            {
                "id": "totp",
                "name": "Приложение-аутентификатор",
                "description": "Google Authenticator, Authy, Microsoft Authenticator",
                "icon": "smartphone",
                "recommended": True,
            },
            {
                "id": "sms",
                "name": "SMS коды",
                "description": "Коды по SMS на номер телефона",
                "icon": "phone",
                "recommended": False,
            },
            {
                "id": "email",
                "name": "Email коды",
                "description": "Коды на email адрес",
                "icon": "mail",
                "recommended": False,
            },
        ]
    }


@router.get("/security-logs", response_model=dict[str, Any])
async def get_security_logs(
    limit: int = Query(50, description="Количество записей"),
    offset: int = Query(0, description="Смещение"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить журнал безопасности 2FA"""
    try:
        service = get_two_factor_service()

        logs = service.get_security_logs(
            db=db, user_id=current_user.id, limit=limit, offset=offset
        )

        return {"logs": logs, "total": len(logs), "limit": limit, "offset": offset}

    except Exception as e:
        raise_two_factor_sms_internal_error(
            "security-logs", "Ошибка получения журнала", e
        )


@router.get("/recovery-methods", response_model=dict[str, Any])
async def get_recovery_methods(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить методы восстановления"""
    try:
        service = get_two_factor_service()

        methods = service.get_recovery_methods(db=db, user_id=current_user.id)

        return {"methods": methods}

    except Exception as e:
        raise_two_factor_sms_internal_error(
            "recovery-methods", "Ошибка получения методов восстановления", e
        )
