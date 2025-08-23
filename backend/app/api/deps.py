# app/api/deps.py
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Annotated, Optional, Dict, Any, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

# app/api/deps.py
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Union
from fastapi import Depends, HTTPException, status

# только для тайпчека — чтобы не плодить циклические импорты в рантайме
if TYPE_CHECKING:
    from app.models.user import User  # noqa: F401


def _role_to_str(val: Union[str, Enum, None]) -> str:
    """Приводим роль к строке ('Admin', 'User', ...), чтобы честно сравнивать."""
    if val is None:
        return ""
    if isinstance(val, Enum):
        # если Enum наследуется от str — вернётся value, иначе — имя члена
        return val.value if isinstance(val.value, str) else val.name
    return str(val)


def require_roles(*allowed: Union[str, Enum]):
    """
    Использование:
      @router.post("/open", dependencies=[Depends(require_roles("Admin", "Registrar"))])
      или
      def handler(..., _=Depends(require_roles("Admin"))): ...
    """
    allowed_norm = { _role_to_str(x) for x in allowed }

    def _dep(current_user=Depends(get_current_user)):  # type: ignore[name-defined]
        role_now = _role_to_str(getattr(current_user, "role", None))
        if role_now not in allowed_norm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: role not allowed",
            )
        return current_user  # удобно, если хэндлеру нужен сам пользователь

    return _dep


# --- Конфиг (мягкий импорт settings + безопасные дефолты из ENV) ---
try:
    # Если у вас есть app.core.config.settings — используем его
    from app.core.config import settings  # type: ignore[attr-defined]

    AUTH_SECRET = getattr(settings, "AUTH_SECRET", os.getenv("JWT_SECRET", "dev-secret"))
    AUTH_ALGORITHM = getattr(settings, "AUTH_ALGORITHM", os.getenv("JWT_ALG", "HS256"))
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", os.getenv("JWT_TTL", "7200"))
    )
except Exception:
    # Фолбэк на переменные окружения
    AUTH_SECRET = os.getenv("JWT_SECRET", "dev-secret")
    AUTH_ALGORITHM = os.getenv("JWT_ALG", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_TTL", "7200"))

API_V1_STR = os.getenv("API_V1_STR", "/api/v1")

# --- DB session dependency ---
from app.db.session import SessionLocal  # оставьте ваш путь, если отличается


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        try:
            db.close()
        except Exception:
            pass


# --- OAuth2 Password flow ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_STR}/auth/login")


# --- JWT helpers ---
def create_access_token(
    subject: str | int,
    *,
    expires_minutes: int | None = None,
    extra: Optional[dict] = None,
) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=int(expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: Dict[str, Any] = {"exp": expire, "sub": str(subject)}
    if extra:
        to_encode.update(extra)
    token = jwt.encode(to_encode, AUTH_SECRET, algorithm=AUTH_ALGORITHM)
    return token


def _decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, AUTH_SECRET, algorithms=[AUTH_ALGORITHM])


# --- CRUD пользователей (через ваши функции) ---
from app.crud.user import (  # type: ignore[attr-defined]
    get_user_by_id,
    get_user_by_username,
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Dict[str, Any]:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = _decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise cred_exc

        user: Optional[Dict[str, Any]] = None
        if str(sub).isdigit():
            user = get_user_by_id(db, int(sub))
        if not user:
            user = get_user_by_username(db, str(sub))

        if not user:
            raise cred_exc
    except JWTError:
        raise cred_exc

    if not user.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def require_roles(*roles: str):
    """Зависимость: пропускает только пользователей с нужными ролями."""
    async def _dep(user: Annotated[Dict[str, Any], Depends(get_current_user)]):
        role = (user.get("role") or "").strip()
        if roles and role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden: role not allowed")
        return user

    return _dep
