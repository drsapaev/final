"""System mixin for NotificationSenderService.

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


class SystemMixin(NotificationSenderMixinBase):
    """System methods for NotificationSenderService."""

    async def send_system_alert(
        self,
        alert_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        db: Session | None = None,
        actor_id: int | None = None,
        actor_role: str | None = None,
    ) -> bool:
        """Отправка системного оповещения"""
        alert_message = f"""
        🚨 <b>Системное оповещение</b>

        Тип: {alert_type}
        Сообщение: {message}
        """

        if details:
            alert_message += "\nДетали:\n"
            for key, value in details.items():
                alert_message += f"• {key}: {value}\n"

        alert_message += f"\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"

        if db:
            platform_service = self._platform_service(db)
            admins = platform_service.resolve_users_for_role("admin")
            await platform_service.record_delivery_for_users(
                users=admins,
                event_type="system_alert",
                title=f"Системное оповещение: {alert_type}",
                message=message,
                source_module="system",
                recipient_type="user",
                severity="critical" if alert_type.lower() in {"critical", "security"} else "warning",
                priority="urgent" if alert_type.lower() in {"critical", "security"} else "high",
                actor_id=actor_id,
                actor_role=actor_role,
                payload_snapshot={
                    "alert_type": alert_type,
                    "message": message,
                    "details": details or {},
                },
                transport_type="system_alert",
            )

        return await self.send_telegram(alert_message)


    async def send_all_free_request_notification(
        self,
        *,
        db: Session,
        visit: Any,
        actor_user: User,
    ) -> bool:
        """Create the canonical inbox signal for a pending All Free request."""
        try:
            platform_service = self._platform_service(db)
            admin_users = platform_service.resolve_users_for_role("admin")
            if not admin_users:
                logger.warning(
                    "[FIX:NOTIFICATIONS] all_free_requested skipped: no admin recipients",
                    extra={"visit_id": getattr(visit, "id", None)},
                )
                return False

            title = "Новая заявка All Free"
            body = f"Визит #{visit.id} ожидает одобрения All Free."
            payload_snapshot = {
                "title": title,
                "message": body,
                "metadata": {
                    "visit_id": visit.id,
                    "patient_id": visit.patient_id,
                    "doctor_id": visit.doctor_id,
                    "discount_mode": visit.discount_mode,
                    "approval_status": visit.approval_status,
                    "request_source": getattr(visit, "source", "desk"),
                    "requested_by": actor_user.id,
                },
            }

            await platform_service.record_delivery_for_users(
                users=admin_users,
                event_type="all_free_requested",
                title=title,
                message=body,
                source_module="registrar",
                recipient_type="user",
                severity="warning",
                priority="high",
                actor_id=actor_user.id,
                actor_role=actor_user.role,
                entity_type="visit",
                entity_id=str(visit.id),
                payload_snapshot=payload_snapshot,
                deep_link="/admin/all-free-requests",
            )
            logger.info(
                "[FIX:NOTIFICATIONS] created all_free_requested delivery",
                extra={
                    "visit_id": visit.id,
                    "recipient_count": len(admin_users),
                    "actor_id": actor_user.id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] failed to create all_free_requested delivery",
                extra={
                    "visit_id": getattr(visit, "id", None),
                    "actor_id": getattr(actor_user, "id", None),
                    "error": str(exc),
                },
            )
            return False


    async def send_all_free_decision_notification(
        self,
        *,
        db: Session,
        visit: Any,
        actor_user: User,
        rejection_reason: str | None = None,
    ) -> bool:
        """Create canonical inbox signals for All Free approve/reject decisions."""
        try:
            from app.models.patient import Patient

            platform_service = self._platform_service(db)
            recipients: dict[int, User] = {}

            registrar_user_id = self._extract_prefixed_user_id(
                getattr(visit, "confirmed_by", None),
                "registrar_",
            )
            if registrar_user_id:
                registrar_user = (
                    db.query(User)
                    .filter(User.id == registrar_user_id, User.is_active.is_(True))
                    .first()
                )
                if registrar_user:
                    recipients[registrar_user.id] = registrar_user

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if patient and patient.user_id:
                patient_user = (
                    db.query(User)
                    .filter(User.id == patient.user_id, User.is_active.is_(True))
                    .first()
                )
                if patient_user:
                    recipients[patient_user.id] = patient_user

            if not recipients:
                logger.warning(
                    "[FIX:NOTIFICATIONS] all_free decision skipped: no linked recipients",
                    extra={"visit_id": getattr(visit, "id", None)},
                )
                return False

            approved = str(getattr(visit, "approval_status", "")).lower() == "approved"
            event_type = "all_free_approved" if approved else "all_free_rejected"
            title = "Заявка All Free одобрена" if approved else "Заявка All Free отклонена"
            body = (
                f"Заявка All Free для визита #{visit.id} одобрена."
                if approved
                else f"Заявка All Free для визита #{visit.id} отклонена."
            )
            payload_snapshot = {
                "title": title,
                "message": body,
                "metadata": {
                    "visit_id": visit.id,
                    "patient_id": visit.patient_id,
                    "doctor_id": visit.doctor_id,
                    "approval_status": visit.approval_status,
                    "approver_id": actor_user.id,
                    "approver_role": actor_user.role,
                    "rejection_reason": rejection_reason,
                },
            }

            await platform_service.record_delivery_for_users(
                users=list(recipients.values()),
                event_type=event_type,
                title=title,
                message=body,
                source_module="registrar",
                recipient_type="user",
                severity="info" if approved else "warning",
                priority="high",
                actor_id=actor_user.id,
                actor_role=actor_user.role,
                entity_type="visit",
                entity_id=str(visit.id),
                payload_snapshot=payload_snapshot,
                deep_link="/registrar",
            )
            logger.info(
                "[FIX:NOTIFICATIONS] created %s delivery",
                event_type,
                extra={
                    "visit_id": visit.id,
                    "recipient_count": len(recipients),
                    "actor_id": actor_user.id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] failed to create all_free decision delivery",
                extra={
                    "visit_id": getattr(visit, "id", None),
                    "actor_id": getattr(actor_user, "id", None),
                    "approval_status": getattr(visit, "approval_status", None),
                    "error": str(exc),
                },
            )
            return False


    async def send_message_received_notification(
        self,
        *,
        db: Session,
        recipient: User,
        sender: User,
        message_id: int,
        conversation_id: str,
        message_type: str,
        preview: str | None = None,
        patient_id: int | None = None,
    ) -> bool:
        """Create a canonical inbox signal for a newly received chat message."""
        try:
            platform_service = self._platform_service(db)
            sender_name = sender.full_name or sender.username or sender.email or f"User {sender.id}"
            normalized_message_type = str(message_type or "text").strip().lower()

            if normalized_message_type == "voice":
                body = f"{sender_name} отправил(а) голосовое сообщение."
            elif normalized_message_type in {"file", "document"}:
                body = f"{sender_name} отправил(а) файл."
            elif normalized_message_type == "image":
                body = f"{sender_name} отправил(а) изображение."
            else:
                preview_text = (preview or "").strip()
                body = (
                    f"{sender_name}: {preview_text}"
                    if preview_text
                    else f"Новое сообщение от {sender_name}"
                )

            title = "Новое сообщение"
            payload_snapshot = {
                "title": title,
                "message": body,
                "metadata": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "sender_id": sender.id,
                    "sender_name": sender_name,
                    "message_type": normalized_message_type,
                    "patient_id": patient_id,
                },
            }

            await platform_service.record_delivery_for_user(
                user=recipient,
                event_type="message_received",
                title=title,
                message=body,
                source_module="messages",
                recipient_type="user",
                severity="info",
                priority="normal",
                actor_id=sender.id,
                actor_role=sender.role,
                entity_type="message",
                entity_id=str(message_id),
                payload_snapshot=payload_snapshot,
                deep_link=f"/messages?user={sender.id}",
            )
            logger.info(
                "[FIX:NOTIFICATIONS] created message_received delivery",
                extra={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "sender_id": sender.id,
                    "recipient_id": recipient.id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] failed to create message_received delivery",
                extra={
                    "message_id": message_id,
                    "sender_id": getattr(sender, "id", None),
                    "recipient_id": getattr(recipient, "id", None),
                    "error": str(exc),
                },
            )
            return False


