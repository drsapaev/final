from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(User).where(User.username == form_data.username))
    user = res.scalars().first()

    if user is None or not verify_password(form_data.password, getattr(user, "hashed_password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    token = create_access_token(subject=str(user.username))
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": getattr(current_user, "id", None),
        "username": getattr(current_user, "username", None),
        "full_name": getattr(current_user, "full_name", None),
        "email": getattr(current_user, "email", None),
        "is_active": getattr(current_user, "is_active", True),
        "is_superuser": getattr(current_user, "is_superuser", False),
    }
