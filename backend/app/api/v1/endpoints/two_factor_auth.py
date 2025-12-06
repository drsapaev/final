"""
API endpoints для двухфакторной аутентификации (2FA)
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud.two_factor_auth import (
    two_factor_auth,
    two_factor_backup_code,
    two_factor_device,
    two_factor_recovery,
    two_factor_session,
)
from app.db.session import get_db
from app.models.authentication import RefreshToken, UserSession
from app.models.user import User
from app.schemas.authentication import LoginResponse
from app.schemas.two_factor_auth import (
    TwoFactorBackupCodesResponse,
    TwoFactorDeviceListResponse,
    TwoFactorDisableRequest,
    TwoFactorErrorResponse,
    TwoFactorRecoveryRequest,
    TwoFactorRecoveryResponse,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    TwoFactorSuccessResponse,
    TwoFactorVerifyRequest,
    TwoFactorVerifyResponse,
)
from app.services.authentication_service import get_authentication_service
from app.services.two_factor_service import get_two_factor_service, TwoFactorService

router = APIRouter()


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting 2FA status: {str(e)}",
        )


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor_auth(
    request_data: TwoFactorSetupRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Настроить 2FA для текущего пользователя"""
    try:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting up 2FA: {str(e)}",
        )


@router.post("/verify-setup", response_model=TwoFactorVerifyResponse)
async def verify_totp_setup(
    totp_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Верифицировать настройку TOTP"""
    try:
        service = get_two_factor_service()

        if len(totp_code) != 6 or not totp_code.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code format",
            )

        success = service.verify_totp_setup(db, current_user.id, totp_code)

        if success:
            return TwoFactorVerifyResponse(
                success=True, message="TOTP setup verified successfully"
            )
        else:
            return TwoFactorVerifyResponse(success=False, message="Invalid TOTP code")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying TOTP setup: {str(e)}",
        )


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
        user: Optional[User] = None
        
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
            pending_session = (
                db.query(UserSession)
                .filter(
                    UserSession.refresh_token == request_data.pending_2fa_token,
                    UserSession.revoked == False,
                    UserSession.expires_at > datetime.utcnow(),
                )
                .first()
            )
            if pending_session:
                user = db.query(User).filter(User.id == pending_session.user_id).first()
        
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
                two_factor_auth_obj = two_factor_auth.get_by_user_id(
                    db, user.id
                )
                if two_factor_auth_obj:
                    backup_codes_remaining = two_factor_backup_code.get_unused_count(
                        db, two_factor_auth_obj.id
                    )

            # Если пришёл pending_2fa_token, обменять на полноценные токены
            pending = request_data.pending_2fa_token
            tokens_payload = None
            if pending:
                # Найдём сессию с таким временным токеном
                pending_session = (
                    db.query(UserSession)
                    .filter(
                        UserSession.user_id == user.id,
                        UserSession.refresh_token == pending,
                        UserSession.revoked == False,
                        UserSession.expires_at > datetime.utcnow(),
                    )
                    .first()
                )
                if pending_session:
                    auth = get_authentication_service()
                    # Выпускаем финальные токены
                    jti = str(uuid.uuid4())
                    access_token = auth.create_access_token(
                        {
                            "sub": str(user.id),
                            "username": user.username,
                            "role": user.role,
                            "is_active": user.is_active,
                            "is_superuser": user.is_superuser,
                        }
                    )
                    refresh_token = auth.create_refresh_token(user.id, jti)
                    # Сохраняем refresh
                    db.add(
                        RefreshToken(
                            user_id=user.id,
                            token=refresh_token,
                            jti=jti,
                            expires_at=datetime.utcnow()
                            + timedelta(days=auth.refresh_token_expire_days),
                        )
                    )
                    # Отмечаем pending сессию как подтвержденную (можно оставить как trusted-маркер)
                    pending_session.user_agent = (
                        pending_session.user_agent or ""
                    ) + "|2fa-verified"
                    db.commit()
                    tokens_payload = {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "token_type": "bearer",
                        "expires_in": auth.access_token_expire_minutes * 60,
                    }

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying 2FA: {str(e)}",
        )


@router.post("/disable", response_model=TwoFactorSuccessResponse)
async def disable_two_factor_auth(
    request_data: TwoFactorDisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отключить 2FA для текущего пользователя"""
    try:
        service = get_two_factor_service()

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error disabling 2FA: {str(e)}",
        )


@router.post("/recovery/request", response_model=TwoFactorRecoveryResponse)
async def request_two_factor_recovery(
    request_data: TwoFactorRecoveryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запросить восстановление 2FA"""
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

        # Создаем токен восстановления
        recovery_token = service.generate_recovery_token()
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # Сохраняем попытку восстановления
        two_factor_auth_obj = two_factor_auth.get_by_user_id(db, current_user.id)
        if not two_factor_auth_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA configuration not found",
            )

        recovery = two_factor_recovery.create(
            db,
            obj_in={
                "two_factor_auth_id": two_factor_auth_obj.id,
                "recovery_type": request_data.recovery_type,
                "recovery_value": request_data.recovery_value,
                "recovery_token": recovery_token,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )

        return TwoFactorRecoveryResponse(
            recovery_token=recovery_token,
            expires_at=expires_at,
            message="Recovery token generated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error requesting 2FA recovery: {str(e)}",
        )


@router.post("/recovery/verify", response_model=TwoFactorVerifyResponse)
async def verify_two_factor_recovery(
    recovery_token: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Верифицировать восстановление 2FA"""
    try:
        service = get_two_factor_service()
        ip_address, user_agent = get_client_info(request)

        # Верифицируем токен восстановления
        success, message, session_token = service.verify_two_factor(
            db=db,
            user_id=current_user.id,
            recovery_token=recovery_token,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying 2FA recovery: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting backup codes: {str(e)}",
        )


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
            generated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerating backup codes: {str(e)}",
        )


@router.get("/devices", response_model=TwoFactorDeviceListResponse)
async def get_trusted_devices(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить список доверенных устройств"""
    try:
        devices = two_factor_device.get_trusted_devices(db, current_user.id)
        return TwoFactorDeviceListResponse(devices=devices, total=len(devices))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting trusted devices: {str(e)}",
        )


@router.delete("/devices/{device_id}")
async def untrust_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отозвать доверие к устройству"""
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error untrusting device: {str(e)}",
        )


@router.get("/health")
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
