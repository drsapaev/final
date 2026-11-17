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
        expected_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Отправляет напоминание о необходимости подтверждения"""
        from app.models.patient import Patient
        from app.models.visit import Visit

        try:
            # Never reuse the worker's potentially stale identity-map row:
            # a transfer may have changed both owner and bearer token.
            visit = db.query(Visit).filter(Visit.id == visit_id).populate_existing().first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            def matches_expected(current: Any) -> bool:
                if expected_context is None:
                    return True
                keys = ("patient_id", "confirmation_context_epoch", "reminder_generation",
                        "reminder_claimed_at", "confirmation_token")
                if set(expected_context) != set(keys):
                    return False
                for key in keys:
                    actual = getattr(current, key)
                    expected = expected_context[key]
                    if key == "reminder_claimed_at" and actual is not None and expected is not None:
                        actual, expected = actual.replace(tzinfo=None), expected.replace(tzinfo=None)
                    if actual != expected:
                        return False
                return True

            if not matches_expected(visit):
                db.rollback()
                return {"success": False, "error": "Контекст визита изменился"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).populate_existing().first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            # PR-1 (Codex round 18, P1): the reminder producer may pin the
            # delivery channel to one PERMITTED BY THE VISIT'S contract —
            # when it does, the auto-selection is bypassed entirely.
            channel = channel or self._determine_best_channel(patient, db)
            notification_data = self._prepare_notification_data(db, visit, patient)
            notification_data["is_reminder"] = True
            notification_data["hours_before"] = hours_before
            snapshot = (visit.patient_id, visit.confirmation_context_epoch,
                        visit.confirmation_token, visit.reminder_generation,
                        visit.confirmation_channel, visit.status, visit.reminder_claimed_at)
            sms_opted_in = True

            # Resolve patient preferences while the read transaction is
            # active. Provider dispatch happens after commit, so it must not
            # trigger another query on this session immediately before await.
            if channel == "pwa":
                sms_opted_in = self._patient_channel_opted_in(
                    db=db,
                    patient_id=patient.id,
                    channel="sms",
                    event_type="appointment_confirmation",
                )

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
                        TelegramUser.chat_id > 0,
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
                link_id = link.id
                link_epoch = link.patient_link_epoch
                linked_patient_id = visit.patient_id
                from app.services.visit_confirmation_service import (
                    build_telegram_visit_action_token,
                )

                telegram_capability = build_telegram_visit_action_token(
                    visit_id=visit.id, confirmation_token=visit.confirmation_token,
                    link_id=link_id, chat_id=chat_id, patient_id=patient.id,
                    link_epoch=link_epoch, visit_context_epoch=visit.confirmation_context_epoch,
                    purpose="view",
                )
            db.commit()

            current = db.query(
                Visit.patient_id, Visit.confirmation_context_epoch,
                Visit.confirmation_token, Visit.reminder_generation,
                Visit.confirmation_channel, Visit.status, Visit.reminder_claimed_at,
            ).filter(Visit.id == visit_id).first()
            if current is None or tuple(current) != snapshot or not matches_expected(current):
                db.rollback()
                return {"success": False, "error": "Контекст визита изменился"}

            if channel == "telegram":
                # Recheck immediately before dispatch. A provider call cannot
                # be recalled, so its text contains no patient or visit data.
                current_link = (
                    db.query(TelegramUser).filter(
                        TelegramUser.id == link_id, TelegramUser.patient_id == linked_patient_id,
                        TelegramUser.chat_id == chat_id,
                        TelegramUser.patient_link_epoch == link_epoch,
                        TelegramUser.active.is_(True), TelegramUser.blocked.is_(False),
                        TelegramUser.notifications_enabled.is_(True),
                        TelegramUser.appointment_reminders.is_(True),
                    ).populate_existing().first()
                )
                db.commit()
                if current_link is None:
                    return {"success": False, "error": "Пациент не привязал Telegram"}
                message = "У вас новое уведомление."
                keyboard = self._create_telegram_keyboard(
                    telegram_capability
                )
                result = await self.telegram_bot.send_confirmation_invitation(
                    chat_id=chat_id, message=message, keyboard=keyboard
                )
                return {"success": result.get("success"), "error": None if result.get("success") else "Ошибка отправки Telegram"}
            elif channel == "pwa":
                sms_opted_in = self._patient_channel_opted_in(
                    db=db, patient_id=snapshot[0], channel="sms",
                    event_type="appointment_confirmation",
                )
                db.commit()
                if not sms_opted_in:
                    return {
                        "success": False,
                        "error": "SMS отключены настройками пациента",
                    }
                return await self._send_pwa_invitation(
                    patient,
                    notification_data,
                    sms_opted_in=sms_opted_in,
                )
            else:
                db.commit()
                return await self._send_phone_invitation(
                    patient, notification_data, db=db
                )

        except Exception as e:
            logger.error("Ошибка отправки напоминания (%s)", type(e).__name__)
            return {"success": False, "error": "Ошибка отправки напоминания"}

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
