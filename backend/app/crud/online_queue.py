"""
CRUD операции для онлайн-очереди согласно detail.md стр. 224-257
"""
import uuid
from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from zoneinfo import ZoneInfo

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.clinic import Doctor
from app.crud.clinic import get_queue_settings


# ===================== ГЕНЕРАЦИЯ QR ТОКЕНОВ =====================

def generate_qr_token(
    db: Session, 
    day: date, 
    specialist_id: int,
    user_id: Optional[int] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Генерация QR токена для онлайн-очереди
    Из detail.md стр. 228: POST /api/online-queue/qrcode?day=YYYY-MM-DD&specialist_id=X → token
    """
    
    # Проверяем существование врача
    doctor = db.query(Doctor).filter(
        and_(Doctor.id == specialist_id, Doctor.active == True)
    ).first()
    
    if not doctor:
        raise ValueError(f"Врач с ID {specialist_id} не найден или неактивен")
    
    # Проверяем что дата не в прошлом
    if day < date.today():
        raise ValueError("Нельзя создать токен для прошедшей даты")
    
    # Получаем настройки очереди
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
    
    # Создаем или получаем дневную очередь
    daily_queue = db.query(DailyQueue).filter(
        and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id)
    ).first()
    
    if not daily_queue:
        daily_queue = DailyQueue(
            day=day,
            specialist_id=specialist_id,
            active=True
        )
        db.add(daily_queue)
        db.commit()
        db.refresh(daily_queue)
    
    # Генерируем уникальный токен
    token = str(uuid.uuid4())
    
    # Вычисляем срок действия токена (до конца дня)
    expires_at = datetime.combine(day, time(23, 59, 59))
    expires_at = timezone.localize(expires_at)
    
    # Сохраняем токен
    queue_token = QueueToken(
        token=token,
        day=day,
        specialist_id=specialist_id,
        generated_by_user_id=user_id,
        expires_at=expires_at,
        active=True
    )
    db.add(queue_token)
    db.commit()
    
    # Формируем ответ
    current_count = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == daily_queue.id).count()
    max_slots = queue_settings.get("max_per_day", {}).get(doctor.specialty, 15)
    
    return token, {
        "specialist_name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
        "specialty": doctor.specialty,
        "cabinet": doctor.cabinet,
        "day": day,
        "start_time": f"{queue_settings.get('queue_start_hour', 7)}:00",
        "max_slots": max_slots,
        "current_count": current_count,
        "queue_id": daily_queue.id
    }


# ===================== ВСТУПЛЕНИЕ В ОЧЕРЕДЬ =====================

def join_online_queue(
    db: Session,
    token: str,
    phone: Optional[str] = None,
    telegram_id: Optional[int] = None,
    patient_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Вступление в онлайн-очередь
    Из detail.md стр. 235: POST /api/online-queue/join { token, phone?, telegram_id? } → номер
    """
    
    # Проверяем токен
    queue_token = db.query(QueueToken).filter(
        and_(QueueToken.token == token, QueueToken.active == True)
    ).first()
    
    if not queue_token:
        return {
            "success": False,
            "error_code": "INVALID_TOKEN",
            "message": "Неверный или истекший токен QR кода"
        }
    
    # Проверяем срок действия токена
    if datetime.utcnow() > queue_token.expires_at.replace(tzinfo=None):
        return {
            "success": False,
            "error_code": "TOKEN_EXPIRED", 
            "message": "Срок действия QR кода истек"
        }
    
    # Получаем дневную очередь
    daily_queue = db.query(DailyQueue).filter(
        and_(
            DailyQueue.day == queue_token.day,
            DailyQueue.specialist_id == queue_token.specialist_id,
            DailyQueue.active == True
        )
    ).first()
    
    if not daily_queue:
        return {
            "success": False,
            "error_code": "QUEUE_NOT_FOUND",
            "message": "Очередь не найдена"
        }
    
    # Проверяем что очередь еще не открыта (opened_at == None)
    if daily_queue.opened_at:
        return {
            "success": False,
            "error_code": "QUEUE_CLOSED",
            "message": "Онлайн-набор закрыт. Обратитесь в регистратуру.",
            "queue_closed": True
        }
    
    # Получаем настройки очереди
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
    
    # Проверяем рабочие часы (с 07:00)
    current_time = datetime.now(timezone)
    queue_start_hour = queue_settings.get("queue_start_hour", 7)
    
    if current_time.hour < queue_start_hour:
        return {
            "success": False,
            "error_code": "OUTSIDE_HOURS",
            "message": f"Онлайн-запись доступна с {queue_start_hour}:00",
            "outside_hours": True
        }
    
    # Проверяем дубликат по телефону или telegram_id
    existing_entry = None
    if phone:
        existing_entry = db.query(OnlineQueueEntry).filter(
            and_(OnlineQueueEntry.queue_id == daily_queue.id, OnlineQueueEntry.phone == phone)
        ).first()
    elif telegram_id:
        existing_entry = db.query(OnlineQueueEntry).filter(
            and_(OnlineQueueEntry.queue_id == daily_queue.id, OnlineQueueEntry.telegram_id == telegram_id)
        ).first()
    
    if existing_entry:
        # Возвращаем существующий номер
        return {
            "success": True,
            "number": existing_entry.number,
            "duplicate": True,
            "message": f"Вы уже записаны под номером {existing_entry.number}",
            "specialist_name": queue_token.specialist.user.full_name if queue_token.specialist.user else "Врач",
            "cabinet": queue_token.specialist.cabinet
        }
    
    # Проверяем лимит мест
    current_count = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == daily_queue.id).count()
    max_slots = queue_settings.get("max_per_day", {}).get(queue_token.specialist.specialty, 15)
    
    if current_count >= max_slots:
        return {
            "success": False,
            "error_code": "QUEUE_FULL",
            "message": f"Все места заняты ({max_slots}/{max_slots})",
            "queue_full": True
        }
    
    # Вычисляем номер в очереди
    start_number = queue_settings.get("start_numbers", {}).get(queue_token.specialist.specialty, 1)
    next_number = start_number + current_count
    
    # Создаем запись в очереди
    queue_entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=next_number,
        patient_name=patient_name,
        phone=phone,
        telegram_id=telegram_id,
        source="online",
        status="waiting"
    )
    db.add(queue_entry)
    
    # Увеличиваем счетчик использования токена
    queue_token.usage_count += 1
    
    db.commit()
    db.refresh(queue_entry)
    
    return {
        "success": True,
        "number": queue_entry.number,
        "duplicate": False,
        "message": f"Ваш номер в очереди: {queue_entry.number}",
        "specialist_name": queue_token.specialist.user.full_name if queue_token.specialist.user else "Врач",
        "cabinet": queue_token.specialist.cabinet,
        "estimated_time": f"Примерно в {queue_start_hour + 2}:00"
    }


