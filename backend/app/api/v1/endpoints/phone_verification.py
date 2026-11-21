"""
API endpoints для верификации телефонных номеров
"""

import re
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, require_roles
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_phone_scope import (
    PatientPhoneScopeConflict,
    acquire_phone_scope_lock,
    verified_phone_candidates,
)
from app.services.phone_verification_service import get_phone_verification_service
from app.services.phone_verification_store import PhoneStoreUnavailable
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_patient_scope,
    check_profile_bearer,
    enforce_phone_scope,
    lock_profile,
    lock_profile_users,
    prepare_phone_change,
)
from app.services.sms_providers import SMSProviderType
from app.services.token_blacklist_service import revoke_account_sessions_locked

router = APIRouter()


class SendVerificationCodeRequest(BaseModel):
    """Запрос на отправку кода верификации"""

    phone: str
    purpose: Literal["verification", "phone_change"] = "verification"
    provider: str | None = None
    custom_message: str | None = Field(
        default=None,
        description="Must be omitted or null for self-service; use the admin endpoint for custom text.",
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Accept familiar formatting, while enforcing ASCII E.164 digits.
        if re.search(r'[^0-9+()\s.\-]', v):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        phone = re.sub(r'[^0-9+]', '', v)
        if not re.fullmatch(r'\+998[0-9]{9}', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')

        return phone

    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        allowed_purposes = [
            'verification',
            'phone_change',
        ]
        if v not in allowed_purposes:
            raise ValueError(
                f'Цель должна быть одной из: {", ".join(allowed_purposes)}'
            )
        return v


class VerifyCodeRequest(BaseModel):
    """Запрос на проверку кода верификации"""

    phone: str
    code: str
    purpose: Literal["verification", "phone_change"] = "verification"

    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        return SendVerificationCodeRequest.validate_purpose(v)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return SendVerificationCodeRequest.validate_phone(v)

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.fullmatch(r'[0-9]{6}', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


class UpdatePhoneRequest(BaseModel):
    """Запрос на обновление номера телефона"""

    new_phone: str
    verification_code: str

    @field_validator('new_phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return SendVerificationCodeRequest.validate_phone(v)

    @field_validator('verification_code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.fullmatch(r'[0-9]{6}', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


class PhoneVerificationScope(BaseModel):
    """Phone and purpose belong in the request body, never in a URL."""

    phone: str
    purpose: Literal["verification", "phone_change"] = "verification"

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return SendVerificationCodeRequest.validate_phone(v)

    @field_validator('purpose')
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        return SendVerificationCodeRequest.validate_purpose(v)


class AdminSendCodeRequest(PhoneVerificationScope):
    provider: str | None = None
    message: str | None = None


class PhoneVerificationSendResponse(BaseModel):
    success: Literal[True]
    message: str
    expires_in_minutes: int
    expires_in_seconds: int
    provider: str | None


class AdminPhoneVerificationSendResponse(PhoneVerificationSendResponse):
    phone: str
    purpose: str
    sent_by_admin: str


class PhoneVerificationProofResponse(BaseModel):
    success: Literal[True]
    message: str
    phone: str
    verified_at: str


class PhoneVerificationUpdateResponse(PhoneVerificationProofResponse):
    sessions_revoked: bool


class PhoneVerificationCancelResponse(BaseModel):
    success: Literal[True]
    message: str


class PhoneVerificationStatusResponse(BaseModel):
    exists: bool
    verified: bool
    phone: str | None = None
    purpose: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    attempts: int | None = None
    max_attempts: int | None = None
    time_left_minutes: int | None = None


class PhoneVerificationFailure(BaseModel):
    success: Literal[False]
    error: str
    error_code: str | None = None
    attempts_left: int | None = None


class PhoneVerificationErrorResponse(BaseModel):
    detail: str | PhoneVerificationFailure


class PhoneVerificationValidationResponse(BaseModel):
    error: str
    message: str
    detail: list[dict[str, Any]]


class PhoneVerificationRateLimitResponse(BaseModel):
    error: str


class PhoneVerificationSettings(BaseModel):
    code_length: int
    ttl_minutes: int
    max_attempts: int
    rate_limit_minutes: int


class PhoneVerificationStatistics(BaseModel):
    total_active_codes: int
    verified_codes: int
    pending_codes: int
    expiring_soon: int
    by_purpose: dict[str, int]
    by_provider: dict[str, int]
    settings: PhoneVerificationSettings


class PhoneVerificationStatisticsResponse(BaseModel):
    statistics: PhoneVerificationStatistics
    timestamp: str


_NO_STORE_RESPONSE = {
    "headers": {"Cache-Control": {"description": "Sensitive response is not cacheable", "schema": {"type": "string"}}}
}


def _phone_error_responses(*codes: int) -> dict[int, dict[str, Any]]:
    # 401, 403 and 429 may be produced by a dependency or middleware before
    # the endpoint sets headers; do not promise no-store for those responses.
    result: dict[int, dict[str, Any]] = {
        code: {"model": (PhoneVerificationErrorResponse | PhoneVerificationRateLimitResponse)
               if code == 429 else PhoneVerificationErrorResponse,
               "description": "Request rejected"}
        for code in codes
    }
    result[422] = {"model": PhoneVerificationValidationResponse, "description": "Invalid verification request"}
    return result


def _capture_actor(request: Request, user: User):
    context = capture_profile_bearer(request, user)
    # A code must be attributable to a revocable, time-limited session.
    if not context.jti or context.expires_at is None:
        raise ProfileBearerInvalid("Bearer session unavailable")
    return context


def _store_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503, detail="Сервис проверки телефона временно недоступен",
        headers={"Cache-Control": "no-store"},
    )


def _locked_actor(db: Session, context, *, check_scope: bool = True):
    actor, _ = lock_profile_users(db, context.user_id, context.user_id)
    check_profile_bearer(db, actor, context)
    if check_scope:
        check_patient_scope(db, actor, context)
    return actor


def _is_admin(user: User) -> bool:
    """Match the admin routes' canonical role check, including superuser."""
    role = getattr(user.role, "value", user.role)
    return bool(user.is_superuser) or (
        isinstance(role, str) and role.casefold() in {"admin", "superadmin"}
    )


def _actor_call(db: Session, context, operation):
    """Serialize short storage operations against account revocation."""
    try:
        actor = _locked_actor(db, context)
        result = operation(actor)
        check_bearer_expiry(context)
        db.rollback()  # no profile mutation; release User lock
        return result
    except Exception:
        db.rollback()
        raise


def _phone_update(db: Session, context, phone: str, code: str) -> dict[str, Any]:
    """Consume a session-bound code and commit the verified profile update."""
    try:
        actor = _locked_actor(db, context, check_scope=False)
        profile = lock_profile(db, actor.id)
        if profile is None:
            profile = UserProfile(user_id=actor.id, full_name=actor.full_name)
            db.add(profile)
            db.flush()

        update = {"phone": phone}
        changed = prepare_phone_change(db, profile, update)
        # The transition unverified -> verified requires the same destination
        # lock even when the normalized number did not otherwise change.
        acquire_phone_scope_lock(db, update["phone"])
        check_patient_scope(db, actor, context)
        check_bearer_expiry(context)
        result = get_phone_verification_service().verify_code(
            phone=update["phone"], code=code, purpose="phone_change",
            actor_id=actor.id, actor_epoch=context.auth_epoch,
            actor_jti=context.jti, allow_admin=False,
        )
        if not result.get("success"):
            db.rollback()
            return result
        # The OTP was consumed by the store.  On any later failure it remains
        # consumed; requesting a new code is safer than reviving a used proof.
        # Check conflicts only after possession is proven: otherwise a caller
        # could enumerate verified phone numbers with arbitrary codes.
        enforce_phone_scope(db, actor, update)
        # The shared resolver accounts for formatted and Unicode-digit legacy
        # profiles.  A scan limit is indeterminate, never a free phone.
        matches = verified_phone_candidates(db, update["phone"], exclude_user_id=actor.id)
        if matches is None:
            raise PhoneStoreUnavailable("Verified phone check unavailable")
        if matches:
            raise PatientPhoneScopeConflict()
        if changed:
            revoke_account_sessions_locked(db, actor, revoke_password_resets=True)
        profile.phone = update["phone"]
        profile.phone_verified = True
        check_bearer_expiry(context)
        db.commit()
        return {
            "success": True,
            "message": "Номер телефона успешно обновлен и подтвержден",
            "phone": update["phone"],
            "verified_at": result.get("verified_at") or datetime.now(UTC).isoformat(),
            "sessions_revoked": changed,
        }
    except Exception:
        db.rollback()
        raise


@router.post("/send-code", response_model=PhoneVerificationSendResponse,
             responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(400, 401, 429, 500, 502, 503)})
@limiter.limit("5/minute")  # P1-1: rate limit
async def send_verification_code(request: Request,
    request_data: SendVerificationCodeRequest, response: Response,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Отправка кода верификации"""
    try:
        context = _capture_actor(request, current_user)
        if request_data.custom_message is not None:
            raise HTTPException(status_code=400, detail="Используйте административный путь для своего текста")
        await run_in_threadpool(_actor_call, db, context, lambda actor: None)
        verification_service = get_phone_verification_service()

        # Определяем провайдера SMS
        provider_type = None
        if request_data.provider:
            try:
                provider_type = SMSProviderType(request_data.provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неподдерживаемый SMS провайдер",
                )

        # Отправляем код
        result = await verification_service.send_verification_code(
            phone=request_data.phone,
            purpose=request_data.purpose,
            provider_type=provider_type,
            custom_message=None,
            owner_binding=(context.user_id, context.auth_epoch, context.jti),
        )

        if result["success"]:
            # Do not hold a database lock during delivery.  The code itself
            # remains bound to this exact epoch and JTI if revocation races.
            await run_in_threadpool(_actor_call, db, context, lambda actor: None)
            response.headers["Cache-Control"] = "no-store"
            return {
                "success": True,
                "message": result["message"],
                "expires_in_minutes": result["expires_in_minutes"],
                "expires_in_seconds": result["expires_in_seconds"],
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

    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )


@router.post("/verify-code", response_model=PhoneVerificationProofResponse,
             responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(400, 401, 404, 410, 429, 500, 503)})
@limiter.limit("5/minute")
async def verify_code(
    request: Request, request_data: VerifyCodeRequest, response: Response,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Проверка кода верификации"""
    try:
        verification_service = get_phone_verification_service()

        context = _capture_actor(request, current_user)
        result = await run_in_threadpool(
            _actor_call, db, context,
            lambda actor: verification_service.verify_code(
                phone=request_data.phone, code=request_data.code,
                purpose=request_data.purpose, actor_id=actor.id,
                actor_epoch=context.auth_epoch, actor_jti=context.jti,
                allow_admin=_is_admin(actor),
            ),
        )

        if result["success"]:
            response.headers["Cache-Control"] = "no-store"
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

    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )


@router.post("/status", response_model=PhoneVerificationStatusResponse,
             response_model_exclude_unset=True,
             responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(401, 500, 503)})
async def get_verification_status(
    request: Request, request_data: PhoneVerificationScope, response: Response,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Получение статуса верификации"""
    try:
        verification_service = get_phone_verification_service()
        context = _capture_actor(request, current_user)
        status_info = await run_in_threadpool(
            _actor_call, db, context,
            lambda actor: verification_service.get_verification_status(
                request_data.phone, request_data.purpose, actor_id=actor.id,
                actor_epoch=context.auth_epoch, actor_jti=context.jti,
                allow_admin=_is_admin(actor),
            ),
        )
        response.headers["Cache-Control"] = "no-store"
        return status_info

    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )


@router.post("/cancel", response_model=PhoneVerificationCancelResponse,
             responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(401, 404, 500, 503)})
async def cancel_verification(
    request: Request, request_data: PhoneVerificationScope, response: Response,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Отмена верификации"""
    try:
        verification_service = get_phone_verification_service()
        context = _capture_actor(request, current_user)
        success = await run_in_threadpool(
            _actor_call, db, context,
            lambda actor: verification_service.cancel_verification(
                request_data.phone, request_data.purpose, actor_id=actor.id,
                actor_epoch=context.auth_epoch, actor_jti=context.jti,
                allow_admin=_is_admin(actor),
            ),
        )

        if success:
            response.headers["Cache-Control"] = "no-store"
            return {"success": True, "message": "Верификация отменена"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Активная верификация не найдена",
            )

    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )


@router.put("/update-phone", response_model=PhoneVerificationUpdateResponse,
            responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(400, 401, 404, 409, 429, 500, 503)})
@limiter.limit("5/minute")
async def update_user_phone(
    request: Request,
    request_data: UpdatePhoneRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление номера телефона пользователя"""
    try:
        context = _capture_actor(request, current_user)
        result = await run_in_threadpool(
            _phone_update, db, context, request_data.new_phone, request_data.verification_code,
        )

        if result["success"]:
            response.headers["Cache-Control"] = "no-store"
            return {
                "success": True,
                "message": result["message"],
                "phone": result["phone"],
                "verified_at": result["verified_at"],
                "sessions_revoked": result["sessions_revoked"],
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "CODE_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "MAX_ATTEMPTS_EXCEEDED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "PHONE_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            elif result.get("error_code") == "USER_UPDATE_FAILED":
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            raise HTTPException(status_code=status_code, detail=result["error"])

    except PatientPhoneScopeConflict as exc:
        raise HTTPException(status_code=409, detail="Номер телефона недоступен", headers={"Cache-Control": "no-store"}) from exc
    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )


@router.get("/statistics", response_model=PhoneVerificationStatisticsResponse,
            responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(401, 403, 500, 503)})
async def get_verification_statistics(
    request: Request, response: Response,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Статистика верификаций (только для администраторов)"""
    try:
        verification_service = get_phone_verification_service()
        context = _capture_actor(request, current_user)

        if not await run_in_threadpool(_actor_call, db, context, _is_admin):
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        # A scan can take longer than a single Redis operation.  Release the
        # account lock and revalidate the session and role before returning it.
        stats = await run_in_threadpool(verification_service.get_statistics)
        if not await run_in_threadpool(_actor_call, db, context, _is_admin):
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        response.headers["Cache-Control"] = "no-store"
        return {"statistics": stats, "timestamp": datetime.now().isoformat()}

    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )


@router.post("/admin/send-code", response_model=AdminPhoneVerificationSendResponse,
             responses={200: _NO_STORE_RESPONSE, **_phone_error_responses(400, 401, 403, 429, 500, 502, 503)})
@limiter.limit("5/minute")
async def admin_send_verification_code(
    request: Request,
    request_data: AdminSendCodeRequest,
    response: Response,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отправка кода верификации администратором"""
    try:
        context = _capture_actor(request, current_user)
        if not await run_in_threadpool(_actor_call, db, context, _is_admin):
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        verification_service = get_phone_verification_service()

        # Определяем провайдера SMS
        provider_type = None
        if request_data.provider:
            try:
                provider_type = SMSProviderType(request_data.provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неподдерживаемый SMS провайдер",
                )

        # Отправляем код
        result = await verification_service.send_verification_code(
            phone=request_data.phone,
            purpose=request_data.purpose,
            provider_type=provider_type,
            custom_message=request_data.message,
            owner_binding=(context.user_id, context.auth_epoch, context.jti),
        )

        if result["success"]:
            admin_info = await run_in_threadpool(
                _actor_call, db, context, lambda actor: (_is_admin(actor), actor.username),
            )
            if not admin_info[0]:
                raise HTTPException(status_code=403, detail="Недостаточно прав")
            response.headers["Cache-Control"] = "no-store"
            return {
                "success": True,
                "message": result["message"],
                "phone": request_data.phone,
                "purpose": request_data.purpose,
                "expires_in_minutes": result["expires_in_minutes"],
                "expires_in_seconds": result["expires_in_seconds"],
                "provider": result.get("provider"),
                "sent_by_admin": admin_info[1],
            }
        else:
            error_code = result.get("error_code")
            if error_code == "INVALID_CUSTOM_MESSAGE":
                result_status = status.HTTP_400_BAD_REQUEST
            elif error_code == "RATE_LIMITED":
                result_status = status.HTTP_429_TOO_MANY_REQUESTS
            else:
                result_status = status.HTTP_502_BAD_GATEWAY
            raise HTTPException(
                status_code=result_status,
                detail=result["error"],
            )

    except PhoneStoreUnavailable as exc:
        raise _store_unavailable() from exc
    except ProfileBearerInvalid as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable", headers={"Cache-Control": "no-store"}) from exc
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
            headers={"Cache-Control": "no-store"},
        )
