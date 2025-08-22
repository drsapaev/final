from __future__ import annotations

from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def _to_dict(u: User) -> Dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "is_active": bool(u.is_active),
        "hashed_password": u.hashed_password,
    }


def get_user_by_username(db: Session, username: str) -> Optional[Dict]:
    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None


def get_user_by_id(db: Session, user_id: int) -> Optional[Dict]:
    stmt = select(User).where(User.id == user_id)
    user = db.execute(stmt).scalar_one_or_none()
    return _to_dict(user) if user else None
