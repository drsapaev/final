from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic CRUD operations for SQLAlchemy models with Pydantic schemas."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    # Read
    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).get(id)

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    # Create
    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        data: Dict[str, Any] = obj_in.dict(exclude_unset=True)
        # ✅ ИСКЛЮЧАЕМ поля, которых нет в модели Patient
        # full_name используется только для нормализации ДО создания модели, но не сохраняется в БД
        # email не существует в модели Patient (есть только в схеме для валидации)
        fields_to_exclude = ["full_name", "email"]
        for field in fields_to_exclude:
            if field in data:
                del data[field]
        
        # ✅ ЗАЩИТА: Не сохраняем пустые значения для first_name и last_name
        # Это предотвращает случайную перезапись нормализованных данных пустыми строками
        protected_fields = ["first_name", "last_name"]
        for field in protected_fields:
            if field in data:
                value = data[field]
                # Если значение пустое или состоит только из пробелов - удаляем из данных
                # Валидатор схемы должен был это предотвратить, но это дополнительная защита
                if not value or not str(value).strip():
                    raise ValueError(f"Поле {field} не может быть пустым при создании пациента")
        
        db_obj = self.model(**data)  # type: ignore[arg-type]
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # Update
    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> ModelType:
        update_data: Dict[str, Any]
        if isinstance(obj_in, BaseModel):
            update_data = obj_in.dict(exclude_unset=True)
        else:
            update_data = dict(obj_in)
        
        # ✅ ЗАЩИТА: Не перезаписываем непустые first_name/last_name пустыми значениями
        # Это предотвращает случайную перезапись нормализованных данных пустыми строками
        protected_fields = ["first_name", "last_name"]
        for field in protected_fields:
            if field in update_data:
                new_value = update_data[field]
                current_value = getattr(db_obj, field, None)
                # Если новое значение пустое, а текущее не пустое - не перезаписываем
                if (not new_value or not str(new_value).strip()) and current_value and str(current_value).strip():
                    del update_data[field]

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    # Delete
    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        obj = db.query(self.model).get(id)
        if not obj:
            return None
        db.delete(obj)
        db.commit()
        return obj
