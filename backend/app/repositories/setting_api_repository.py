"""Repository helpers for settings API endpoints."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.setting import Setting


class SettingApiRepository:
    """Encapsulates setting queries for API service layer."""

    def __init__(self, db: Session):
        self.db = db

    def list_by_category(
        self,
        *,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Setting]:
        stmt = (
            select(Setting)
            .where(Setting.category == category)
            .order_by(Setting.key.asc())
            .offset(offset)
            .limit(limit)
        )
        return self.db.execute(stmt).scalars().all()

    def upsert(
        self,
        *,
        category: str,
        key: str,
        value: str | None,
    ) -> Setting:
        stmt = select(Setting).where(
            Setting.category == category,
            Setting.key == key,
        )
        row = self.db.execute(stmt).scalar_one_or_none()
        if row is None:
            row = Setting(category=category, key=key, value=value)
            self.db.add(row)
        else:
            row.value = value

        self.db.commit()
        self.db.refresh(row)
        return row
