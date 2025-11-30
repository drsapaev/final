from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from jose import jwt
from passlib.context import CryptContext

# Настройки с дефолтами
try:
    from app.core.config import settings  # type: ignore

    SECRET_KEY: str = getattr(settings, "SECRET_KEY", "dev-secret-key-change-me")
    ALGORITHM: str = getattr(settings, "ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    )
except Exception:
    SECRET_KEY = "dev-secret-key-change-me"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Поддерживаем верификацию старых хэшей bcrypt, новые хешируем argon2
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, dict[str, Any]], expires_minutes: Optional[int] = None
) -> str:
    if expires_minutes is None:
        expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    if isinstance(subject, str):
        to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    else:
        to_encode = {**subject, "exp": expire}
        to_encode.setdefault(
            "sub", subject.get("username") or subject.get("id") or "user"
        )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ===================== ФУНКЦИИ ПРАВ ДОСТУПА (SSOT) =====================


def require_roles(*roles: str):
    """
    Dependency factory для проверки ролей (SSOT).

    Использование:
        @router.get("/secret")
        def secret(user=Depends(require_roles("Admin"))):
            ...

    Если роль пользователя не в списке roles и is_superuser=False -> 403.
    """
    from fastapi import Depends, HTTPException, status

    from app.api.deps import get_current_user
    from app.models.user import User

    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if not roles:
            return current_user

        role = getattr(current_user, "role", None)
        is_super = bool(getattr(current_user, "is_superuser", False))

        if is_super:
            return current_user

        # Проверяем роль с учетом регистра
        role_lower = str(role).lower() if role else ""
        allowed_roles_lower = [r.lower() for r in roles]

        if role_lower not in allowed_roles_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Доступ запрещен. Требуются роли: {', '.join(roles)}",
            )

        return current_user

    return _dep


def check_permission(user: Any, permission: str) -> bool:
    """
    Проверить разрешение пользователя (SSOT).

    Args:
        user: Объект пользователя
        permission: Разрешение для проверки (например, "read:patients", "create:appointments")

    Returns:
        True если разрешение есть, False если нет
    """
    from app.crud import user as crud_user

    # Получаем разрешения пользователя
    permissions = crud_user.get_user_permissions(user)

    # Проверяем конкретное разрешение
    return permission in permissions


def get_user_permissions(user: Any) -> list[str]:
    """
    Получить список разрешений пользователя (SSOT).

    Args:
        user: Объект пользователя

    Returns:
        Список разрешений пользователя
    """
    from app.crud import user as crud_user

    return crud_user.get_user_permissions(user)


def validate_role_transition(current_role: str, new_role: str) -> bool:
    """
    Валидация перехода ролей (SSOT).

    Args:
        current_role: Текущая роль
        new_role: Новая роль

    Returns:
        True если переход допустим, False если нет
    """
    # Запрещенные переходы
    forbidden_transitions = {
        "Admin": [],  # Админ не может быть изменен (кроме суперадмина)
    }

    # Если текущая роль в списке запрещенных для изменения
    if current_role in forbidden_transitions:
        return False

    # Разрешенные роли
    allowed_roles = [
        "Admin",
        "Doctor",
        "Registrar",
        "Cashier",
        "Lab",
        "Patient",
        "cardio",
        "derma",
        "dentist",
    ]

    # Проверяем, что новая роль разрешена
    if new_role not in allowed_roles:
        return False

    return True
