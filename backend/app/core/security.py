from __future__ import annotations

import importlib.metadata
import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import argon2 as _argon2
import jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

if "__version__" not in vars(_argon2):
    _argon2.__version__ = importlib.metadata.version("argon2-cffi")
    logger.debug("[FIX] Applied argon2 version shim for passlib compatibility")

# JWT configuration is owned by app.core.config and fails closed on invalid env.
from app.core.config import (  # noqa: E402  # manual-review: conditional import after config — intentional
    settings,  # type: ignore  # noqa: E402  # manual-review: conditional import after config — intentional
)

SECRET_KEY: str = settings.SECRET_KEY
ALGORITHM: str = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)

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
    subject: str | dict[str, Any], expires_minutes: int | None = None
) -> str:
    if expires_minutes is None:
        expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    if isinstance(subject, str):
        to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    else:
        to_encode = {**subject, "exp": expire}
        to_encode.setdefault(
            "sub", subject.get("username") or subject.get("id") or "user"
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _coerce_role_label(role: Any) -> str:
    """Normalize a role-like object to a trimmed string label."""
    if role is None:
        return ""

    if isinstance(role, Enum):
        role = role.value
    elif not isinstance(role, (str, bytes)) and hasattr(role, "value"):
        value = getattr(role, "value", None)
        if isinstance(value, str):
            role = value

    if isinstance(role, bytes):
        role = role.decode("utf-8", errors="ignore")

    return str(role).strip()


def _normalize_required_roles(*roles: Any) -> tuple[str, ...]:
    """Flatten and normalize role inputs while preserving legacy call styles."""
    normalized: list[str] = []
    for role in roles:
        if role is None:
            continue
        if isinstance(role, (list, tuple, set, frozenset)):
            nested_roles = tuple(role)
            nested_normalized = _normalize_required_roles(*nested_roles)
            if nested_normalized:
                logger.debug(
                    "[FIX:require_roles] Flattened nested role collection %s -> %s",
                    nested_roles,
                    nested_normalized,
                )
                normalized.extend(nested_normalized)
            continue

        role_label = _coerce_role_label(role)
        if role_label:
            normalized.append(role_label)

    return tuple(normalized)


# ===================== ФУНКЦИИ ПРАВ ДОСТУПА (SSOT) =====================


def require_roles(*roles: Any):
    """
    Dependency factory для проверки ролей (SSOT) с автоматическим логированием 403.

    Использование:
        @router.get("/secret")
        def secret(user=Depends(require_roles("Admin"))):
            ...

    Если роль пользователя не в списке roles и is_superuser=False -> 403 + audit log.
    """
    from fastapi import Depends, HTTPException, status

    from app.api.deps import get_current_user, get_db
    from app.middleware.audit_middleware import get_current_request
    from app.models.user import User

    def _dep(
        current_user: User = Depends(get_current_user),
        db = Depends(get_db),
    ) -> User:
        # Получаем Request из contextvar (установлен в AuditMiddleware)
        request = get_current_request()

        normalized_roles = _normalize_required_roles(*roles)
        logger.debug(
            "[FIX:require_roles] raw_roles=%s normalized_roles=%s user_role=%s",
            roles,
            normalized_roles,
            getattr(current_user, "role", None),
        )

        if not normalized_roles:
            return current_user

        role = getattr(current_user, "role", None)
        is_super = bool(getattr(current_user, "is_superuser", False))

        if is_super:
            return current_user

        # Проверяем роль с учетом регистра
        role_label = _coerce_role_label(role)
        role_lower = role_label.lower() if role_label else ""

        # ✅ ROLE NORMALIZATION: Map 'receptionist' to 'registrar' for compatibility
        # DB stores 'Receptionist' but API endpoints expect 'Registrar'
        role_normalized = role_lower
        if role_normalized == "receptionist":
            role_normalized = "registrar"

        allowed_roles_lower = [r.lower() for r in normalized_roles]
        # Also add 'receptionist' as allowed if 'registrar' is in allowed roles
        if "registrar" in allowed_roles_lower and "receptionist" not in allowed_roles_lower:
            allowed_roles_lower.append("receptionist")

        logger.debug(
            "RBAC role check evaluated",
            extra={
                "required_role_count": len(normalized_roles),
                "allowed_role_count": len(allowed_roles_lower),
                "user_role": role_label or None,
                "normalized_user_role": role_normalized or None,
                "request_available": request is not None,
            },
        )

        if role_normalized not in allowed_roles_lower and role_lower not in allowed_roles_lower:
            # ✅ AUDIT LOG: Логируем попытку несанкционированного доступа
            from app.core.audit import log_critical_change

            # Извлекаем resource_type из пути (если Request доступен)
            resource_type = None
            resource_id = None
            path_str = "unknown"
            method_str = "UNKNOWN"

            if request:
                path_parts = [p for p in request.url.path.split("/") if p]  # Убираем пустые части
                path_str = request.url.path
                method_str = request.method
                # Ищем /api/v1/{resource_type} или /api/v1/{resource_type}/{id}
                if len(path_parts) >= 3 and path_parts[0] == "api" and path_parts[1] == "v1":
                    resource_type = path_parts[2]  # /api/v1/{resource_type}
                if len(path_parts) >= 4 and path_parts[3].isdigit():
                    resource_id = int(path_parts[3])
            else:
                # ✅ FIX: Если request недоступен, логируем с предупреждением
                audit_logger = logging.getLogger(__name__)
                audit_logger.warning(
                    "ACCESS_DENIED audit request context unavailable",
                    extra={
                        "required_role_count": len(normalized_roles),
                        "user_role": role_label or None,
                    },
                )

            # Keep operational security logs non-identifying; the audit log below
            # stores actor/resource context through the dedicated audit channel.
            audit_logger = logging.getLogger(__name__)
            audit_logger.error(
                "RBAC role check denied",
                extra={
                    "required_roles": list(normalized_roles),
                    "allowed_roles": allowed_roles_lower,
                    "user_role": role_label or None,
                    "normalized_user_role": role_normalized or None,
                    "resource_type": resource_type or "unknown",
                    "resource_id_present": resource_id is not None,
                    "request_available": request is not None,
                },
            )

            # ✅ FIX: Всегда логируем 403, даже если request недоступен (для безопасности)
            try:
                log_critical_change(
                    db=db,
                    user_id=current_user.id,
                    action="ACCESS_DENIED",
                    table_name=resource_type or "unknown",
                    row_id=resource_id,
                    old_data=None,
                    new_data={
                        "required_roles": list(normalized_roles),
                        "user_role": role,
                        "request_available": request is not None,
                    },
                    request=request,  # Может быть None
                    description=f"403 Forbidden: {method_str} {path_str} - требуется роль: {', '.join(normalized_roles)}, текущая роль: {role_label}",
                )
                db.commit()
            except Exception as e:
                # ✅ FIX: Если логирование не удалось, все равно выбрасываем 403
                audit_logger = logging.getLogger(__name__)
                audit_logger.error(
                    "Failed to log ACCESS_DENIED audit",
                    extra={"exception_type": type(e).__name__},
                    exc_info=True,
                )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Доступ запрещен. Требуются роли: {', '.join(normalized_roles)}",
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
