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
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.rate_limiter import limiter
from app.crud import push_device as crud_push_device
from app.crud import user as crud_user
from app.db.session import get_db
from app.models.user import User
from app.services.fcm_service import FCMResponse, is_unregistered_token_response, get_fcm_service

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

    @field_validator("device_token")
    @classmethod
    def _token_not_blank(cls, value: str) -> str:
        # PR-5 (codex round 2): whitespace-only tokens pass min_length=1 and
        # would normalize to an empty string at the endpoint — i.e. persist a
        # token every sender treats as absent while flipping push on. Strip
        # at the contract layer and reject blanks with 422.
        stripped = value.strip()
        if not stripped:
            raise ValueError("device_token must contain non-whitespace characters")
        return stripped


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
@limiter.limit("30/minute")  # registration is client-initiated; keyed by client IP (PR-34), so clinics behind shared egress (Wi-Fi/proxy) need headroom for distinct authenticated users
async def register_fcm_token(  # P1-7: token ownership validated via current_user
    request: Request,
    payload: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Регистрация FCM токена пользователя"""
    try:
        # PR-5: the contract validator strips and rejects blank tokens, so
        # this value is non-empty and within the column width already.
        # PR-2: persist to existing User.device_token + new mobile metadata columns
        crud_user.update_user(
            db,
            user_id=current_user.id,
            user_data={
                "device_token": payload.device_token,
                "device_type": payload.device_type,
                "device_info": payload.device_info,
                "push_notifications_enabled": True,
            },
        )

        # PR-6: dual-write into the canonical multi-device registry. The
        # legacy column stays as the DEPRECATED mirror (last registration
        # wins) so every existing sender keeps working. Registry platforms
        # are android|web only — legacy "ios" registrations stay
        # mirror-only (documented transitional behavior; apkfinal removed
        # Firebase and no iOS push client exists).
        if payload.device_type in ("android", "web"):
            crud_push_device.register_device(
                db,
                user_id=current_user.id,
                provider="fcm",
                platform=payload.device_type,
                token=payload.device_token,
            )

        return {
            "success": True,
            "message": "FCM токен успешно зарегистрирован",
            "device_token": payload.device_token,
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
        # PR-6: capture the mirrored credential BEFORE clearing — the exact
        # registry row for THIS credential is invalidated; the user's other
        # registry devices stay untouched (device-level isolation).
        legacy_token = current_user.device_token

        # PR-2: clear device_token + mobile metadata (legacy global opt-out
        # contract preserved: this endpoint is the user's explicit
        # "turn push off" act in the single-device world).
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

        # PR-6: invalidate the exact registry credential that was mirrored.
        if legacy_token:
            crud_push_device.invalidate_active_credential(
                db, provider="fcm", token=legacy_token
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
        # Registry-based send: map each user token back to its owner(s) so a
        # canonical UNREGISTERED verdict can purge exactly those registry rows
        # (PR-5 codex rounds 4-5: the schema allows one token on several
        # accounts — a dead shared token must be cleared for ALL of them).
        # Directly supplied tokens have no registry linkage and are never
        # purged here.
        registry_owners_by_token: dict[str, list[int]] = {}

        # Получаем токены по user_ids (PR-2: device_token is the real column)
        if request.user_ids:
            users = crud_user.get_users_by_ids(db, user_ids=request.user_ids)
            for user in users:
                token = getattr(user, "device_token", None)
                push_on = getattr(user, "push_notifications_enabled", True)
                if token and push_on:
                    device_tokens.append(token)
                    registry_owners_by_token.setdefault(token, []).append(user.id)

        # Добавляем прямо указанные токены
        if request.device_tokens:
            device_tokens.extend(request.device_tokens)

        # PR-5 codex round 6: one physical device may be registered by several
        # accounts — fan out each unique token once while keeping every owner
        # mapped for the conditional cleanup.
        device_tokens = list(dict.fromkeys(device_tokens))

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

            if (
                not result.success
                and device_tokens[0] in registry_owners_by_token
                and is_unregistered_token_response(result)
            ):
                for owner_id in registry_owners_by_token[device_tokens[0]]:
                    crud_user.clear_device_token_if_unchanged(
                        db,
                        user_id=owner_id,
                        expected_token=device_tokens[0],
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

            for entry in result.get("results", []):
                if entry.get("success"):
                    continue
                failed_token = device_tokens[entry.get("token_index", -1)]
                for owner_id in registry_owners_by_token.get(failed_token, []):
                    if is_unregistered_token_response(
                        FCMResponse(
                            success=False,
                            error=entry.get("error"),
                            error_code=entry.get("error_code"),
                        )
                    ):
                        crud_user.clear_device_token_if_unchanged(
                            db,
                            user_id=owner_id,
                            expected_token=failed_token,
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

        if is_unregistered_token_response(result):
            # PR-5 codex round 4: registry-based send path — drop the dead
            # self token so subsequent sends stop targeting this device.
            crud_user.clear_device_token_if_unchanged(
                db,
                user_id=current_user.id,
                expected_token=current_user.device_token,
            )

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
