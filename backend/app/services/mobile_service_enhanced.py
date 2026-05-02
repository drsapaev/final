"""
Расширенный сервис для мобильного приложения
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.crud import (
    appointment as crud_appointment,
)
from app.crud import (
    patient as crud_patient,
)
from app.crud import (
    user as crud_user,
)
from app.services.fcm_service import get_fcm_service
from app.services.sms_providers import get_sms_manager
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot

logger = logging.getLogger(__name__)


class MobileServiceEnhanced:
    """Расширенный сервис для мобильного приложения"""

    def __init__(self):
        self.sms_manager = get_sms_manager()
        self.telegram_bot = get_enhanced_telegram_bot()
        self.fcm_service = get_fcm_service()

    async def send_appointment_reminder(
        self, db: Session, appointment_id: int, reminder_type: str = "24h"
    ) -> bool:
        """Отправка напоминания о записи"""
        try:
            appointment = crud_appointment.get_appointment(
                db, appointment_id=appointment_id
            )
            if not appointment:
                return False

            patient = crud_patient.get_patient(db, patient_id=appointment.patient_id)
            if not patient:
                return False

            # Формируем сообщение
            appointment_time = appointment.appointment_date.strftime('%d.%m.%Y в %H:%M')
            doctor_name = appointment.doctor.full_name if appointment.doctor else "врач"

            if reminder_type == "24h":
                message = f"📅 Напоминание: завтра у вас запись к {doctor_name} на {appointment_time}"
            elif reminder_type == "2h":
                message = f"⏰ Напоминание: через 2 часа у вас запись к {doctor_name} на {appointment_time}"
            elif reminder_type == "30min":
                message = f"🔔 Напоминание: через 30 минут у вас запись к {doctor_name} на {appointment_time}"
            else:
                message = f"📋 У вас запись к {doctor_name} на {appointment_time}"

            # Отправляем через доступные каналы
            success_count = 0

            # SMS
            if patient.phone and patient.sms_notifications:
                sms_result = await self.sms_manager.send_sms(patient.phone, message)
                if sms_result.success:
                    success_count += 1

            # Telegram
            if patient.telegram_chat_id and patient.telegram_notifications:
                telegram_success = await self.telegram_bot._send_message(
                    patient.telegram_chat_id, message
                )
                if telegram_success:
                    success_count += 1

            # FCM Push уведомление (если есть fcm_token)
            user = crud_user.get_user_by_patient_id(db, patient_id=patient.id)
            if user and user.fcm_token and user.push_notifications_enabled:
                fcm_result = await self.fcm_service.send_notification(
                    device_token=user.fcm_token,
                    title="Напоминание о записи",
                    body=message,
                    data={"appointment_id": str(appointment_id), "type": "reminder"},
                )
                if fcm_result.success:
                    success_count += 1

            return success_count > 0

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
            return False

    async def send_lab_result_notification(
        self, db: Session, lab_result_id: int
    ) -> bool:
        """Уведомление о готовности результата анализа"""
        try:
            # Здесь должна быть логика получения результата анализа
            # lab_result = crud_lab.get_lab_result(db, result_id=lab_result_id)

            # Пока заглушка
            _message = "📊 Результаты ваших анализов готовы. Вы можете посмотреть их в мобильном приложении."

            # Логика отправки аналогична напоминаниям
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о результатах: {e}")
            return False

    async def send_queue_notification(
        self, db: Session, patient_id: int, queue_position: int, estimated_time: int
    ) -> bool:
        """Уведомление о приближении очереди"""
        try:
            patient = crud_patient.get_patient(db, patient_id=patient_id)
            if not patient:
                return False

            if estimated_time <= 15:  # Осталось 15 минут или меньше
                message = f"🔔 Ваша очередь подходит! Номер {queue_position}. Примерное время ожидания: {estimated_time} мин."
            elif estimated_time <= 30:  # Осталось 30 минут или меньше
                message = f"⏰ До вашей очереди осталось примерно {estimated_time} минут. Номер {queue_position}."
            else:
                return False  # Не отправляем уведомления если времени много

            # Отправляем уведомление
            success = False

            # Telegram (приоритетный канал для очередей)
            if patient.telegram_chat_id:
                success = await self.telegram_bot._send_message(
                    patient.telegram_chat_id, message
                )

            # FCM Push уведомление
            user = crud_user.get_user_by_patient_id(db, patient_id=patient_id)
            if user and user.fcm_token and user.push_notifications_enabled:
                fcm_result = await self.fcm_service.send_notification(
                    device_token=user.fcm_token,
                    title="Очередь",
                    body=message,
                    data={"queue_position": str(queue_position), "type": "queue"},
                )
                success = success or fcm_result.success

            return success

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об очереди: {e}")
            return False

    async def send_payment_notification(
        self, db: Session, payment_id: int, status: str
    ) -> bool:
        """Уведомление о статусе платежа"""
        try:
            # Здесь должна быть логика получения информации о платеже
            # payment = crud_payment.get_payment(db, payment_id=payment_id)

            status_messages = {
                "completed": "✅ Платеж успешно проведен",
                "failed": "❌ Платеж не прошел. Попробуйте еще раз",
                "pending": "⏳ Платеж обрабатывается",
                "cancelled": "🚫 Платеж отменен",
            }

            _message = status_messages.get(status, f"Статус платежа: {status}")

            # Логика отправки
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о платеже: {e}")
            return False

    async def send_promotional_notification(
        self,
        db: Session,
        user_ids: list[int],
        title: str,
        message: str,
        promo_data: dict[str, Any] | None = None,
    ) -> int:
        """Отправка промо-уведомлений"""
        try:
            success_count = 0

            for user_id in user_ids:
                user = crud_user.get_user(db, user_id=user_id)
                if not user or not user.promotions_notifications:
                    continue

                # FCM Push уведомление
                if user.fcm_token and user.push_notifications_enabled:
                    fcm_result = await self.fcm_service.send_notification(
                        device_token=user.fcm_token,
                        title=title,
                        body=message,
                        data={"type": "promotion", "promo_data": promo_data},
                    )
                    if fcm_result.success:
                        success_count += 1

                # Небольшая задержка между отправками
                await asyncio.sleep(0.1)

            return success_count

        except Exception as e:
            logger.error(f"Ошибка отправки промо-уведомлений: {e}")
            return 0

    async def send_fcm_notification_to_users(
        self,
        db: Session,
        user_ids: list[int],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        image: str | None = None,
    ) -> dict[str, Any]:
        """Отправка FCM уведомлений списку пользователей"""
        try:
            if not self.fcm_service.active:
                return {
                    "success": False,
                    "error": "FCM service not configured",
                    "sent_count": 0,
                    "failed_count": len(user_ids),
                }

            # Получаем FCM токены пользователей
            device_tokens = []
            for user_id in user_ids:
                user = crud_user.get_user(db, user_id=user_id)
                if user and user.fcm_token and user.push_notifications_enabled:
                    device_tokens.append(user.fcm_token)

            if not device_tokens:
                return {
                    "success": False,
                    "error": "No active FCM tokens found",
                    "sent_count": 0,
                    "failed_count": len(user_ids),
                }

            # Отправляем уведомления
            result = await self.fcm_service.send_multicast(
                device_tokens=device_tokens,
                title=title,
                body=body,
                data=data,
                image=image,
            )

            return result

        except Exception as e:
            logger.error(f"Ошибка отправки FCM уведомлений: {e}")
            return {
                "success": False,
                "error": str(e),
                "sent_count": 0,
                "failed_count": len(user_ids),
            }

    async def schedule_appointment_reminders(self, db: Session) -> int:
        """Планирование напоминаний о записях"""
        try:
            now = datetime.now()

            # Напоминания за 24 часа
            tomorrow = now + timedelta(hours=24)
            appointments_24h = crud_appointment.get_appointments_for_reminder(
                db,
                start_time=tomorrow - timedelta(minutes=30),
                end_time=tomorrow + timedelta(minutes=30),
            )

            # Напоминания за 2 часа
            in_2h = now + timedelta(hours=2)
            appointments_2h = crud_appointment.get_appointments_for_reminder(
                db,
                start_time=in_2h - timedelta(minutes=15),
                end_time=in_2h + timedelta(minutes=15),
            )

            # Напоминания за 30 минут
            in_30m = now + timedelta(minutes=30)
            appointments_30m = crud_appointment.get_appointments_for_reminder(
                db,
                start_time=in_30m - timedelta(minutes=5),
                end_time=in_30m + timedelta(minutes=5),
            )

            sent_count = 0

            # Отправляем напоминания
            for appointment in appointments_24h:
                success = await self.send_appointment_reminder(
                    db, appointment.id, "24h"
                )
                if success:
                    sent_count += 1

            for appointment in appointments_2h:
                success = await self.send_appointment_reminder(db, appointment.id, "2h")
                if success:
                    sent_count += 1

            for appointment in appointments_30m:
                success = await self.send_appointment_reminder(
                    db, appointment.id, "30min"
                )
                if success:
                    sent_count += 1

            return sent_count

        except Exception as e:
            logger.error(f"Ошибка планирования напоминаний: {e}")
            return 0

    async def get_mobile_analytics(self, db: Session, user_id: int) -> dict[str, Any]:
        """Аналитика для мобильного приложения"""
        try:
            patient = crud_patient.get_patient_by_user_id(db, user_id=user_id)
            if not patient:
                return {}

            # Собираем статистику
            total_appointments = crud_appointment.count_patient_appointments(
                db, patient_id=patient.id
            )
            completed_appointments = crud_appointment.count_completed_appointments(
                db, patient_id=patient.id
            )
            cancelled_appointments = crud_appointment.count_cancelled_appointments(
                db, patient_id=patient.id
            )

            # Статистика по месяцам (последние 12 месяцев)
            monthly_stats = []
            for i in range(12):
                month_start = datetime.now().replace(day=1) - timedelta(days=30 * i)
                month_end = month_start + timedelta(days=30)

                month_appointments = crud_appointment.count_appointments_in_period(
                    db,
                    patient_id=patient.id,
                    start_date=month_start,
                    end_date=month_end,
                )

                monthly_stats.append(
                    {
                        "month": month_start.strftime("%Y-%m"),
                        "appointments": month_appointments,
                    }
                )

            # Любимые врачи
            favorite_doctors = crud_appointment.get_patient_favorite_doctors(
                db, patient_id=patient.id, limit=3
            )

            # Статистика по услугам
            service_stats = crud_appointment.get_patient_service_stats(
                db, patient_id=patient.id
            )

            return {
                "total_appointments": total_appointments,
                "completed_appointments": completed_appointments,
                "cancelled_appointments": cancelled_appointments,
                "success_rate": (
                    (completed_appointments / total_appointments * 100)
                    if total_appointments > 0
                    else 0
                ),
                "monthly_stats": monthly_stats,
                "favorite_doctors": [
                    {
                        "name": doctor.full_name,
                        "specialty": doctor.specialty,
                        "visits_count": doctor.visits_count,
                    }
                    for doctor in favorite_doctors
                ],
                "service_stats": service_stats,
                "member_since": patient.created_at.strftime("%Y-%m-%d"),
                "last_visit": crud_appointment.get_last_visit_date(
                    db, patient_id=patient.id
                ),
            }

        except Exception as e:
            logger.error(f"Ошибка получения аналитики: {e}")
            return {}


# Глобальный экземпляр сервиса
mobile_service_enhanced = MobileServiceEnhanced()


def get_mobile_service_enhanced() -> MobileServiceEnhanced:
    """Получить экземпляр расширенного мобильного сервиса"""
    return mobile_service_enhanced
