"""
Сервис уведомлений через Telegram
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.user import User
from ...models.visit import Visit
from .bot import telegram_bot

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """Сервис для отправки уведомлений через Telegram"""

    def __init__(self):
        self.bot = telegram_bot

    async def send_appointment_reminder(
        self, user_id: int, visit_id: int, hours_before: int = 24
    ) -> bool:
        """Отправка напоминания о визите"""
        try:
            db = next(get_db())

            # Получаем информацию о визите
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                logger.warning(f"Visit {visit_id} not found")
                return False

            # Получаем пользователя
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.telegram_id:
                logger.warning(f"User {user_id} not found or no telegram_id")
                return False

            appointment_data = {
                "id": visit.id,
                "doctor": visit.doctor.full_name if visit.doctor else "Врач",
                "specialty": visit.doctor.specialty if visit.doctor else "Консультация",
                "date": visit.scheduled_date.strftime("%d.%m.%Y"),
                "time": visit.scheduled_time.strftime("%H:%M"),
                "room": visit.room or "Уточнить на ресепшене",
                "hours_before": hours_before,
            }

            await self.bot.send_appointment_reminder(user.telegram_id, appointment_data)

            # Логируем отправку
            logger.info(
                f"Appointment reminder sent to user {user_id} for visit {visit_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send appointment reminder: {str(e)}")
            return False
        finally:
            db.close()

    async def send_lab_results_notification(
        self, user_id: int, test_name: str, test_date: datetime
    ) -> bool:
        """Уведомление о готовности результатов анализов"""
        try:
            db = next(get_db())

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.telegram_id:
                return False

            results_info = {
                "test_name": test_name,
                "date": test_date.strftime("%d.%m.%Y"),
                "patient_name": user.full_name,
            }

            await self.bot.send_lab_results_ready(user.telegram_id, results_info)

            logger.info(f"Lab results notification sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send lab results notification: {str(e)}")
            return False
        finally:
            db.close()

    async def send_queue_notification(
        self, user_id: int, queue_number: int, specialist_name: str, estimated_time: str
    ) -> bool:
        """Уведомление о вызове в очереди"""
        try:
            db = next(get_db())

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.telegram_id:
                return False

            message = f"""
🔔 **Ваша очередь подошла!**

👨‍⚕️ Специалист: {specialist_name}
🎫 Ваш номер: {queue_number}
⏰ Ориентировочное время: {estimated_time}

Пожалуйста, подойдите к кабинету врача.
            """

            await self.bot.send_notification(user.telegram_id, message)

            logger.info(f"Queue notification sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send queue notification: {str(e)}")
            return False
        finally:
            db.close()

    async def send_prescription_ready(
        self, user_id: int, prescription_id: int, doctor_name: str
    ) -> bool:
        """Уведомление о готовности рецепта"""
        try:
            db = next(get_db())

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.telegram_id:
                return False

            message = f"""
💊 **Рецепт готов**

👨‍⚕️ Врач: {doctor_name}
📄 Рецепт №{prescription_id}
📅 Дата: {datetime.now().strftime("%d.%m.%Y")}

Рецепт доступен для скачивания в приложении.
            """

            # Добавляем кнопку для скачивания
            from aiogram.types import (
                InlineKeyboardButton,
                InlineKeyboardMarkup,
                WebAppInfo,
            )

            from ...core.config import settings

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📄 Скачать рецепт",
                            web_app=WebAppInfo(
                                url=f"{settings.FRONTEND_URL}/prescription/{prescription_id}"
                            ),
                        )
                    ]
                ]
            )

            await self.bot.send_notification(user.telegram_id, message, keyboard)

            logger.info(f"Prescription notification sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send prescription notification: {str(e)}")
            return False
        finally:
            db.close()

    async def send_schedule_change_notification(
        self,
        user_id: int,
        change_type: str,  # "cancelled", "rescheduled", "doctor_changed"
        old_data: Dict[str, Any],
        new_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Уведомление об изменении в расписании"""
        try:
            db = next(get_db())

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.telegram_id:
                return False

            if change_type == "cancelled":
                message = f"""
❌ **Визит отменен**

👨‍⚕️ Врач: {old_data.get('doctor', 'Врач')}
📅 Дата: {old_data.get('date', 'не указана')}
⏰ Время: {old_data.get('time', 'не указано')}

Для записи на новое время обратитесь к администратору или используйте приложение.
                """

            elif change_type == "rescheduled":
                message = f"""
📅 **Визит перенесен**

**Было:**
👨‍⚕️ Врач: {old_data.get('doctor', 'Врач')}
📅 Дата: {old_data.get('date', 'не указана')}
⏰ Время: {old_data.get('time', 'не указано')}

**Стало:**
👨‍⚕️ Врач: {new_data.get('doctor', 'Врач')}
📅 Дата: {new_data.get('date', 'не указана')}
⏰ Время: {new_data.get('time', 'не указано')}

Просим прийти в новое назначенное время.
                """

            elif change_type == "doctor_changed":
                message = f"""
👨‍⚕️ **Смена врача**

**Было:** {old_data.get('doctor', 'Врач')}
**Стало:** {new_data.get('doctor', 'Врач')}

📅 Дата: {new_data.get('date', 'не указана')}
⏰ Время: {new_data.get('time', 'не указано')}

Время визита остается прежним.
                """

            await self.bot.send_notification(user.telegram_id, message)

            logger.info(f"Schedule change notification sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send schedule change notification: {str(e)}")
            return False
        finally:
            db.close()

    async def send_bulk_notification(
        self, user_ids: List[int], message: str, delay_seconds: float = 0.1
    ) -> Dict[str, int]:
        """Массовая рассылка уведомлений"""
        results = {"sent": 0, "failed": 0}

        for user_id in user_ids:
            try:
                db = next(get_db())
                user = db.query(User).filter(User.id == user_id).first()

                if user and user.telegram_id:
                    success = await self.bot.send_notification(
                        user.telegram_id, message
                    )
                    if success:
                        results["sent"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["failed"] += 1

                # Задержка между отправками для избежания лимитов
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

            except Exception as e:
                logger.error(
                    f"Failed to send bulk notification to user {user_id}: {str(e)}"
                )
                results["failed"] += 1
            finally:
                if 'db' in locals():
                    db.close()

        logger.info(f"Bulk notification completed: {results}")
        return results

    async def schedule_daily_reminders(self):
        """Планирование ежедневных напоминаний"""
        try:
            db = next(get_db())

            # Получаем визиты на завтра
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow_end = tomorrow.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

            visits = (
                db.query(Visit)
                .filter(
                    Visit.scheduled_date >= tomorrow_start,
                    Visit.scheduled_date <= tomorrow_end,
                    Visit.status == "scheduled",
                )
                .all()
            )

            reminder_count = 0
            for visit in visits:
                if visit.patient and visit.patient.telegram_id:
                    success = await self.send_appointment_reminder(
                        visit.patient.id, visit.id, hours_before=24
                    )
                    if success:
                        reminder_count += 1

            logger.info(f"Sent {reminder_count} daily reminders")
            return reminder_count

        except Exception as e:
            logger.error(f"Failed to schedule daily reminders: {str(e)}")
            return 0
        finally:
            db.close()


# Глобальный экземпляр сервиса
notification_service = TelegramNotificationService()
