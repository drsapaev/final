# app/api/deps.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User

settings = get_settings()

# tokenUrl — это путь твоей ручки логина
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": str(subject), "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise cred_exc
    except JWTError:
        raise cred_exc

    # поддержим sub = id или sub = username
    user: User | None
    if sub.isdigit():
        user = db.get(User, int(sub))
    else:
        user = db.query(User).filter(User.username == sub).first()

    if not user or not user.is_active:
        raise cred_exc
    return user


def require_roles(*roles: str) -> Callable[[User], bool]:
    def _dep(user: User = Depends(get_current_user)) -> bool:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden: role not allowed")
        return True
    return _dep
