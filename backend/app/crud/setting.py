from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.setting import Setting

def get_setting(db: Session, category: str, key: str) -> Optional[Setting]:
    return (
        db.query(Setting)
        .filter(Setting.category == category, Setting.key == key)
        .first()
    )

def upsert_setting(db: Session, category: str, key: str, value: str) -> Setting:
    """
    Безопасный upsert: всегда заполняем timestamps, чтобы не ловить NOT NULL.
    """
    obj = get_setting(db, category, key)
    now = datetime.utcnow()
    if obj:
        obj.value = value
        obj.updated_at = now
    else:
        obj = Setting(
            category=category,
            key=key,
            value=value,
            created_at=now,
            updated_at=now,
        )
        db.add(obj)

    db.commit()
    db.refresh(obj)
    return obj
