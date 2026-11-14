"""
API endpoints для верификации телефонных номеров
"""

import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.services.phone_verification_service import get_phone_verification_service
from app.services.sms_providers import SMSProviderType

router = APIRouter()

# SECURITY (PHONEVER-BE-001/002, #4063): self-service surface is scoped to the
# two purposes a user legitimately drives themselves. password_reset belongs to
# the dedicated unauthenticated /password-reset/initiate flow (its own 3/minute
# gate); registration has no authenticated caller.
ALLOWED_SELF_PURPOSES = ("verification", "phone_change")


class SendVerificationCodeRequest(BaseModel):
    """Запрос на отправку кода верификации"""

    phone: str
    purpose: str = "verification"
    provider: str | None = None
    custom_message: str | None = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Удаляем все символы кроме цифр и +
        phone = re.sub(r'[^\d+]', '', v)

        # Проверяем формат
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')

        return phone

    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        # SECURITY (PHONEVER-BE-001, #4063): password_reset удалён из
        # аутентифицированной поверхности — коды сброса чеканит только
        # /password-reset/initiate со своим лимитом 3/minute; registration —
        # неаутентифицированный флоу.
        allowed_purposes = list(ALLOWED_SELF_PURPOSES)
        if v not in allowed_purposes:
            raise ValueError(
                f'Цель должна быть одной из: {", ".join(allowed_purposes)}'
            )
        return v


class VerifyCodeRequest(BaseModel):
    """Запрос на проверку кода верификации"""

    phone: str
    code: str
    purpose: str = "verification"

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r'[^\d+]', '', v)
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


class UpdatePhoneRequest(BaseModel):
    """Запрос на обновление номера телефона"""

    new_phone: str
    verification_code: str

    @field_validator('new_phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r'[^\d+]', '', v)
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone

    @field_validator('verification_code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


@router.post("/send-code", response_model=dict[str, Any])
@limiter.limit("5/minute")  # P1-1: rate limit
async def send_verification_code(
    request: Request,
    request_data: SendVerificationCodeRequest,
    current_user: User = Depends(get_current_user),
):
    """Отправка кода верификации"""
    try:
        verification_service = get_phone_verification_service()

        # SECURITY (PHONEVER-BE-001, #4063): произвольный текст SMS под
        # sender-идентичностью клиники недоступен обычным пользователям —
        # шаблоны сервиса фиксированы; кастомное сообщение — только
        # администраторам через /admin/send-code.
        if request_data.custom_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Кастомное сообщение SMS доступно только администраторам (используйте /admin/send-code).",
            )

        # Определяем провайдера SMS
        provider_type = None
        if request_data.provider:
            try:
                provider_type = SMSProviderType(request_data.provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неподдерживаемый SMS провайдер: {request_data.provider}",
                )

        # Отправляем код; SECURITY (PHONEVER-BE-001/002, #4063): запись
        # привязывается к запросившему пользователю для ownership-проверок
        # в status/cancel/verify.
        result = await verification_service.send_verification_code(
            phone=request_data.phone,
            purpose=request_data.purpose,
            provider_type=provider_type,
            custom_message=None,
            user_id=current_user.id,
        )

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "expires_in_minutes": result["expires_in_minutes"],
                "provider": result.get("provider"),
            }
        else:
            # Определяем HTTP статус код по типу ошибки
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if result.get("error_code") == "RATE_LIMITED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "SMS_SEND_FAILED":
                status_code = status.HTTP_502_BAD_GATEWAY

            raise HTTPException(status_code=status_code, detail=result["error"])

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/verify-code", response_model=dict[str, Any])
@limiter.limit("5/minute")  # SECURITY (PHONEVER-BE-003, #4063): паритет с /send-code
async def verify_code(
    request: Request,
    request_data: VerifyCodeRequest,
    current_user: User = Depends(get_current_user),
):
    """Проверка кода верификации"""
    try:
        verification_service = get_phone_verification_service()

        # SECURITY (PHONEVER-BE-002, #4063): чужая (или незнакомая purpose)
        # запись неотличима от отсутствующей — ни успеха, ни attempts_left.
        if request_data.purpose not in ALLOWED_SELF_PURPOSES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": "Код не найден или истек",
                    "error_code": "CODE_NOT_FOUND",
                },
            )
        record_owner = verification_service.get_record_user_id(
            request_data.phone, request_data.purpose
        )
        if (
            record_owner is not None
            and record_owner != current_user.id
            and current_user.role not in ("Admin", "SuperAdmin")
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": "Код не найден или истек",
                    "error_code": "CODE_NOT_FOUND",
                },
            )

        result = verification_service.verify_code(
            phone=request_data.phone,
            code=request_data.code,
            purpose=request_data.purpose,
        )

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "phone": result["phone"],
                "verified_at": result["verified_at"],
            }
        else:
            # Определяем HTTP статус код по типу ошибки
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "CODE_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "CODE_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "MAX_ATTEMPTS_EXCEEDED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS

            response_data = {
                "success": False,
                "error": result["error"],
                "error_code": result.get("error_code"),
            }

            # Добавляем информацию об оставшихся попытках
            if "attempts_left" in result:
                response_data["attempts_left"] = result["attempts_left"]

            raise HTTPException(status_code=status_code, detail=response_data)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/status", response_model=dict[str, Any])
