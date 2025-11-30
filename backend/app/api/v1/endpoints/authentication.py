"""
API endpoints для системы аутентификации
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.authentication_service import (
    AuthenticationService,
    get_authentication_service,
)

logger = logging.getLogger(__name__)
from app.crud.authentication import (
    email_verification_token,
    login_attempt,
    password_reset_token,
    refresh_token,
    security_event,
    user,
    user_activity,
    user_session,
)
from app.schemas.authentication import (
    AuthErrorResponse,
    AuthStatsResponse,
    AuthStatusResponse,
    AuthSuccessResponse,
    DeviceInfoResponse,
    EmailVerificationConfirmRequest,
    EmailVerificationRequest,
    LoginAttemptResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordStrengthResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SecurityEventListResponse,
    SecurityEventResolveRequest,
    SecurityEventResponse,
    SessionListResponse,
    SessionRevokeRequest,
    TokenValidationResponse,
    UserActivityResponse,
    UserCreateRequest,
    UserDeleteRequest,
    UserListResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserSessionResponse,
    UserUpdateRequest,
)

router = APIRouter()


def get_client_info(request: Request) -> tuple[str, str]:
    """Получить информацию о клиенте"""
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return ip_address, user_agent


@router.post("/login", response_model=LoginResponse)
async def login(
    request_data: LoginRequest, request: Request, db: Session = Depends(get_db)
):
    """Вход в систему"""
    try:
        print(f"DEBUG: Login endpoint called with username={request_data.username}")

        ip_address, user_agent = get_client_info(request)
        print(f"DEBUG: IP={ip_address}, UserAgent={user_agent}")

        service = get_authentication_service()
        print(f"DEBUG: Service obtained: {service}")

        result = service.login_user(
            db=db,
            username=request_data.username,
            password=request_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=request_data.device_fingerprint,
            remember_me=request_data.remember_me,
        )

        print(f"DEBUG: login_user result: {result}")

        if not result["success"]:
            print(f"DEBUG: Authentication failed, raising HTTPException")
            print(f"DEBUG: Result details: {result}")
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
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Exception in login endpoint: {e}")
        import traceback

        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(e)}",
        )


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
            refresh_token=request_data.refresh_token,  # Возвращаем тот же refresh токен
            token_type=result["token_type"],
            expires_in=result["expires_in"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления токена: {str(e)}",
        )


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
        result = service.logout_user(
            db=db,
            refresh_token=request_data.refresh_token,
            user_id=current_user.id,
            logout_all=request_data.logout_all_devices,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        return LogoutResponse(success=True, message=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка выхода: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запроса сброса пароля: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сброса пароля: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка смены пароля: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запроса верификации email: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка верификации email: {str(e)}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения профиля: {str(e)}",
        )


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    request_data: UserProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить профиль пользователя"""
    try:
        # Обновляем данные пользователя
        update_data = request_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(current_user, field):
                setattr(current_user, field, value)

        db.commit()
        db.refresh(current_user)

        # Получаем обновленный профиль
        service = get_authentication_service()
        profile = service.get_user_profile(db, current_user.id)

        return UserProfileResponse(**profile)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления профиля: {str(e)}",
        )


@router.get("/sessions", response_model=SessionListResponse)
async def get_user_sessions(
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

        # Конвертируем в ответы
        session_responses = []
        for session in sessions:
            session_responses.append(
                UserSessionResponse(
                    id=session.id,
                    session_id=session.session_id,
                    created_at=session.created_at,
                    last_activity=session.last_activity,
                    expires_at=session.expires_at,
                    is_active=session.is_active,
                    ip_address=session.ip_address,
                    user_agent=session.user_agent,
                    device_name=session.device_name,
                    current_session=False,  # TODO: определить текущую сессию
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сессий: {str(e)}",
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отзыва сессии: {str(e)}",
        )


@router.get("/activity", response_model=List[UserActivityResponse])
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
                        json.loads(activity.metadata) if activity.metadata else None
                    ),
                )
            )

        return activity_responses

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения активности: {str(e)}",
        )


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

        return AuthStatusResponse(
            authenticated=True,
            user=UserProfileResponse(**profile),
            session=(
                UserSessionResponse(
                    id=current_session.id,
                    session_id=current_session.session_id,
                    created_at=current_session.created_at,
                    last_activity=current_session.last_activity,
                    expires_at=current_session.expires_at,
                    is_active=current_session.is_active,
                    ip_address=current_session.ip_address,
                    user_agent=current_session.user_agent,
                    device_name=current_session.device_name,
                    current_session=True,
                )
                if current_session
                else None
            ),
            two_factor_required=profile.get("two_factor_enabled", False),
            two_factor_verified=profile.get("two_factor_enabled", False),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса: {str(e)}",
        )


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
        logger.error(f"Error getting current session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения текущей сессии",
        )


@router.get("/sessions")
async def get_user_sessions(
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
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения сессий пользователя",
        )


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: int,
    reason: str = Query("manual", description="Причина отзыва сессии"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отозвать сессию"""
    try:
        auth_service = get_authentication_service()

        # Проверяем, что сессия принадлежит текущему пользователю
        from app.models.authentication import UserSession

        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
            )

        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этой сессии",
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking session {session_id}: {e}")
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
        logger.error(f"Error revoking all sessions: {e}")
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
        logger.error(f"Error cleaning up expired sessions: {e}")
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

        # Проверяем, что сессия принадлежит текущему пользователю или пользователь - администратор
        from app.models.authentication import UserSession

        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
            )

        if session.user_id != current_user.id and current_user.role not in [
            "Admin",
            "SuperAdmin",
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этой сессии",
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения информации о сессии",
        )
