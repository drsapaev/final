from __future__ import annotations

from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.schemas.user import UserOut

# Зависимости проекта
from app.api.deps import create_access_token, get_db, get_current_user
from app.crud.user import get_user_by_username  # type: ignore[attr-defined]

try:
    from passlib.hash import bcrypt  # pragma: no cover
except Exception:  # pragma: no cover
    bcrypt = None  # type: ignore


# ВНИМАНИЕ: префикс "/auth" задаётся в api_router.include_router(..., prefix="/auth")
router = APIRouter(tags=["auth"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _verify_password(plain: str, hashed_or_plain: str) -> bool:
    """Поддерживаем как bcrypt-хэши, так и dev-пароли в открытом виде."""
    if not hashed_or_plain:
        return False
    if bcrypt and str(hashed_or_plain).startswith("$2"):
        try:
            return bool(bcrypt.verify(plain, hashed_or_plain))
        except Exception:
            return False
    return plain == hashed_or_plain


@router.post("/login", response_model=TokenOut, summary="Логин (OAuth2 Password)")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),  # требует python-multipart
    db: Session = Depends(get_db),
) -> TokenOut:
    user: Optional[Dict[str, Any]] = get_user_by_username(db, form.username)
    if not user or not _verify_password(form.password, user.get("hashed_password") or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    subject = user.get("id") or user.get("username")
    token = create_access_token(subject)
    return TokenOut(access_token=token)

@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user