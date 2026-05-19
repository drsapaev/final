from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.models.audit import AuditLog
from app.models.lab import LabReportInstance
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment_invoice import PaymentInvoice
from app.models.payment_webhook import PaymentWebhook
from app.models.telegram_config import TelegramStaffConfirmationToken, TelegramUser
from app.models.visit import Visit
from app.models.webhook import (
    Webhook,
    WebhookCall,
    WebhookCallStatus,
    WebhookEvent,
    WebhookEventType,
    WebhookStatus,
)
from app.services.lab_reporting_service import LabReportingService


class FakeTelegramBotService:
    def __init__(self):
        self._send_message = AsyncMock(return_value=True)


def _link_staff_chat(db_session, *, chat_id: int, user_id: int) -> TelegramUser:
    telegram_user = TelegramUser(
        chat_id=chat_id,
        user_id=user_id,
        username="staff_chat",
        first_name="Staff",
        language_code="ru",
        notifications_enabled=False,
        appointment_reminders=False,
        lab_notifications=False,
        active=True,
        blocked=False,
    )
    db_session.add(telegram_user)
    db_session.commit()
    db_session.refresh(telegram_user)
    return telegram_user


@pytest.mark.unit
class TestTelegramStaffReadOnlyMenuRuntime:
    @pytest.mark.asyncio
    async def test_staff_command_returns_read_only_role_menu(
        self, db_session, admin_user
    ):
        _link_staff_chat(db_session, chat_id=7201, user_id=admin_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 201,
            "message": {
                "message_id": 1,
                "chat": {"id": 7201},
                "from": {"id": 7201},
                "text": "/staff",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        chat_id, text, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7201
        assert "Staff read-only menu" in text
        assert "Role: admin" in text
        assert "State-changing actions are disabled" in text
        assert reply_markup["resize_keyboard"] is True
        assert ["/staff", "/help"] == [
            item["text"] for item in reply_markup["keyboard"][-1]
        ]
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.actor_user_id == admin_user.id
        assert audit_log.entity_id is not None
        assert audit_log.payload["actor_role"] == "admin"
        assert audit_log.payload["command_key"] == "/staff"
        assert audit_log.payload["menu_item_key"] == "staff_menu"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False
        assert "telegram_chat:" in audit_log.payload["telegram_user_id_hash"]
        assert "7201" not in str(audit_log.payload)

    @pytest.mark.asyncio
    async def test_staff_read_only_command_does_not_execute_patient_queue(
        self, db_session, registrar_user
    ):
        _link_staff_chat(db_session, chat_id=7202, user_id=registrar_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 202,
            "message": {
                "message_id": 1,
                "chat": {"id": 7202},
                "from": {"id": 7202},
                "text": "/queue",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Queue overview" in text
        assert "Mode: read-only aggregate snapshot" in text
        assert "7202" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.actor_user_id == registrar_user.id
        assert audit_log.payload["command_key"] == "/queue"
        assert audit_log.payload["menu_item_key"] == "queue_overview"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_readiness_menu_item_returns_safe_live_status(
        self, db_session, admin_user
    ):
        _link_staff_chat(db_session, chat_id=7205, user_id=admin_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 205,
            "message": {
                "message_id": 1,
                "chat": {"id": 7205},
                "from": {"id": 7205},
                "text": "staff_readiness",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Staff bot readiness" in text
        assert "Live data: limited read-only aggregates" in text
        assert "State-changing actions: disabled" in text
        assert "7205" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["menu_item_key"] == "staff_readiness"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_next_patient_menu_item_returns_read_only_queue_snapshot(
        self, db_session, registrar_user, test_doctor, test_patient
    ):
        _link_staff_chat(db_session, chat_id=7206, user_id=registrar_user.id)
        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        next_queue_time = datetime.utcnow().replace(microsecond=0) - timedelta(
            minutes=20
        )
        later_queue_time = next_queue_time + timedelta(minutes=10)
        next_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=8,
            patient_id=test_patient.id,
            patient_name="Queue Alpha",
            phone="+998901234567",
            source="desk",
            status="waiting",
            queue_time=next_queue_time,
        )
        later_entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=9,
            patient_id=test_patient.id,
            patient_name="Queue Beta",
            phone="+998901234568",
            source="desk",
            status="waiting",
            queue_time=later_queue_time,
        )
        db_session.add_all([later_entry, next_entry])
        db_session.commit()
        db_session.refresh(next_entry)
        original_queue_time = next_entry.queue_time

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 206,
            "message": {
                "message_id": 1,
                "chat": {"id": 7206},
                "from": {"id": 7206},
                "text": "next_patient",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Next patient" in text
        assert "Queue number: 8" in text
        assert "Mode: read-only queue snapshot" in text
        assert "Queue Alpha" not in text
        assert "+998901234567" not in text
        assert "7206" not in text
        db_session.refresh(next_entry)
        assert next_entry.status == "waiting"
        assert next_entry.queue_time == original_queue_time
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["menu_item_key"] == "next_patient"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_today_schedule_command_returns_read_only_visit_snapshot(
        self, db_session, test_doctor_user, test_doctor, test_patient
    ):
        _link_staff_chat(db_session, chat_id=7207, user_id=test_doctor_user.id)
        test_doctor.user_id = test_doctor_user.id
        db_session.flush()
        db_session.add_all(
            [
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today(),
                    visit_time="09:00",
                    status="open",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today(),
                    visit_time="10:00",
                    status="in_progress",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today(),
                    visit_time="11:00",
                    status="completed",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today() - timedelta(days=1),
                    visit_time="12:00",
                    status="open",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=None,
                    visit_date=date.today(),
                    visit_time="13:00",
                    status="open",
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 207,
            "message": {
                "message_id": 1,
                "chat": {"id": 7207},
                "from": {"id": 7207},
                "text": "/schedule",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Today's schedule" in text
        assert "Visits today: 3" in text
        assert "Open visits: 1" in text
        assert "In progress: 1" in text
        assert "Completed/cancelled: 1" in text
        assert "Mode: read-only schedule snapshot" in text
        assert test_patient.first_name not in text
        if test_patient.phone:
            assert test_patient.phone not in text
        assert "7207" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "/schedule"
        assert audit_log.payload["menu_item_key"] == "today_schedule"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_emr_reminders_menu_item_returns_safe_aggregate(
        self, db_session, test_doctor_user, test_doctor, test_patient
    ):
        _link_staff_chat(db_session, chat_id=7208, user_id=test_doctor_user.id)
        test_doctor.user_id = test_doctor_user.id
        db_session.flush()
        db_session.add_all(
            [
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today(),
                    visit_time="09:00",
                    status="open",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today(),
                    visit_time="10:00",
                    status="in_progress",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=test_doctor.id,
                    visit_date=date.today(),
                    visit_time="11:00",
                    status="closed",
                ),
                Visit(
                    patient_id=test_patient.id,
                    doctor_id=None,
                    visit_date=date.today(),
                    visit_time="12:00",
                    status="open",
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 208,
            "message": {
                "message_id": 1,
                "chat": {"id": 7208},
                "from": {"id": 7208},
                "text": "emr_reminders",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "EMR reminders" in text
        assert "Visits needing EMR closure: 2" in text
        assert "Open visits: 1" in text
        assert "In progress: 1" in text
        assert "Closed/cancelled: 1" in text
        assert "Mode: read-only EMR reminder snapshot" in text
        assert test_patient.first_name not in text
        if test_patient.phone:
            assert test_patient.phone not in text
        assert "7208" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "emr_reminders"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_unpaid_invoices_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, test_patient
    ):
        admin_user.role = "cashier"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7209, user_id=admin_user.id)
        db_session.add_all(
            [
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=7000,
                    currency="UZS",
                    status="pending",
                    payment_method="click",
                    provider="click",
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=5000,
                    currency="UZS",
                    status="processing",
                    payment_method="payme",
                    provider="payme",
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=3000,
                    currency="UZS",
                    status="paid",
                    payment_method="cash",
                    provider=None,
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 209,
            "message": {
                "message_id": 1,
                "chat": {"id": 7209},
                "from": {"id": 7209},
                "text": "unpaid_invoices",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Unpaid invoices" in text
        assert "Invoices today: 3" in text
        assert "Unpaid invoices: 2" in text
        assert "Unpaid total: 12 000" in text
        assert "Mode: read-only invoice aggregate snapshot" in text
        assert test_patient.first_name not in text
        if test_patient.phone:
            assert test_patient.phone not in text
        assert "7209" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "unpaid_invoices"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_paid_invoices_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, test_patient
    ):
        admin_user.role = "cashier"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7210, user_id=admin_user.id)
        db_session.add_all(
            [
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=9000,
                    currency="UZS",
                    status="paid",
                    payment_method="cash",
                    provider=None,
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=4000,
                    currency="UZS",
                    status="refunded",
                    payment_method="click",
                    provider="click",
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=3000,
                    currency="UZS",
                    status="pending",
                    payment_method="payme",
                    provider="payme",
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 210,
            "message": {
                "message_id": 1,
                "chat": {"id": 7210},
                "from": {"id": 7210},
                "text": "paid_invoices",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Paid invoices" in text
        assert "Invoices today: 3" in text
        assert "Paid invoices: 1" in text
        assert "Paid total: 9 000" in text
        assert "Mode: read-only invoice aggregate snapshot" in text
        assert test_patient.first_name not in text
        if test_patient.phone:
            assert test_patient.phone not in text
        assert "7210" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "paid_invoices"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_revenue_summary_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, test_patient
    ):
        admin_user.role = "owner"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7215, user_id=admin_user.id)
        db_session.add_all(
            [
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=9000,
                    currency="UZS",
                    status="paid",
                    payment_method="cash",
                    provider="cashier",
                    provider_payment_id="paid-provider-secret",
                    provider_transaction_id="paid-transaction-secret",
                    payment_url="https://pay.example/paid-secret",
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=5000,
                    currency="UZS",
                    status="pending",
                    payment_method="click",
                    provider="click",
                    provider_payment_id="pending-provider-secret",
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=2000,
                    currency="UZS",
                    status="processing",
                    payment_method="payme",
                    provider="payme",
                    provider_transaction_id="processing-transaction-secret",
                ),
                PaymentInvoice(
                    patient_id=test_patient.id,
                    total_amount=4000,
                    currency="UZS",
                    status="refunded",
                    payment_method="card",
                    provider="card",
                    provider_data={"secret": "refund-provider-secret"},
                    notes="patient-visible secret note",
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 215,
            "message": {
                "message_id": 1,
                "chat": {"id": 7215},
                "from": {"id": 7215},
                "text": "revenue_summary",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Revenue summary" in text
        assert "Invoices today: 4" in text
        assert "Gross invoiced: 20 000" in text
        assert "Collected revenue: 9 000" in text
        assert "Pending revenue: 7 000" in text
        assert "Other invoice total: 4 000" in text
        assert "Mode: read-only revenue aggregate snapshot" in text
        assert test_patient.first_name not in text
        if test_patient.phone:
            assert test_patient.phone not in text
        assert "paid-provider-secret" not in text
        assert "paid-transaction-secret" not in text
        assert "pending-provider-secret" not in text
        assert "processing-transaction-secret" not in text
        assert "refund-provider-secret" not in text
        assert "patient-visible secret note" not in text
        assert "7215" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "revenue_summary"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_reconciliation_alerts_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, monkeypatch
    ):
        admin_user.role = "cashier"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7211, user_id=admin_user.id)

        class FakeReconciliationApiService:
            def __init__(self, db):
                self.db = db

            def get_reconciliation_alerts(self, *, threshold):
                assert threshold == 1000.0
                return {
                    "alerts": [
                        {
                            "severity": "high",
                            "provider": "click",
                            "message": "transaction 123 mismatch",
                        },
                        {
                            "severity": "medium",
                            "provider": "payme",
                            "message": "payment 456 missing",
                        },
                        {
                            "severity": "error",
                            "provider": "kaspi",
                            "message": "provider secret failed",
                        },
                    ],
                    "alert_count": 3,
                    "high_severity_count": 1,
                }

        monkeypatch.setattr(
            telegram_webhook,
            "PaymentReconciliationApiService",
            FakeReconciliationApiService,
        )

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 211,
            "message": {
                "message_id": 1,
                "chat": {"id": 7211},
                "from": {"id": 7211},
                "text": "reconciliation_alerts",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Reconciliation alerts" in text
        assert "Alerts: 3" in text
        assert "High severity: 1" in text
        assert "Medium severity: 1" in text
        assert "Error severity: 1" in text
        assert "Providers: click, kaspi, payme" in text
        assert "Mode: read-only reconciliation aggregate snapshot" in text
        assert "transaction 123" not in text
        assert "payment 456" not in text
        assert "secret" not in text
        assert "7211" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "reconciliation_alerts"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_pending_reports_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, test_patient
    ):
        admin_user.role = "lab"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7212, user_id=admin_user.id)
        template = LabReportingService(db_session).list_templates()[0]
        version = template.versions[-1]
        db_session.add_all(
            [
                LabReportInstance(
                    patient_id=test_patient.id,
                    template_id=template.id,
                    template_version_id=version.id,
                    status="DRAFT",
                    patient_snapshot={"name": test_patient.first_name},
                    branding_snapshot={},
                    signer_snapshot={},
                ),
                LabReportInstance(
                    patient_id=test_patient.id,
                    template_id=template.id,
                    template_version_id=version.id,
                    status="IN_PROGRESS",
                    patient_snapshot={"name": test_patient.first_name},
                    branding_snapshot={},
                    signer_snapshot={},
                ),
                LabReportInstance(
                    patient_id=test_patient.id,
                    template_id=template.id,
                    template_version_id=version.id,
                    status="READY",
                    patient_snapshot={"name": test_patient.first_name},
                    branding_snapshot={},
                    signer_snapshot={},
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 212,
            "message": {
                "message_id": 1,
                "chat": {"id": 7212},
                "from": {"id": 7212},
                "text": "pending_reports",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Pending lab reports" in text
        assert "Reports today: 3" in text
        assert "Pending reports: 2" in text
        assert "Draft reports: 1" in text
        assert "In progress: 1" in text
        assert "Ready/final: 1" in text
        assert "Mode: read-only lab aggregate snapshot" in text
        assert test_patient.first_name not in text
        assert "7212" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "pending_reports"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_delivery_status_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, test_patient
    ):
        admin_user.role = "lab"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7213, user_id=admin_user.id)
        event = NotificationEvent(
            event_type="lab_results",
            dedup_key="lab-results-delivery-status-test",
            source_module="lab",
            entity_type="lab_result",
            entity_id="result-77",
            severity="info",
            priority="high",
            title="Lab results ready",
            message=f"Results for {test_patient.first_name}",
            payload_snapshot={"patient_id": test_patient.id},
            deep_link="/lab/results",
        )
        db_session.add(event)
        db_session.flush()
        db_session.add_all(
            [
                NotificationDelivery(
                    event_id=event.id,
                    recipient_type="user",
                    recipient_id=admin_user.id,
                    role="lab",
                    channel="telegram",
                    dedup_key="delivery-status-delivered",
                    sequence_id=1,
                    delivery_status="delivered",
                    payload_snapshot={"patient_id": test_patient.id},
                ),
                NotificationDelivery(
                    event_id=event.id,
                    recipient_type="user",
                    recipient_id=admin_user.id,
                    role="lab",
                    channel="telegram",
                    dedup_key="delivery-status-pending",
                    sequence_id=2,
                    delivery_status="pending",
                    payload_snapshot={"patient_id": test_patient.id},
                ),
                NotificationDelivery(
                    event_id=event.id,
                    recipient_type="user",
                    recipient_id=admin_user.id,
                    role="lab",
                    channel="telegram",
                    dedup_key="delivery-status-failed",
                    sequence_id=3,
                    delivery_status="failed",
                    last_error="patient phone missing",
                    payload_snapshot={"patient_id": test_patient.id},
                ),
                NotificationDelivery(
                    event_id=event.id,
                    recipient_type="user",
                    recipient_id=admin_user.id,
                    role="lab",
                    channel="sms",
                    dedup_key="delivery-status-sms",
                    sequence_id=4,
                    delivery_status="delivered",
                    last_error="sms secret detail",
                    payload_snapshot={"patient_id": test_patient.id},
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 213,
            "message": {
                "message_id": 1,
                "chat": {"id": 7213},
                "from": {"id": 7213},
                "text": "delivery_status",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Lab result delivery status" in text
        assert "Telegram deliveries today: 3" in text
        assert "Delivered/seen/read: 1" in text
        assert "Pending/dispatched: 1" in text
        assert "Failed: 1" in text
        assert "Mode: read-only delivery aggregate snapshot" in text
        assert test_patient.first_name not in text
        assert "result-77" not in text
        assert "patient phone missing" not in text
        assert "sms secret detail" not in text
        assert "7213" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "delivery_status"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_integration_errors_menu_item_returns_safe_aggregate(
        self, db_session, admin_user, test_patient
    ):
        admin_user.role = "admin"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7214, user_id=admin_user.id)
        webhook = Webhook(
            name="Provider sync",
            url="https://integrations.example/secret-hook",
            events=[WebhookEventType.PAYMENT_COMPLETED.value],
            headers={"Authorization": "secret-token"},
            status=WebhookStatus.ACTIVE,
            is_active=True,
            created_by=admin_user.id,
        )
        db_session.add(webhook)
        db_session.flush()
        now = datetime.utcnow()
        db_session.add_all(
            [
                WebhookCall(
                    webhook_id=webhook.id,
                    event_type=WebhookEventType.PAYMENT_COMPLETED,
                    event_data={"patient": test_patient.first_name},
                    url="https://integrations.example/secret-call",
                    method="POST",
                    headers={"Authorization": "secret-token"},
                    payload={"patient_id": test_patient.id},
                    status=WebhookCallStatus.FAILED,
                    response_status_code=500,
                    response_body="private provider response",
                    error_message="provider rejected patient payload",
                    attempt_number=1,
                    max_attempts=3,
                    created_at=now,
                ),
                WebhookCall(
                    webhook_id=webhook.id,
                    event_type=WebhookEventType.PAYMENT_FAILED,
                    event_data={"transaction": "secret-transaction"},
                    url="https://integrations.example/retry-call",
                    method="POST",
                    headers={},
                    payload={"secret": "retry-payload"},
                    status=WebhookCallStatus.RETRYING,
                    response_status_code=503,
                    error_message="retry later secret",
                    attempt_number=2,
                    max_attempts=3,
                    created_at=now,
                ),
                WebhookEvent(
                    event_type=WebhookEventType.PAYMENT_COMPLETED,
                    event_data={"patient_id": test_patient.id},
                    source="provider-secret",
                    source_id="source-77",
                    processed=False,
                    failed_webhooks=[webhook.id],
                    created_at=now,
                ),
                PaymentWebhook(
                    provider="payme",
                    webhook_id="payment-webhook-secret",
                    transaction_id="transaction-secret",
                    status="failed",
                    amount=120000,
                    raw_data={"patient": test_patient.first_name},
                    signature="signature-secret",
                    visit_id=1001,
                    patient_id=test_patient.id,
                    created_at=now,
                    error_message="signature mismatch secret",
                ),
            ]
        )
        db_session.commit()

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 214,
            "message": {
                "message_id": 1,
                "chat": {"id": 7214},
                "from": {"id": 7214},
                "text": "integration_errors",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Integration errors" in text
        assert "Total attention items: 4" in text
        assert "Failed webhook calls today: 1" in text
        assert "Retrying webhook calls: 1" in text
        assert "Unprocessed webhook events: 1" in text
        assert "Failed payment webhooks today: 1" in text
        assert "Mode: read-only integration aggregate snapshot" in text
        assert test_patient.first_name not in text
        assert "secret-token" not in text
        assert "secret-hook" not in text
        assert "private provider response" not in text
        assert "provider rejected patient payload" not in text
        assert "transaction-secret" not in text
        assert "signature mismatch secret" not in text
        assert "7214" not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.payload["command_key"] == "staff_menu_item"
        assert audit_log.payload["menu_item_key"] == "integration_errors"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_staff_state_change_command_requests_confirmation_without_mutation(
        self, db_session, admin_user
    ):
        _link_staff_chat(db_session, chat_id=7204, user_id=admin_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 204,
            "message": {
                "message_id": 1,
                "chat": {"id": 7204},
                "from": {"id": 7204},
                "text": "/refund",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Staff action confirmation requested" in text
        assert "Action:" in text
        assert "Domain: payment" in text
        assert "Telegram execution: disabled" in text
        assert "Domain mutation: not performed" in text
        assert "7204" not in text
        confirmation_record = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(
                TelegramStaffConfirmationToken.staff_user_id == admin_user.id,
                TelegramStaffConfirmationToken.telegram_chat_id == 7204,
            )
            .one()
        )
        assert confirmation_record.token_hash.startswith("staff_confirmation_token:")
        assert confirmation_record.operation_key == "refund_issue"
        assert confirmation_record.command_key == "/refund"
        assert confirmation_record.target_type == "telegram_staff_action"
        assert confirmation_record.target_reference_hash.startswith("staff_action:")
        assert confirmation_record.idempotency_key_hash.startswith(
            "staff_action_idempotency:"
        )
        assert confirmation_record.consumed_at is None
        assert confirmation_record.token_hash not in text
        assert confirmation_record.target_reference_hash not in text
        assert confirmation_record.idempotency_key_hash not in text
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_action_confirmation_requested")
            .one()
        )
        assert audit_log.actor_user_id == admin_user.id
        assert audit_log.payload["actor_role"] == "admin"
        assert audit_log.payload["operation_key"] == "refund_issue"
        assert audit_log.payload["command_key"] == "/refund"
        assert audit_log.payload["result"] == "confirmation_requested"
        assert audit_log.payload["confirmation_required"] is True
        assert audit_log.payload["confirmation_token_hash_stored"] is True
        assert audit_log.payload["confirmation_token_returned_to_telegram"] is False
        assert audit_log.payload["idempotency_key_present"] is True
        assert audit_log.payload["idempotency_key_hash_stored"] is True
        assert audit_log.payload["idempotency_key_returned_to_telegram"] is False
        assert audit_log.payload["telegram_execution_enabled"] is False
        assert audit_log.payload["domain_mutation"] is False
        assert audit_log.payload["state_changing_action"] is True
        assert "staff_action:" in audit_log.payload["target_reference_hash"]
        assert confirmation_record.idempotency_key_hash not in str(audit_log.payload)
        assert "7204" not in str(audit_log.payload)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", ["/call", "/skip"])
    async def test_staff_queue_state_change_command_requests_confirmation_without_queue_mutation(
        self, db_session, registrar_user, test_doctor, test_patient, command
    ):
        _link_staff_chat(db_session, chat_id=7220, user_id=registrar_user.id)
        queue = DailyQueue(
            day=date.today(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()

        original_queue_time = datetime.utcnow().replace(microsecond=0)
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=14,
            patient_id=test_patient.id,
            patient_name="Queue Mutation Guard",
            phone="+998901234570",
            source="desk",
            status="waiting",
            queue_time=original_queue_time,
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 220,
            "message": {
                "message_id": 1,
                "chat": {"id": 7220},
                "from": {"id": 7220},
                "text": command,
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        text = fake_service._send_message.await_args.args[1]
        assert "Staff action confirmation requested" in text
        assert "Domain: queue" in text
        assert "Telegram execution: disabled" in text
        assert "Domain mutation: not performed" in text
        assert "Queue Mutation Guard" not in text
        assert "7220" not in text

        db_session.refresh(entry)
        assert entry.status == "waiting"
        assert entry.queue_time == original_queue_time
        assert entry.called_at is None

        confirmation_record = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(
                TelegramStaffConfirmationToken.staff_user_id == registrar_user.id,
                TelegramStaffConfirmationToken.telegram_chat_id == 7220,
            )
            .one()
        )
        assert confirmation_record.operation_key == "queue_call_or_skip_patient"
        assert confirmation_record.command_key == command
        assert confirmation_record.consumed_at is None
        assert confirmation_record.token_hash not in text
        assert confirmation_record.idempotency_key_hash not in text

        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_action_confirmation_requested")
            .one()
        )
        assert audit_log.actor_user_id == registrar_user.id
        assert audit_log.payload["actor_role"] == "registrar"
        assert audit_log.payload["operation_key"] == "queue_call_or_skip_patient"
        assert audit_log.payload["command_key"] == command
        assert audit_log.payload["telegram_execution_enabled"] is False
        assert audit_log.payload["domain_mutation"] is False
        assert audit_log.payload["state_changing_action"] is True
        assert confirmation_record.idempotency_key_hash not in str(audit_log.payload)
        assert "7220" not in str(audit_log.payload)

    @pytest.mark.asyncio
    async def test_staff_state_change_command_denies_unauthorized_role(
        self, db_session, admin_user
    ):
        admin_user.role = "lab"
        db_session.flush()
        _link_staff_chat(db_session, chat_id=7216, user_id=admin_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 216,
            "message": {
                "message_id": 1,
                "chat": {"id": 7216},
                "from": {"id": 7216},
                "text": "/refund",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        assert (
            fake_service._send_message.await_args.args[1]
            == telegram_webhook.TELEGRAM_STAFF_MENU_FORBIDDEN_MESSAGE
        )
        assert db_session.query(TelegramStaffConfirmationToken).count() == 0
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_action_denied")
            .one()
        )
        assert audit_log.actor_user_id == admin_user.id
        assert audit_log.payload["actor_role"] == "lab"
        assert audit_log.payload["operation_key"] == "refund_issue"
        assert audit_log.payload["command_key"] == "/refund"
        assert audit_log.payload["reason"] == "role_not_allowed"
        assert audit_log.payload["confirmation_required"] is True
        assert audit_log.payload["telegram_execution_enabled"] is False
        assert audit_log.payload["domain_mutation"] is False
        assert audit_log.payload["state_changing_action"] is True
        assert "7216" not in str(audit_log.payload)

    @pytest.mark.asyncio
    async def test_unlinked_staff_menu_request_does_not_create_patient_link(
        self, db_session
    ):
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 203,
            "message": {
                "message_id": 1,
                "chat": {"id": 7203},
                "from": {"id": 7203},
                "text": "/staff",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7203,
            telegram_webhook.TELEGRAM_STAFF_MENU_UNLINKED_MESSAGE,
            telegram_webhook.TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        assert (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7203)
            .first()
            is None
        )
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.actor_user_id is None
        assert audit_log.entity_id is None
        assert audit_log.payload["actor_role"] == "unlinked"
        assert audit_log.payload["command_key"] == "/staff"
        assert audit_log.payload["result"] == "denied"
        assert audit_log.payload["reason"] == "staff_not_linked"
        assert "telegram_chat:" in audit_log.payload["telegram_user_id_hash"]
        assert "7203" not in str(audit_log.payload)
