"""Formatting mixin for NotificationSenderService.

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


class FormattingMixin(NotificationSenderMixinBase):
    """Formatting methods for NotificationSenderService."""

    def _determine_best_channel(self, patient: Any) -> str:
        """Определяет лучший канал для отправки уведомления"""
        # Приоритет: Telegram > PWA > Phone
        if hasattr(patient, 'telegram_id') and patient.telegram_id:
            return "telegram"
        if patient.phone and patient.phone.startswith('+998'):
            return "pwa"
        return "phone"


    def _prepare_notification_data(
        self, db: Session, visit: Any, patient: Any
    ) -> dict[str, Any]:
        """Подготавливает данные для уведомления"""
        from app.models.clinic import Doctor
        from app.models.visit import VisitService

        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        services_text = []
        total_amount = 0
        for vs in visit_services:
            services_text.append(f"• {vs.name} - {vs.price} сум")
            total_amount += float(vs.price) if vs.price else 0

        doctor_name = "Без врача"
        if visit.doctor_id:
            doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
            if doctor and doctor.user:
                doctor_name = doctor.user.full_name or doctor.user.username

        return {
            "visit_id": visit.id,
            "patient_name": patient.short_name() if hasattr(patient, 'short_name') else f"{patient.first_name} {patient.last_name}",
            "doctor_name": doctor_name,
            "visit_date": visit.visit_date.strftime("%d.%m.%Y"),
            "visit_time": visit.visit_time or "Время не указано",
            "services": services_text,
            "total_amount": total_amount,
            "confirmation_token": visit.confirmation_token,
            "expires_at": visit.confirmation_expires_at,
            "visit_type": self._get_visit_type_text(visit.discount_mode),
        }


    def _get_visit_type_text(self, discount_mode: str | None) -> str:
        if discount_mode == "repeat":
            return "Повторный визит"
        elif discount_mode == "benefit":
            return "Льготный визит"
        elif discount_mode == "all_free":
            return "Бесплатный визит"
        else:
            return "Платный визит"


    def _format_telegram_message(self, data: dict[str, Any]) -> str:
        services_list = "\n".join(data["services"])
        message = f"""
🏥 **Подтверждение визита в клинику**

👤 **Пациент:** {data["patient_name"]}
👨‍⚕️ **Врач:** {data["doctor_name"]}
📅 **Дата:** {data["visit_date"]}
🕐 **Время:** {data["visit_time"]}
💰 **Тип:** {data["visit_type"]}

📋 **Услуги:**
{services_list}

💵 **Общая сумма:** {data["total_amount"]} сум

⏰ **Подтвердите визит до:** {data["expires_at"].strftime("%d.%m.%Y %H:%M") if data["expires_at"] else "Не указано"}

Нажмите кнопку ниже для подтверждения:
        """.strip()
        return message


    def _create_telegram_keyboard(
        self, confirmation_token: str
    ) -> list[list[dict[str, str]]]:
        return [
            [
                {
                    "text": "✅ Подтвердить визит",
                    "callback_data": f"confirm_visit:{confirmation_token}",
                }
            ],
            [
                {
                    "text": "❌ Отменить визит",
                    "callback_data": f"cancel_visit:{confirmation_token}",
                }
            ],
            [
                {
                    "text": "📞 Связаться с клиникой",
                    "url": f"tel:{settings.CLINIC_PHONE}",
                }
            ],
        ]


    def _format_sms_message(self, data: dict[str, Any], pwa_url: str) -> str:
        return f"""
Клиника: Подтвердите визит на {data["visit_date"]} в {data["visit_time"]} к врачу {data["doctor_name"]}.
Сумма: {data["total_amount"]} сум.
Подтвердить: {pwa_url}
        """.strip()


    async def _send_telegram_invitation(
        self, patient: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет приглашение через Telegram"""
        try:
            if not hasattr(patient, 'telegram_id') or not patient.telegram_id:
                return {"success": False, "error": "У пациента нет Telegram ID"}

            message = self._format_telegram_message(data)
            keyboard = self._create_telegram_keyboard(data["confirmation_token"])

            # Используем telegram_bot для отправки
            result = await self.telegram_bot.send_confirmation_invitation(
                chat_id=patient.telegram_id, message=message, keyboard=keyboard
            )

            if result.get("success"):
                logger.info(f"Telegram приглашение отправлено пациенту {patient.id}")
                return {
                    "success": True,
                    "channel": "telegram",
                    "message_id": result.get("message_id"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Ошибка отправки Telegram"),
                }

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram приглашения: {e}")
            return {"success": False, "error": str(e)}


    async def _send_pwa_invitation(
        self, patient: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет приглашение через PWA (SMS с deep link)"""
        try:
            if not patient.phone:
                return {"success": False, "error": "У пациента нет номера телефона"}

            pwa_url = f"{settings.PWA_BASE_URL}/confirm-visit?token={data['confirmation_token']}"
            sms_text = self._format_sms_message(data, pwa_url)

            success = await self.send_sms(patient.phone, sms_text)

            if success:
                logger.info(f"PWA приглашение отправлено пациенту {patient.id}")
                return {"success": True, "channel": "pwa", "pwa_url": pwa_url}
            else:
                return {"success": False, "error": "Ошибка отправки SMS"}

        except Exception as e:
            logger.error(f"Ошибка отправки PWA приглашения: {e}")
            return {"success": False, "error": str(e)}


    async def _send_phone_invitation(
        self, patient: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Создает задачу для регистратуры - позвонить пациенту"""
        # Пока просто логируем, в будущем можно интегрировать с CRM/Task системой
        logger.info(f"Создано уведомление для регистратуры: позвонить пациенту {patient.id} для подтверждения визита {data['visit_id']}")
        return {
            "success": True,
            "channel": "phone",
            "message": "Создана задача для регистратуры",
        }


