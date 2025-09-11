"""
API endpoints для системы аутентификации
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.authentication_service import get_authentication_service, AuthenticationService
from app.crud.authentication import (
    refresh_token, user_session, password_reset_token, 
    email_verification_token, login_attempt, user_activity, 
    security_event, user
)
from app.schemas.authentication import (
    LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse,
    LogoutRequest, LogoutResponse, PasswordResetRequest, PasswordResetConfirmRequest,
    PasswordChangeRequest, EmailVerificationRequest, EmailVerificationConfirmRequest,
    UserProfileUpdateRequest, UserProfileResponse, UserSessionResponse,
    LoginAttemptResponse, UserActivityResponse, SecurityEventResponse,
    TokenValidationResponse, AuthStatusResponse, PasswordStrengthResponse,
    DeviceInfoResponse, AuthErrorResponse, AuthSuccessResponse,
    UserListResponse, UserCreateRequest, UserUpdateRequest, UserDeleteRequest,
    SessionListResponse, SessionRevokeRequest, SecurityEventListResponse,
    SecurityEventResolveRequest, AuthStatsResponse
)

router = APIRouter()


def get_client_info(request: Request) -> tuple[str, str]:
    """Получить информацию о клиенте"""
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return ip_address, user_agent


@router.post("/login", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
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
            remember_me=request_data.remember_me
        )
        
        print(f"DEBUG: login_user result: {result}")
        
        if not result["success"]:
            print(f"DEBUG: Authentication failed, raising HTTPException")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["message"]
            )
        
        return LoginResponse(
            access_token=result["tokens"]["access_token"],
            refresh_token=result["tokens"]["refresh_token"],
            token_type=result["tokens"]["token_type"],
            expires_in=result["tokens"]["expires_in"],
            user=result["user"],
            requires_2fa=result["requires_2fa"],
            two_factor_method=result["two_factor_method"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(e)}"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Обновление access токена"""
    try:
        service = get_authentication_service()
        result = service.refresh_access_token(db, request_data.refresh_token)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["message"]
            )
        
        return RefreshTokenResponse(
            access_token=result["access_token"],
            refresh_token=request_data.refresh_token,  # Возвращаем тот же refresh токен
            token_type=result["token_type"],
            expires_in=result["expires_in"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления токена: {str(e)}"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request_data: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Выход из системы"""
    try:
        service = get_authentication_service()
        result = service.logout_user(
            db=db,
            refresh_token=request_data.refresh_token,
            user_id=current_user.id,
            logout_all=request_data.logout_all_devices
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return LogoutResponse(
            success=True,
            message=result["message"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка выхода: {str(e)}"
        )


@router.post("/password-reset", response_model=AuthSuccessResponse)
async def request_password_reset(
    request_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Запрос сброса пароля"""
    try:
        ip_address, user_agent = get_client_info(request)
        
        service = get_authentication_service()
        result = service.create_password_reset_token(
            db=db,
            email=request_data.email,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return AuthSuccessResponse(
            success=True,
            message="Инструкции по сбросу пароля отправлены на email",
            data={"expires_at": result["expires_at"].isoformat()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запроса сброса пароля: {str(e)}"
        )


@router.post("/password-reset/confirm", response_model=AuthSuccessResponse)
async def confirm_password_reset(
    request_data: PasswordResetConfirmRequest,
    db: Session = Depends(get_db)
):
    """Подтверждение сброса пароля"""
    try:
        service = get_authentication_service()
        result = service.reset_password(
            db=db,
            token=request_data.token,
            new_password=request_data.new_password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return AuthSuccessResponse(
            success=True,
            message=result["message"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сброса пароля: {str(e)}"
        )


@router.post("/password-change", response_model=AuthSuccessResponse)
async def change_password(
    request_data: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Смена пароля"""
    try:
        service = get_authentication_service()
        result = service.change_password(
            db=db,
            user_id=current_user.id,
            current_password=request_data.current_password,
            new_password=request_data.new_password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return AuthSuccessResponse(
            success=True,
            message=result["message"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка смены пароля: {str(e)}"
        )


@router.post("/email-verification", response_model=AuthSuccessResponse)
async def request_email_verification(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Запрос верификации email"""
    try:
        ip_address, user_agent = get_client_info(request)
        
        service = get_authentication_service()
        result = service.create_email_verification_token(
            db=db,
            user_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return AuthSuccessResponse(
            success=True,
            message="Ссылка для верификации email отправлена",
            data={"expires_at": result["expires_at"].isoformat()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запроса верификации email: {str(e)}"
        )


@router.post("/email-verification/confirm", response_model=AuthSuccessResponse)
async def confirm_email_verification(
    request_data: EmailVerificationConfirmRequest,
    db: Session = Depends(get_db)
):
    """Подтверждение верификации email"""
    try:
        service = get_authentication_service()
        result = service.verify_email(
            db=db,
            token=request_data.token
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return AuthSuccessResponse(
            success=True,
            message=result["message"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка верификации email: {str(e)}"
        )


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить профиль пользователя"""
    try:
        service = get_authentication_service()
        profile = service.get_user_profile(db, current_user.id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль пользователя не найден"
            )
        
        return UserProfileResponse(**profile)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения профиля: {str(e)}"
        )


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    request_data: UserProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
            detail=f"Ошибка обновления профиля: {str(e)}"
        )


@router.get("/sessions", response_model=SessionListResponse)
async def get_user_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить сессии пользователя"""
    try:
        skip = (page - 1) * per_page
        sessions = user_session.get_by_user_id(db, current_user.id)
        
        # Пагинация
        total = len(sessions)
        sessions = sessions[skip:skip + per_page]
        
        # Конвертируем в ответы
        session_responses = []
        for session in sessions:
            session_responses.append(UserSessionResponse(
                id=session.id,
                session_id=session.session_id,
                created_at=session.created_at,
                last_activity=session.last_activity,
                expires_at=session.expires_at,
                is_active=session.is_active,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                device_name=session.device_name,
                current_session=False  # TODO: определить текущую сессию
            ))
        
        return SessionListResponse(
            sessions=session_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сессий: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    request_data: SessionRevokeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отозвать сессию"""
    try:
        # Проверяем, что сессия принадлежит пользователю
        session = user_session.get_by_session_id(db, str(session_id))
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сессия не найдена"
            )
        
        success = user_session.deactivate_session(db, str(session_id))
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка отзыва сессии"
            )
        
        return AuthSuccessResponse(
            success=True,
            message="Сессия успешно отозвана"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отзыва сессии: {str(e)}"
        )


@router.get("/activity", response_model=List[UserActivityResponse])
async def get_user_activity(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить активность пользователя"""
    try:
        activities = user_activity.get_by_user_id(db, current_user.id, limit)
        
        activity_responses = []
        for activity in activities:
            activity_responses.append(UserActivityResponse(
                id=activity.id,
                activity_type=activity.activity_type,
                description=activity.description,
                created_at=activity.created_at,
                ip_address=activity.ip_address,
                metadata=eval(activity.metadata) if activity.metadata else None
            ))
        
        return activity_responses
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения активности: {str(e)}"
        )


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
                two_factor_verified=False
            )
        
        # Получаем текущую сессию (упрощенно)
        sessions = user_session.get_active_sessions(db, current_user.id)
        current_session = sessions[0] if sessions else None
        
        return AuthStatusResponse(
            authenticated=True,
            user=UserProfileResponse(**profile),
            session=UserSessionResponse(
                id=current_session.id,
                session_id=current_session.session_id,
                created_at=current_session.created_at,
                last_activity=current_session.last_activity,
                expires_at=current_session.expires_at,
                is_active=current_session.is_active,
                ip_address=current_session.ip_address,
                user_agent=current_session.user_agent,
                device_name=current_session.device_name,
                current_session=True
            ) if current_session else None,
            two_factor_required=profile.get("two_factor_enabled", False),
            two_factor_verified=profile.get("two_factor_enabled", False)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса: {str(e)}"
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
            "security_events"
        ],
        "token_types": ["access", "refresh"],
        "access_token_expire_minutes": 30,
        "refresh_token_expire_days": 30,
        "password_reset_expire_hours": 1,
        "email_verification_expire_hours": 24
    }
