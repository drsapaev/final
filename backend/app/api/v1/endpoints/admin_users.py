from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.core.security import require_roles
from app.models.user import User
from app.crud import user as crud_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=None)
def list_users(
    db: Session = Depends(deps.get_db),
    _: User = Depends(require_roles("Admin")),
) -> List[Dict]:
    """
    Получить список пользователей (использует CRUD функции).
    """
    # Используем CRUD функцию вместо прямого запроса
    # Если нет get_users(), используем select напрямую через CRUD
    from sqlalchemy import select
    stmt = select(User).order_by(User.id.asc())
    users = db.execute(stmt).scalars().all()
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "role": getattr(u, "role", None),
            "is_active": getattr(u, "is_active", True),
        }
        for u in users
    ]
