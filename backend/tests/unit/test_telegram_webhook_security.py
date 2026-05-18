from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import admin_telegram, telegram_webhook
from app.models.audit import AuditLog
from app.services import telegram_bot
from app.services.telegram_templates import TelegramTemplatesService
from app.models.lab import LabReportInstance, LabReportTemplate, LabReportTemplateVersion
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.telegram_config import (
    TelegramConfig,
    TelegramMessage,
    TelegramStaffLinkToken,
    TelegramUser,
)


class FakeTelegramBotService:
    def __init__(self, active: bool = True):
        self.active = active
        self.initialize = AsyncMock(return_value=True)
        self.process_webhook_update = AsyncMock(return_value=None)
        self._send_message = AsyncMock(return_value=True)
        self._send_document = AsyncMock(return_value=(True, 77, None))
        self.bot_token = "bot-token"
        self.webhook_url = "https://example.com/webhook"


def _link_patient_to_chat(db_session, *, chat_id: int, patient_id: int) -> TelegramUser:
    telegram_user = TelegramUser(
        chat_id=chat_id,
        patient_id=patient_id,
        username="patient_chat",
        first_name="Patient",
        language_code="ru",
        notifications_enabled=True,
        appointment_reminders=True,
        lab_notifications=True,
        active=True,
        blocked=False,
    )
    db_session.add(telegram_user)
    db_session.commit()
    db_session.refresh(telegram_user)
    return telegram_user


def _create_lab_report_instance(
    db_session,
    *,
    patient_id: int,
    template: LabReportTemplate,
    version: LabReportTemplateVersion,
    status_value: str,
    created_at: datetime,
) -> LabReportInstance:
    instance = LabReportInstance(
        patient_id=patient_id,
        template_id=template.id,
        template_version_id=version.id,
        status=status_value,
        patient_snapshot={},
        branding_snapshot={},
        signer_snapshot={},
        created_at=created_at,
        finalized_at=created_at if status_value == "FINALIZED" else None,
        printed_at=created_at if status_value == "PRINTED" else None,
    )
    db_session.add(instance)
    db_session.flush()
    return instance


