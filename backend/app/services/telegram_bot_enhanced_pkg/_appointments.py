"""Appointments mixin for EnhancedTelegramBotService.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg._base import *  # noqa: F401, F403
from app.services.telegram_bot_enhanced_pkg._base import (
    EnhancedTelegramBotServiceMixinBase,
)


class AppointmentsMixin(EnhancedTelegramBotServiceMixinBase):
    """Appointments methods for EnhancedTelegramBotService."""

    async def _handle_appointments(self, chat_id: int, telegram_user, db: Session):
        """Мои записи"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем записи пользователя
                appointments = (
                    db.query(Appointment)
                    .filter(Appointment.patient_id == user.id)
                    .order_by(Appointment.appointment_date.desc())
                    .limit(10)
                    .all()
                )

                if appointments:
                    message = f"📅 **Ваши записи ({len(appointments)}):**\\n\\n"

                    for appointment in appointments:
                        date_str = appointment.appointment_date.strftime('%d.%m.%Y')
                        time_str = (
                            appointment.appointment_time.strftime('%H:%M')
                            if appointment.appointment_time
                            else 'Время не указано'
                        )

                        status_icons = {
                            "pending": "⏳",
                            "confirmed": "✅",
                            "completed": "✅",
                            "cancelled": "❌",
                            "no_show": "👻",
                        }

                        status = appointment.status or "pending"
                        icon = status_icons.get(status, "📋")

                        message += f"{icon} **{date_str} в {time_str}**\\n"
                        message += (
                            f"👨‍⚕️ {appointment.doctor_name or 'Врач не указан'}\\n"
                        )
                        message += f"📋 Статус: {status}\\n\\n"
                else:
                    message = "📅 У вас пока нет записей\\n\\nИспользуйте /book для записи на прием"

                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "📝 Записаться",
                                "callback_data": "book_appointment",
                            }
                        ],
                        [
                            {
                                "text": "🔄 Обновить",
                                "callback_data": "refresh_appointments",
                            }
                        ],
                    ]
                }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды appointments: {e}")
            await self._send_error_message(chat_id)


    async def _handle_book(self, chat_id: int, telegram_user, db: Session):
        """Записаться на прием"""
        try:
            message = """📝 **Запись на прием**

Выберите тип записи:"""

            keyboard = {
                "inline_keyboard": [
                    [{"text": "👨‍⚕️ К врачу", "callback_data": "book_doctor"}],
                    [{"text": "💊 На процедуру", "callback_data": "book_procedure"}],
                    [{"text": "🔬 В лабораторию", "callback_data": "book_lab"}],
                    [{"text": "📋 В очередь", "callback_data": "book_queue"}],
                    [
                        {
                            "text": "📞 Позвонить в регистратуру",
                            "callback_data": "call_registry",
                        }
                    ],
                ]
            }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды book: {e}")
            await self._send_error_message(chat_id)


    async def _handle_cancel(self, chat_id: int, telegram_user, db: Session):
        """Отменить запись"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем активные записи пользователя
                appointments = (
                    db.query(Appointment)
                    .filter(
                        and_(
                            Appointment.patient_id == user.id,
                            Appointment.status.in_(["pending", "confirmed"]),
                        )
                    )
                    .order_by(Appointment.appointment_date.asc())
                    .limit(5)
                    .all()
                )

                if appointments:
                    message = "❌ **Отмена записи**\\n\\nВыберите запись для отмены:"

                    keyboard_buttons = []
                    for appointment in appointments:
                        date_str = appointment.appointment_date.strftime('%d.%m.%Y')
                        time_str = (
                            appointment.appointment_time.strftime('%H:%M')
                            if appointment.appointment_time
                            else 'Время не указано'
                        )

                        button_text = f"📅 {date_str} {time_str}"
                        callback_data = f"cancel_appointment_{appointment.id}"
                        keyboard_buttons.append(
                            [{"text": button_text, "callback_data": callback_data}]
                        )

                    keyboard = {"inline_keyboard": keyboard_buttons}
                else:
                    message = "📅 У вас нет активных записей для отмены"
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📝 Записаться",
                                    "callback_data": "book_appointment",
                                }
                            ]
                        ]
                    }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды cancel: {e}")
            await self._send_error_message(chat_id)


    async def _handle_reschedule(self, chat_id: int, telegram_user, db: Session):
        """Перенести запись"""
        try:
            # Находим пользователя по Telegram ID
            user = db.query(User).filter(User.telegram_chat_id == str(chat_id)).first()

            if not user:
                message = "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь в системе."
            else:
                # Получаем активные записи пользователя
                appointments = (
                    db.query(Appointment)
                    .filter(
                        and_(
                            Appointment.patient_id == user.id,
                            Appointment.status.in_(["pending", "confirmed"]),
                        )
                    )
                    .order_by(Appointment.appointment_date.asc())
                    .limit(5)
                    .all()
                )

                if appointments:
                    message = "🔄 **Перенос записи**\\n\\nВыберите запись для переноса:"

                    keyboard_buttons = []
                    for appointment in appointments:
                        date_str = appointment.appointment_date.strftime('%d.%m.%Y')
                        time_str = (
                            appointment.appointment_time.strftime('%H:%M')
                            if appointment.appointment_time
                            else 'Время не указано'
                        )

                        button_text = f"📅 {date_str} {time_str}"
                        callback_data = f"reschedule_appointment_{appointment.id}"
                        keyboard_buttons.append(
                            [{"text": button_text, "callback_data": callback_data}]
                        )

                    keyboard = {"inline_keyboard": keyboard_buttons}
                else:
                    message = "📅 У вас нет активных записей для переноса"
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "📝 Записаться",
                                    "callback_data": "book_appointment",
                                }
                            ]
                        ]
                    }

            await self._send_message(
                chat_id, message, parse_mode="Markdown", reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка команды reschedule: {e}")
            await self._send_error_message(chat_id)


