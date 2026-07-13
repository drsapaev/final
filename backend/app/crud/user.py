from __future__ import annotations

from datetime import UTC, datetime, timedelta

from passlib.context import CryptContext
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def _to_dict(u: User) -> dict:
    return {
        "id": getattr(u, "id", None),
        "username": getattr(u, "username", None),
        "full_name": getattr(u, "full_name", None),
        "email": getattr(u, "email", None),
        "is_active": getattr(u, "is_active", True),
        "is_superuser": getattr(u, "is_superuser", False),
        "hashed_password": getattr(u, "hashed_password", None),
    }


# === СИНХРОННЫЕ ВАРИАНТЫ (если где-то используются) ===
def get_user_by_username(db: Session, username: str) -> dict | None:
    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None


def get_user_by_id(db: Session, user_id: int) -> dict | None:
    stmt = select(User).where(User.id == user_id)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None


# === АСИНХРОННЫЕ ВАРИАНТЫ (для AsyncSession) ===
async def a_get_user_by_username(db: AsyncSession, username: str) -> User | None:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalars().first()


async def a_get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    res = await db.execute(select(User).where(User.id == user_id))
    return res.scalars().first()


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===


def get_user_by_phone(db: Session, phone: str) -> User | None:
    """Получить пользователя по номеру телефона"""
    stmt = select(User).where(User.phone == phone)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_telegram_id(db: Session, telegram_id: str) -> User | None:
    """Получить пользователя по Telegram ID"""
    stmt = select(User).where(User.telegram_id == telegram_id)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, user_data: dict) -> User:
    """Создать нового пользователя"""
    # Хешируем пароль если он есть
    if "password" in user_data:
        user_data["hashed_password"] = pwd_context.hash(user_data.pop("password"))

    # Устанавливаем значения по умолчанию
    user_data.setdefault("is_active", True)
    user_data.setdefault("is_superuser", False)
    user_data.setdefault("created_at", datetime.now(UTC))

    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def verify_password(password: str, hashed_password: str) -> bool:
    """Проверить пароль"""
    return pwd_context.verify(password, hashed_password)


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Аутентификация пользователя"""
    user = get_user_by_username(db, username)
    if not user:
        return None

    # Если user - это словарь, получаем объект User
    if isinstance(user, dict):
        user_obj = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if not user_obj or not verify_password(password, user_obj.hashed_password):
            return None
        return user_obj

    if not verify_password(password, user.hashed_password):
        return None

    return user


def get_user_permissions(user: User) -> list[str]:
    """Получить разрешения пользователя"""
    permissions = []

    # Базовые разрешения для всех пользователей
    permissions.extend(["read:profile", "update:profile"])

    # Разрешения в зависимости от роли
    if user.role == "Admin":
        permissions.extend(
            [
                "read:all",
                "create:all",
                "update:all",
                "delete:all",
                "manage:users",
                "manage:appointments",
                "manage:patients",
                "view:analytics",
                "manage:settings",
            ]
        )
    elif user.role == "Doctor":
        permissions.extend(
            [
                "read:patients",
                "create:appointments",
                "update:appointments",
                "read:medical_records",
                "create:medical_records",
                "update:medical_records",
                "read:lab_results",
                "create:prescriptions",
            ]
        )
    elif user.role == "Patient":
        permissions.extend(
            [
                "read:own_appointments",
                "create:appointments",
                "read:own_medical_records",
                "read:own_lab_results",
                "read:own_payments",
            ]
        )
    elif user.role == "Registrar":
        permissions.extend(
            [
                "read:patients",
                "create:appointments",
                "update:appointments",
                "read:appointments",
                "manage:queue",
            ]
        )
    elif user.role == "Cashier":
        permissions.extend(
            [
                "read:appointments",
                "update:payments",
                "read:payments",
                "create:payments",
                "read:patients",
            ]
        )
    elif user.role == "Lab":
        permissions.extend(
            [
                "read:lab_tests",
                "create:lab_tests",
                "update:lab_tests",
                "read:lab_results",
                "create:lab_results",
                "update:lab_results",
            ]
        )

    return permissions


def create_access_token(data: dict) -> str:
    """Создать токен доступа"""
    import jwt

    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.AUTH_SECRET, algorithm=settings.AUTH_ALGORITHM
    )
    return encoded_jwt


def search_users(db: Session, query: str, limit: int = 10) -> list[User]:
    """
    Поиск пользователей по имени, телефону или email
    """
    search_pattern = f"%{query}%"

    stmt = (
        select(User)
        .where(
            or_(
                User.full_name.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.phone.ilike(search_pattern),
            )
        )
        .limit(limit)
    )

    result = db.execute(stmt)
    return result.scalars().all()


def get(db: Session, id: int) -> User | None:
    """Получить пользователя по ID"""
    return db.query(User).filter(User.id == id).first()


# === PR-2: FCM token management wrappers ===

# Whitelisted fields that update_user is allowed to set on the User model.
# Keep this explicit to prevent mass-assignment from arbitrary API payloads.
_USER_UPDATABLE_FIELDS: set[str] = {
    "device_token",
    "device_type",
    "device_info",
    "push_notifications_enabled",
    "full_name",
    "email",
    "is_active",
}


def update_user(db: Session, *, user_id: int, user_data: dict) -> User | None:
    """Update whitelisted fields on a User row.

    PR-2: Previously the FCM endpoints called a non-existent `crud_user.update_user`
    and crashed with HTTP 500. This wrapper accepts a partial dict and only
    writes attributes that exist on the User model and are in the whitelist.
    Returns the updated User, or None if the user was not found.
    """
    user = db.get(User, user_id)
    if user is None:
        return None
    for key, value in user_data.items():
        if key in _USER_UPDATABLE_FIELDS and hasattr(User, key):
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def get_users_by_ids(db: Session, *, user_ids: list[int]) -> list[User]:
    """Return Users whose id is in user_ids. PR-2: was missing, FCM endpoints crashed."""
    if not user_ids:
        return []
    stmt = select(User).where(User.id.in_(user_ids))
    return list(db.execute(stmt).scalars().all())


def get_users_with_fcm_tokens(db: Session) -> list[User]:
    """Return all Users that have a non-empty device_token. PR-2: was missing."""
    stmt = select(User).where(User.device_token.isnot(None)).where(
        User.device_token != ""
    )
    return list(db.execute(stmt).scalars().all())


# === PR-1: Mobile API wrappers ===

from app.models.user_profile import UserNotificationSettings, UserProfile

# Coarse endpoint keys → list of concrete UserNotificationSettings columns.
# PR-1 deliberately keeps a small, well-documented mapping; full granularity
# can be wired up once the mobile request schema is updated to use real
# column names.
_NOTIFICATION_KEY_MAP: dict[str, list[str]] = {
    "push_notifications": [
        "push_appointment_reminder",
        "push_appointment_cancellation",
        "push_appointment_confirmation",
    ],
    "sms_notifications": [
        "sms_appointment_reminder",
        "sms_appointment_cancellation",
        "sms_appointment_confirmation",
    ],
    "email_notifications": [
        "email_appointment_reminder",
        "email_appointment_cancellation",
        "email_appointment_confirmation",
    ],
    "appointment_reminders": [
        "push_appointment_reminder",
        "sms_appointment_reminder",
        "email_appointment_reminder",
    ],
    "lab_results_notifications": [
        "push_system_updates",
        "email_system_updates",
    ],
    "promotions_notifications": [
        "email_newsletter",
    ],
}


def _ensure_notification_settings(db: Session, user_id: int) -> UserNotificationSettings | None:
    """Return the user's UserNotificationSettings, creating linked
    UserProfile + UserNotificationSettings rows if they don't exist yet.
    Returns None only if the user itself is missing.
    """
    user = db.get(User, user_id)
    if user is None:
        return None

    profile = user.profile
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.flush()
        db.refresh(profile)

    settings = user.notification_settings
    if settings is None:
        settings = UserNotificationSettings(
            user_id=user.id,
            profile_id=profile.id,
        )
        db.add(settings)
        db.flush()
        db.refresh(settings)
    return settings


def update_notification_settings(
    db: Session,
    *,
    user_id: int,
    settings: dict[str, bool],
) -> None:
    """Map coarse mobile-app keys to concrete UserNotificationSettings columns
    and upsert the user's settings row. Unknown keys are ignored.
    """
    notif = _ensure_notification_settings(db, user_id)
    if notif is None:
        return
    for coarse_key, columns in _NOTIFICATION_KEY_MAP.items():
        if coarse_key not in settings:
            continue
        value = bool(settings[coarse_key])
        for col in columns:
            if hasattr(notif, col):
                setattr(notif, col, value)
    db.commit()


def get_notification_settings(
    db: Session,
    *,
    user_id: int,
) -> dict[str, bool]:
    """Load the user's notification settings and map concrete columns back
    to the coarse mobile-app keys. Returns defaults (all True except
    ``promotions_notifications`` which is False) if no row exists.
    """
    notif = _ensure_notification_settings(db, user_id)
    defaults: dict[str, bool] = {
        "push_notifications": True,
        "sms_notifications": True,
        "email_notifications": True,
        "appointment_reminders": True,
        "lab_results_notifications": True,
        "promotions_notifications": False,
    }
    if notif is None:
        return defaults
    result: dict[str, bool] = {}
    for coarse_key, columns in _NOTIFICATION_KEY_MAP.items():
        # Use the first mapped column's value as the representative for the
        # coarse key (PR-1 doesn't try to aggregate, to keep semantics simple).
        first_col = columns[0]
        result[coarse_key] = bool(getattr(notif, first_col, defaults[coarse_key]))
    return result