async def get_verification_status(
    phone: str = Query(..., description="Номер телефона в формате +998XXXXXXXXX"),
    purpose: str = Query("verification", description="Цель верификации"),
    current_user: User = Depends(get_current_user),
):
    """Получение статуса верификации"""
    try:
        # Валидация номера телефона
        phone = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^\+998\d{9}$', phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Номер телефона должен быть в формате +998XXXXXXXXX",
            )

        verification_service = get_phone_verification_service()

        # SECURITY (PHONEVER-BE-002, #4063): статус чужой записи (или
        # незнакомой purpose) неотличим от отсутствующей — оракул закрыт.
        if purpose not in ALLOWED_SELF_PURPOSES:
            return {"exists": False, "verified": False}
        record_owner = verification_service.get_record_user_id(phone, purpose)
        if (
            record_owner is not None
            and record_owner != current_user.id
            and current_user.role not in ("Admin", "SuperAdmin")
        ):
            return {"exists": False, "verified": False}

        status_info = verification_service.get_verification_status(phone, purpose)

        return status_info

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/cancel", response_model=dict[str, Any])
async def cancel_verification(
    phone: str = Query(..., description="Номер телефона в формате +998XXXXXXXXX"),
    purpose: str = Query("verification", description="Цель верификации"),
    current_user: User = Depends(get_current_user),
):
    """Отмена верификации"""
    try:
        # Валидация номера телефона
        phone = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^\+998\d{9}$', phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Номер телефона должен быть в формате +998XXXXXXXXX",
            )

        verification_service = get_phone_verification_service()

        # SECURITY (PHONEVER-BE-002, #4063): чужая (или незнакомая purpose)
        # запись не отменяется и отвечает так же, как отсутствующая (404).
        if purpose not in ALLOWED_SELF_PURPOSES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Активная верификация не найдена",
            )
        record_owner = verification_service.get_record_user_id(phone, purpose)
        if (
            record_owner is not None
            and record_owner != current_user.id
            and current_user.role not in ("Admin", "SuperAdmin")
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Активная верификация не найдена",
            )

        success = verification_service.cancel_verification(phone, purpose)

        if success:
            return {"success": True, "message": "Верификация отменена"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Активная верификация не найдена",
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/update-phone", response_model=dict[str, Any])
async def update_user_phone(
    request_data: UpdatePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление номера телефона пользователя"""
    try:
        verification_service = get_phone_verification_service()

        result = await verification_service.verify_and_update_user_phone(
            db=db,
            user_id=current_user.id,
            phone=request_data.new_phone,
            code=request_data.verification_code,
            purpose="phone_change",
        )

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "phone": result["phone"],
                "verified_at": result["verified_at"],
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "PHONE_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            elif result.get("error_code") == "USER_UPDATE_FAILED":
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            raise HTTPException(status_code=status_code, detail=result["error"])

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/statistics", response_model=dict[str, Any])
async def get_verification_statistics(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Статистика верификаций (только для администраторов)"""
    try:
        verification_service = get_phone_verification_service()

        stats = verification_service.get_statistics()

        return {"statistics": stats, "timestamp": datetime.now().isoformat()}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/admin/send-code", response_model=dict[str, Any])
async def admin_send_verification_code(
    phone: str = Query(..., description="Номер телефона в формате +998XXXXXXXXX"),
    purpose: str = Query("verification", description="Цель верификации"),
    provider: str | None = Query(None, description="SMS провайдер"),
    message: str | None = Query(None, description="Кастомное сообщение с {code}"),
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
):
    """Отправка кода верификации администратором"""
    try:
        # Валидация номера телефона
        phone = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^\+998\d{9}$', phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Номер телефона должен быть в формате +998XXXXXXXXX",
            )

        verification_service = get_phone_verification_service()

        # Определяем провайдера SMS
        provider_type = None
        if provider:
            try:
                provider_type = SMSProviderType(provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неподдерживаемый SMS провайдер: {provider}",
                )

        # Отправляем код
        result = await verification_service.send_verification_code(
            phone=phone,
            purpose=purpose,
            provider_type=provider_type,
            custom_message=message,
        )

        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "phone": phone,
                "purpose": purpose,
                "expires_in_minutes": result["expires_in_minutes"],
                "provider": result.get("provider"),
                "sent_by_admin": current_user.username,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"],
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
