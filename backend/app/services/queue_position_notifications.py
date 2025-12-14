"""
Сервис Push-уведомлений о позиции в очереди
согласно ONLINE_QUEUE_SYSTEM_V2.md раздел 16

Реализует:
1. Уведомление о позиции в очереди: "Перед вами 5 человек"
2. Уведомление о вызове: "Вас вызывают!"
3. Уведомление об изменении позиции
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.services.fcm_service import FCMService, get_fcm_service

logger = logging.getLogger(__name__)


class QueuePositionNotificationError(Exception):
    """Ошибка при отправке уведомлений о позиции"""
    pass


class QueuePositionNotificationService:
    """
    Сервис для уведомлений о позиции в очереди
    
    Интегрируется с FCM для отправки push-уведомлений.
    """
    
    # Пороги для уведомлений (человек перед вами)
    NOTIFICATION_THRESHOLDS = [5, 3, 1, 0]
    
    def __init__(self, db: Session):
        self.db = db
        self.fcm_service = get_fcm_service()
    
    async def notify_patient_called(
        self, 
        entry: OnlineQueueEntry,
        cabinet_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Уведомление о вызове пациента
        
        Args:
            entry: Запись в очереди
            cabinet_number: Номер кабинета
        
        Returns:
            Результат отправки уведомления
        """
        patient_name = entry.patient_name or "Пациент"
        cabinet_info = f"\nКабинет: {cabinet_number}" if cabinet_number else ""
        
        title = "🔔 Вас вызывают!"
        body = (
            f"{patient_name}, пройдите в кабинет врача."
            f"{cabinet_info}\n"
            f"Номер в очереди: {entry.number}"
        )
        
        data = {
            "type": "queue_call",
            "entry_id": str(entry.id),
            "queue_number": str(entry.number),
            "cabinet": cabinet_number or "",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self._send_notification_to_patient(
            entry=entry,
            title=title,
            body=body,
            data=data,
            sound="call_notification",  # Специальный звонок
            priority="high"
        )
    
    async def notify_position_update(
        self, 
        entry: OnlineQueueEntry,
        people_ahead: int,
        estimated_wait_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Уведомление об обновлении позиции в очереди
        
        Args:
            entry: Запись в очереди
            people_ahead: Количество людей впереди
            estimated_wait_minutes: Примерное время ожидания в минутах
        
        Returns:
            Результат отправки уведомления
        """
        # Проверяем, нужно ли отправлять уведомление (по порогам)
        if people_ahead not in self.NOTIFICATION_THRESHOLDS and people_ahead > 5:
            return {"success": True, "sent": False, "reason": "threshold_not_met"}
        
        patient_name = entry.patient_name or "Уважаемый пациент"
        
        # Формируем сообщение
        if people_ahead == 0:
            title = "⏰ Ваша очередь подошла!"
            body = f"{patient_name}, приготовьтесь к вызову."
        elif people_ahead == 1:
            title = "👀 Вы следующий!"
            body = f"{patient_name}, перед вами 1 человек."
        else:
            title = f"📊 Обновление очереди"
            body = f"{patient_name}, перед вами {people_ahead} человек(а)."
        
        # Добавляем время ожидания если есть
        if estimated_wait_minutes:
            body += f"\nПримерное время ожидания: ~{estimated_wait_minutes} мин."
        
        data = {
            "type": "queue_position",
            "entry_id": str(entry.id),
            "queue_number": str(entry.number),
            "people_ahead": str(people_ahead),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if estimated_wait_minutes:
            data["estimated_wait_minutes"] = str(estimated_wait_minutes)
        
        return await self._send_notification_to_patient(
            entry=entry,
            title=title,
            body=body,
            data=data,
            sound="position_update"
        )
    
    async def notify_queue_changes_batch(
        self, 
        queue_id: int,
        changed_after_number: int
    ) -> Dict[str, Any]:
        """
        Массовое уведомление об изменении очереди
        
        Вызывается когда кто-то обслужен или убран из очереди,
        все последующие получают уведомление об улучшении позиции.
        
        Args:
            queue_id: ID очереди
            changed_after_number: Номер, после которого изменились позиции
        
        Returns:
            Результат массовой отправки
        """
        # Получаем записи со статусом waiting после указанного номера
        entries = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue_id,
            OnlineQueueEntry.status == "waiting",
            OnlineQueueEntry.number > changed_after_number
        ).order_by(
            OnlineQueueEntry.priority.desc(),
            OnlineQueueEntry.queue_time
        ).all()
        
        if not entries:
            return {
                "success": True,
                "total_notified": 0,
                "message": "Нет записей для уведомления"
            }
        
        results = []
        position = 1  # Позиция после обслуженного
        
        for entry in entries:
            # Вычисляем количество людей впереди
            people_ahead = self._count_people_ahead(entry)
            
            # Отправляем уведомление только для порогов или <= 5
            if people_ahead in self.NOTIFICATION_THRESHOLDS or people_ahead <= 5:
                try:
                    result = await self.notify_position_update(
                        entry=entry,
                        people_ahead=people_ahead
                    )
                    results.append({
                        "entry_id": entry.id,
                        "number": entry.number,
                        "people_ahead": people_ahead,
                        "sent": result.get("sent", False),
                        "success": result.get("success", False)
                    })
                except Exception as e:
                    logger.error(f"Error notifying entry {entry.id}: {e}")
                    results.append({
                        "entry_id": entry.id,
                        "error": str(e)
                    })
            
            position += 1
        
        sent_count = sum(1 for r in results if r.get("sent"))
        
        logger.info(
            f"Queue {queue_id}: Sent {sent_count} position notifications "
            f"after number {changed_after_number}"
        )
        
        return {
            "success": True,
            "total_notified": sent_count,
            "details": results
        }
    
    async def send_waiting_reminder(
        self, 
        entry: OnlineQueueEntry
    ) -> Dict[str, Any]:
        """
        Напоминание о том, что пациент всё ещё в очереди
        
        Используется для периодических уведомлений (например, каждые 30 мин)
        """
        people_ahead = self._count_people_ahead(entry)
        patient_name = entry.patient_name or "Уважаемый пациент"
        
        title = "⏳ Вы всё ещё в очереди"
        body = f"{patient_name}, перед вами {people_ahead} человек(а)."
        
        if people_ahead <= 3:
            body += "\nСкоро ваша очередь!"
        
        data = {
            "type": "queue_reminder",
            "entry_id": str(entry.id),
            "queue_number": str(entry.number),
            "people_ahead": str(people_ahead),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self._send_notification_to_patient(
            entry=entry,
            title=title,
            body=body,
            data=data
        )
    
    async def notify_diagnostics_return_needed(
        self, 
        entry: OnlineQueueEntry,
        specialist_name: str
    ) -> Dict[str, Any]:
        """
        Уведомление о необходимости вернуться после диагностики
        
        Вызывается когда врач готов продолжить осмотр
        """
        patient_name = entry.patient_name or "Пациент"
        
        title = "🔄 Вернитесь к врачу"
        body = (
            f"{patient_name}, врач {specialist_name} ожидает вас.\n"
            f"Пожалуйста, вернитесь в кабинет для продолжения осмотра."
        )
        
        data = {
            "type": "diagnostics_return",
            "entry_id": str(entry.id),
            "queue_number": str(entry.number),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self._send_notification_to_patient(
            entry=entry,
            title=title,
            body=body,
            data=data,
            sound="return_notification",
            priority="high"
        )
    
    def _count_people_ahead(self, entry: OnlineQueueEntry) -> int:
        """Подсчитать количество людей впереди в очереди"""
        count = self.db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.status == "waiting",
            OnlineQueueEntry.id != entry.id,
            # Учитываем приоритет и время
            (
                (OnlineQueueEntry.priority > entry.priority) |
                (
                    (OnlineQueueEntry.priority == entry.priority) &
                    (OnlineQueueEntry.queue_time < entry.queue_time)
                )
            )
        ).count()
        
        return count
    
    async def _send_notification_to_patient(
        self,
        entry: OnlineQueueEntry,
        title: str,
        body: str,
        data: Dict[str, Any],
        sound: str = "default",
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Отправить push-уведомление пациенту
        
        Ищет FCM токен по:
        1. patient_id -> Patient -> User -> fcm_token
        2. telegram_id -> User (через связку) -> fcm_token
        """
        device_token = None
        
        # Способ 1: Через patient_id
        if entry.patient_id:
            patient = self.db.query(Patient).filter(
                Patient.id == entry.patient_id
            ).first()
            
            if patient and patient.user_id:
                user = self.db.query(User).filter(
                    User.id == patient.user_id
                ).first()
                
                if user and hasattr(user, 'fcm_token') and user.fcm_token:
                    device_token = user.fcm_token
        
        # Способ 2: Через telegram_id (если есть связь)
        if not device_token and entry.telegram_id:
            user = self.db.query(User).filter(
                User.telegram_id == entry.telegram_id
            ).first()
            
            if user and hasattr(user, 'fcm_token') and user.fcm_token:
                device_token = user.fcm_token
        
        if not device_token:
            logger.debug(
                f"No FCM token found for entry {entry.id} "
                f"(patient_id={entry.patient_id}, telegram_id={entry.telegram_id})"
            )
            return {
                "success": True,
                "sent": False,
                "reason": "no_fcm_token"
            }
        
        # Отправляем уведомление
        try:
            result = await self.fcm_service.send_notification(
                device_token=device_token,
                title=title,
                body=body,
                data=data,
                sound=sound
            )
            
            return {
                "success": result.success if hasattr(result, 'success') else True,
                "sent": True,
                "message_id": result.message_id if hasattr(result, 'message_id') else None
            }
            
        except Exception as e:
            logger.error(f"FCM notification error for entry {entry.id}: {e}")
            return {
                "success": False,
                "sent": False,
                "error": str(e)
            }
    
    def get_queue_position_info(self, entry: OnlineQueueEntry) -> Dict[str, Any]:
        """
        Получить информацию о позиции в очереди
        
        Используется для API и отображения в приложении
        """
        people_ahead = self._count_people_ahead(entry)
        
        # Получаем информацию об очереди
        queue = self.db.query(DailyQueue).filter(
            DailyQueue.id == entry.queue_id
        ).first()
        
        queue_info = {}
        if queue:
            queue_info = {
                "queue_id": queue.id,
                "queue_tag": queue.queue_tag,
                "cabinet_number": queue.cabinet_number,
                "is_open": queue.opened_at is not None
            }
            
            # Получаем имя специалиста
            if queue.specialist:
                # Имя берём из связанного пользователя
                if queue.specialist.user and queue.specialist.user.full_name:
                    queue_info["specialist_name"] = queue.specialist.user.full_name
                else:
                    # Fallback на специальность
                    queue_info["specialist_name"] = queue.specialist.specialty
        
        return {
            "entry_id": entry.id,
            "queue_number": entry.number,
            "status": entry.status,
            "people_ahead": people_ahead,
            "priority": entry.priority,
            "queue_time": entry.queue_time.isoformat() if entry.queue_time else None,
            "queue_info": queue_info
        }


# Factory function
def get_queue_position_service(db: Session) -> QueuePositionNotificationService:
    """Получить экземпляр сервиса уведомлений о позиции"""
    return QueuePositionNotificationService(db)


# Вспомогательная функция для вызова из синхронного кода
def notify_patient_called_sync(
    db: Session, 
    entry: OnlineQueueEntry, 
    cabinet_number: Optional[str] = None
) -> Dict[str, Any]:
    """Синхронная обёртка для уведомления о вызове"""
    service = get_queue_position_service(db)
    return asyncio.run(service.notify_patient_called(entry, cabinet_number))


def notify_queue_changes_sync(
    db: Session, 
    queue_id: int, 
    changed_after_number: int
) -> Dict[str, Any]:
    """Синхронная обёртка для массового уведомления"""
    service = get_queue_position_service(db)
    return asyncio.run(service.notify_queue_changes_batch(queue_id, changed_after_number))
