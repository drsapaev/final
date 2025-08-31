from __future__ import annotations

from typing import List, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=None)
def list_users(
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.require_roles("Admin")),
) -> List[Dict]:
    rows = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "role": getattr(u, "role", None),
            "is_active": getattr(u, "is_active", True),
        }
        for u in rows
    ]