@pytest.mark.unit
class TestTelegramWebhookSecurity:
    def test_webhook_rejects_missing_secret_configuration(
        self, client, monkeypatch
    ):
        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 10},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Telegram webhook secret is not configured"
        assert fake_service.process_webhook_update.await_count == 0

    def test_webhook_rejects_invalid_secret(self, client, db_session, monkeypatch):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 1},
            headers={"x-telegram-bot-api-secret-token": "wrong-secret"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid Telegram webhook secret"
        assert fake_service.process_webhook_update.await_count == 0

    def test_webhook_accepts_valid_secret(self, client, db_session, monkeypatch):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        update_payload = {"update_id": 2, "message": {"message_id": 11}}

        response = client.post(
            "/api/v1/telegram/webhook",
            json=update_payload,
            headers={"x-telegram-bot-api-secret-token": "topsecret"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        fake_service.process_webhook_update.assert_awaited_once()

    def test_webhook_does_not_log_full_payload(
        self, client, db_session, monkeypatch, caplog
    ):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        caplog.set_level("INFO", logger="app.api.v1.endpoints.telegram_webhook")
        response = client.post(
            "/api/v1/telegram/webhook",
            json={
                "update_id": 3,
                "message": {
                    "message_id": 12,
                    "text": "Sensitive Patient Diagnosis",
                },
            },
            headers={"x-telegram-bot-api-secret-token": "topsecret"},
        )

        assert response.status_code == 200
        assert "Telegram webhook update accepted" in caplog.text
        assert "Sensitive Patient Diagnosis" not in caplog.text

    def test_send_message_requires_admin_auth(self, client):
        response = client.post(
            "/api/v1/telegram/send-message",
            params={"chat_id": 123456, "message": "Привет"},
        )

        assert response.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_contact_spoof_is_rejected(self, db_session):
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 101,
            "message": {
                "message_id": 1,
                "chat": {"id": 7001},
                "from": {"id": 111},
                "contact": {
                    "user_id": 222,
                    "phone_number": "+998901234567",
                },
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        assert (
            fake_service._send_message.await_args.args[1]
            == telegram_webhook.TELEGRAM_CONTACT_REJECTED_MESSAGE
        )
        assert (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7001)
            .first()
            is None
        )

    def test_patient_language_normalization_uses_canonical_uz_latn(self):
        assert telegram_webhook._normalize_patient_language("uz") == "uz-Latn"
        assert telegram_webhook._normalize_patient_language("uz_Latn") == "uz-Latn"
        assert telegram_webhook._normalize_patient_language("uzbek") == "uz-Latn"
        assert telegram_webhook._normalize_patient_language("ru") == "ru"

    def test_legacy_templates_accept_canonical_uz_latn(self):
        templates = TelegramTemplatesService()

        template = templates.get_template(
            "welcome",
            "uz-Latn",
            {"first_name": "Ali"},
        )

        assert "Programma Clinic-ga" in template["text"]
        assert "Ali" in template["text"]
        assert "Dobro" not in template["text"]

    @pytest.mark.asyncio
    async def test_uzbek_language_choice_stores_canonical_uz_latn(self, db_session):
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 102,
            "message": {
                "message_id": 1,
                "chat": {"id": 7006},
                "from": {"id": 111, "language_code": "uz"},
                "text": "🇺🇿 O'zbekcha",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7006)
            .one()
        )
        assert telegram_user.language_code == "uz-Latn"
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False
        assert "O'zbekchaga" in fake_service._send_message.await_args.args[1]
        reply_markup = fake_service._send_message.await_args.args[2]
        assert reply_markup["keyboard"][0][0]["text"].startswith("📱")
        assert reply_markup["keyboard"][1][0]["text"].startswith("🎫")
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7006)
            .one()
        )
        assert log.template_key == "telegram_patient_language_selected"
        assert log.message_type == "patient_bot_reply"
        assert log.status == "sent"

    @pytest.mark.asyncio
    async def test_plain_uzbek_button_switches_next_visible_menu(self, db_session):
        fake_service = FakeTelegramBotService(active=True)
        language_update = {
            "update_id": 120,
            "message": {
                "message_id": 1,
                "chat": {"id": 7020},
                "from": {"id": 111, "language_code": "ru"},
                "text": "O'zbekcha",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            language_update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7020)
            .one()
        )
        assert telegram_user.language_code == "uz-Latn"
        assert fake_service._send_message.await_args.args[1] == (
            telegram_webhook._localized_text("language_selected", "uz-Latn")
        )
        assert fake_service._send_message.await_args.args[2] == (
            telegram_webhook._localized_main_menu("uz-Latn")
        )

        fake_service._send_message.reset_mock()
        help_update = {
            "update_id": 121,
            "message": {
                "message_id": 2,
                "chat": {"id": 7020},
                "from": {"id": 111, "language_code": "ru"},
                "text": "Yordam",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            help_update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7020,
            telegram_webhook._localized_text("help", "uz-Latn"),
            telegram_webhook._localized_main_menu("uz-Latn"),
        )

    @pytest.mark.asyncio
    async def test_language_choice_preserves_existing_notification_consent(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7015,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 109,
            "message": {
                "message_id": 1,
                "chat": {"id": 7015},
                "from": {"id": 111, "language_code": "uz"},
                "text": "🇷🇺 Русский",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.language_code == "ru"
        assert telegram_user.notifications_enabled is True
        assert telegram_user.appointment_reminders is True
        assert telegram_user.lab_notifications is True
        assert "русский" in fake_service._send_message.await_args.args[1]

    @pytest.mark.asyncio
    async def test_notification_consent_accept_enables_patient_notifications(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7007,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=False,
            appointment_reminders=False,
            lab_notifications=False,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 103,
            "message": {
                "message_id": 1,
                "chat": {"id": 7007},
                "from": {"id": 111},
                "text": "🔔 Xabarnomalarga roziman",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.notifications_enabled is True
        assert telegram_user.appointment_reminders is True
        assert telegram_user.lab_notifications is True
        assert fake_service._send_message.await_args.args[1] == "Xabarnomalar yoqildi."

    @pytest.mark.asyncio
    async def test_notification_consent_decline_disables_patient_notifications(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7008,
            username="patient_chat",
            first_name="Patient",
            language_code="ru",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 104,
            "message": {
                "message_id": 1,
                "chat": {"id": 7008},
                "from": {"id": 111},
                "text": "Без уведомлений",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False

    @pytest.mark.asyncio
    async def test_settings_command_returns_localized_settings_menu(self, db_session):
        telegram_user = TelegramUser(
            chat_id=7009,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 105,
            "message": {
                "message_id": 1,
                "chat": {"id": 7009},
                "from": {"id": 111},
                "text": "/settings",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7009,
            telegram_webhook._localized_text("settings", "uz-Latn"),
            telegram_webhook._localized_settings_menu("uz-Latn"),
        )

    @pytest.mark.asyncio
    async def test_staff_start_token_links_user_and_writes_audit(
        self, db_session, admin_user
    ):
        token = admin_telegram.issue_staff_link_start_token(
            db_session,
            user_id=admin_user.id,
            chat_id=7010,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            issued_by_user_id=admin_user.id,
            request_id="staff-link-webhook-test",
            nonce="staffwebhook",
        )
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 106,
            "message": {
                "message_id": 1,
                "chat": {"id": 7010},
                "from": {
                    "id": 7010,
                    "username": "staff_chat",
                    "first_name": "Staff",
                    "language_code": "ru",
                },
                "text": f"/start {token}",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7010)
            .one()
        )
        assert telegram_user.user_id == admin_user.id
        assert telegram_user.patient_id is None
        assert telegram_user.notifications_enabled is False

        token_record = (
            db_session.query(TelegramStaffLinkToken)
            .filter(
                TelegramStaffLinkToken.staff_user_id == admin_user.id,
                TelegramStaffLinkToken.telegram_chat_id == 7010,
            )
            .one()
        )
        assert token_record.consumed_at is not None

        audit_log = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "staff_link_created",
                AuditLog.actor_user_id == admin_user.id,
                AuditLog.entity_id == telegram_user.id,
            )
            .one()
        )
        payload_text = str(audit_log.payload)
        assert audit_log.payload["result"] == "success"
        assert audit_log.payload["actor_role"] == "admin"
        assert "telegram_chat:" in audit_log.payload["telegram_user_id_hash"]
        assert "7010" not in payload_text
        assert token not in payload_text
        fake_service._send_message.assert_awaited_once()
        assert (
            fake_service._send_message.await_args.args[1]
            == f"{telegram_webhook.TELEGRAM_STAFF_LINKED_MESSAGE}\nРоль: admin"
        )
        reply_markup = fake_service._send_message.await_args.args[2]
        assert "keyboard" in reply_markup
        assert reply_markup["resize_keyboard"] is True
        assert reply_markup["keyboard"][-1] == [{"text": "/staff"}, {"text": "/help"}]

    @pytest.mark.asyncio
    async def test_staff_start_token_replay_is_rejected_before_patient_onboarding(
        self, db_session, admin_user
    ):
        token = admin_telegram.issue_staff_link_start_token(
            db_session,
            user_id=admin_user.id,
            chat_id=7011,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            issued_by_user_id=admin_user.id,
            nonce="staffreplay",
        )
        update = {
            "update_id": 107,
            "message": {
                "message_id": 1,
                "chat": {"id": 7011},
                "from": {"id": 7011, "first_name": "Staff"},
                "text": f"/start {token}",
            },
        }

        first_service = FakeTelegramBotService(active=True)
        second_service = FakeTelegramBotService(active=True)
        first = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, first_service
        )
        replay = await telegram_webhook._handle_clinic_bot_update(
            {**update, "update_id": 108}, db_session, second_service
        )

        assert first is True
        assert replay is True
        second_service._send_message.assert_awaited_once_with(
            7011,
            telegram_webhook.TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
            telegram_webhook.TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        assert second_service._send_message.await_args.args[1] != (
            telegram_webhook._localized_text("language_prompt", "ru")
        )
        rejection_audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_link_token_rejected")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert rejection_audit is not None
        assert rejection_audit.payload["reason"] == "already_used"
        assert "7011" not in str(rejection_audit.payload)

    @pytest.mark.asyncio
    async def test_invalid_staff_start_token_does_not_create_telegram_user(
        self, db_session
    ):
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 109,
            "message": {
                "message_id": 1,
                "chat": {"id": 7013},
                "from": {"id": 7013, "first_name": "Staff"},
                "text": "/start stl_invalid",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        assert (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7013)
            .first()
            is None
        )
        fake_service._send_message.assert_awaited_once_with(
            7013,
            telegram_webhook.TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
            telegram_webhook.TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        rejection_audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_link_token_rejected")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert rejection_audit is not None
        assert rejection_audit.payload["reason"] == "signature_invalid"
        assert "7013" not in str(rejection_audit.payload)

    @pytest.mark.asyncio
    async def test_patient_dispatch_routes_staff_start_before_generic_start(
        self, db_session
    ):
        service = telegram_bot.TelegramBotService()
        calls = []
        update = {
            "update_id": 110,
            "message": {
                "message_id": 1,
                "chat": {"id": 7012},
                "from": {"id": 7012},
                "text": "/start stl_test",
            },
        }

        async def staff_start_handler(update_arg, db_arg, bot_arg):
            assert update_arg is update
            assert db_arg is db_session
            assert bot_arg is service
            calls.append("staff")
            return True

        async def ticket_start_handler(_update, _db, _bot):
            calls.append("ticket")
            return False

        async def contact_handler(_message, _db, _bot):
            calls.append("contact")
            return False

        async def start_handler(_chat_id, _message):
            calls.append("start")

        handled = await service.process_patient_bot_update(
            update,
            db_session,
            staff_start_handler=staff_start_handler,
            ticket_start_handler=ticket_start_handler,
            contact_handler=contact_handler,
            start_handler=start_handler,
            command_handlers={},
            text_handlers={},
        )

        assert handled is True
        assert calls == ["staff"]

    def test_queue_message_reports_linked_patient_position_and_cabinet(
        self, db_session, test_patient, test_daily_queue, test_queue_entry
    ):
        _link_patient_to_chat(db_session, chat_id=7002, patient_id=test_patient.id)
        now = datetime.utcnow()
        test_daily_queue.cabinet_number = "205"
        test_queue_entry.number = 2
        test_queue_entry.status = "waiting"
        test_queue_entry.queue_time = now
        earlier_entry = OnlineQueueEntry(
            queue_id=test_daily_queue.id,
            number=1,
            patient_id=None,
            patient_name="Earlier Patient",
            source="desk",
            status="waiting",
            queue_time=now - timedelta(minutes=5),
        )
        db_session.add(earlier_entry)
        db_session.commit()

        message = telegram_webhook._clinic_queue_message(db_session, 7002)

        assert "№2" in message
        assert "позиция: 2" in message
        assert "Кабинет 205" in message
        assert "Кардиология" in message

    def test_payments_message_calculates_debt_from_queue_total_and_payments(
        self, db_session, test_patient, test_visit, test_queue_entry
    ):
        _link_patient_to_chat(db_session, chat_id=7003, patient_id=test_patient.id)
        test_queue_entry.visit_id = test_visit.id
        test_queue_entry.total_amount = 120000
        db_session.add_all(
            [
                Payment(
                    visit_id=test_visit.id,
                    amount=Decimal("50000"),
                    status="paid",
                    method="cash",
                ),
                Payment(
                    visit_id=test_visit.id,
                    amount=Decimal("10000"),
                    status="pending",
                    method="cash",
                ),
            ]
        )
        db_session.commit()

        message = telegram_webhook._clinic_payments_message(db_session, 7003)

        assert "Начислено: 120 000 сум" in message
        assert "Оплачено: 50 000 сум" in message
        assert "Долг: 70 000 сум" in message
        assert "Ожидает подтверждения: 10 000 сум" in message

    def test_ready_lab_reports_are_filtered_by_patient_status_and_limited(
        self, db_session, test_patient
    ):
        other_patient = Patient(first_name="Other", last_name="Patient")
        template = LabReportTemplate(
            code="TG_TEST_REPORT",
            name="Telegram Test Report",
            family="test",
        )
        db_session.add_all([other_patient, template])
        db_session.flush()
        version = LabReportTemplateVersion(
            template_id=template.id,
            version_no=1,
            status="PUBLISHED",
            layout_preset="default",
            page_settings={},
            branding_overrides={},
            signer_defaults={},
        )
        db_session.add(version)
        db_session.flush()
        base_time = datetime.utcnow()
        ready_instances = [
            _create_lab_report_instance(
                db_session,
                patient_id=test_patient.id,
                template=template,
                version=version,
                status_value=status_value,
                created_at=base_time + timedelta(minutes=index),
            )
            for index, status_value in enumerate(
                ["FINALIZED", "PRINTED", "FINALIZED", "PRINTED"], start=1
            )
        ]
        _create_lab_report_instance(
            db_session,
            patient_id=test_patient.id,
            template=template,
            version=version,
            status_value="DRAFT",
            created_at=base_time + timedelta(minutes=99),
        )
        _create_lab_report_instance(
            db_session,
            patient_id=other_patient.id,
            template=template,
            version=version,
            status_value="FINALIZED",
            created_at=base_time + timedelta(minutes=100),
        )
        db_session.commit()

        result = telegram_webhook._latest_ready_lab_report_instances(
            db_session, test_patient.id
        )

        assert len(result) == 3
        assert {item.patient_id for item in result} == {test_patient.id}
        assert {item.status for item in result} <= {"FINALIZED", "PRINTED"}
        assert [item.id for item in result] == [
            ready_instances[3].id,
            ready_instances[2].id,
            ready_instances[1].id,
        ]

    @pytest.mark.asyncio
    async def test_lab_results_flow_sends_pdf_through_bot_service(
        self, db_session, test_patient, monkeypatch
    ):
        _link_patient_to_chat(db_session, chat_id=7004, patient_id=test_patient.id)
        fake_service = FakeTelegramBotService(active=True)
        fake_instance = SimpleNamespace(id=456)
        monkeypatch.setattr(
            telegram_webhook,
            "_latest_ready_lab_report_instances",
            lambda db, patient_id: [fake_instance],
        )
        monkeypatch.setattr(
            telegram_webhook,
            "_build_lab_report_pdf",
            lambda db, instance: (
                "result.pdf",
                b"%PDF-1.4",
                "Ready result",
            ),
        )

        await telegram_webhook._send_clinic_lab_results(db_session, fake_service, 7004)

        fake_service._send_document.assert_awaited_once_with(
            7004,
            "result.pdf",
            b"%PDF-1.4",
            "Ready result",
        )
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.related_entity_id == 456)
            .one()
        )
        assert log.message_type == "lab_result_pdf"
        assert log.related_entity_type == "lab_report_instance"
        assert log.status == "sent"
        assert log.message_id == 77

    @pytest.mark.asyncio
    async def test_telegram_bot_service_send_document_posts_pdf_bytes(self, monkeypatch):
        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"ok": True, "result": {"message_id": 88}}

        def fake_post(url, data, files, timeout):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            captured["timeout"] = timeout
            return FakeResponse()

        monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
        service = telegram_bot.TelegramBotService()
        service.bot_token = "bot-token"

        ok, message_id, error = await service._send_document(
            7005,
            "service-result.pdf",
            b"%PDF-1.4 service",
            "Service result",
        )

        assert ok is True
        assert message_id == 88
        assert error is None
        assert captured["url"].endswith("/sendDocument")
        assert captured["data"] == {
            "chat_id": 7005,
            "caption": "Service result",
            "parse_mode": "HTML",
        }
        assert captured["files"]["document"] == (
            "service-result.pdf",
            b"%PDF-1.4 service",
            "application/pdf",
        )
        assert captured["timeout"] == 20

    @pytest.mark.asyncio
    async def test_telegram_bot_service_registers_patient_commands(self, monkeypatch):
        captured = []

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"ok": True, "result": True}

        def fake_post(url, json, timeout):
            captured.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse()

        monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
        service = telegram_bot.TelegramBotService()
        service.bot_token = "bot-token"

        ok, error = await service.set_patient_bot_commands()

        assert ok is True
        assert error is None
        assert [item["json"].get("language_code") for item in captured] == [None, "uz"]
        assert captured[0]["url"].endswith("/setMyCommands")
        assert captured[0]["json"]["commands"] == telegram_bot.PATIENT_BOT_COMMANDS_RU
        assert captured[1]["json"]["commands"] == telegram_bot.PATIENT_BOT_COMMANDS_UZ
        assert {command["command"] for command in captured[0]["json"]["commands"]} == {
            "start",
            "queue",
            "payments",
            "results",
            "profile",
            "settings",
            "help",
        }
