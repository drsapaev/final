"""
API endpoints для Firebase Cloud Messaging (FCM) push уведомлений
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.crud import user as crud_user
from app.db.session import get_db
from app.models.user import User
from app.services.fcm_service import FCMService, get_fcm_service

router = APIRouter()


class FCMTokenRequest(BaseModel):
    """Запрос на регистрацию FCM токена"""

    device_token: str
    device_type: str = "web"  # web, android, ios
    device_info: Optional[Dict[str, str]] = None


class FCMNotificationRequest(BaseModel):
    """Запрос на отправку FCM уведомления"""

    title: str
    body: str
    user_ids: Optional[List[int]] = None
    device_tokens: Optional[List[str]] = None
    data: Optional[Dict[str, Any]] = None
    image: Optional[str] = None
    click_action: Optional[str] = None
    sound: str = "default"
    badge: Optional[int] = None


class FCMTopicRequest(BaseModel):
    """Запрос для работы с топиками FCM"""

    topic: str
    device_tokens: List[str]


class FCMTopicNotificationRequest(BaseModel):
    """Запрос на отправку уведомления по топику"""

    topic: str
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None
    image: Optional[str] = None
    condition: Optional[str] = None


@router.post("/register-token")
async def register_fcm_token(
    request: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Регистрация FCM токена пользователя"""
    try:
        # Обновляем токен пользователя
        user_data = {
            "fcm_token": request.device_token,
            "device_type": request.device_type,
            "device_info": request.device_info,
            "push_notifications_enabled": True,
        }

        crud_user.update_user(db, user_id=current_user.id, user_data=user_data)

        return {
            "success": True,
            "message": "FCM токен успешно зарегистрирован",
            "device_token": request.device_token,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка регистрации FCM токена: {str(e)}",
        )


@router.delete("/unregister-token")
async def unregister_fcm_token(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Отмена регистрации FCM токена"""
    try:
        # Удаляем токен пользователя
        user_data = {
            "fcm_token": None,
            "device_type": None,
            "device_info": None,
            "push_notifications_enabled": False,
        }

        crud_user.update_user(db, user_id=current_user.id, user_data=user_data)

        return {"success": True, "message": "FCM токен успешно удален"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления FCM токена: {str(e)}",
        )


@router.post("/send-notification")
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

        # Получаем токены по user_ids
        if request.user_ids:
            users = crud_user.get_users_by_ids(db, user_ids=request.user_ids)
            for user in users:
                if user.fcm_token and user.push_notifications_enabled:
                    device_tokens.append(user.fcm_token)

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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки FCM уведомления: {str(e)}",
        )


@router.post("/send-test-notification")
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

        if not current_user.fcm_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FCM токен не зарегистрирован",
            )

        # Отправляем тестовое уведомление
        result = await fcm_service.send_notification(
            device_token=current_user.fcm_token,
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки тестового уведомления: {str(e)}",
        )


@router.post("/subscribe-topic")
async def subscribe_to_topic(
    request: FCMTopicRequest,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Подписка устройств на топик"""
    try:
        fcm_service = get_fcm_service()

        if not fcm_service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="FCM сервис не настроен"
            )

        result = await fcm_service.subscribe_to_topic(
            device_tokens=request.device_tokens, topic=request.topic
        )

        return {
            "success": result["success"],
            "message": f"Подписка на топик '{request.topic}' {'выполнена' if result['success'] else 'не выполнена'}",
            "topic": request.topic,
            "device_count": len(request.device_tokens),
            "response": result.get("response"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подписки на топик: {str(e)}",
        )


@router.post("/unsubscribe-topic")
async def unsubscribe_from_topic(
    request: FCMTopicRequest,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отписка устройств от топика"""
    try:
        fcm_service = get_fcm_service()

        if not fcm_service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="FCM сервис не настроен"
            )

        result = await fcm_service.unsubscribe_from_topic(
            device_tokens=request.device_tokens, topic=request.topic
        )

        return {
            "success": result["success"],
            "message": f"Отписка от топика '{request.topic}' {'выполнена' if result['success'] else 'не выполнена'}",
            "topic": request.topic,
            "device_count": len(request.device_tokens),
            "response": result.get("response"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отписки от топика: {str(e)}",
        )


@router.post("/send-topic-notification")
async def send_topic_notification(
    request: FCMTopicNotificationRequest,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отправка уведомления по топику"""
    try:
        fcm_service = get_fcm_service()

        if not fcm_service.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="FCM сервис не настроен"
            )

        result = await fcm_service.send_topic_notification(
            topic=request.topic,
            title=request.title,
            body=request.body,
            data=request.data,
            image=request.image,
            condition=request.condition,
        )

        return {
            "success": result.success,
            "message": f"Уведомление по топику '{request.topic}' {'отправлено' if result.success else 'не отправлено'}",
            "topic": request.topic,
            "message_id": result.message_id,
            "error": result.error,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки уведомления по топику: {str(e)}",
        )


@router.get("/status")
async def get_fcm_status(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Статус FCM сервиса"""
    try:
        fcm_service = get_fcm_service()
        status_info = fcm_service.get_status()

        return {"fcm_service": status_info, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса FCM: {str(e)}",
        )


@router.get("/user-tokens")
async def get_user_fcm_tokens(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Список пользователей с FCM токенами"""
    try:
        users_with_tokens = crud_user.get_users_with_fcm_tokens(db)

        result = []
        for user in users_with_tokens:
            result.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "fcm_token": (
                        user.fcm_token[:20] + "..." if user.fcm_token else None
                    ),
                    "device_type": user.device_type,
                    "push_enabled": user.push_notifications_enabled,
                    "last_login": (
                        user.last_login.isoformat() if user.last_login else None
                    ),
                }
            )

        return {"users": result, "total_count": len(result)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения FCM токенов: {str(e)}",
        )
