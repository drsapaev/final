"""
API endpoints для двухфакторной аутентификации (2FA)
"""

import logging
from datetime import UTC, datetime
from typing import Any, NoReturn

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.user_token_claims import is_user_access_claims, parse_user_auth_epoch
from app.crud.two_factor_auth import (
    two_factor_auth,
    two_factor_backup_code,
    two_factor_device,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.two_factor_auth import (
    TwoFactorBackupCodesResponse,
    TwoFactorDeviceListResponse,
    TwoFactorDisableRequest,
    TwoFactorRecoveryRequest,
    TwoFactorRecoveryResponse,
    TwoFactorRecoveryVerifyRequest,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    TwoFactorSuccessResponse,
    TwoFactorVerifyRequest,
    TwoFactorVerifyResponse,
    TwoFactorVerifySetupRequest,
)
from app.services.authentication_service import get_authentication_service
from app.services.two_factor_auth_api_service import TwoFactorAuthApiService
from app.services.two_factor_service import (
    BearerSessionInvalid,
    EnrollmentSessionInvalid,
    PendingSessionInvalid,
    TwoFactorAlreadyEnabled,
    get_two_factor_service,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_TWO_FACTOR_ERROR_CONTENT = {
    "application/json": {
        "schema": {
            "type": "object",
            "required": ["detail"],
            "properties": {"detail": {"type": "string"}},
        }
    }
}
_NO_STORE_HEADER = {
    "Cache-Control": {
        "required": True,
        "schema": {"type": "string", "const": "no-store"},
        "description": "Sensitive response must not be cached",
    }
}
_RATE_LIMIT_RESPONSE = {
    "description": "Too many requests from this client",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["detail", "retry_after"],
                "properties": {
                    "detail": {"type": "string"},
                    "retry_after": {"type": ["integer", "null"]},
                },
            }
        }
    },
    "headers": {"Retry-After": {"schema": {"type": "string"}}},
}


