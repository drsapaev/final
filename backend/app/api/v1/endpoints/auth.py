# app/api/v1/endpoints/auth.py
"""
Auth endpoints: /login (OAuth2 password form) and /me (current profile).

This implementation is defensive: it supports get_db() returning either an
AsyncSession (async DB) or a sync Session/sessionmaker. The DB calls are
dispatched either by awaiting (async) or via run_in_threadpool (sync).
"""
from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

# helpers from deps
from app.api.deps import create_access_token, get_current_user

# password verification helper (assumed present in project)
from app.core.security import verify_password

# Import your project's DB session factory / dependency
# get_db should be a dependency that yields either an AsyncSession or sync Session
from app.db.session import get_db

# ORM user model
from app.models.user import User

router = APIRouter()


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)
) -> Any:
    """
    OAuth2 password flow (token endpoint).

    Accepts form fields:
      - username
      - password
      - scope (ignored)
    Returns:
      {"access_token": "<jwt>", "token_type": "bearer"}

    Works with both async and sync SQLAlchemy sessions returned by get_db().
    """
    # build select statement
    stmt = select(User).where(User.username == form_data.username)

    # Detect whether db.execute is a coroutine function (AsyncSession) or sync Session
    execute_callable = getattr(db, "execute", None)
    if inspect.iscoroutinefunction(execute_callable):
        # AsyncSession: await directly
        result = await db.execute(stmt)
    else:
        # Sync Session: run in threadpool to avoid blocking event loop
        result = await run_in_threadpool(db.execute, stmt)

    # Try to extract user from result in a robust way
    user = None
    try:
        user = result.scalar_one_or_none()
    except Exception:
        try:
            # fallback for Result API
            user = result.scalars().first()
        except Exception:
            user = None

    if not user or not verify_password(
        form_data.password, getattr(user, "hashed_password", "")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT access token (create_access_token implemented in deps)
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=None)
async def me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user profile as plain JSON."""
    return {
        "id": getattr(current_user, "id", None),
        "username": getattr(current_user, "username", None),
        "full_name": getattr(current_user, "full_name", None),
        "email": getattr(current_user, "email", None),
        "role": getattr(current_user, "role", None),
        "is_active": getattr(current_user, "is_active", True),
        "is_superuser": getattr(current_user, "is_superuser", False),
    }
