# CRUD для settings (Sync Session). Если у тебя Async CRUD — скажи, выдам async-версию.
from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.setting import Setting

def list_settings(db: Session, category: str, limit: int = 100, offset: int = 0) -> List[Setting]:
    q = db.query(Setting).filter(Setting.category == category)
    if offset:
        q = q.offset(offset)
    if limit:
        q = q.limit(limit)
    return q.all()

def get_setting(db: Session, category: str, key: str) -> Optional[Setting]:
    return (
        db.query(Setting)
        .filter(Setting.category == category, Setting.key == key)
        .first()
    )

def upsert_setting(db: Session, category: str, key: str, value: str) -> Setting:
    obj = get_setting(db, category, key)
    if obj:
        obj.value = value
    else:
        obj = Setting(category=category, key=key, value=value)
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def delete_setting(db: Session, category: str, key: str) -> bool:
    obj = get_setting(db, category, key)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True
