"""
Сервис для отправки уведомлений о подтверждении визитов
Поддерживает Telegram, PWA deep links и уведомления регистратуры
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.patient import Patient
from app.models.visit import Visit
from app.services.telegram.bot import TelegramBotService

logger = logging.getLogger(__name__)

VISIT_INVITATION_ERROR = "Не удалось отправить приглашение на подтверждение"
TELEGRAM_INVITATION_ERROR = "Не удалось отправить Telegram-приглашение"
PWA_INVITATION_ERROR = "Не удалось отправить PWA-приглашение"
PHONE_INVITATION_ERROR = "Не удалось создать задачу для регистратуры"
REMINDER_ERROR = "Не удалось отправить напоминание"


def _log_notification_failure(operation: str, exc: Exception) -> None:
    logger.error("%s failed error_type=%s", operation, type(exc).__name__)


class NotificationService:
    """Сервис для отправки уведомлений о подтверждении визитов"""

    def __init__(self, db: Session):
        self.db = db
        self.telegram_service = TelegramBotService()

    async def send_visit_confirmation_invitation(
        self, visit: Visit, channel: str = "auto"
    ) -> dict[str, Any]:
        """
        Отправляет приглашение на подтверждение визита

        Args:
            visit: Объект визита для подтверждения
            channel: Канал отправки (telegram, pwa, phone, auto)

        Returns:
            Dict с результатом отправки
        """
        try:
            # Получаем данные пациента
            patient = (
                self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
            )
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            # Определяем канал автоматически если нужно
            if channel == "auto":
                channel = self._determine_best_channel(patient)

            # Формируем данные для уведомления
            notification_data = self._prepare_notification_data(visit, patient)

            # Отправляем уведомление по выбранному каналу
            if channel == "telegram":
                return await self._send_telegram_invitation(patient, notification_data)
            elif channel == "pwa":
                return await self._send_pwa_invitation(patient, notification_data)
            elif channel == "phone":
                return await self._send_phone_invitation(patient, notification_data)
            else:
                return {"success": False, "error": f"Неподдерживаемый канал: {channel}"}

        except Exception as exc:
            _log_notification_failure("visit_confirmation_invitation", exc)
            return {"success": False, "error": VISIT_INVITATION_ERROR}

    def _determine_best_channel(self, patient: Patient) -> str:
        """Определяет лучший канал для отправки уведомления"""
        # Приоритет: Telegram > PWA > Phone

        # Проверяем есть ли Telegram ID
        if hasattr(patient, 'telegram_id') and patient.telegram_id:
            return "telegram"

        # Проверяем есть ли мобильный номер для PWA
        if patient.phone and patient.phone.startswith('+998'):
            return "pwa"

        # По умолчанию - звонок регистратуры
        return "phone"

    def _prepare_notification_data(
        self, visit: Visit, patient: Patient
    ) -> dict[str, Any]:
        """Подготавливает данные для уведомления"""
        # Получаем услуги визита
        from app.models.visit import VisitService

        visit_services = (
            self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        services_text = []
        total_amount = 0
        for vs in visit_services:
            services_text.append(f"• {vs.name} - {vs.price} сум")
            total_amount += float(vs.price) if vs.price else 0

        # Получаем врача
        doctor_name = "Без врача"
        if visit.doctor_id:
            from app.models.clinic import Doctor

            doctor = self.db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
            if doctor and doctor.user:
                doctor_name = doctor.user.full_name or doctor.user.username

        return {
            "visit_id": visit.id,
            "patient_name": patient.short_name(),
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
        """Возвращает текстовое описание типа визита"""
        if discount_mode == "repeat":
            return "Повторный визит"
        elif discount_mode == "benefit":
            return "Льготный визит"
        elif discount_mode == "all_free":
            return "Бесплатный визит"
        else:
            return "Платный визит"

    async def _send_telegram_invitation(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет приглашение через Telegram"""
        try:
            if not hasattr(patient, 'telegram_id') or not patient.telegram_id:
                return {"success": False, "error": "У пациента нет Telegram ID"}

            # Формируем сообщение
            message = self._format_telegram_message(data)

            # Создаем inline клавиатуру
            keyboard = self._create_telegram_keyboard(data["confirmation_token"])

            # Отправляем через Telegram сервис
            result = await self.telegram_service.send_confirmation_invitation(
                chat_id=patient.telegram_id, message=message, keyboard=keyboard
            )

            if result.get("success"):
                logger.info("Telegram invitation sent channel=telegram")
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

        except Exception as exc:
            _log_notification_failure("telegram_invitation", exc)
            return {"success": False, "error": TELEGRAM_INVITATION_ERROR}

    def _format_telegram_message(self, data: dict[str, Any]) -> str:
        """Форматирует сообщение для Telegram"""
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
        """Создает inline клавиатуру для Telegram"""
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

    async def _send_pwa_invitation(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет приглашение через PWA (SMS с deep link)"""
        try:
            if not patient.phone:
                return {"success": False, "error": "У пациента нет номера телефона"}

            # Формируем deep link для PWA
            pwa_url = f"{settings.PWA_BASE_URL}/confirm-visit?token={data['confirmation_token']}"

            # Формируем SMS сообщение
            sms_text = self._format_sms_message(data, pwa_url)

            # Отправляем SMS (здесь должна быть интеграция с SMS провайдером)
            result = await self._send_sms(patient.phone, sms_text)

            if result.get("success"):
                logger.info("PWA invitation sent channel=pwa")
                return {"success": True, "channel": "pwa", "pwa_url": pwa_url}
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Ошибка отправки SMS"),
                }

        except Exception as exc:
            _log_notification_failure("pwa_invitation", exc)
            return {"success": False, "error": PWA_INVITATION_ERROR}

    def _format_sms_message(self, data: dict[str, Any], pwa_url: str) -> str:
        """Форматирует SMS сообщение"""
        return f"""
Клиника: Подтвердите визит на {data["visit_date"]} в {data["visit_time"]} к врачу {data["doctor_name"]}.
Сумма: {data["total_amount"]} сум.
Подтвердить: {pwa_url}
        """.strip()

    async def _send_sms(self, phone: str, text: str) -> dict[str, Any]:
        """Отправляет SMS (заглушка для интеграции с SMS провайдером)"""
        # TODO: Интеграция с реальным SMS провайдером (Eskiz, PlayMobile и т.д.)
        logger.info("SMS invitation sent channel=sms")
        return {"success": True, "sms_id": f"mock_sms_{datetime.now().timestamp()}"}

    async def _send_phone_invitation(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Создает задачу для регистратуры - позвонить пациенту"""
        try:
            # Создаем уведомление для регистратуры
            notification = await self._create_registrar_notification(patient, data)

            logger.info("Registrar call notification created channel=phone")
            return {
                "success": True,
                "channel": "phone",
                "notification_id": notification.get("id"),
                "message": "Создана задача для регистратуры",
            }

        except Exception as exc:
            _log_notification_failure("phone_invitation", exc)
            return {"success": False, "error": PHONE_INVITATION_ERROR}

    async def _create_registrar_notification(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Создает уведомление для регистратуры"""
        # TODO: Интеграция с системой уведомлений регистратуры
        # Это может быть запись в базу данных, отправка в очередь задач и т.д.

        notification_data = {
            "id": f"phone_confirm_{data['visit_id']}_{datetime.now().timestamp()}",
            "type": "phone_confirmation_required",
            "patient_id": patient.id,
            "patient_name": data["patient_name"],
            "patient_phone": patient.phone,
            "visit_id": data["visit_id"],
            "visit_date": data["visit_date"],
            "visit_time": data["visit_time"],
            "doctor_name": data["doctor_name"],
            "confirmation_token": data["confirmation_token"],
            "created_at": datetime.now(),
            "status": "pending",
        }

        logger.info(
            "Registrar notification placeholder created type=%s status=%s",
            notification_data["type"],
            notification_data["status"],
        )
        return notification_data

    async def send_confirmation_reminder(
        self, visit: Visit, hours_before: int = 24
    ) -> dict[str, Any]:
        """Отправляет напоминание о необходимости подтверждения"""
        try:
            patient = (
                self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
            )
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            # Определяем канал для напоминания
            channel = self._determine_best_channel(patient)

            # Формируем данные для напоминания
            notification_data = self._prepare_notification_data(visit, patient)
            notification_data["is_reminder"] = True
            notification_data["hours_before"] = hours_before

            # Отправляем напоминание
            if channel == "telegram":
                return await self._send_telegram_reminder(patient, notification_data)
            elif channel == "pwa":
                return await self._send_pwa_reminder(patient, notification_data)
            else:
                return await self._send_phone_reminder(patient, notification_data)

        except Exception as exc:
            _log_notification_failure("confirmation_reminder", exc)
            return {"success": False, "error": REMINDER_ERROR}

    async def _send_telegram_reminder(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет напоминание через Telegram"""
        message = f"""
🔔 **Напоминание о подтверждении визита**

Уважаемый(ая) {data["patient_name"]}!

Напоминаем, что у вас запланирован визит:
📅 **Дата:** {data["visit_date"]}
🕐 **Время:** {data["visit_time"]}
👨‍⚕️ **Врач:** {data["doctor_name"]}

⚠️ **Визит требует подтверждения!**
Пожалуйста, подтвердите ваш визит как можно скорее.
        """.strip()

        keyboard = self._create_telegram_keyboard(data["confirmation_token"])

        result = await self.telegram_service.send_confirmation_invitation(
            chat_id=patient.telegram_id, message=message, keyboard=keyboard
        )

        return result

    async def _send_pwa_reminder(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет напоминание через PWA"""
        pwa_url = (
            f"{settings.PWA_BASE_URL}/confirm-visit?token={data['confirmation_token']}"
        )

        sms_text = f"""
Клиника: Напоминание! Подтвердите визит на {data["visit_date"]} в {data["visit_time"]}.
Подтвердить: {pwa_url}
        """.strip()

        return await self._send_sms(patient.phone, sms_text)

    async def _send_phone_reminder(
        self, patient: Patient, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Создает задачу для регистратуры - напомнить пациенту"""
        data["is_reminder"] = True
        return await self._create_registrar_notification(patient, data)
