from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

def _to_dict(u: User) -> Dict:
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
def get_user_by_username(db: Session, username: str) -> Optional[Dict]:
    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None

def get_user_by_id(db: Session, user_id: int) -> Optional[Dict]:
    stmt = select(User).where(User.id == user_id)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None

# === АСИНХРОННЫЕ ВАРИАНТЫ (для AsyncSession) ===
async def a_get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalars().first()

async def a_get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    res = await db.execute(select(User).where(User.id == user_id))
    return res.scalars().first()
