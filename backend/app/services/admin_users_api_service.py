from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.core.security import require_roles
from app.models.user import User
from app.repositories.admin_users_api_repository import AdminUsersApiRepository

router = APIRouter(prefix="/admin", tags=["admin"])



def _repo(db: Session) -> AdminUsersApiRepository:
    return AdminUsersApiRepository(db)

@router.get("/users", response_model=None)
def list_users(
    db: Session = Depends(deps.get_db),
    _: User = Depends(require_roles("Admin")),
) -> list[dict]:
    """
    Получить список пользователей (использует CRUD функции).
    """
    # Используем CRUD функцию вместо прямого запроса
    # Если нет get_users(), используем select напрямую через CRUD
    from sqlalchemy import select

    stmt = select(User).order_by(User.id.asc())
    users = _repo(db).execute(stmt).scalars().all()

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

