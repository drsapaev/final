"""Repository helpers for roles endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.role_permission import Role


class RolesApiRepository:
    """Encapsulates ORM operations for role management endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def list_roles(self, *, is_active: bool | None, is_system: bool | None) -> list[Role]:
        query = self.db.query(Role)
        if is_active is not None:
            query = query.filter(Role.is_active == is_active)
        if is_system is not None:
            query = query.filter(Role.is_system == is_system)
        return query.order_by(Role.level.desc()).all()

    def list_active_roles(self) -> list[Role]:
        return (
            self.db.query(Role)
            .filter(Role.is_active == True)  # noqa: E712
            .order_by(Role.level.desc())
            .all()
        )

    def get_role(self, role_id: int) -> Role | None:
        return self.db.query(Role).filter(Role.id == role_id).first()

    def get_role_by_name(self, name: str) -> Role | None:
        return self.db.query(Role).filter(Role.name == name).first()

    def create_role(self, role_data: dict) -> Role:
        role = Role(**role_data)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def save_role(self, role: Role) -> Role:
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete_role(self, role: Role) -> None:
        self.db.delete(role)
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
