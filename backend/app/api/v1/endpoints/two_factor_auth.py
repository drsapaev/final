"""
API endpoints для двухфакторной аутентификации (2FA)
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
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
from app.services.two_factor_service import get_two_factor_service

router = APIRouter()
logger = logging.getLogger(__name__)


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
    # 1) Bearer JWT — уже вошедший пользователь управляет своей 2FA
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

    # 2) enrollment-токен из двухстадийного логина
    if enrollment_token:
        user = TwoFactorAuthApiService(db).get_user_from_enrollment_token(
            enrollment_token
        )
        if user:
            return user, enrollment_token
    return None, None


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor_auth(
    request_data: TwoFactorSetupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Настроить 2FA для текущего пользователя.

    Авторизация: Bearer JWT (уже вошедший) ИЛИ одноразовый
    enrollment_token из login-ответа (двухстадийная аутентификация
    для критичных ролей без 2FA).
    """
    try:
        current_user, _ = await _resolve_user_bearer_or_enrollment(
            request, request_data.enrollment_token, db
        )
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide a Bearer token or a valid enrollment_token",
            )

        service = get_two_factor_service()

        # Проверяем, не настроена ли уже 2FA
        if service.get_two_factor_status(db, current_user.id)["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is already enabled for this user",
            )

        # Настраиваем 2FA
        setup_data = service.setup_two_factor_auth(
            db=db,
            user_id=current_user.id,
            recovery_email=request_data.recovery_email,
            recovery_phone=request_data.recovery_phone,
        )

        return TwoFactorSetupResponse(**setup_data)

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("setting up 2FA", e)


@router.post("/verify-setup", response_model=TwoFactorVerifyResponse)
async def verify_totp_setup(
    request_data: TwoFactorVerifySetupRequest,
    request: Request,
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
        totp_code = request_data.totp_code

        if len(totp_code) != 6 or not totp_code.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code format",
            )

        success = service.verify_totp_setup(db, current_user.id, totp_code)

        if success:
            tokens_payload = None
            if enrollment_token:
                auth = get_authentication_service()
                tokens_payload = TwoFactorAuthApiService(
                    db
                ).exchange_enrollment_token_for_tokens(
                    user=current_user,
                    enrollment_token=enrollment_token,
                    auth_service=auth,
                )
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

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("verifying TOTP setup", e)


@router.post("/verify", response_model=TwoFactorVerifyResponse)
async def verify_two_factor(
    request_data: TwoFactorVerifyRequest,
    request: Request,
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

        # ✅ CERTIFICATION: Получаем пользователя из access_token или pending_2fa_token
        user: User | None = None

        # Пробуем получить из access_token (если передан в заголовке)
        try:
            from fastapi.security import HTTPBearer

            security = HTTPBearer(auto_error=False)
            token_result = await security(request)
            if token_result and token_result.credentials:
                try:
                    user = await get_current_user(token_result.credentials, db)
                except HTTPException:
                    pass  # Не JWT токен, пробуем pending_2fa_token
        except Exception:
            pass

        # Если access_token не сработал, пробуем pending_2fa_token
        if not user and request_data.pending_2fa_token:
            user = TwoFactorAuthApiService(db).get_user_from_pending_token(
                request_data.pending_2fa_token
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide either access_token or valid pending_2fa_token",
            )

        # Верифицируем 2FA
        success, message, session_token = service.verify_two_factor(
            db=db,
            user_id=user.id,
            totp_code=request_data.totp_code,
            backup_code=request_data.backup_code,
            recovery_token=request_data.recovery_token,
            device_fingerprint=request_data.device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if success:
            # Получаем количество оставшихся backup кодов
            backup_codes_remaining = None
            if request_data.backup_code:
                two_factor_auth_obj = two_factor_auth.get_by_user_id(db, user.id)
                if two_factor_auth_obj:
                    backup_codes_remaining = two_factor_backup_code.get_unused_count(
                        db, two_factor_auth_obj.id
                    )

            # Если пришёл pending_2fa_token, обменять на полноценные токены
            pending = request_data.pending_2fa_token
            tokens_payload = None
            if pending:
                auth = get_authentication_service()
                tokens_payload = TwoFactorAuthApiService(
                    db
                ).exchange_pending_token_for_tokens(
                    user=user,
                    pending_token=pending,
                    auth_service=auth,
                )

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

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("verifying 2FA", e)


@router.post("/disable", response_model=TwoFactorSuccessResponse)
async def disable_two_factor_auth(
    request_data: TwoFactorDisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отключить 2FA для текущего пользователя.

    SECURITY (AUTH-REAUDIT-28): требуется ОБА фактора — пароль + 2FA-код.
    """
    try:
        service = get_two_factor_service()

        # SECURITY: 2FA-код обязателен.
        if not request_data.totp_code and not request_data.backup_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Отключение 2FA требует подтверждения текущим TOTP-кодом или backup-кодом.",
            )

        success = service.disable_two_factor_auth(
            db=db,
            user_id=current_user.id,
            password=request_data.password,
            totp_code=request_data.totp_code,
            backup_code=request_data.backup_code,
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

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("disabling 2FA", e)


@router.post("/recovery/request", response_model=TwoFactorRecoveryResponse)
@limiter.limit("3/hour")
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
        )
        if not result.get("success"):
            error_code = result.get("error_code", "RECOVERY_FAILED")
            status_code = {
                "EMAIL_SEND_FAILED": 502,
                "CHANNEL_NOT_CONFIGURED": 400,
                "UNSUPPORTED_CHANNEL": 400,
                "PHONE_CHANNEL_UNAVAILABLE": 503,
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
            message="Код восстановления отправлен на настроенный канал.",
        )

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


@router.get("/backup-codes", response_model=TwoFactorBackupCodesResponse)
async def get_backup_codes(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить backup коды для текущего пользователя"""
    try:
        two_factor_auth_obj = two_factor_auth.get_by_user_id(db, current_user.id)
        if not two_factor_auth_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA not configured for this user",
            )

        backup_codes = two_factor_backup_code.get_unused_codes(
            db, two_factor_auth_obj.id
        )
        codes = [code.code for code in backup_codes]

        return TwoFactorBackupCodesResponse(
            backup_codes=codes,
            total=len(codes),
            generated_at=two_factor_auth_obj.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_two_factor_internal_error("getting backup codes", e)


@router.post("/backup-codes/regenerate", response_model=TwoFactorBackupCodesResponse)
async def regenerate_backup_codes(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Перегенерировать backup коды"""
    try:
        service = get_two_factor_service()

        # Проверяем, что 2FA включена
        status_data = service.get_two_factor_status(db, current_user.id)
        if not status_data["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is not enabled for this user",
            )

        # Перегенерируем коды
        backup_codes = service.regenerate_backup_codes(db, current_user.id)

        return TwoFactorBackupCodesResponse(
            backup_codes=backup_codes,
            total=len(backup_codes),
            generated_at=datetime.now(UTC),
        )

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
        # Проверяем, что устройство принадлежит пользователю
        device = two_factor_device.get(device_id)
        if not device or device.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )

        success = two_factor_device.untrust_device(db, device_id)
        if success:
            return TwoFactorSuccessResponse(
                success=True, message="Device untrusted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to untrust device",
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
