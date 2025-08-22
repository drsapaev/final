from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.setting import Setting  # type: ignore[attr-defined]


def list_settings(
    db: Session,
    *,
    category: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Setting]:
    stmt = select(Setting)
    if category:
        stmt = stmt.where(Setting.category == category)
    stmt = stmt.order_by(Setting.category, Setting.key).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def upsert_setting(
    db: Session,
    *,
    category: str,
    key: str,
    value: Optional[str],
) -> Setting:
    row = (
        db.execute(
            select(Setting).where(and_(Setting.category == category, Setting.key == key))
        )
        .scalars()
        .first()
    )
    if row:
        row.value = value
        db.flush()
        return row
    row = Setting(category=category, key=key, value=value)
    db.add(row)
    db.flush()
    return row


def delete_setting(db: Session, *, category: str, key: str) -> bool:
    row = (
        db.execute(
            select(Setting).where(and_(Setting.category == category, Setting.key == key))
        )
        .scalars()
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.flush()
    return True