def raise_two_factor_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.warning(
        "2FA endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


def get_client_info(request: Request) -> tuple[str, str]:
    """Получить информацию о клиенте"""
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return ip_address, user_agent


def _capture_bearer_context(request: Request, user: User) -> dict[str, Any]:
    """Capture signed bearer claims for a second check under the User lock."""
    scheme, token = get_authorization_scheme_param(request.headers.get("Authorization"))
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Bearer session unavailable")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        epoch = parse_user_auth_epoch(payload)
        if not is_user_access_claims(payload) or epoch is None or epoch != user.auth_epoch:
            raise ValueError("Invalid bearer claims")
        jti = payload.get("jti")
        if jti is not None and not isinstance(jti, str):
            raise ValueError("Invalid bearer identifier")
        raw_exp = payload.get("exp")
        if isinstance(raw_exp, bool):
            raise ValueError("Invalid bearer expiry")
        exp = int(raw_exp) if raw_exp is not None else None
        patient_id = payload.get("patient_id") if payload.get("scope") == "patient_portal" else None
        return {
            "expected_auth_epoch": epoch,
            "expected_jti": jti,
            "expected_exp": exp,
            "expected_patient_id": patient_id,
        }
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from exc


@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_two_factor_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить статус 2FA для текущего пользователя"""
    try:
        service = get_two_factor_service()
        status_data = service.get_two_factor_status(db, current_user.id)
        return TwoFactorStatusResponse(**status_data)
    except Exception as e:
        raise_two_factor_internal_error("getting 2FA status", e)


async def _resolve_user_bearer_or_enrollment(
    request: Request,
    enrollment_token: str | None,
    db: Session,
):
    """Resolve the acting user from a Bearer JWT or an enrollment token.

    Two-stage authentication: a critical-role user whose password verified
    at login holds a single-use server-side '2fa_enrollment' session token
    (NOT a JWT). It is valid ONLY here — business endpoints require JWTs,
    so the enrollment token can never reach them by construction.
    Returns (user, enrollment_token_or_None); (None, None) if unauthorized.
    """
    # An explicitly supplied enrollment token is authoritative, like the
    # pending token on /verify. Never fall back to a different bearer user.
    if enrollment_token is not None:
        user = TwoFactorAuthApiService(db).get_user_from_enrollment_token(
            enrollment_token
        )
        if user and user.is_active:
            return user, enrollment_token
        return None, None

    # Bearer JWT — уже вошедший пользователь управляет своей 2FA
    try:
        from fastapi.security import HTTPBearer

        security = HTTPBearer(auto_error=False)
        token_result = await security(request)
        if token_result and token_result.credentials:
            try:
                return await get_current_user(token_result.credentials, db), None
            except HTTPException:
                pass
    except Exception:
        pass

    return None, None


@router.post(
    "/setup",
    response_model=TwoFactorSetupResponse,
    responses={
        200: {"description": "2FA setup artifacts", "headers": _NO_STORE_HEADER},
        400: {"description": "2FA is already enabled", "content": _TWO_FACTOR_ERROR_CONTENT},
        401: {
            "description": "Authentication or enrollment session invalid",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        500: {"description": "Internal error", "content": _TWO_FACTOR_ERROR_CONTENT},
    },
)
async def setup_two_factor_auth(
    request_data: TwoFactorSetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Настроить 2FA для текущего пользователя.

    Авторизация: Bearer JWT (уже вошедший) ИЛИ одноразовый
    enrollment_token из login-ответа (двухстадийная аутентификация
    для критичных ролей без 2FA).
    """
    try:
        current_user, enrollment_token = await _resolve_user_bearer_or_enrollment(
            request, request_data.enrollment_token, db
        )
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide a Bearer token or a valid enrollment_token",
            )

        service = get_two_factor_service()
        bearer_context = _capture_bearer_context(request, current_user) if enrollment_token is None else {}

        # Настраиваем 2FA
        setup_data = await run_in_threadpool(
            service.setup_two_factor_auth,
            db=db,
            user_id=current_user.id,
            recovery_email=request_data.recovery_email,
            recovery_phone=request_data.recovery_phone,
            enrollment_token=enrollment_token,
            **bearer_context,
        )

        response.headers["Cache-Control"] = "no-store"
        return TwoFactorSetupResponse(**setup_data)

    except (EnrollmentSessionInvalid, BearerSessionInvalid) as e:
        db.rollback()
        raise HTTPException(
            status_code=401, detail="Enrollment session unavailable"
        ) from e
    except TwoFactorAlreadyEnabled as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="2FA is already enabled for this user") from e
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise_two_factor_internal_error("setting up 2FA", e)


