"""Repository helpers for settings API endpoints."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import Setting


class SettingApiRepository:
    """Encapsulates setting queries for API service layer."""

    def __init__(self, db: Session):
        self.db = db

    def list_by_category(self, *, category: str) -> list[Setting]:
        stmt = select(Setting).where(Setting.category == category)
        return self.db.execute(stmt).scalars().all()
