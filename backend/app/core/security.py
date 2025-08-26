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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60))
except Exception:
    SECRET_KEY = "dev-secret-key-change-me"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, dict[str, Any]], expires_minutes: Optional[int] = None) -> str:
    if expires_minutes is None:
        expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    if isinstance(subject, str):
        to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    else:
        to_encode = {**subject, "exp": expire}
        to_encode.setdefault("sub", subject.get("username") or subject.get("id") or "user")
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