@router.post(
    "/verify-setup",
    response_model=TwoFactorVerifyResponse,
    responses={
        200: {
            "description": "Verification result and optional session tokens",
            "headers": _NO_STORE_HEADER,
        },
        400: {"description": "Invalid TOTP code format", "content": _TWO_FACTOR_ERROR_CONTENT},
        401: {
            "description": "Authentication or enrollment session invalid",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        500: {"description": "Internal error", "content": _TWO_FACTOR_ERROR_CONTENT},
    },
)
async def verify_totp_setup(
    request_data: TwoFactorVerifySetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Верифицировать настройку TOTP.

    SECURITY (AUTH-REAUDIT-28): totp_code перенесён из query-param в body.

    Двухстадийная аутентификация: при авторизации через enrollment_token
    успешная верификация завершает enrollment — токен отзывается
    (одноразовость) и выдаются нормальные access/refresh токены.
    """
    try:
        current_user, enrollment_token = await _resolve_user_bearer_or_enrollment(
            request, request_data.enrollment_token, db
        )
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide a Bearer token or a valid enrollment_token",
            )

        service = get_two_factor_service()
        bearer_context = _capture_bearer_context(request, current_user) if enrollment_token is None else {}
        totp_code = request_data.totp_code

        if len(totp_code) != 6 or not totp_code.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code format",
            )

        def verify_and_exchange():
            success = service.verify_totp_setup(
                db,
                current_user.id,
                totp_code,
                enrollment_token=enrollment_token,
                commit=enrollment_token is None,
                **bearer_context,
            )
            tokens_payload = None
            if success and enrollment_token is not None:
                auth = get_authentication_service()
                tokens_payload = TwoFactorAuthApiService(
                    db
                ).exchange_enrollment_token_for_tokens(
                    user=current_user,
                    enrollment_token=enrollment_token,
                    auth_service=auth,
                )
                if tokens_payload is None:
                    db.rollback()
                    raise EnrollmentSessionInvalid("Enrollment session unavailable")
            return success, tokens_payload

        # Both verification and exchange must share one session and transaction
        # in the same worker; row-lock waits must not block the event loop.
        success, tokens_payload = await run_in_threadpool(verify_and_exchange)
        response.headers["Cache-Control"] = "no-store"

        if success:
            return TwoFactorVerifyResponse(
                success=True,
                message="TOTP setup verified successfully",
                access_token=(tokens_payload or {}).get("access_token"),
                refresh_token=(tokens_payload or {}).get("refresh_token"),
                token_type=(tokens_payload or {}).get("token_type"),
                expires_in=(tokens_payload or {}).get("expires_in"),
            )
        else:
            return TwoFactorVerifyResponse(success=False, message="Invalid TOTP code")

    except (EnrollmentSessionInvalid, BearerSessionInvalid) as e:
        db.rollback()
        raise HTTPException(
            status_code=401, detail="Enrollment session unavailable"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise_two_factor_internal_error("verifying TOTP setup", e)


@router.post(
    "/verify", response_model=TwoFactorVerifyResponse,
    responses={
        200: {"description": "2FA verification and optional session tokens", "headers": _NO_STORE_HEADER},
        400: {"description": "A verification factor is required", "content": _TWO_FACTOR_ERROR_CONTENT},
        401: {"description": "Authentication or pending session invalid", "content": _TWO_FACTOR_ERROR_CONTENT},
        500: {"description": "Internal error", "content": _TWO_FACTOR_ERROR_CONTENT},
    },
)
async def verify_two_factor(
    request_data: TwoFactorVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Верифицировать 2FA код"""
    try:
        service = get_two_factor_service()
        ip_address, user_agent = get_client_info(request)

        # Проверяем, что хотя бы один код предоставлен
        if not any(
            [
                request_data.totp_code,
                request_data.backup_code,
                request_data.recovery_token,
            ]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one verification method must be provided",
            )

        # ✅ CERTIFICATION: Получаем пользователя из pending_2fa_token или access_token.
        # SECURITY (#2986): when pending_2fa_token is present it is the authoritative
        # credential of the BLOCKING LOGIN challenge and must win. Resolving the
        # access_token header first let any unrelated valid token stored in the
        # browser (e.g. another staff user's session) hijack the challenge —
        # verify ran against THAT user and returned "2FA not enabled" for a
        # fully correct admin code. Access_token remains the path for the
        # already-authenticated settings flow (no pending token in that case).
        user: User | None = None

        pending = request_data.pending_2fa_token
        if pending is not None:
            user = TwoFactorAuthApiService(db).get_user_from_pending_token(
                pending
            )

        # Fallback for the authenticated settings flow: access_token header.
        if pending is None:
            try:
                from fastapi.security import HTTPBearer

                security = HTTPBearer(auto_error=False)
                token_result = await security(request)
                if token_result and token_result.credentials:
                    try:
                        user = await get_current_user(token_result.credentials, db)
                    except HTTPException:
                        pass  # Не JWT токен
            except Exception:
                pass

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide either access_token or valid pending_2fa_token",
            )

        bearer_context = _capture_bearer_context(request, user) if pending is None else {}

        def verify_and_exchange():
            success, message, session_token = service.verify_two_factor(
                db=db,
                user_id=user.id,
                totp_code=request_data.totp_code,
                backup_code=request_data.backup_code,
                recovery_token=request_data.recovery_token,
                device_fingerprint=(request_data.device_fingerprint if request_data.remember_device else None),
                ip_address=ip_address,
                user_agent=user_agent,
                pending_token=pending,
                commit=pending is None,
                **bearer_context,
            )
            backup_codes_remaining = None
            tokens_payload = None
            if success and request_data.backup_code:
                auth_record = two_factor_auth.get_by_user_id(db, user.id)
                if auth_record:
                    backup_codes_remaining = two_factor_backup_code.get_unused_count(db, auth_record.id)
            if success and pending is not None:
                tokens_payload = TwoFactorAuthApiService(db).exchange_pending_token_for_tokens(
                    user=user, pending_token=pending, auth_service=get_authentication_service(),
                )
                if tokens_payload is None:
                    db.rollback()
                    raise PendingSessionInvalid("Pending 2FA session unavailable")
            return success, message, session_token, backup_codes_remaining, tokens_payload

        success, message, session_token, backup_codes_remaining, tokens_payload = await run_in_threadpool(verify_and_exchange)
        response.headers["Cache-Control"] = "no-store"

        if success:
            # Возвращаем успех 2FA (фронт, при наличии tokens_payload, может завершить логин)
            return TwoFactorVerifyResponse(
                success=True,
                message=message,
                session_token=session_token,
                device_trusted=bool(session_token),
                backup_codes_remaining=backup_codes_remaining,
                access_token=(tokens_payload or {}).get("access_token"),
                refresh_token=(tokens_payload or {}).get("refresh_token"),
                token_type=(tokens_payload or {}).get("token_type"),
                expires_in=(tokens_payload or {}).get("expires_in"),
            )
        else:
            return TwoFactorVerifyResponse(success=False, message=message)

    except (PendingSessionInvalid, BearerSessionInvalid) as e:
        db.rollback()
        raise HTTPException(status_code=401, detail="Pending 2FA session unavailable") from e
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise_two_factor_internal_error("verifying 2FA", e)


@router.post(
    "/disable",
    response_model=TwoFactorSuccessResponse,
    responses={429: _RATE_LIMIT_RESPONSE},
)
@limiter.limit("20/minute")
async def disable_two_factor_auth(
    request_data: TwoFactorDisableRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отключить 2FA для текущего пользователя.

    SECURITY (AUTH-REAUDIT-28): требуется ОБА фактора — пароль + 2FA-код.
    """
    try:
        service = get_two_factor_service()
        bearer_context = _capture_bearer_context(request, current_user)

        # SECURITY: 2FA-код обязателен.
        if not request_data.totp_code and not request_data.backup_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Отключение 2FA требует подтверждения текущим TOTP-кодом или backup-кодом.",
            )

        success = await run_in_threadpool(
            service.disable_two_factor_auth,
            db=db,
            user_id=current_user.id,
            password=request_data.password,
            totp_code=request_data.totp_code,
            backup_code=request_data.backup_code,
            **bearer_context,
        )

        if success:
            return TwoFactorSuccessResponse(
                success=True, message="2FA disabled successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password or 2FA code",
            )

    except BearerSessionInvalid as e:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from e
    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("disabling 2FA", e)


@router.post("/recovery/request", response_model=TwoFactorRecoveryResponse)
# IP-бакет — грубая защита от абьюза SMTP-провайдера; точный лимит
# по аккаунту (3/час) считает сервис — NAT-клинику не блокируем.
@limiter.limit("10/hour")
async def request_two_factor_recovery(
    request: Request,
    request_data: TwoFactorRecoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запросить восстановление 2FA.

    Токен ДОСТАВЛЯЕТСЯ по настроенному каналу (email через SMTP-провайдера).
    Доставка выполняется до записи в БД: при сбое провайдера не остаётся
    «повисшего» невыданного токена (HTTP 502, можно безопасно повторить).
    Прежние неотработанные токены сжигаются — действующий всегда один.
    """
    try:
        service = get_two_factor_service()
        ip_address, user_agent = get_client_info(request)
        bearer_context = _capture_bearer_context(request, current_user)

        # Проверяем, что 2FA включена
        status_data = service.get_two_factor_status(db, current_user.id)
        if not status_data["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is not enabled for this user",
            )

        two_factor_auth_obj = two_factor_auth.get_by_user_id(db, current_user.id)
        if not two_factor_auth_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA configuration not found",
            )

        result = await service.create_and_dispatch_recovery(
            db=db,
            two_factor_auth=two_factor_auth_obj,
            recovery_type=request_data.recovery_type,
            ip_address=ip_address,
            user_agent=user_agent,
            **bearer_context,
        )
        if not result.get("success"):
            error_code = result.get("error_code", "RECOVERY_FAILED")
            status_code = {
                "EMAIL_SEND_FAILED": 502,
                "CHANNEL_NOT_CONFIGURED": 400,
                "UNSUPPORTED_CHANNEL": 400,
                "PHONE_CHANNEL_UNAVAILABLE": 503,
                "RATE_LIMITED": 429,
            }.get(error_code, 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get("error", "Recovery dispatch failed"),
            )

        # SECURITY (AUTH-REAUDIT-28): НЕ возвращаем recovery_token в ответе.
        # Раньше токен возвращался напрямую, что позволяло атакующему с
        # украденным паролем (но заблокированным 2FA) получить recovery-токен
        # и обойти канал восстановления (email/phone).
        # Токен отправляется через recovery-канал; API возвращает только
        # подтверждение и expiry.
        return TwoFactorRecoveryResponse(
            recovery_token=None,  # не возвращаем
            expires_at=result["expires_at"],
            message=result.get(
                "message", "Код восстановления отправлен на настроенный канал."
            ),
        )

    except BearerSessionInvalid as e:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from e
    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("requesting 2FA recovery", e)


@router.post("/recovery/verify", response_model=TwoFactorVerifyResponse)
async def verify_two_factor_recovery(
    request_data: TwoFactorRecoveryVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Верифицировать восстановление 2FA.

    SECURITY (AUTH-REAUDIT-28): recovery_token перенесён из query-param в body.
    """
    try:
        service = get_two_factor_service()
        ip_address, user_agent = get_client_info(request)

        # Верифицируем токен восстановления
        success, message, session_token = service.verify_two_factor(
            db=db,
            user_id=current_user.id,
            recovery_token=request_data.recovery_token,
            device_fingerprint=None,  # Device fingerprint не требуется для recovery verify
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TwoFactorVerifyResponse(
            success=success,
            message=message,
            session_token=session_token,
            device_trusted=bool(session_token),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("verifying 2FA recovery", e)


@router.get(
    "/backup-codes",
    response_model=TwoFactorBackupCodesResponse,
    responses={
        200: {
            "description": "Remaining count; backup values are not returned",
            "headers": _NO_STORE_HEADER,
        },
        401: {
            "description": "Authentication required",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        404: {
            "description": "2FA not configured",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        500: {"description": "Internal error", "content": _TWO_FACTOR_ERROR_CONTENT},
    },
)
async def get_backup_codes(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить backup коды для текущего пользователя"""
    try:
        bearer_context = _capture_bearer_context(request, current_user)
        result = await run_in_threadpool(
            get_two_factor_service().get_backup_codes_count,
            db, current_user.id, **bearer_context,
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA not configured for this user",
            )

        remaining, generated_at = result
        response.headers["Cache-Control"] = "no-store"

        return TwoFactorBackupCodesResponse(
            backup_codes=[],
            total=remaining,
            generated_at=generated_at,
        )

    except BearerSessionInvalid as e:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from e
    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("getting backup codes", e)


@router.post(
    "/backup-codes/regenerate",
    response_model=TwoFactorBackupCodesResponse,
    responses={
        200: {
            "description": "New codes, disclosed only in this response",
            "headers": _NO_STORE_HEADER,
        },
        400: {
            "description": "A second factor is required",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        401: {
            "description": "Authentication required",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        403: {
            "description": "Reauthentication failed or is temporarily locked",
            "content": _TWO_FACTOR_ERROR_CONTENT,
        },
        429: _RATE_LIMIT_RESPONSE,
        500: {"description": "Internal error", "content": _TWO_FACTOR_ERROR_CONTENT},
    },
)
@limiter.limit("20/minute")
async def regenerate_backup_codes(
    request_data: TwoFactorDisableRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rotate backup codes after password and second-factor verification."""
    try:
        service = get_two_factor_service()
        bearer_context = _capture_bearer_context(request, current_user)

        if not request_data.totp_code and not request_data.backup_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A TOTP or backup code is required",
            )

        backup_codes = await run_in_threadpool(
            service.regenerate_backup_codes,
            db,
            current_user.id,
            request_data.password,
            totp_code=request_data.totp_code,
            backup_code=request_data.backup_code,
            **bearer_context,
        )
        if backup_codes is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid password or 2FA code, or temporarily unavailable",
            )

        response.headers["Cache-Control"] = "no-store"
        return TwoFactorBackupCodesResponse(
            backup_codes=backup_codes,
            total=len(backup_codes),
            generated_at=datetime.now(UTC),
        )

    except BearerSessionInvalid as e:
        db.rollback()
        raise HTTPException(status_code=401, detail="Bearer session unavailable") from e
    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("regenerating backup codes", e)


@router.get(
    "/devices", response_model=TwoFactorDeviceListResponse, include_in_schema=False
)
async def get_trusted_devices(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить список доверенных устройств.

    P0-3 NOTE (ENDPOINT-VALIDATION-AUDIT): FastAPI uses first-registration-
    wins for route resolution. This router (two_factor_auth.py) is mounted
    at /2fa BEFORE two_factor_devices.py in api.py (line 336 vs 342), so
    this handler takes precedence for GET /2fa/devices. The duplicate
    handler in two_factor_devices.py::get_trusted_devices is dead code
    and has been removed.

    Frontend expects `response.data.devices` (matching this handler's
    TwoFactorDeviceListResponse schema).
    """
    try:
        devices = two_factor_device.get_trusted_devices(db, current_user.id)
        return TwoFactorDeviceListResponse(devices=devices, total=len(devices))

    except Exception as e:
        raise_two_factor_internal_error("getting trusted devices", e)


@router.delete("/devices/{device_id}", response_model=dict[str, Any])
async def untrust_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отозвать доверие к устройству.

    P0-3 NOTE (ENDPOINT-VALIDATION-AUDIT): This handler wins over the
    duplicate in two_factor_devices.py::revoke_device because two_factor_auth
    is mounted first. Note this handler takes device_id:int while
    two_factor_devices took device_id:str — they are NOT API-compatible.
    The duplicate has been removed from two_factor_devices.py.
    """
    try:
        # TWOFACTOR-BE-003 (#4063): enforce ownership in the update query so
        # ownership cannot race between a separate check and the write.
        success = two_factor_device.untrust_device(db, device_id, current_user.id)
        if success:
            return TwoFactorSuccessResponse(
                success=True, message="Device untrusted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("untrusting device", e)


@router.get("/health", response_model=dict[str, Any])
async def two_factor_health_check():
    """Проверка здоровья сервиса 2FA"""
    return {
        "status": "ok",
        "service": "two_factor_auth",
        "features": [
            "totp_setup",
            "totp_verification",
            "backup_codes",
            "recovery_tokens",
            "trusted_devices",
            "session_management",
        ],
        "supported_methods": ["totp", "backup_code", "recovery"],
        "totp_window": 1,
        "backup_codes_count": 10,
        "session_expiry_hours": 24,
    }
