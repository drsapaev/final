"""Reminders mixin for NotificationSenderService.

Split from notifications.py.
"""

from __future__ import annotations

from app.services.notifications_pkg._base import (
    Any,
    NotificationSenderMixinBase,
    Session,
    logger,
)


class RemindersMixin(NotificationSenderMixinBase):
    """Reminders methods for NotificationSenderService."""

    async def send_confirmation_reminder(
        self,
        db: Session,
        visit_id: int,
        hours_before: int = 24,
        channel: str | None = None,
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

            # PR-1 (Codex round 18, P1): the reminder producer may pin the
            # delivery channel to one PERMITTED BY THE VISIT'S contract —
            # when it does, the auto-selection is bypassed entirely.
            channel = channel or self._determine_best_channel(patient, db)
            notification_data = self._prepare_notification_data(db, visit, patient)
            notification_data["is_reminder"] = True
            notification_data["hours_before"] = hours_before

            # Codex round 12, P2: the provider dispatch can hold this
            # connection for up to the arq job timeout (300s). End the
            # read-only transaction BEFORE the await so a slow provider
            # never pins an idle-in-transaction connection (max_jobs
            # workers would otherwise hold every connection and block
            # vacuum / operational DDL). The reminder worker's session is
            # created with expire_on_commit=False, so the attribute reads
            # below (patient ids/phone) stay in-memory instead of
            # reopening a transaction right under the await. Only reads
            # happened on this session so far — the commit carries no
            # caller state.
            if channel == "telegram":
                from app.models.telegram_config import TelegramUser

                link = (
                    db.query(TelegramUser)
                    .filter(
                        TelegramUser.patient_id == visit.patient_id,
                        TelegramUser.active.is_(True),
                        TelegramUser.blocked.is_(False),
                        TelegramUser.notifications_enabled.is_(True),
                        TelegramUser.appointment_reminders.is_(True),
                    )
                    .order_by(TelegramUser.id.desc())
                    .first()
                )
                if link is None:
                    return {
                        "success": False,
                        "error": "Пациент не привязал Telegram",
                    }
                chat_id = link.chat_id
            db.commit()

            if channel == "telegram":
                # Упрощенная версия напоминания для Telegram (можно расширить)
                message = f"🔔 Напоминание! Пожалуйста, подтвердите визит к врачу {notification_data['doctor_name']} на {notification_data['visit_date']} {notification_data['visit_time']}."
                keyboard = self._create_telegram_keyboard(
                    notification_data["confirmation_token"]
                )
                result = await self.telegram_bot.send_confirmation_invitation(
                    chat_id=chat_id, message=message, keyboard=keyboard
                )
                return {"success": result.get("success"), "error": result.get("error")}
            elif channel == "pwa":
                return await self._send_pwa_invitation(
                    patient, notification_data, db=db
                )
            else:
                return await self._send_phone_invitation(
                    patient, notification_data, db=db
                )

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
            return {"success": False, "error": str(e)}

    async def send_telegram_message(
        self,
        user_id: int | str,
        message: str,
        parse_mode: str = "HTML",
        *,
        db: Session | None = None,
    ) -> dict[str, Any]:
        """
        Send through the Telegram link owned by this patient account.

        ``user_id`` is never treated as a Telegram chat ID. The legacy
        wrapper remains for compatibility, but requires a DB session so the
        destination can be resolved from the canonical TelegramUser link.
        """
        del parse_mode  # The canonical sender always applies the safe HTML mode.
        if db is None:
            return {"success": False, "error": "database session required"}
        try:
            normalized_user_id = int(user_id)
        except (TypeError, ValueError):
            return {"success": False, "error": "patient account ID required"}

        success = await self.send_linked_user_telegram_notification(
            db=db,
            user_id=normalized_user_id,
            event_type="notification",
            message=message,
        )
        return {"success": success}

    # === End merged methods ===
