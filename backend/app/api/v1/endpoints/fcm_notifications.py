"""
API endpoints для Firebase Cloud Messaging (FCM) push уведомлений

PR-5 (hygiene of a dead surface): the topic management endpoints were
removed. They called FCMService methods that never existed and always
returned HTTP 500, while no client could ever reach them in practice
(topics require device-side SDK subscription; the mobile app removed
Firebase on purpose). Group fan-outs, if ever needed, must go through
the per-user token registry instead of FCM topics.
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.rate_limiter import limiter
from app.crud import user as crud_user
from app.db.session import get_db
from app.models.user import User
from app.services.fcm_service import get_fcm_service

router = APIRouter()


class FCMTokenRequest(BaseModel):
    """Запрос на регистрацию FCM токена"""

    # PR-5 (codex round 1): the contract matches the persisted column width
    # (users.device_token is String(255)); real FCM registration tokens are
    # well under this bound. Oversized values must 422 here instead of
    # blowing up as a DataError on flush.
    device_token: str = Field(min_length=1, max_length=255)
    device_type: Literal["web", "android", "ios"] = "web"
    device_info: dict[str, str] | None = None


class FCMNotificationRequest(BaseModel):
    """Запрос на отправку FCM уведомления"""

    title: str
    body: str
    user_ids: list[int] | None = None
    device_tokens: list[str] | None = None
    data: dict[str, Any] | None = None
    image: str | None = None
    click_action: str | None = None
    sound: str = "default"
    badge: int | None = None


@router.post("/register-token", response_model=dict[str, Any])
@limiter.limit("10/minute")  # registration is client-initiated; keep blast radius tiny
async def register_fcm_token(  # P1-7: token ownership validated via current_user
    request: Request,
    payload: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Регистрация FCM токена пользователя"""
    try:
        # PR-5: normalise once; empty/oversized tokens are rejected by the
        # request model before we ever touch the registry.
        device_token = payload.device_token.strip()

        # PR-2: persist to existing User.device_token + new mobile metadata columns
        crud_user.update_user(
            db,
            user_id=current_user.id,
            user_data={
                "device_token": device_token,
                "device_type": payload.device_type,
                "device_info": payload.device_info,
                "push_notifications_enabled": True,
            },
        )

        return {
            "success": True,
            "message": "FCM токен успешно зарегистрирован",
            "device_token": device_token,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/unregister-token", response_model=dict[str, Any])
async def unregister_fcm_token(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Отмена регистрации FCM токена"""
    try:
        # PR-2: clear device_token + mobile metadata
        crud_user.update_user(
            db,
            user_id=current_user.id,
            user_data={
                "device_token": None,
                "device_type": None,
                "device_info": None,
                "push_notifications_enabled": False,
            },
        )

        return {"success": True, "message": "FCM токен успешно удален"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-notification", response_model=dict[str, Any])
async def send_fcm_notification(
    request: FCMNotificationRequest,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отправка FCM уведомления (только для администраторов)"""
    try:
        fcm_service = get_fcm_service()

        if not fcm_service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="FCM сервис не настроен"
            )

        device_tokens = []

        # Получаем токены по user_ids (PR-2: device_token is the real column)
        if request.user_ids:
            users = crud_user.get_users_by_ids(db, user_ids=request.user_ids)
            for user in users:
                token = getattr(user, "device_token", None)
                push_on = getattr(user, "push_notifications_enabled", True)
                if token and push_on:
                    device_tokens.append(token)

        # Добавляем прямо указанные токены
        if request.device_tokens:
            device_tokens.extend(request.device_tokens)

        if not device_tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не найдено активных FCM токенов",
            )

        # Отправляем уведомления
        if len(device_tokens) == 1:
            # Одиночная отправка
            result = await fcm_service.send_notification(
                device_token=device_tokens[0],
                title=request.title,
                body=request.body,
                data=request.data,
                image=request.image,
                click_action=request.click_action,
                sound=request.sound,
                badge=request.badge,
            )

            return {
                "success": result.success,
                "message": (
                    "Уведомление отправлено"
                    if result.success
                    else f"Ошибка: {result.error}"
                ),
                "sent_count": 1 if result.success else 0,
                "failed_count": 0 if result.success else 1,
                "message_id": result.message_id,
            }
        else:
            # Массовая отправка
            result = await fcm_service.send_multicast(
                device_tokens=device_tokens,
                title=request.title,
                body=request.body,
                data=request.data,
                image=request.image,
                click_action=request.click_action,
                sound=request.sound,
                badge=request.badge,
            )

            return {
                "success": result["success"],
                "message": f"Отправлено {result['sent_count']} из {result['total_count']} уведомлений",
                "sent_count": result["sent_count"],
                "failed_count": result["failed_count"],
                "total_count": result["total_count"],
            }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-test-notification", response_model=dict[str, Any])
async def send_test_fcm_notification(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Отправка тестового FCM уведомления текущему пользователю"""
    try:
        fcm_service = get_fcm_service()

        if not fcm_service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="FCM сервис не настроен"
            )

        # PR-2: device_token is the real column name on User
        if not current_user.device_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FCM токен не зарегистрирован",
            )

        # Отправляем тестовое уведомление
        result = await fcm_service.send_notification(
            device_token=current_user.device_token,
            title="Тестовое уведомление",
            body=f"Привет, {current_user.full_name or current_user.username}! FCM работает корректно.",
            data={
                "type": "test",
                "timestamp": str(int(datetime.now().timestamp())),
                "user_id": str(current_user.id),
            },
            sound="default",
        )

        if result.success:
            return {
                "success": True,
                "message": "Тестовое уведомление отправлено",
                "message_id": result.message_id,
            }
        else:
            return {
                "success": False,
                "message": f"Ошибка отправки: {result.error}",
                "error_code": result.error_code,
            }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/status", response_model=dict[str, Any])
async def get_fcm_status(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Статус FCM сервиса"""
    try:
        fcm_service = get_fcm_service()
        status_info = fcm_service.get_status()

        return {"fcm_service": status_info, "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/user-tokens", response_model=dict[str, Any])
async def get_user_fcm_tokens(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Список пользователей с FCM токенами"""
    try:
        # PR-2: device_token is the real column; last_login lives on UserProfile
        users_with_tokens = crud_user.get_users_with_fcm_tokens(db)

        result = []
        for user in users_with_tokens:
            token = getattr(user, "device_token", None) or ""
            # last_login is on UserProfile (user.profile), not User
            profile = getattr(user, "profile", None)
            last_login = getattr(profile, "last_login", None) if profile else None
            result.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "fcm_token": "[redacted]" if token else None,
                    "fcm_token_length": len(token),
                    "device_type": getattr(user, "device_type", None),
                    "push_enabled": getattr(user, "push_notifications_enabled", False),
                    "last_login": (
                        last_login.isoformat() if last_login else None
                    ),
                }
            )

        return {"users": result, "total_count": len(result)}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
