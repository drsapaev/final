"""
CRUD операции для управления клиникой в админ панели
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.clinic import ClinicSettings, Doctor, Schedule, ServiceCategory
from app.models.service import Service
from app.schemas.clinic import (
    ClinicSettingsCreate, ClinicSettingsUpdate,
    DoctorCreate, DoctorUpdate,
    ScheduleCreate, ScheduleUpdate,
    ServiceCategoryCreate, ServiceCategoryUpdate
)


# ===================== НАСТРОЙКИ КЛИНИКИ =====================

def get_settings_by_category(db: Session, category: str) -> List[ClinicSettings]:
    """Получить настройки по категории"""
    return db.query(ClinicSettings).filter(ClinicSettings.category == category).all()


def get_setting_by_key(db: Session, key: str) -> Optional[ClinicSettings]:
    """Получить настройку по ключу"""
    return db.query(ClinicSettings).filter(ClinicSettings.key == key).first()


def create_setting(db: Session, setting: ClinicSettingsCreate, user_id: int) -> ClinicSettings:
    """Создать настройку"""
    db_setting = ClinicSettings(
        **setting.model_dump(),
        updated_by=user_id
    )
    db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting


def update_setting(db: Session, key: str, setting: ClinicSettingsUpdate, user_id: int) -> Optional[ClinicSettings]:
    """Обновить настройку"""
    db_setting = get_setting_by_key(db, key)
    if not db_setting:
        return None
    
    for field, value in setting.model_dump(exclude_unset=True).items():
        setattr(db_setting, field, value)
    
    db_setting.updated_by = user_id
    db.commit()
    db.refresh(db_setting)
    return db_setting


def update_settings_batch(db: Session, category: str, settings: Dict[str, Any], user_id: int) -> List[ClinicSettings]:
    """Массовое обновление настроек"""
    updated_settings = []
    
    for key, value in settings.items():
        # Проверяем существование настройки
        db_setting = db.query(ClinicSettings).filter(ClinicSettings.key == key).first()
        
        if db_setting:
            # Обновляем существующую
            db_setting.value = value
            db_setting.updated_by = user_id
        else:
            # Создаем новую
            db_setting = ClinicSettings(
                key=key,
                value=value,
                category=category,
                updated_by=user_id
            )
            db.add(db_setting)
        
        updated_settings.append(db_setting)
    
    db.commit()
    for setting in updated_settings:
        db.refresh(setting)
    
    return updated_settings


# ===================== ВРАЧИ =====================

def get_doctors(db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Doctor]:
    """Получить список врачей"""
    query = db.query(Doctor)
    
    if active_only:
        query = query.filter(Doctor.active == True)
    
    return query.offset(skip).limit(limit).all()


def get_doctor_by_id(db: Session, doctor_id: int) -> Optional[Doctor]:
    """Получить врача по ID"""
    return db.query(Doctor).filter(Doctor.id == doctor_id).first()


def get_doctor_by_user_id(db: Session, user_id: int) -> Optional[Doctor]:
    """Получить врача по ID пользователя"""
    return db.query(Doctor).filter(Doctor.user_id == user_id).first()


def get_doctors_by_specialty(db: Session, specialty: str) -> List[Doctor]:
    """Получить врачей по специальности"""
    return db.query(Doctor).filter(
        and_(Doctor.specialty == specialty, Doctor.active == True)
    ).all()


def create_doctor(db: Session, doctor: DoctorCreate) -> Doctor:
    """Создать врача"""
    db_doctor = Doctor(**doctor.model_dump())
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor


def update_doctor(db: Session, doctor_id: int, doctor: DoctorUpdate) -> Optional[Doctor]:
    """Обновить врача"""
    db_doctor = get_doctor_by_id(db, doctor_id)
    if not db_doctor:
        return None
    
    for field, value in doctor.model_dump(exclude_unset=True).items():
        setattr(db_doctor, field, value)
    
    db.commit()
    db.refresh(db_doctor)
    return db_doctor


def delete_doctor(db: Session, doctor_id: int) -> bool:
    """Удалить врача (мягкое удаление)"""
    db_doctor = get_doctor_by_id(db, doctor_id)
    if not db_doctor:
        return False
    
    db_doctor.active = False
    db.commit()
    return True


# ===================== РАСПИСАНИЯ =====================

def get_doctor_schedules(db: Session, doctor_id: int) -> List[Schedule]:
    """Получить расписание врача"""
    return db.query(Schedule).filter(
        and_(Schedule.doctor_id == doctor_id, Schedule.active == True)
    ).order_by(Schedule.weekday).all()


def create_schedule(db: Session, schedule: ScheduleCreate) -> Schedule:
    """Создать расписание"""
    db_schedule = Schedule(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def update_schedule(db: Session, schedule_id: int, schedule: ScheduleUpdate) -> Optional[Schedule]:
    """Обновить расписание"""
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        return None
    
    for field, value in schedule.model_dump(exclude_unset=True).items():
        setattr(db_schedule, field, value)
    
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


def update_weekly_schedule(db: Session, doctor_id: int, schedules: List[Dict]) -> List[Schedule]:
    """Обновить недельное расписание врача"""
    # Деактивируем старые расписания
    db.query(Schedule).filter(Schedule.doctor_id == doctor_id).update({"active": False})
    
    # Создаем новые
    new_schedules = []
    for schedule_data in schedules:
        db_schedule = Schedule(
            doctor_id=doctor_id,
            **schedule_data
        )
        db.add(db_schedule)
        new_schedules.append(db_schedule)
    
    db.commit()
    for schedule in new_schedules:
        db.refresh(schedule)
    
    return new_schedules


def delete_schedule(db: Session, schedule_id: int) -> bool:
    """Удалить расписание"""
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        return False
    
    db_schedule.active = False
    db.commit()
    return True


# ===================== КАТЕГОРИИ УСЛУГ =====================

def get_service_categories(db: Session, specialty: Optional[str] = None, active_only: bool = True) -> List[ServiceCategory]:
    """Получить категории услуг"""
    query = db.query(ServiceCategory)
    
    if specialty:
        query = query.filter(ServiceCategory.specialty == specialty)
    
    if active_only:
        query = query.filter(ServiceCategory.active == True)
    
    return query.all()


def get_service_category_by_id(db: Session, category_id: int) -> Optional[ServiceCategory]:
    """Получить категорию по ID"""
    return db.query(ServiceCategory).filter(ServiceCategory.id == category_id).first()


def get_service_category_by_code(db: Session, code: str) -> Optional[ServiceCategory]:
    """Получить категорию по коду"""
    return db.query(ServiceCategory).filter(ServiceCategory.code == code).first()


def create_service_category(db: Session, category: ServiceCategoryCreate) -> ServiceCategory:
    """Создать категорию услуг"""
    db_category = ServiceCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_service_category(db: Session, category_id: int, category: ServiceCategoryUpdate) -> Optional[ServiceCategory]:
    """Обновить категорию услуг"""
    db_category = get_service_category_by_id(db, category_id)
    if not db_category:
        return None
    
    for field, value in category.model_dump(exclude_unset=True).items():
        setattr(db_category, field, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category


def delete_service_category(db: Session, category_id: int) -> bool:
    """Удалить категорию (мягкое удаление)"""
    db_category = get_service_category_by_id(db, category_id)
    if not db_category:
        return False
    
    db_category.active = False
    db.commit()
    return True


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def get_queue_settings(db: Session) -> Dict[str, Any]:
    """Получить настройки очередей"""
    settings = get_settings_by_category(db, "queue")
    
    result = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
        "start_numbers": {},
        "max_per_day": {}
    }
    
    for setting in settings:
        if setting.key == "timezone":
            result["timezone"] = setting.value
        elif setting.key == "queue_start_hour":
            result["queue_start_hour"] = setting.value
        elif setting.key == "auto_close_time":
            result["auto_close_time"] = setting.value
        elif setting.key.startswith("start_number_"):
            specialty = setting.key.replace("start_number_", "")
            result["start_numbers"][specialty] = setting.value
        elif setting.key.startswith("max_per_day_"):
            specialty = setting.key.replace("max_per_day_", "")
            result["max_per_day"][specialty] = setting.value
    
    return result


def update_queue_settings(db: Session, settings: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Обновить настройки очередей"""
    updates = {}
    
    # Базовые настройки
    if "timezone" in settings:
        updates["timezone"] = settings["timezone"]
    if "queue_start_hour" in settings:
        updates["queue_start_hour"] = settings["queue_start_hour"]
    if "auto_close_time" in settings:
        updates["auto_close_time"] = settings["auto_close_time"]
    
    # Стартовые номера по специальностям
    if "start_numbers" in settings:
        for specialty, number in settings["start_numbers"].items():
            updates[f"start_number_{specialty}"] = number
    
    # Лимиты по специальностям
    if "max_per_day" in settings:
        for specialty, limit in settings["max_per_day"].items():
            updates[f"max_per_day_{specialty}"] = limit
    
    # Массовое обновление
    update_settings_batch(db, "queue", updates, user_id)
    
    return get_queue_settings(db)
