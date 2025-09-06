"""
CRUD операции для Telegram системы
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.telegram_config import TelegramConfig, TelegramTemplate, TelegramUser, TelegramMessage

# ===================== КОНФИГУРАЦИЯ =====================

def get_telegram_config(db: Session) -> Optional[TelegramConfig]:
    """Получить конфигурацию Telegram бота"""
    return db.query(TelegramConfig).first()

def create_telegram_config(db: Session, config_data: Dict[str, Any]) -> TelegramConfig:
    """Создать конфигурацию Telegram"""
    config = TelegramConfig(**config_data)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

def update_telegram_config(
    db: Session,
    config_data: Dict[str, Any]
) -> Optional[TelegramConfig]:
    """Обновить конфигурацию Telegram"""
    config = get_telegram_config(db)
    if not config:
        return None
    
    for field, value in config_data.items():
        if hasattr(config, field):
            setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    return config

# ===================== ШАБЛОНЫ =====================

def get_telegram_templates(
    db: Session,
    template_type: Optional[str] = None,
    language: Optional[str] = None,
    active_only: bool = True
) -> List[TelegramTemplate]:
    """Получить шаблоны сообщений"""
    query = db.query(TelegramTemplate)
    
    if template_type:
        query = query.filter(TelegramTemplate.template_type == template_type)
    
    if language:
        query = query.filter(TelegramTemplate.language == language)
    
    if active_only:
        query = query.filter(TelegramTemplate.active == True)
    
    return query.all()

def get_template_by_key(
    db: Session,
    template_key: str,
    language: str = "ru"
) -> Optional[TelegramTemplate]:
    """Получить шаблон по ключу"""
    return db.query(TelegramTemplate).filter(
        and_(
            TelegramTemplate.template_key == template_key,
            TelegramTemplate.language == language,
            TelegramTemplate.active == True
        )
    ).first()

def create_telegram_template(db: Session, template_data: Dict[str, Any]) -> TelegramTemplate:
    """Создать шаблон сообщения"""
    template = TelegramTemplate(**template_data)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

def update_telegram_template(
    db: Session,
    template_id: int,
    template_data: Dict[str, Any]
) -> Optional[TelegramTemplate]:
    """Обновить шаблон сообщения"""
    template = db.query(TelegramTemplate).filter(TelegramTemplate.id == template_id).first()
    if not template:
        return None
    
    for field, value in template_data.items():
        if hasattr(template, field):
            setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    return template

# ===================== ПОЛЬЗОВАТЕЛИ =====================

def get_telegram_user_by_chat_id(db: Session, chat_id: int) -> Optional[TelegramUser]:
    """Получить пользователя по chat_id"""
    return db.query(TelegramUser).filter(TelegramUser.chat_id == chat_id).first()

def get_telegram_users(
    db: Session,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100
) -> List[TelegramUser]:
    """Получить список пользователей Telegram"""
    query = db.query(TelegramUser)
    
    if active_only:
        query = query.filter(TelegramUser.active == True)
    
    return query.offset(skip).limit(limit).all()

def create_telegram_user(db: Session, user_data: Dict[str, Any]) -> TelegramUser:
    """Создать пользователя Telegram"""
    user = TelegramUser(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_telegram_user(
    db: Session,
    user_id: int,
    user_data: Dict[str, Any]
) -> Optional[TelegramUser]:
    """Обновить пользователя Telegram"""
    user = db.query(TelegramUser).filter(TelegramUser.id == user_id).first()
    if not user:
        return None
    
    for field, value in user_data.items():
        if hasattr(user, field):
            setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user

def link_patient_to_telegram(
    db: Session,
    chat_id: int,
    patient_id: int
) -> Optional[TelegramUser]:
    """Привязать пациента к Telegram аккаунту"""
    user = get_telegram_user_by_chat_id(db, chat_id)
    if user:
        user.patient_id = patient_id
        db.commit()
        db.refresh(user)
        return user
    return None

# ===================== СООБЩЕНИЯ =====================

def create_message_log(db: Session, message_data: Dict[str, Any]) -> TelegramMessage:
    """Создать лог сообщения"""
    message = TelegramMessage(**message_data)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message

def get_message_logs(
    db: Session,
    chat_id: Optional[int] = None,
    message_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TelegramMessage]:
    """Получить логи сообщений"""
    query = db.query(TelegramMessage)
    
    if chat_id:
        query = query.filter(TelegramMessage.chat_id == chat_id)
    
    if message_type:
        query = query.filter(TelegramMessage.message_type == message_type)
    
    return query.order_by(TelegramMessage.created_at.desc()).offset(skip).limit(limit).all()

# ===================== УВЕДОМЛЕНИЯ =====================

def get_users_for_notifications(
    db: Session,
    notification_type: str
) -> List[TelegramUser]:
    """Получить пользователей для уведомлений"""
    query = db.query(TelegramUser).filter(
        and_(
            TelegramUser.active == True,
            TelegramUser.blocked == False,
            TelegramUser.notifications_enabled == True
        )
    )
    
    if notification_type == "appointment_reminder":
        query = query.filter(TelegramUser.appointment_reminders == True)
    elif notification_type == "lab_results":
        query = query.filter(TelegramUser.lab_notifications == True)
    
    return query.all()

def find_patient_by_phone(db: Session, phone: str) -> Optional[Dict[str, Any]]:
    """Найти пациента по номеру телефона"""
    try:
        from app.models.patient import Patient
        patient = db.query(Patient).filter(Patient.phone == phone).first()
        
        if patient:
            return {
                "id": patient.id,
                "full_name": f"{patient.last_name} {patient.first_name} {patient.middle_name or ''}".strip(),
                "phone": patient.phone,
                "birth_date": patient.birth_date
            }
        return None
        
    except Exception as e:
        print(f"Ошибка поиска пациента: {e}")
        return None
