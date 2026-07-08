"""Medical mixin for NotificationSenderService.

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


class MedicalMixin(NotificationSenderMixinBase):
    """Medical methods for NotificationSenderService."""

    async def send_lab_results_notification(
        self,
        db: Session,
        user_id: int,
        test_name: str,
        test_date: datetime,
        lab_result_id: int | None = None,
    ) -> dict[str, bool]:
        """Уведомление о готовности результатов анализов"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = "Результаты анализов готовы"
            message = f"Результаты анализа '{test_name}' от {test_date.strftime('%d.%m.%Y')} готовы к просмотру."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"🔬 <b>{subject}</b>\n\n{message}"
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "lab_results", "lab_result_id": lab_result_id},
                    db=db
                )

            return results
        except Exception as e:
            logger.error(f"Error sending lab results notification: {e}")
            return {}


    async def send_prescription_ready_notification(
        self,
        db: Session,
        user_id: int,
        prescription_id: int,
        doctor_name: str,
    ) -> dict[str, bool]:
        """Уведомление о готовности рецепта"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = "Рецепт готов"
            message = f"Ваш рецепт №{prescription_id} от врача {doctor_name} готов."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"""
💊 <b>{subject}</b>

👨‍⚕️ Врач: {doctor_name}
📄 Рецепт №{prescription_id}
📅 Дата: {datetime.now().strftime("%d.%m.%Y")}

Рецепт доступен в приложении.
"""
                # TODO: Add download button if using pure telegram bot API manually,
                # but send_telegram_message is simple text.
                # For now keeping clear text.
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "prescription_ready", "prescription_id": prescription_id},
                    db=db
                )

            return results
        except Exception as e:
            logger.error(f"Error sending prescription notification: {e}")
            return {}


    async def send_schedule_change_notification(
        self,
        db: Session,
        user_id: int,
        change_type: str,
        old_data: dict[str, Any],
        new_data: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Уведомление об изменении в расписании"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = ""
            message = ""

            if change_type == "cancelled":
                subject = "Визит отменен"
                message = f"Визит к врачу {old_data.get('doctor')} на {old_data.get('date')} {old_data.get('time')} отменен."
            elif change_type == "rescheduled":
                subject = "Визит перенесен"
                message = f"Визит перенесен на {new_data.get('date')} {new_data.get('time')}."
            elif change_type == "doctor_changed":
                subject = "Смена врача"
                message = f"Ваш лечащий врач изменен на {new_data.get('doctor')}."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"📅 <b>{subject}</b>\n\n{message}"
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "schedule_change", "change_type": change_type},
                    db=db
                )

            return results
        except Exception as e:
            logger.error(f"Error sending schedule change notification: {e}")
            return {}


    async def send_appointment_cancellation(
        self,
        db: Session,
        appointment_id: int,
        reason: str | None = None
    ) -> bool:
        """Отправка уведомления об отмене записи (Wrapper logic)"""
        from app.models.appointment import Appointment

        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False

        old_data = {
            "doctor": appointment.doctor.name if appointment.doctor else "Врач",
            "date": appointment.appointment_date.strftime("%d.%m.%Y"),
            "time": appointment.appointment_date.strftime("%H:%M") # Assuming appointment_date has time or separate field
        }

        return await self.send_schedule_change_notification(
            db=db,
            user_id=appointment.patient_id,
            change_type="cancelled",
            old_data=old_data
        )


    async def send_visit_confirmation_invitation(
        self, db: Session, visit_id: int, channel: str = "auto"
    ) -> dict[str, Any]:
        """
        Отправляет приглашение на подтверждение визита
        """
        from app.models.patient import Patient
        from app.models.visit import Visit

        try:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            # Определяем канал автоматически если нужно
            if channel == "auto":
                channel = self._determine_best_channel(patient)

            # Формируем данные для уведомления
            notification_data = self._prepare_notification_data(db, visit, patient)

            # Отправляем уведомление по выбранному каналу
            if channel == "telegram":
                return await self._send_telegram_invitation(patient, notification_data)
            elif channel == "pwa":
                return await self._send_pwa_invitation(patient, notification_data)
            elif channel == "phone":
                return await self._send_phone_invitation(patient, notification_data)
            else:
                return {"success": False, "error": f"Неподдерживаемый канал: {channel}"}

        except Exception as e:
            logger.error(f"Ошибка отправки приглашения на подтверждение: {e}")
            return {"success": False, "error": str(e)}


