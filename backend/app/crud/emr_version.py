"""
CRUD операции для версий EMR
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.emr_version import EMRVersion
from app.schemas.emr_version import EMRVersionCreate, EMRVersionUpdate


def get_version(db: Session, version_id: int) -> Optional[EMRVersion]:
    """Получить версию EMR по ID"""
    return db.query(EMRVersion).filter(EMRVersion.id == version_id).first()


def get_versions_by_emr(db: Session, emr_id: int, limit: int = 100) -> List[EMRVersion]:
    """Получить все версии EMR"""
    return (
        db.query(EMRVersion)
        .filter(EMRVersion.emr_id == emr_id)
        .order_by(desc(EMRVersion.version_number))
        .limit(limit)
        .all()
    )


def get_current_version(db: Session, emr_id: int) -> Optional[EMRVersion]:
    """Получить текущую версию EMR"""
    return (
        db.query(EMRVersion)
        .filter(and_(EMRVersion.emr_id == emr_id, EMRVersion.is_current == True))
        .first()
    )


def create_version(db: Session, version_data: EMRVersionCreate) -> EMRVersion:
    """Создать новую версию EMR"""
    db_version = EMRVersion(**version_data.dict())
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    return db_version


def update_version(db: Session, version_id: int, version_data: EMRVersionUpdate) -> Optional[EMRVersion]:
    """Обновить версию EMR"""
    db_version = get_version(db, version_id)
    if not db_version:
        return None
    
    for field, value in version_data.dict(exclude_unset=True).items():
        setattr(db_version, field, value)
    
    db_version.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_version)
    return db_version


def delete_version(db: Session, version_id: int) -> bool:
    """Удалить версию EMR"""
    db_version = get_version(db, version_id)
    if not db_version:
        return False
    
    db.delete(db_version)
    db.commit()
    return True


def set_current_version(db: Session, emr_id: int, version_id: int) -> bool:
    """Установить текущую версию EMR"""
    # Снимаем флаг is_current со всех версий
    db.query(EMRVersion).filter(EMRVersion.emr_id == emr_id).update({"is_current": False})
    
    # Устанавливаем флаг для указанной версии
    db_version = get_version(db, version_id)
    if not db_version or db_version.emr_id != emr_id:
        return False
    
    db_version.is_current = True
    db.commit()
    return True


def get_next_version_number(db: Session, emr_id: int) -> int:
    """Получить следующий номер версии"""
    max_version = (
        db.query(EMRVersion.version_number)
        .filter(EMRVersion.emr_id == emr_id)
        .order_by(desc(EMRVersion.version_number))
        .first()
    )
    
    return (max_version[0] + 1) if max_version else 1


def get_versions_by_user(db: Session, user_id: int, limit: int = 50) -> List[EMRVersion]:
    """Получить версии по пользователю"""
    return (
        db.query(EMRVersion)
        .filter(EMRVersion.changed_by == user_id)
        .order_by(desc(EMRVersion.created_at))
        .limit(limit)
        .all()
    )


def get_versions_by_date_range(
    db: Session,
    date_from: datetime,
    date_to: datetime,
    limit: int = 100
) -> List[EMRVersion]:
    """Получить версии в диапазоне дат"""
    return (
        db.query(EMRVersion)
        .filter(and_(
            EMRVersion.created_at >= date_from,
            EMRVersion.created_at <= date_to
        ))
        .order_by(desc(EMRVersion.created_at))
        .limit(limit)
        .all()
    )
