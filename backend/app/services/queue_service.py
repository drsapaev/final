"""
Сервис для бизнес-логики очереди
"""
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User


class QueueBusinessService:
    """Сервис для управления бизнес-логикой очереди"""
    
    # Стартовые номера по специальностям (согласно MASTER TODO LIST)
    SPECIALTY_START_NUMBERS = {
        "cardio": 1,      # Кардиолог - с №1
        "derma": 15,      # Дерматолог - с №15 
        "dental": 3,      # Стоматолог - с №3
        "general": 1,     # Общий врач - с №1
        "default": 1      # По умолчанию - с №1
    }
    
    # Время работы онлайн-записи
    ONLINE_QUEUE_START_TIME = time(7, 0)  # 07:00
    
    # Лимиты по умолчанию
    DEFAULT_MAX_SLOTS = 15
    
    @classmethod
    def get_start_number_for_specialist(cls, specialist: User) -> int:
        """Получить стартовый номер для специалиста"""
        # Определяем специальность по роли или другим атрибутам
        specialty = cls._determine_specialty(specialist)
        return cls.SPECIALTY_START_NUMBERS.get(specialty, cls.SPECIALTY_START_NUMBERS["default"])
    
    @classmethod
    def _determine_specialty(cls, specialist: User) -> str:
        """Определить специальность врача"""
        # Можно расширить логику определения специальности
        if hasattr(specialist, 'specialty'):
            return specialist.specialty.lower()
        
        # Пока используем роль или username
        username = specialist.username.lower()
        if 'cardio' in username or 'кардио' in username:
            return "cardio"
        elif 'derma' in username or 'дерма' in username:
            return "derma"
        elif 'dental' in username or 'стомат' in username:
            return "dental"
        else:
            return "general"
    
    @classmethod
    def check_queue_time_window(cls, target_date: date, queue_opened_at: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Проверить, доступна ли онлайн-запись по времени
        
        Returns:
            (is_allowed, message)
        """
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        
        if target_date < today:
            return False, "❌ QR код устарел. Обратитесь в регистратуру за новым кодом."
        
        if target_date == today:
            # Проверяем время для сегодняшнего дня
            if current_time < cls.ONLINE_QUEUE_START_TIME:
                return False, f"⏰ Онлайн-запись откроется в {cls.ONLINE_QUEUE_START_TIME.strftime('%H:%M')}. Текущее время: {current_time.strftime('%H:%M')}"
            
            if queue_opened_at:
                opened_time = queue_opened_at.strftime('%H:%M')
                return False, f"🚪 Прием уже открыт в {opened_time}. Онлайн-запись закрыта. Обратитесь в регистратуру."
        
        # Для будущих дней разрешаем запись
        return True, ""
    
    @classmethod
    def check_queue_limits(cls, db: Session, daily_queue: DailyQueue) -> Tuple[bool, str]:
        """
        Проверить лимиты очереди
        
        Returns:
            (is_allowed, message)
        """
        current_entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).count()
        
        max_slots = getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS
        
        if current_entries >= max_slots:
            return False, f"🚫 Достигнут лимит мест ({max_slots}). Обратитесь в регистратуру."
        
        return True, ""
    
    @classmethod
    def check_uniqueness(cls, db: Session, daily_queue: DailyQueue, phone: Optional[str] = None, 
                        telegram_id: Optional[str] = None) -> Tuple[Optional[OnlineQueueEntry], str]:
        """
        Проверить уникальность записи
        
        Returns:
            (existing_entry, duplicate_reason)
        """
        if not phone and not telegram_id:
            return None, ""
        
        # Проверяем по телефону
        if phone:
            phone_entry = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.phone == phone,
                OnlineQueueEntry.status.in_(["waiting", "called"])
            ).first()
            
            if phone_entry:
                return phone_entry, f"телефону {phone}"
        
        # Проверяем по Telegram ID
        if telegram_id:
            telegram_entry = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.telegram_id == telegram_id,
                OnlineQueueEntry.status.in_(["waiting", "called"])
            ).first()
            
            if telegram_entry:
                return telegram_entry, f"Telegram ID {telegram_id}"
        
        return None, ""
    
    @classmethod
    def calculate_next_number(cls, db: Session, daily_queue: DailyQueue) -> int:
        """Вычислить следующий номер в очереди"""
        current_entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).count()
        
        return daily_queue.start_number + current_entries
    
    @classmethod
    def get_queue_statistics(cls, db: Session, daily_queue: DailyQueue) -> Dict:
        """Получить статистику очереди"""
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id
        ).all()
        
        stats = {
            "total_entries": len(entries),
            "waiting": len([e for e in entries if e.status == "waiting"]),
            "called": len([e for e in entries if e.status == "called"]),
            "completed": len([e for e in entries if e.status == "completed"]),
            "cancelled": len([e for e in entries if e.status == "cancelled"]),
            "max_slots": getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS,
            "available_slots": max(0, (getattr(daily_queue, 'max_slots', None) or cls.DEFAULT_MAX_SLOTS) - len([e for e in entries if e.status in ["waiting", "called"]])),
            "is_open": daily_queue.opened_at is not None,
            "opened_at": daily_queue.opened_at.isoformat() if daily_queue.opened_at else None
        }
        
        return stats
    
    @classmethod
    def validate_queue_entry_data(cls, patient_name: str, phone: Optional[str] = None, 
                                 telegram_id: Optional[str] = None) -> Tuple[bool, str]:
        """Валидация данных записи в очередь"""
        if not patient_name or not patient_name.strip():
            return False, "❌ Укажите ваше ФИО"
        
        if not phone and not telegram_id:
            return False, "❌ Укажите телефон или Telegram ID"
        
        if phone:
            # Простая валидация телефона
            cleaned_phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            if not cleaned_phone.isdigit() or len(cleaned_phone) < 9:
                return False, "❌ Неверный формат телефона"
        
        return True, ""


# Глобальный экземпляр сервиса
queue_service = QueueBusinessService()

def get_queue_service() -> QueueBusinessService:
    """Получить экземпляр сервиса очереди"""
    return queue_service
