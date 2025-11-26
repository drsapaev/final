"""
CRUD операции для фото дерматологии
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.dermatology_photos import DermatologyPhoto

def create_photo(db: Session, photo_data: Dict[str, Any]) -> DermatologyPhoto:
    """Создать запись о фото"""
    photo = DermatologyPhoto(**photo_data)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo

def get_photo(db: Session, photo_id: int) -> Optional[DermatologyPhoto]:
    """Получить фото по ID"""
    return db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.id == photo_id,
            DermatologyPhoto.is_active == True
        )
    ).first()

def get_patient_photos(
    db: Session,
    patient_id: int,
    category: Optional[str] = None
) -> List[DermatologyPhoto]:
    """Получить фото пациента"""
    query = db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.is_active == True
        )
    )
    
    if category:
        query = query.filter(DermatologyPhoto.category == category)
    
    return query.order_by(DermatologyPhoto.created_at.desc()).all()

def update_photo(
    db: Session,
    photo_id: int,
    photo_data: Dict[str, Any]
) -> Optional[DermatologyPhoto]:
    """Обновить фото"""
    photo = get_photo(db, photo_id)
    if not photo:
        return None
    
    for field, value in photo_data.items():
        if hasattr(photo, field):
            setattr(photo, field, value)
    
    db.commit()
    db.refresh(photo)
    return photo

def delete_photo(db: Session, photo_id: int) -> bool:
    """Удалить фото (мягкое удаление)"""
    photo = get_photo(db, photo_id)
    if not photo:
        return False
    
    photo.is_active = False
    db.commit()
    return True

def get_patient_photo_stats(db: Session, patient_id: int) -> Dict[str, Any]:
    """Получить статистику фото пациента"""
    # Общее количество фото
    total = db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.is_active == True
        )
    ).count()
    
    # Количество по категориям
    before = db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.category == "before",
            DermatologyPhoto.is_active == True
        )
    ).count()
    
    after = db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.category == "after",
            DermatologyPhoto.is_active == True
        )
    ).count()
    
    progress = db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.category == "progress",
            DermatologyPhoto.is_active == True
        )
    ).count()
    
    # Общий размер файлов
    total_size = db.query(func.sum(DermatologyPhoto.file_size)).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.is_active == True
        )
    ).scalar() or 0
    
    # Последняя загрузка
    last_upload = db.query(func.max(DermatologyPhoto.created_at)).filter(
        and_(
            DermatologyPhoto.patient_id == patient_id,
            DermatologyPhoto.is_active == True
        )
    ).scalar()
    
    return {
        "total": total,
        "before": before,
        "after": after,
        "progress": progress,
        "total_size": total_size,
        "last_upload": last_upload.isoformat() if last_upload else None
    }

def get_photos_by_category(
    db: Session,
    category: str,
    limit: int = 100,
    offset: int = 0
) -> List[DermatologyPhoto]:
    """Получить фото по категории"""
    return db.query(DermatologyPhoto).filter(
        and_(
            DermatologyPhoto.category == category,
            DermatologyPhoto.is_active == True
        )
    ).offset(offset).limit(limit).all()

def search_photos(
    db: Session,
    patient_id: Optional[int] = None,
    category: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[DermatologyPhoto]:
    """Поиск фото по параметрам"""
    query = db.query(DermatologyPhoto).filter(
        DermatologyPhoto.is_active == True
    )
    
    if patient_id:
        query = query.filter(DermatologyPhoto.patient_id == patient_id)
    
    if category:
        query = query.filter(DermatologyPhoto.category == category)
    
    if tags:
        # Поиск по тегам (через запятую)
        tag_list = [tag.strip() for tag in tags.split(',')]
        for tag in tag_list:
            query = query.filter(DermatologyPhoto.tags.contains(tag))
    
    return query.offset(offset).limit(limit).all()
