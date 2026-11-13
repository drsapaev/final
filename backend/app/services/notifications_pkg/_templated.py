"""Templated mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    Any,
    NotificationHistory,
    NotificationHistoryCreate,
    NotificationSenderMixinBase,
    Session,
    User,
    crud_notification_history,
    crud_notification_template,
    datetime,
    logger,
)
from app.services.notifications_pkg._helpers import (
    _normalize_notification_event_type,  # noqa: F401
)


class TemplatedMixin(NotificationSenderMixinBase):
    """Templated methods for NotificationSenderService."""

    async def send_templated_notification(
        self,
        db: Session,
        notification_type: str,
        channel: str,
        recipient_contact: str,
        template_data: dict[str, Any],
        recipient_type: str = "patient",
        recipient_id: int | None = None,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
        priority: str = "normal",
    ) -> NotificationHistory | None:
        """Отправка уведомления с использованием шаблона"""

        raw_notification_type = str(notification_type or "").strip().lower()
        canonical_notification_type = _normalize_notification_event_type(
            raw_notification_type,
            fallback="notification",
        )

        recipient_user = None
        if recipient_id is not None:
            from app.models.patient import Patient
            from app.models.telegram_config import TelegramUser

            if recipient_type == "patient":
                patient = db.query(Patient).filter(Patient.id == recipient_id).first()
                if patient is None:
                    return None
                if patient.user_id:
                    recipient_user = db.query(User).filter(User.id == patient.user_id).first()
            else:
                recipient_user = db.query(User).filter(User.id == recipient_id).first()

            if channel in {"email", "sms"} and not self._channel_opted_in(
                db=db,
                user_id=recipient_user.id if recipient_user is not None else None,
                channel=channel,
                event_type=canonical_notification_type,
            ):
                logger.info(
                    "Templated notification skipped by recipient preference",
                    extra={"channel": channel, "notification_type": canonical_notification_type},
                )
                return None

            if channel == "telegram":
                if recipient_type != "patient":
                    logger.info(
                        "Templated Telegram notification requires a linked patient chat",
                        extra={"notification_type": canonical_notification_type},
                    )
                    return None
                telegram_user = (
                    db.query(TelegramUser)
                    .filter(
                        TelegramUser.patient_id == recipient_id,
                        TelegramUser.active.is_(True),
                        TelegramUser.blocked.is_(False),
                        TelegramUser.notifications_enabled.is_(True),
                    )
                    .order_by(TelegramUser.id.desc())
                    .first()
                )
                if telegram_user is None:
                    return None
                from app.services.notifications_pkg._helpers import (
                    PATIENT_TELEGRAM_EVENT_PREFERENCES,
                )

                preference_field = PATIENT_TELEGRAM_EVENT_PREFERENCES.get(
                    canonical_notification_type, "notifications_enabled"
                )
                if not bool(getattr(telegram_user, preference_field, False)):
                    return None
                recipient_contact = str(telegram_user.chat_id)
        template_lookup_types = [canonical_notification_type]
        if raw_notification_type and raw_notification_type != canonical_notification_type:
            template_lookup_types.append(raw_notification_type)

        # Получаем шаблон
        template = None
        for template_type in template_lookup_types:
            template = crud_notification_template.get_by_type_and_channel(
                db, type=template_type, channel=channel
            )
            if template:
                break

        if not template:
            logger.warning(
                f"Шаблон не найден: {canonical_notification_type}/{channel}"
            )
            # Используем базовый шаблон
            subject = template_data.get("subject", "Уведомление")
            content = template_data.get("message", "Сообщение")
        else:
            subject = (
                self.render_template(template.subject or "", template_data)
                if template.subject
                else None
            )
            content = self.render_template(template.template, template_data)

        # Создаем запись в истории
        history_data = NotificationHistoryCreate(
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_contact=recipient_contact,
            notification_type=canonical_notification_type,
            channel=channel,
            template_id=template.id if template else None,
            subject=subject,
            content=content,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            notification_metadata=template_data,
        )

        history = crud_notification_history.create(db, obj_in=history_data)

        if db and recipient_id is not None:
            platform_service = self._platform_service(db)
            if recipient_user:
                normalized_priority = str(priority or "normal").strip().lower()
                if normalized_priority not in {"low", "normal", "high", "urgent"}:
                    normalized_priority = "normal"
                severity = {
                    "urgent": "critical",
                    "high": "warning",
                    "normal": "info",
                    "low": "info",
                }[normalized_priority]
                await platform_service.record_delivery_for_user(
                    user=recipient_user,
                    event_type=canonical_notification_type,
                    title=subject or "Уведомление",
                    message=content,
                    source_module="notifications",
                    recipient_type=recipient_type,
                    severity=severity,
                    priority=normalized_priority,
                    entity_type=related_entity_type,
                    entity_id=related_entity_id,
                    payload_snapshot={
                        "template_data": template_data,
                    },
                    transport_type=channel,
                )

        # Отправляем уведомление
        success = False
        error_message = None

        try:
            if channel == "email":
                success = await self.send_email(
                    recipient_contact, subject or "Уведомление", content
                )
            elif channel == "sms":
                success = await self.send_sms(recipient_contact, content)
            elif channel == "telegram":
                success = await self.send_telegram(content, recipient_contact)
            else:
                error_message = f"Неподдерживаемый канал: {channel}"

        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка отправки уведомления: {e}")

        # Обновляем статус в истории
        status = "sent" if success else "failed"
        crud_notification_history.update_status(
            db, notification_id=history.id, status=status, error_message=error_message
        )

        return history


    async def send_bulk_notification(
        self,
        db: Session,
        notification_type: str,
        channels: list[str],
        recipients: list[dict[str, Any]],
        template_data: dict[str, Any],
        priority: str = "normal",
    ) -> list[NotificationHistory]:
        """Массовая отправка уведомлений с проверкой настроек пользователей"""
        results = []
        unique_channels = list(dict.fromkeys(channels))
        unique_recipients = []
        seen_recipients: set[tuple[str, Any]] = set()
        for recipient in recipients:
            key = (str(recipient.get("type") or ""), recipient.get("id"))
            if key in seen_recipients:
                continue
            seen_recipients.add(key)
            unique_recipients.append(recipient)

        for recipient in unique_recipients:
            for channel in unique_channels:
                # Получаем контакт для канала
                contact = None
                if channel == "email":
                    contact = recipient.get("email")
                elif channel == "sms":
                    contact = recipient.get("phone")
                elif channel == "telegram":
                    contact = recipient.get("telegram")

                if not contact:
                    continue  # Пропускаем, если нет контакта

                # Объединяем данные получателя с общими данными шаблона
                merged_data = {**template_data, **recipient}

                # Отправляем уведомление
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=merged_data,
                    recipient_type=recipient["type"],
                    recipient_id=recipient["id"],
                    priority=priority,
                )

                if history is not None:
                    results.append(history)

        return results


    async def send_appointment_notification(
        self,
        db: Session,
        appointment_id: int,
        patient_id: int,
        notification_type: str = "appointment_reminder",
        channels: list[str] | None = None,
    ) -> list[NotificationHistory]:
        """Отправка уведомления о записи"""
        from app.crud import patient as patient_crud
        from app.models.appointment import Appointment

        # Получаем данные записи
        appointment = (
            db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )
        if not appointment:
            logger.warning(
                "Appointment notification skipped: appointment not found",
                extra={"notification_type": notification_type},
            )
            return []

        # Получаем данные пациента
        patient = patient_crud.get(db, id=patient_id)
        if not patient:
            logger.warning(
                "Appointment notification skipped: patient not found",
                extra={"notification_type": notification_type},
            )
            return []

        # Данные для шаблона
        template_data = {
            "patient_name": patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            "patient_phone": patient.phone,
            "appointment_date": appointment.appointment_date.strftime("%d.%m.%Y"),
            "appointment_time": (
                appointment.appointment_time.strftime("%H:%M")
                if appointment.appointment_time
                else ""
            ),
            "doctor_name": appointment.doctor_name or "врач",
            # Round-6 (owner P1, PR #3340): the ORM attribute is a Department
            # OBJECT once department_id is persisted — map the canonical key.
            "department": appointment.department_key or "отделение",
            "clinic_name": "Медицинская клиника",
            "clinic_phone": "+998 90 123 45 67",
        }

        # Определяем каналы
        if channels is None:
            channels = ["email", "sms"]

        # Отправляем уведомления
        results = []
        for channel in channels:
            contact = None
            if channel == "email":
                contact = patient.email
            elif channel == "sms":
                contact = patient.phone
            elif channel == "telegram":
                from app.models.telegram_config import TelegramUser

                telegram_user = (
                    db.query(TelegramUser)
                    .filter(
                        TelegramUser.patient_id == patient.id,
                        TelegramUser.active.is_(True),
                        TelegramUser.blocked.is_(False),
                        TelegramUser.notifications_enabled.is_(True),
                    )
                    .order_by(TelegramUser.id.desc())
                    .first()
                )
                contact = str(telegram_user.chat_id) if telegram_user else None

            if contact:
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=template_data,
                    recipient_type="patient",
                    recipient_id=patient_id,
                    related_entity_type="appointment",
                    related_entity_id=appointment_id,
                )
                if history is not None:
                    results.append(history)

        return results


    async def send_payment_notification(
        self,
        patient_email: str,
        patient_phone: str,
        amount: float,
        currency: str,
        visit_date: datetime,
        doctor_name: str,
        db: Session | None = None,
        patient_id: int | None = None,
    ) -> dict[str, bool]:
        """Отправка уведомления об оплате"""
        subject = "Подтверждение оплаты"

        email_body = f"""
        Здравствуйте!

        Получена оплата за визит к врачу {doctor_name}.
        Сумма: {amount} {currency}
        Дата визита: {visit_date.strftime('%d.%m.%Y в %H:%M')}

        Спасибо за оплату!

        С уважением,
        Администрация клиники
        """

        sms_message = f"Оплата {amount} {currency} получена за визит к {doctor_name}"

        telegram_message = f"""
        💰 <b>Подтверждение оплаты</b>

        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        💵 Сумма: {amount} {currency}
        👨‍⚕️ Врач: {doctor_name}
        📅 Дата визита: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        # Отправляем уведомления
        results = {}

        if db and patient_id:
            from app.models.patient import Patient

            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient and patient.user_id:
                await self.send_push(
                    user_id=patient.user_id,
                    title=subject,
                    message=f"Оплата {amount} {currency} за визит к {doctor_name} подтверждена",
                    data={
                        "type": "payment_notification",
                        "amount": amount,
                        "currency": currency,
                        "visit_date": visit_date.isoformat(),
                        "doctor_name": doctor_name,
                    },
                    db=db,
                )

        if patient_email and self._patient_channel_opted_in(
            db=db,
            patient_id=patient_id,
            channel="email",
            event_type="payment_notification",
        ):
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone and self._patient_channel_opted_in(
            db=db,
            patient_id=patient_id,
            channel="sms",
            event_type="payment_notification",
        ):
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        if db and patient_id:
            results["telegram"] = await self.send_patient_telegram_event_notification(
                db=db,
                patient_id=patient_id,
                event_type="payment_notification",
                metadata={
                    "amount": amount,
                    "currency": currency,
                    "visit_date": visit_date.strftime("%d.%m.%Y %H:%M"),
                    "doctor_name": doctor_name,
                },
            )
        else:
            results["telegram"] = False

        return results


    async def send_payment_notification_by_id(
        self,
        db: Session,
        payment_id: int,
        patient_id: int,
        amount: float,
        currency: str = "UZS",
        notification_type: str = "payment_success",
        channels: list[str] | None = None,
    ) -> list[NotificationHistory]:
        """Отправка уведомления об оплате"""
        from app.crud import patient as patient_crud


        # Получаем данные пациента
        canonical_notification_type = _normalize_notification_event_type(
            notification_type,
            fallback="payment_notification",
        )

        patient = patient_crud.get(db, id=patient_id)
        if not patient:
            logger.warning(
                "Payment notification skipped: patient not found",
                extra={"notification_type": canonical_notification_type},
            )
            return []


        # Данные для шаблона
        template_data = {
            "patient_name": patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            "amount": amount,
            "currency": currency,
            "formatted_amount": f"{amount:,.0f} {currency}",
            "payment_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "clinic_name": "Медицинская клиника",
            "clinic_phone": "+998 90 123 45 67",
        }

        # Определяем каналы
        if channels is None:
            channels = ["email", "sms"]

        # Отправляем уведомления
        results = []
        for channel in channels:
            contact = None
            if channel == "email":
                contact = patient.email
            elif channel == "sms":
                contact = patient.phone
            elif channel == "telegram":
                from app.models.telegram_config import TelegramUser

                telegram_user = (
                    db.query(TelegramUser)
                    .filter(
                        TelegramUser.patient_id == patient.id,
                        TelegramUser.active.is_(True),
                        TelegramUser.blocked.is_(False),
                        TelegramUser.notifications_enabled.is_(True),
                    )
                    .order_by(TelegramUser.id.desc())
                    .first()
                )
                contact = str(telegram_user.chat_id) if telegram_user else None

            if contact:
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=canonical_notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=template_data,
                    recipient_type="patient",
                    recipient_id=patient_id,
                    related_entity_type="payment",
                    related_entity_id=payment_id,
                )
                if history is not None:
                    results.append(history)

        return results

    # === Business Logic Methods (Merged from Mobile/Telegram Services) ===


