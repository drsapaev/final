"""
Enums для различных статусов в системе
"""
from enum import Enum


class AppointmentStatus(str, Enum):
    """
    Статусы записей - жесткий поток: запись → платеж → прием → медкарта → рецепт
    
    Совместимость с существующими статусами:
    - scheduled -> pending (ожидает оплаты)
    - confirmed -> paid (оплачено)  
    - cancelled -> cancelled (отменено)
    - completed -> completed (завершено)
    """
    # Новые статусы жесткого потока
    PENDING = "pending"      # Запись создана, ожидает оплаты
    PAID = "paid"           # Оплачено, можно отправлять к врачу
    IN_VISIT = "in_visit"   # Прием у врача в процессе
    COMPLETED = "completed" # Прием завершен (EMR + рецепт готовы)
    CANCELLED = "cancelled" # Отменено
    NO_SHOW = "no_show"     # Пациент не явился
    
    # Совместимость со старыми статусами
    SCHEDULED = "scheduled" # Старый статус -> маппится на pending
    CONFIRMED = "confirmed" # Старый статус -> маппится на paid


class PaymentStatus(str, Enum):
    """Статусы платежей"""
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Методы оплаты"""
    CASH = "cash"
    CARD = "card"
    ONLINE = "online"
    BANK_TRANSFER = "bank_transfer"


class EMRStatus(str, Enum):
    """Статусы ЭМК"""
    DRAFT = "draft"
    SAVED = "saved"
    COMPLETED = "completed"


class PrescriptionStatus(str, Enum):
    """Статусы рецептов"""
    DRAFT = "draft"
    SAVED = "saved"
    PRINTED = "printed"


class QueueStatus(str, Enum):
    """Статусы очереди"""
    WAITING = "waiting"
    CALLED = "called"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Маппинг старых статусов на новые для обратной совместимости
APPOINTMENT_STATUS_MAPPING = {
    "scheduled": AppointmentStatus.PENDING,
    "confirmed": AppointmentStatus.PAID,
    "cancelled": AppointmentStatus.CANCELLED,
    "completed": AppointmentStatus.COMPLETED,
}


def normalize_appointment_status(status: str) -> AppointmentStatus:
    """
    Нормализует старые статусы к новым для обратной совместимости
    """
    if status in APPOINTMENT_STATUS_MAPPING:
        return APPOINTMENT_STATUS_MAPPING[status]
    
    try:
        return AppointmentStatus(status)
    except ValueError:
        # Если статус неизвестен, считаем pending
        return AppointmentStatus.PENDING


def can_transition_status(from_status: str, to_status: str) -> bool:
    """
    Проверяет возможность перехода между статусами
    """
    from_normalized = normalize_appointment_status(from_status)
    to_normalized = normalize_appointment_status(to_status)
    
    # Разрешенные переходы
    allowed_transitions = {
        AppointmentStatus.PENDING: [AppointmentStatus.PAID, AppointmentStatus.CANCELLED],
        AppointmentStatus.PAID: [AppointmentStatus.IN_VISIT, AppointmentStatus.NO_SHOW, AppointmentStatus.CANCELLED],
        AppointmentStatus.IN_VISIT: [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED],
        AppointmentStatus.COMPLETED: [],  # Финальный статус
        AppointmentStatus.CANCELLED: [],  # Финальный статус
        AppointmentStatus.NO_SHOW: [],    # Финальный статус
    }
    
    return to_normalized in allowed_transitions.get(from_normalized, [])
