"""
API endpoints для системы аутентификации
"""

import json
import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud.authentication import (
    user_activity,
    user_session,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.authentication import (
    AuthStatusResponse,
    AuthSuccessResponse,
    EmailVerificationConfirmRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SessionListResponse,
    SessionRevokeRequest,
    UserActivityResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserSessionResponse,
)
from app.services.authentication_api_service import (
    AuthenticationApiDomainError,
    AuthenticationApiService,
)
from app.services.authentication_service import (
    get_authentication_service,
)
from app.services.user_management_service import get_user_management_service

router = APIRouter()
logger = logging.getLogger(__name__)


def get_client_info(request: Request) -> tuple[str, str]:
    """Получить информацию о клиенте"""
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return ip_address, user_agent


def raise_authentication_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.error(
        "Authentication endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


@router.post("/login", response_model=LoginResponse)
async def login(
    request_data: LoginRequest, request: Request, db: Session = Depends(get_db)
):
    """Вход в систему"""
    try:
        ip_address, user_agent = get_client_info(request)
        logger.debug(
            "Authentication login requested",
            extra={
                "has_client_ip": ip_address != "unknown",
                "has_user_agent": user_agent != "unknown",
                "has_device_fingerprint": bool(request_data.device_fingerprint),
                "remember_me": bool(request_data.remember_me),
            },
        )

        service = get_authentication_service()

        result = service.login_user(
            db=db,
            username=request_data.username,
            password=request_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=request_data.device_fingerprint,
            remember_me=request_data.remember_me,
        )

        logger.debug(
            "Authentication service completed",
            extra={
                "success": bool(result.get("success")),
                "requires_2fa": bool(result.get("requires_2fa")),
                "must_change_password": bool(result.get("must_change_password")),
            },
        )

        if not result["success"]:
            logger.info("Authentication login rejected")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=result["message"]
            )

        return LoginResponse(
            access_token=(result.get("tokens") or {}).get("access_token"),
            refresh_token=(result.get("tokens") or {}).get("refresh_token"),
            token_type=(result.get("tokens") or {}).get("token_type", "bearer"),
            expires_in=(result.get("tokens") or {}).get("expires_in", 0),
            user=result["user"],
            requires_2fa=result["requires_2fa"],
            two_factor_method=result["two_factor_method"],
            pending_2fa_token=result.get("pending_2fa_token"),
            must_change_password=result.get("must_change_password", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("login", e)


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request_data: RefreshTokenRequest, db: Session = Depends(get_db)
):
    """Обновление access токена"""
    try:
        service = get_authentication_service()
        result = service.refresh_access_token(db, request_data.refresh_token)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=result["message"]
            )

        return RefreshTokenResponse(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token") or request_data.refresh_token,
            token_type=result["token_type"],
            expires_in=result["expires_in"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("refresh_access_token", e)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request_data: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Выход из системы"""
    try:
        service = get_authentication_service()

        # Извлекаем jti + expiry из access-токена, чтобы отозвать его индивидуально.
        access_jti: str | None = None
        access_exp = None
        auth_header = request.headers.get("authorization") or ""
        if auth_header.lower().startswith("bearer "):
            try:
                from jose import jwt as _jwt
                from app.core.config import settings as _settings
                _payload = _jwt.decode(
                    auth_header.split(" ", 1)[1],
                    _settings.SECRET_KEY,
                    algorithms=[_settings.ALGORITHM],
                )
                access_jti = _payload.get("jti")
                _exp = _payload.get("exp")
                if _exp:
                    from datetime import datetime as _dt
                    access_exp = _dt.utcfromtimestamp(_exp)
            except Exception:
                # Non-blocking: если не удалось декодировать — просто не отзываем jti.
                pass

        result = service.logout_user(
            db=db,
            refresh_token=request_data.refresh_token,
            user_id=current_user.id,
            logout_all=request_data.logout_all_devices,
            access_token_jti=access_jti,
            access_token_exp=access_exp,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return LogoutResponse(success=True, message=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("logout", e)


@router.post("/password-reset", response_model=AuthSuccessResponse)
async def request_password_reset(
    request_data: PasswordResetRequest, request: Request, db: Session = Depends(get_db)
):
    """Запрос сброса пароля"""
    try:
        ip_address, user_agent = get_client_info(request)

        service = get_authentication_service()
        result = service.create_password_reset_token(
            db=db,
            email=request_data.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return AuthSuccessResponse(
            success=True,
            message="Инструкции по сбросу пароля отправлены на email",
            data={"expires_at": result["expires_at"].isoformat()},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("request_password_reset", e)


@router.post("/password-reset/confirm", response_model=AuthSuccessResponse)
async def confirm_password_reset(
    request_data: PasswordResetConfirmRequest, db: Session = Depends(get_db)
):
    """Подтверждение сброса пароля"""
    try:
        service = get_authentication_service()
        result = service.reset_password(
            db=db, token=request_data.token, new_password=request_data.new_password
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return AuthSuccessResponse(success=True, message=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("confirm_password_reset", e)


@router.post("/password-change", response_model=AuthSuccessResponse)
async def change_password(
    request_data: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Смена пароля"""
    try:
        service = get_authentication_service()
        result = service.change_password(
            db=db,
            user_id=current_user.id,
            current_password=request_data.current_password,
            new_password=request_data.new_password,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return AuthSuccessResponse(success=True, message=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("change_password", e)


@router.post("/email-verification", response_model=AuthSuccessResponse)
async def request_email_verification(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запрос верификации email"""
    try:
        ip_address, user_agent = get_client_info(request)

        service = get_authentication_service()
        result = service.create_email_verification_token(
            db=db, user_id=current_user.id, ip_address=ip_address, user_agent=user_agent
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return AuthSuccessResponse(
            success=True,
            message="Ссылка для верификации email отправлена",
            data={"expires_at": result["expires_at"].isoformat()},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("request_email_verification", e)


@router.post("/email-verification/confirm", response_model=AuthSuccessResponse)
async def confirm_email_verification(
    request_data: EmailVerificationConfirmRequest, db: Session = Depends(get_db)
):
    """Подтверждение верификации email"""
    try:
        service = get_authentication_service()
        result = service.verify_email(db=db, token=request_data.token)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return AuthSuccessResponse(success=True, message=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("confirm_email_verification", e)


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить профиль пользователя"""
    try:
        service = get_authentication_service()
        profile = service.get_user_profile(db, current_user.id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль пользователя не найден",
            )

        return UserProfileResponse(**profile)

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("get_user_profile", e)


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    request_data: UserProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить профиль пользователя"""
    api_service = AuthenticationApiService(db)
    try:
        service = get_authentication_service()
        profile = api_service.update_user_profile(
            current_user=current_user,
            update_data=request_data.model_dump(exclude_unset=True),
            profile_loader=lambda user_id: service.get_user_profile(db, user_id),
            support_records_loader=lambda: get_user_management_service().ensure_user_support_records(
                db, current_user
            ),
        )

        return UserProfileResponse(**profile)

    except AuthenticationApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        api_service.rollback()
        raise_authentication_internal_error("update_user_profile", e)


@router.get("/sessions", response_model=SessionListResponse)
async def get_paginated_user_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить сессии пользователя"""
    try:
        skip = (page - 1) * per_page
        sessions = user_session.get_by_user_id(db, current_user.id)

        # Пагинация
        total = len(sessions)
        sessions = sessions[skip : skip + per_page]

        # Конвертируем в ответы (поля соответствуют модели UserSession).
        from datetime import datetime as _dt
        now = _dt.utcnow()
        session_responses = []
        for session in sessions:
            session_responses.append(
                UserSessionResponse(
                    id=session.id,
                    user_id=session.user_id,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                    is_active=(not session.revoked and session.expires_at > now),
                    revoked=session.revoked,
                    revoked_at=getattr(session, "revoked_at", None),
                    ip_address=session.ip,  # alias
                    user_agent=session.user_agent,
                    refresh_token=None,  # не возвращаем токен в API-ответе
                    current_session=False,
                )
            )

        return SessionListResponse(
            sessions=session_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
        )

    except Exception as e:
        raise_authentication_internal_error("get_user_sessions", e)


@router.delete("/sessions/{session_id}")
async def delete_user_session(
    session_id: int,
    request_data: SessionRevokeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отозвать сессию"""
    try:
        # Проверяем, что сессия принадлежит пользователю
        session = user_session.get_by_session_id(db, str(session_id))
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
            )

        success = user_session.deactivate_session(db, str(session_id))
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ошибка отзыва сессии"
            )

        return AuthSuccessResponse(success=True, message="Сессия успешно отозвана")

    except HTTPException:
        raise
    except Exception as e:
        raise_authentication_internal_error("revoke_session", e)


@router.get("/activity", response_model=list[UserActivityResponse])
async def get_user_activity(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить активность пользователя"""
    try:
        activities = user_activity.get_by_user_id(db, current_user.id, limit)

        activity_responses = []
        for activity in activities:
            activity_responses.append(
                UserActivityResponse(
                    id=activity.id,
                    activity_type=activity.activity_type,
                    description=activity.description,
                    created_at=activity.created_at,
                    ip_address=activity.ip_address,
                    metadata=(
                        json.loads(activity.extra_data) if activity.extra_data else None
                    ),
                )
            )

        return activity_responses

    except Exception as e:
        raise_authentication_internal_error("get_user_activity", e)


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Получить статус аутентификации"""
    try:
        service = get_authentication_service()
        profile = service.get_user_profile(db, current_user.id)

        if not profile:
            return AuthStatusResponse(
                authenticated=False,
                user=None,
                session=None,
                two_factor_required=False,
                two_factor_verified=False,
            )

        # Получаем текущую сессию (упрощенно)
        sessions = user_session.get_active_sessions(db, current_user.id)
        current_session = sessions[0] if sessions else None

        from datetime import datetime as _dt
        now = _dt.utcnow()
        return AuthStatusResponse(
            authenticated=True,
            user=UserProfileResponse(**profile),
            session=(
                UserSessionResponse(
                    id=current_session.id,
                    user_id=current_session.user_id,
                    created_at=current_session.created_at,
                    expires_at=current_session.expires_at,
                    is_active=(not current_session.revoked and current_session.expires_at > now),
                    revoked=current_session.revoked,
                    revoked_at=getattr(current_session, "revoked_at", None),
                    ip_address=current_session.ip,
                    user_agent=current_session.user_agent,
                    refresh_token=None,
                    current_session=True,
                )
                if current_session
                else None
            ),
            two_factor_required=profile.get("two_factor_enabled", False),
            # 2FA-статус сессии не сохраняется отдельно; используем флаг профиля.
            two_factor_verified=profile.get("two_factor_enabled", False),
        )

    except Exception as e:
        raise_authentication_internal_error("get_auth_status", e)


@router.get("/health")
async def auth_health_check():
    """Проверка здоровья сервиса аутентификации"""
    return {
        "status": "ok",
        "service": "authentication",
        "features": [
            "jwt_tokens",
            "refresh_tokens",
            "password_reset",
            "email_verification",
            "user_sessions",
            "login_attempts",
            "user_activity",
            "security_events",
        ],
        "token_types": ["access", "refresh"],
        "access_token_expire_minutes": 30,
        "refresh_token_expire_days": 30,
        "password_reset_expire_hours": 1,
        "email_verification_expire_hours": 24,
    }


# ===================== УПРАВЛЕНИЕ СЕССИЯМИ =====================


@router.get("/sessions/current")
async def get_current_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить текущую сессию пользователя"""
    try:
        auth_service = get_authentication_service()
        ip_address, user_agent = get_client_info(request)

        session = auth_service.get_current_session(
            db, current_user.id, ip_address, user_agent
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Активная сессия не найдена",
            )

        session_info = auth_service.get_session_info(db, session.id)

        return {
            "success": True,
            "message": "Текущая сессия получена",
            "session": session_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Authentication endpoint failed action=%s error_type=%s",
            "get current session",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения текущей сессии",
        )


@router.get("/sessions", include_in_schema=False)
async def get_active_user_sessions(
    active_only: bool = Query(True, description="Только активные сессии"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить все сессии пользователя"""
    try:
        auth_service = get_authentication_service()
        sessions = auth_service.get_user_sessions(db, current_user.id, active_only)

        sessions_info = []
        for session in sessions:
            session_info = auth_service.get_session_info(db, session.id)
            if session_info:
                sessions_info.append(session_info)

        return {
            "success": True,
            "message": f"Найдено {len(sessions_info)} сессий",
            "sessions": sessions_info,
            "total": len(sessions_info),
        }

    except Exception as e:
        logger.error(
            "Authentication endpoint failed action=%s error_type=%s",
            "get active user sessions",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения сессий пользователя",
        )


@router.post("/sessions/{session_id}/revoke")
async def revoke_user_session(
    session_id: int,
    reason: str = Query("manual", description="Причина отзыва сессии"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отозвать сессию"""
    try:
        auth_service = get_authentication_service()
        AuthenticationApiService(db).ensure_session_access(
            session_id=session_id,
            current_user_id=current_user.id,
            allow_admin_access=False,
        )

        success = auth_service.revoke_session(db, session_id, reason)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось отозвать сессию",
            )

        return {
            "success": True,
            "message": f"Сессия {session_id} отозвана",
            "reason": reason,
        }

    except AuthenticationApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Authentication endpoint failed action=%s error_type=%s",
            "revoke session",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка отзыва сессии",
        )


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    request: Request,
    except_current: bool = Query(True, description="Исключить текущую сессию"),
    reason: str = Query("logout_all", description="Причина отзыва сессий"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отозвать все сессии пользователя"""
    try:
        auth_service = get_authentication_service()

        current_session_id = None
        if except_current:
            ip_address, user_agent = get_client_info(request)
            current_session = auth_service.get_current_session(
                db, current_user.id, ip_address, user_agent
            )
            if current_session:
                current_session_id = current_session.id

        revoked_count = auth_service.revoke_all_user_sessions(
            db, current_user.id, current_session_id, reason
        )

        return {
            "success": True,
            "message": f"Отозвано {revoked_count} сессий",
            "revoked_count": revoked_count,
            "reason": reason,
        }

    except Exception as e:
        logger.error(
            "Authentication endpoint failed action=%s error_type=%s",
            "revoke all sessions",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка отзыва всех сессий",
        )


@router.post("/sessions/cleanup")
async def cleanup_expired_sessions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Очистить истекшие сессии (только для администраторов)"""
    try:
        # Проверяем права администратора
        if current_user.role not in ["Admin", "SuperAdmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )

        auth_service = get_authentication_service()
        cleaned_count = auth_service.cleanup_expired_sessions(db)

        return {
            "success": True,
            "message": f"Очищено {cleaned_count} истекших сессий",
            "cleaned_count": cleaned_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Authentication endpoint failed action=%s error_type=%s",
            "cleanup expired sessions",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка очистки истекших сессий",
        )


@router.get("/sessions/{session_id}")
async def get_session_info(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить информацию о сессии"""
    try:
        auth_service = get_authentication_service()
        AuthenticationApiService(db).ensure_session_access(
            session_id=session_id,
            current_user_id=current_user.id,
            allow_admin_access=current_user.role in ["Admin", "SuperAdmin"],
        )

        session_info = auth_service.get_session_info(db, session_id)

        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Информация о сессии не найдена",
            )

        return {
            "success": True,
            "message": "Информация о сессии получена",
            "session": session_info,
        }

    except AuthenticationApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Authentication endpoint failed action=%s error_type=%s",
            "get session info",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения информации о сессии",
        )
