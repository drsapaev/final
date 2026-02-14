from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.core.security import require_roles
from app.models.user import User
from app.services.admin_users_service import AdminUsersService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=None)
def list_users(
    db: Session = Depends(deps.get_db),
    _: User = Depends(require_roles("Admin")),
) -> list[dict]:
    """
    Получить список пользователей (использует CRUD функции).
    """
    return AdminUsersService(db).list_users()
