"""
CRUD операции для шаблонов EMR
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.emr_template import EMRTemplate, EMRVersion
from app.schemas.emr_template import (
    EMRTemplateCreate,
    EMRTemplateUpdate,
    EMRVersionCreate,
)


class CRUDEMRTemplate(CRUDBase[EMRTemplate, EMRTemplateCreate, EMRTemplateUpdate]):
    """CRUD операции для шаблонов EMR"""

    def get_by_specialty(
        self, db: Session, *, specialty: str, is_active: bool = True
    ) -> List[EMRTemplate]:
        """Получить шаблоны по специализации"""
        query = db.query(self.model).filter(
            and_(
                self.model.specialty == specialty,
                self.model.is_active == is_active
            )
        )
        return query.order_by(self.model.name).all()

    def get_public_templates(
        self, db: Session, *, specialty: Optional[str] = None
    ) -> List[EMRTemplate]:
        """Получить публичные шаблоны"""
        query = db.query(self.model).filter(
            and_(
                self.model.is_public == True,
                self.model.is_active == True
            )
        )
        
        if specialty:
            query = query.filter(self.model.specialty == specialty)
            
        return query.order_by(self.model.specialty, self.model.name).all()

    def get_user_templates(
        self, db: Session, *, user_id: int, specialty: Optional[str] = None
    ) -> List[EMRTemplate]:
        """Получить шаблоны пользователя"""
        query = db.query(self.model).filter(
            and_(
                self.model.created_by == user_id,
                self.model.is_active == True
            )
        )
        
        if specialty:
            query = query.filter(self.model.specialty == specialty)
            
        return query.order_by(self.model.name).all()

    def create_from_structure(
        self, db: Session, *, structure: dict, created_by: int
    ) -> EMRTemplate:
        """Создать шаблон из структуры"""
        template_data = EMRTemplateCreate(
            name=structure.get("template_name", "Новый шаблон"),
            description=structure.get("description", ""),
            specialty=structure.get("specialty", "general"),
            template_structure=structure,
            created_by=created_by
        )
        return self.create(db, obj_in=template_data)

    def clone_template(
        self, db: Session, *, template_id: int, new_name: str, created_by: int
    ) -> EMRTemplate:
        """Клонировать шаблон"""
        original = self.get(db, id=template_id)
        if not original:
            raise ValueError("Шаблон не найден")
        
        clone_data = EMRTemplateCreate(
            name=new_name,
            description=f"Копия: {original.description or ''}",
            specialty=original.specialty,
            template_structure=original.template_structure,
            created_by=created_by,
            is_public=False  # Клоны по умолчанию приватные
        )
        return self.create(db, obj_in=clone_data)


class CRUDEMRVersion(CRUDBase[EMRVersion, EMRVersionCreate, None]):
    """CRUD операции для версий EMR"""

    def get_by_emr(
        self, db: Session, *, emr_id: int, limit: int = 50
    ) -> List[EMRVersion]:
        """Получить версии EMR"""
        return (
            db.query(self.model)
            .filter(self.model.emr_id == emr_id)
            .order_by(desc(self.model.version_number))
            .limit(limit)
            .all()
        )

    def get_latest_version(
        self, db: Session, *, emr_id: int
    ) -> Optional[EMRVersion]:
        """Получить последнюю версию EMR"""
        return (
            db.query(self.model)
            .filter(self.model.emr_id == emr_id)
            .order_by(desc(self.model.version_number))
            .first()
        )

    def create_version(
        self,
        db: Session,
        *,
        emr_id: int,
        version_data: dict,
        change_type: str,
        change_description: Optional[str] = None,
        changed_by: Optional[int] = None
    ) -> EMRVersion:
        """Создать новую версию EMR"""
        from datetime import datetime
        
        # Функция для преобразования datetime в ISO строки
        def convert_datetimes_to_iso(obj):
            """Рекурсивно преобразует все datetime объекты в ISO строки"""
            if isinstance(obj, dict):
                return {k: convert_datetimes_to_iso(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetimes_to_iso(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        # Преобразуем все datetime объекты в version_data в ISO строки
        version_data_clean = convert_datetimes_to_iso(version_data)
        
        # Получаем номер следующей версии
        latest = self.get_latest_version(db, emr_id=emr_id)
        next_version = (latest.version_number + 1) if latest else 1
        
        version_create = EMRVersionCreate(
            emr_id=emr_id,
            version_data=version_data_clean,
            version_number=next_version,
            change_type=change_type,
            change_description=change_description,
            changed_by=changed_by
        )
        return self.create(db, obj_in=version_create)

    def restore_version(
        self, db: Session, *, version_id: int, restored_by: int
    ) -> Optional[EMRVersion]:
        """Восстановить версию EMR"""
        version = self.get(db, id=version_id)
        if not version:
            return None
        
        # Создаем новую версию с данными из выбранной версии
        return self.create_version(
            db,
            emr_id=version.emr_id,
            version_data=version.version_data,
            change_type="restored",
            change_description=f"Восстановлено из версии {version.version_number}",
            changed_by=restored_by
        )


# Экземпляры CRUD
emr_template = CRUDEMRTemplate(EMRTemplate)
emr_version = CRUDEMRVersion(EMRVersion)
