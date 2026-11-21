"""Formatting mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    Any,
    NotificationSenderMixinBase,
    Session,
    logger,
    settings,
)


class FormattingMixin(NotificationSenderMixinBase):
    """Formatting methods for NotificationSenderService."""

    def _determine_best_channel(self, patient: Any, db: Session | None = None) -> str:
        """Определяет лучший канал для отправки уведомления"""
        # Приоритет: Telegram > PWA > Phone
        if db is not None and getattr(patient, "id", None) is not None:
            from app.models.telegram_config import TelegramUser

            linked_chat = (
                db.query(TelegramUser.id)
                .filter(
                    TelegramUser.patient_id == patient.id,
                    TelegramUser.chat_id > 0,
                    TelegramUser.active.is_(True),
                    TelegramUser.blocked.is_(False),
                    TelegramUser.notifications_enabled.is_(True),
                    TelegramUser.appointment_reminders.is_(True),
                )
                .first()
            )
            if linked_chat:
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
        from app.services.payment_invariant_service import PaymentInvariantService

        invariant = PaymentInvariantService(db)
        quote = invariant.compute_visit_quote(visit)
        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).populate_existing().all()
        )
        # Refreshing names and quantities is a separate query: compare another
        # complete quote so a concurrent line change cannot mix two contexts.
        if (invariant.compute_visit_quote(visit) != quote
                or getattr(patient, "id", None) != quote.patient_id
                or {vs.id for vs in visit_services} != set(quote.line_totals)):
            raise ValueError("Контекст визита изменился")
        if quote.currency is None and (quote.line_totals or quote.total):
            raise ValueError("Валюта визита требует сверки")

        services_text = []
        currency_label = "сум" if quote.currency == "UZS" else quote.currency
        for vs in visit_services:
            quantity = f" × {vs.qty}" if vs.qty != 1 else ""
            services_text.append(f"• {vs.name}{quantity} - {quote.line_totals[vs.id]} {currency_label}")

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
            "total_amount": quote.total,
            "currency": quote.currency,
            "confirmation_token": visit.confirmation_token,
            "confirmation_context_epoch": visit.confirmation_context_epoch,
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

💵 **Общая сумма:** {data["total_amount"]} {data.get("currency") or "(валюта не указана)"}

⏰ **Подтвердите визит до:** {data["expires_at"].strftime("%d.%m.%Y %H:%M") if data["expires_at"] else "Не указано"}

Нажмите кнопку ниже для подтверждения:
        """.strip()
        return message


    def _create_telegram_keyboard(
        self, confirmation_token: str
    ) -> list[list[dict[str, str]]]:
        # DOCINVITE-BE-001 / NOTIFYTGPHONEURL-BE-001 (audit #3892): the
        # historical third button used a ``tel:`` URL scheme that Telegram
        # inline keyboards do not support, built from
        # ``settings.CLINIC_PHONE`` — a field the Settings model never
        # declared. Every invitation died with AttributeError inside the
        # keyboard builder (caught downstream as success:false) BEFORE the
        # bot dispatch, so even the merged TelegramUser identity resolution
        # never delivered an initial invitation. Telegram inline keyboards
        # support only https/tg:// URLs — the unsupported contact button is
        # removed; authenticated preview must precede a decision.
        return [
            [
                {
                    "text": "Просмотреть",
                    "callback_data": f"view_visit:{confirmation_token}",
                }
            ],
        ]


    def _format_sms_message(self, data: dict[str, Any], pwa_url: str) -> str:
        # The fragment remains the existing scoped confirmation capability;
        # no appointment, physician or payment details go over SMS.
        return f"У вас новое уведомление. Откройте ссылку: {pwa_url}"


    async def _send_telegram_invitation(
        self, patient: Any, data: dict[str, Any], db: Session | None = None,
        *, expected_link: tuple[int, int] | None = None,
    ) -> dict[str, Any]:
        """Отправляет приглашение через Telegram"""
        try:
            if db is None:
                return {"success": False, "error": "Для Telegram нужна привязка пациента"}

            from app.models.telegram_config import TelegramUser

            link_query = db.query(TelegramUser).filter(
                    TelegramUser.patient_id == patient.id,
                    TelegramUser.chat_id > 0,
                    TelegramUser.active.is_(True),
                    TelegramUser.blocked.is_(False),
                    TelegramUser.notifications_enabled.is_(True),
                    TelegramUser.appointment_reminders.is_(True),
            )
            if expected_link is not None:
                link_query = link_query.filter(
                    TelegramUser.id == expected_link[0],
                    TelegramUser.patient_link_epoch == expected_link[1],
                )
            telegram_user = link_query.order_by(TelegramUser.id.desc()).first()
            if telegram_user is None:
                return {"success": False, "error": "У пациента нет активной привязки Telegram"}

            from app.services.visit_confirmation_service import (
                build_telegram_visit_action_token,
            )

            capability = build_telegram_visit_action_token(
                visit_id=data["visit_id"], confirmation_token=data["confirmation_token"],
                link_id=telegram_user.id, chat_id=telegram_user.chat_id,
                patient_id=patient.id, link_epoch=telegram_user.patient_link_epoch,
                visit_context_epoch=data["confirmation_context_epoch"], purpose="view",
            )
            # Telegram delivery cannot be recalled after a concurrent opt-out.
            # Keep the push itself neutral; the action remains actor-bound.
            message = "У вас новое уведомление."
            keyboard = self._create_telegram_keyboard(capability)

            current_link = (
                db.query(TelegramUser).filter(
                    TelegramUser.id == telegram_user.id,
                    TelegramUser.patient_id == patient.id,
                    TelegramUser.chat_id == telegram_user.chat_id,
                    TelegramUser.patient_link_epoch == telegram_user.patient_link_epoch,
                    TelegramUser.active.is_(True), TelegramUser.blocked.is_(False),
                    TelegramUser.notifications_enabled.is_(True),
                    TelegramUser.appointment_reminders.is_(True),
                ).populate_existing().first()
            )
            if current_link is None:
                return {"success": False, "error": "У пациента нет активной привязки Telegram"}

            # Используем telegram_bot для отправки
            result = await self.telegram_bot.send_confirmation_invitation(
                chat_id=current_link.chat_id, message=message, keyboard=keyboard
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
                    "error": "Ошибка отправки Telegram",
                }

        except Exception as e:
            logger.error("Ошибка отправки Telegram приглашения (%s)", type(e).__name__)
            return {"success": False, "error": "Ошибка отправки Telegram"}


    async def _send_pwa_invitation(
        self,
        patient: Any,
        data: dict[str, Any],
        db: Session | None = None,
        *,
        sms_opted_in: bool | None = None,
    ) -> dict[str, Any]:
        """Отправляет приглашение через PWA (SMS с deep link)"""
        try:
            if not patient.phone:
                return {"success": False, "error": "У пациента нет номера телефона"}
            if sms_opted_in is None:
                sms_opted_in = self._patient_channel_opted_in(
                    db=db,
                    patient_id=getattr(patient, "id", None),
                    channel="sms",
                    event_type="appointment_confirmation",
                )
            if not sms_opted_in:
                return {"success": False, "error": "SMS отключены настройками пациента"}

            # Canonical public base URL for user-facing deep links — the
            # same source as the password-reset link, Telegram web-app
            # buttons and QR codes. The PWA is served by the same frontend
            # origin; there is no separate PWA_BASE_URL setting (staging
            # Check 5b finding: reading it crashed every PWA reminder).
            # rstrip("/"): Settings already normalizes FRONTEND_URL, but the
            # deep-link builders follow the defensive repo convention
            # (see telegram_service) so a stray trailing slash can never
            # yield a "//confirm-visit" path that misses the route.
            # The fragment never enters the HTTP request target or Referer.
            pwa_url = (
                f"{settings.FRONTEND_URL.rstrip('/')}"
                f"/confirm-visit#token={data['confirmation_token']}"
            )
            sms_text = self._format_sms_message(data, pwa_url)

            success = await self.send_sms(patient.phone, sms_text)

            if success:
                logger.info(f"PWA приглашение отправлено пациенту {patient.id}")
                return {"success": True, "channel": "pwa", "pwa_url": pwa_url}
            else:
                return {"success": False, "error": "Ошибка отправки SMS"}

        except Exception as exc:
            # Provider exceptions may contain the SMS body and capability URL.
            logger.error("Ошибка отправки PWA приглашения (%s)", type(exc).__name__)
            return {"success": False, "error": "Ошибка отправки PWA приглашения"}


    async def _send_phone_invitation(
        self, patient: Any, data: dict[str, Any], db: Session | None = None
    ) -> dict[str, Any]:
        """Create a durable protected-inbox action for the registrar team."""
        if db is None:
            return {
                "success": False,
                "error": "Не удалось создать задачу регистратуре",
            }

        visit_id = data.get("visit_id")
        patient_id = getattr(patient, "id", None)
        created = await self.send_canonical_notification_to_roles(
            db=db,
            roles=["registrar"],
            event_type="appointment_confirmation_task",
            title="Задача регистратуре: позвонить пациенту",
            message=f"Позвоните пациенту для подтверждения визита №{visit_id}.",
            source_module="visit_confirmation",
            metadata={"visit_id": visit_id, "patient_id": patient_id},
            deep_link="/registrar",
            severity="warning",
            priority="high",
            entity_type="visit",
            entity_id=visit_id,
        )
        return {
            "success": created,
            "channel": "phone",
            "message": (
                "Создана задача для регистратуры"
                if created
                else "Не удалось создать задачу для регистратуры"
            ),
        }