# ===================== ОТКРЫТИЕ ПРИЕМА =====================

def open_daily_queue(
    db: Session,
    day: date,
    specialist_id: int,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Открытие приема и закрытие онлайн-набора
    Из detail.md стр. 253: POST /api/online-queue/open?day&specialist_id
    """
    
    # Получаем дневную очередь
    daily_queue = db.query(DailyQueue).filter(
        and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id)
    ).first()
    
    if not daily_queue:
        # Создаем очередь если не существует
        daily_queue = DailyQueue(
            day=day,
            specialist_id=specialist_id,
            active=True
        )
        db.add(daily_queue)
    
    # Отмечаем время открытия
    if not daily_queue.opened_at:
        daily_queue.opened_at = datetime.utcnow()
    
    db.commit()
    db.refresh(daily_queue)
    
    # Подсчитываем онлайн-записи
    online_entries_count = db.query(OnlineQueueEntry).filter(
        and_(OnlineQueueEntry.queue_id == daily_queue.id, OnlineQueueEntry.source == "online")
    ).count()
    
    return {
        "success": True,
        "message": f"Прием открыт. Онлайн-набор закрыт.",
        "opened_at": daily_queue.opened_at,
        "online_entries_count": online_entries_count,
        "closed_online_registration": True
    }


# ===================== ПОЛУЧЕНИЕ СОСТОЯНИЯ ОЧЕРЕДИ =====================

def get_queue_status(
    db: Session,
    day: date,
    specialist_id: int
) -> Dict[str, Any]:
    """Получить статус очереди"""
    
    # Получаем очередь
    daily_queue = db.query(DailyQueue).filter(
        and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id)
    ).first()
    
    if not daily_queue:
        return {
            "queue_exists": False,
            "queue_open": False,
            "entries_count": 0
        }
    
    # Подсчитываем записи
    total_entries = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == daily_queue.id).count()
    waiting_entries = db.query(OnlineQueueEntry).filter(
        and_(OnlineQueueEntry.queue_id == daily_queue.id, OnlineQueueEntry.status == "waiting")
    ).count()
    
    return {
        "queue_exists": True,
        "queue_open": daily_queue.opened_at is not None,
        "opened_at": daily_queue.opened_at,
        "total_entries": total_entries,
        "waiting_entries": waiting_entries,
        "queue_id": daily_queue.id
    }


# ===================== ПРОВЕРКА РАБОЧИХ ЧАСОВ =====================

def check_queue_availability(
    db: Session,
    day: date,
    specialist_id: int
) -> Dict[str, Any]:
    """
    Проверка доступности онлайн-очереди
    Из detail.md стр. 238-246: правила доступности
    """
    
    # Получаем настройки
    queue_settings = get_queue_settings(db)
    timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
    
    # Текущее время в часовом поясе клиники
    current_time = datetime.now(timezone)
    queue_start_hour = queue_settings.get("queue_start_hour", 7)
    
    # Проверяем дату
    if day < date.today():
        return {
            "available": False,
            "reason": "DATE_PAST",
            "message": "Нельзя записаться на прошедшую дату"
        }
    
    # Если сегодня, проверяем время
    if day == date.today():
        if current_time.hour < queue_start_hour:
            return {
                "available": False,
                "reason": "TOO_EARLY",
                "message": f"Онлайн-запись доступна с {queue_start_hour}:00",
                "available_from": f"{queue_start_hour}:00"
            }
    
    # Проверяем что очередь не открыта
    daily_queue = db.query(DailyQueue).filter(
        and_(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id)
    ).first()
    
    if daily_queue and daily_queue.opened_at:
        return {
            "available": False,
            "reason": "QUEUE_OPENED",
            "message": "Онлайн-набор закрыт. Обратитесь в регистратуру.",
            "opened_at": daily_queue.opened_at
        }
    
    # Проверяем лимит мест
    if daily_queue:
        current_count = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == daily_queue.id).count()
        max_slots = queue_settings.get("max_per_day", {}).get(
            db.query(Doctor).filter(Doctor.id == specialist_id).first().specialty, 
            15
        )
        
        if current_count >= max_slots:
            return {
                "available": False,
                "reason": "QUEUE_FULL", 
                "message": f"Все места заняты ({current_count}/{max_slots})"
            }
    
    return {
        "available": True,
        "message": "Онлайн-запись доступна"
    }


# ===================== ПОИСК ДУБЛИКАТОВ =====================

def find_existing_entry(
    db: Session,
    queue_id: int,
    phone: Optional[str] = None,
    telegram_id: Optional[int] = None
) -> Optional[OnlineQueueEntry]:
    """
    Поиск существующей записи по телефону или Telegram ID
    Из detail.md стр. 241: "Один номер на телефон или Telegram‑чат"
    """
    
    if phone:
        return db.query(OnlineQueueEntry).filter(
            and_(OnlineQueueEntry.queue_id == queue_id, OnlineQueueEntry.phone == phone)
        ).first()
    elif telegram_id:
        return db.query(OnlineQueueEntry).filter(
            and_(OnlineQueueEntry.queue_id == queue_id, OnlineQueueEntry.telegram_id == telegram_id)
        ).first()
    
    return None


# ===================== ВАЛИДАЦИЯ ТОКЕНА =====================

def validate_queue_token(db: Session, token: str) -> Tuple[bool, Optional[QueueToken], str]:
    """Валидация QR токена"""
    
    queue_token = db.query(QueueToken).filter(
        and_(QueueToken.token == token, QueueToken.active == True)
    ).first()
    
    if not queue_token:
        return False, None, "Неверный токен QR кода"
    
    if datetime.utcnow() > queue_token.expires_at.replace(tzinfo=None):
        return False, queue_token, "Срок действия QR кода истек"
    
    return True, queue_token, "Токен валиден"


# ===================== СТАТИСТИКА ОЧЕРЕДИ =====================

def get_queue_statistics(
    db: Session,
    day: date,
    specialist_id: Optional[int] = None
) -> Dict[str, Any]:
    """Статистика очереди за день"""
    
    query = db.query(DailyQueue).filter(DailyQueue.day == day)
    
    if specialist_id:
        query = query.filter(DailyQueue.specialist_id == specialist_id)
    
    queues = query.all()
    
    total_entries = 0
    online_entries = 0
    served_entries = 0
    
    for queue in queues:
        entries = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == queue.id).all()
        total_entries += len(entries)
        online_entries += len([e for e in entries if e.source == "online"])
        served_entries += len([e for e in entries if e.status == "served"])
    
    return {
        "day": day,
        "total_queues": len(queues),
        "total_entries": total_entries,
        "online_entries": online_entries,
        "served_entries": served_entries,
        "queues": [
            {
                "specialist_id": q.specialist_id,
                "specialist_name": q.specialist.user.full_name if q.specialist.user else f"Врач #{q.specialist_id}",
                "opened_at": q.opened_at,
                "entries_count": db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == q.id).count()
            }
            for q in queues
        ]
    }
