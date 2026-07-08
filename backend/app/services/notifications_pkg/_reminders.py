"""Reminders mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    NotificationSenderMixinBase,
    logger,
    settings,
    Any,
    Session,
    datetime,
    UTC,
    httpx,
    smtplib,
    MIMEMultipart,
    MIMEText,
    escape,
    _jinja_env,
    crud_notification_history,
    crud_notification_template,
    crud_user_notification_settings,
    NotificationHistory,
    User,
    NotificationHistoryCreate,
    get_fcm_service,
    get_notification_platform_service,
    get_notification_ws_manager,
    telegram_bot,
)


class RemindersMixin(NotificationSenderMixinBase):
    """Reminders methods for NotificationSenderService."""

    async def send_confirmation_reminder(
        self, db: Session, visit_id: int, hours_before: int = 24
    ) -> dict[str, Any]:
        """Отправляет напоминание о необходимости подтверждения"""
        from app.models.patient import Patient
        from app.models.visit import Visit

        try:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            channel = self._determine_best_channel(patient)
            notification_data = self._prepare_notification_data(db, visit, patient)
            notification_data["is_reminder"] = True
            notification_data["hours_before"] = hours_before

            if channel == "telegram":
                # Упрощенная версия напоминания для Telegram (можно расширить)
                message = f"🔔 Напоминание! Пожалуйста, подтвердите визит к врачу {notification_data['doctor_name']} на {notification_data['visit_date']} {notification_data['visit_time']}."
                keyboard = self._create_telegram_keyboard(notification_data["confirmation_token"])
                result = await self.telegram_bot.send_confirmation_invitation(
                    chat_id=patient.telegram_id, message=message, keyboard=keyboard
                )
                return {"success": result.get("success"), "error": result.get("error")}
            elif channel == "pwa":
                 return await self._send_pwa_invitation(patient, notification_data)
            else:
                 return await self._send_phone_invitation(patient, notification_data)

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
            return {"success": False, "error": str(e)}


    async def send_telegram_message(
        self, user_id: int | str, message: str, parse_mode: str = "HTML"
    ) -> dict[str, Any]:
        """
        Отправляет сообщение через Telegram бот.
        Метод-обертка для совместимости с кодом, использующим NotificationService.
        """
        try:
            if not self.telegram_bot:
                logger.warning("Telegram bot integration not initialized")
                return {"success": False, "error": "Telegram bot not initialized"}

            # Используем telegram_bot.send_message (предполагая что такой метод есть или будет добавлен)
            # Если в TelegramBotService нет send_message, используем telegram_bot.application.bot.send_message
            # Но лучше использовать методы сервиса.
            # Проверим есть ли метод send_message в TelegramBotService,
            # если нет - используем send_message из bot instance

            # В TelegramBotService обычно есть send_message
            if hasattr(self.telegram_bot, "send_message"):
                 return await self.telegram_bot.send_message(user_id=user_id, text=message, parse_mode=parse_mode)
            else:
                 # Fallback
                 await self.telegram_bot.application.bot.send_message(chat_id=user_id, text=message, parse_mode=parse_mode)
                 return {"success": True}

        except Exception as e:
            logger.error(f"Error sending telegram message: {e}")
            return {"success": False, "error": str(e)}

    # === End merged methods ===




