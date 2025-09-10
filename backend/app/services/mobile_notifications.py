"""
Сервис для мобильных уведомлений
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.appointment import Appointment
from app.models.notification import NotificationHistory
from app.crud import notification as crud_notification
from app.services.fcm_service import get_fcm_service
from app.core.config import settings


class MobileNotificationService:
    """Сервис для отправки мобильных уведомлений"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def send_push_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Отправка push-уведомления"""
        try:
            # Получаем пользователя
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Здесь должна быть интеграция с FCM (Firebase Cloud Messaging)
            # Пока создаем запись в базе данных
            notification_data = {
                "recipient_type": "patient",
                "recipient_id": user_id,
                "recipient_contact": "mobile_app",
                "notification_type": notification_type,
                "channel": "mobile",
                "subject": title,
                "content": message,
                "status": "sent"
            }
            
            # Сохраняем уведомление в БД
            crud_notification.create_notification(self.db, notification_data)
            
            # Отправляем через FCM
            fcm_service = await get_fcm_service()
            await fcm_service.send_notification(
                device_token=user.device_token,
                title=title,
                body=message,
                data=data or {}
            )
            
            return True
            
        except Exception as e:
            print(f"Ошибка отправки push-уведомления: {e}")
            return False
    
    async def send_appointment_reminder(
        self,
        appointment_id: int,
        reminder_type: str = "24h"
    ) -> bool:
        """Отправка напоминания о записи"""
        try:
            appointment = self.db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()
            
            if not appointment:
                return False
            
            # Определяем время напоминания
            if reminder_type == "24h":
                reminder_time = appointment.appointment_date - timedelta(hours=24)
            elif reminder_type == "2h":
                reminder_time = appointment.appointment_date - timedelta(hours=2)
            else:
                return False
            
            # Проверяем, не пора ли отправлять напоминание
            if datetime.utcnow() < reminder_time:
                return False
            
            # Формируем сообщение
            title = "Напоминание о записи"
            message = f"У вас запись к врачу {appointment.doctor.name} завтра в {appointment.appointment_date.strftime('%H:%M')}"
            
            data = {
                "appointment_id": appointment_id,
                "type": "appointment_reminder",
                "reminder_type": reminder_type
            }
            
            return await self.send_push_notification(
                appointment.patient_id,
                title,
                message,
                data
            )
            
        except Exception as e:
            print(f"Ошибка отправки напоминания о записи: {e}")
            return False
    
    async def send_queue_update(
        self,
        patient_id: int,
        queue_position: int,
        specialty: str
    ) -> bool:
        """Отправка обновления позиции в очереди"""
        try:
            title = "Обновление очереди"
            message = f"Ваша позиция в очереди к {specialty}: #{queue_position}"
            
            data = {
                "type": "queue_update",
                "queue_position": queue_position,
                "specialty": specialty
            }
            
            return await self.send_push_notification(
                patient_id,
                title,
                message,
                data
            )
            
        except Exception as e:
            print(f"Ошибка отправки обновления очереди: {e}")
            return False
    
    async def send_lab_results(
        self,
        patient_id: int,
        lab_result_id: int,
        test_name: str
    ) -> bool:
        """Отправка результатов анализов"""
        try:
            title = "Результаты анализов готовы"
            message = f"Результаты анализа '{test_name}' готовы к просмотру"
            
            data = {
                "type": "lab_results",
                "lab_result_id": lab_result_id,
                "test_name": test_name
            }
            
            return await self.send_push_notification(
                patient_id,
                title,
                message,
                data
            )
            
        except Exception as e:
            print(f"Ошибка отправки результатов анализов: {e}")
            return False
    
    async def send_payment_notification(
        self,
        patient_id: int,
        payment_id: int,
        amount: float,
        status: str
    ) -> bool:
        """Отправка уведомления об оплате"""
        try:
            if status == "paid":
                title = "Оплата прошла успешно"
                message = f"Оплата на сумму {amount} UZS прошла успешно"
            elif status == "failed":
                title = "Ошибка оплаты"
                message = f"Оплата на сумму {amount} UZS не прошла. Попробуйте еще раз"
            else:
                return False
            
            data = {
                "type": "payment_notification",
                "payment_id": payment_id,
                "amount": amount,
                "status": status
            }
            
            return await self.send_push_notification(
                patient_id,
                title,
                message,
                data
            )
            
        except Exception as e:
            print(f"Ошибка отправки уведомления об оплате: {e}")
            return False
    
    async def send_appointment_confirmation(
        self,
        appointment_id: int
    ) -> bool:
        """Отправка подтверждения записи"""
        try:
            appointment = self.db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()
            
            if not appointment:
                return False
            
            title = "Запись подтверждена"
            message = f"Ваша запись к врачу {appointment.doctor.name} на {appointment.appointment_date.strftime('%d.%m.%Y в %H:%M')} подтверждена"
            
            data = {
                "type": "appointment_confirmation",
                "appointment_id": appointment_id
            }
            
            return await self.send_push_notification(
                appointment.patient_id,
                title,
                message,
                data
            )
            
        except Exception as e:
            print(f"Ошибка отправки подтверждения записи: {e}")
            return False
    
    async def send_appointment_cancellation(
        self,
        appointment_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """Отправка уведомления об отмене записи"""
        try:
            appointment = self.db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()
            
            if not appointment:
                return False
            
            title = "Запись отменена"
            message = f"Ваша запись к врачу {appointment.doctor.name} отменена"
            
            if reason:
                message += f". Причина: {reason}"
            
            data = {
                "type": "appointment_cancellation",
                "appointment_id": appointment_id,
                "reason": reason
            }
            
            return await self.send_push_notification(
                appointment.patient_id,
                title,
                message,
                data
            )
            
        except Exception as e:
            print(f"Ошибка отправки уведомления об отмене: {e}")
            return False
    
    async def _send_fcm_notification(
        self,
        device_token: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Отправка уведомления через FCM (заглушка)"""
        # TODO: Реальная интеграция с Firebase Cloud Messaging
        print(f"FCM уведомление для {device_token}: {title} - {message}")
        return True
    
    async def get_notification_history(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получение истории уведомлений"""
        try:
            notifications = crud_notification.get_user_notifications(
                self.db, user_id=user_id, limit=limit
            )
            
            return [
                {
                    "id": notif.id,
                    "title": notif.title,
                    "message": notif.message,
                    "type": notif.type,
                    "data": notif.data,
                    "sent_at": notif.sent_at,
                    "read": notif.read
                }
                for notif in notifications
            ]
            
        except Exception as e:
            print(f"Ошибка получения истории уведомлений: {e}")
            return []
    
    async def mark_notification_read(
        self,
        notification_id: int,
        user_id: int
    ) -> bool:
        """Отметить уведомление как прочитанное"""
        try:
            notification = crud_notification.get_notification(
                self.db, notification_id=notification_id
            )
            
            if not notification or notification.user_id != user_id:
                return False
            
            notification.read = True
            self.db.commit()
            
            return True
            
        except Exception as e:
            print(f"Ошибка отметки уведомления как прочитанного: {e}")
            return False


# Глобальные функции для использования в API
async def get_mobile_notification_service(db: Session) -> MobileNotificationService:
    """Получить экземпляр сервиса мобильных уведомлений"""
    return MobileNotificationService(db)
