"""Subject-bound reminder tests using a synthetic SQLite 0102 migration."""

from __future__ import annotations

import asyncio
import importlib.util
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.services.notification_subject_intent_service import (
    create_patient_notification_intent,
    dispatch_patient_notification_intent,
)
from app.services.profile_contact_security import ProfileBearerContext


@pytest.fixture
def subject_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'notification_subject.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def fk_on(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0102_visit_confirmation_context.py"
    )
    spec = importlib.util.spec_from_file_location("synthetic_notification_0102", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        connection.execute(
            sa.text("ALTER TABLE visits DROP COLUMN confirmation_context_epoch")
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
    yield engine
    engine.dispose()


def _seed(engine, *, linked_user=True, contacts=True):
    with Session(engine, expire_on_commit=False) as db:
        actor = User(
            username="synthetic-admin",
            hashed_password="synthetic",
            role="Admin",
            is_active=True,
            auth_epoch=2,
        )
        user = User(
            username="synthetic-patient",
            hashed_password="synthetic",
            role="Patient",
            is_active=True,
        )
        db.add_all([actor, user])
        db.flush()
        patient = Patient(
            first_name="Synthetic",
            last_name="Patient",
            user_id=user.id if linked_user else None,
            email="synthetic@example.test" if contacts else None,
            phone="+15550000123" if contacts else None,
        )
        other = Patient(first_name="Synthetic", last_name="Other")
        db.add_all([patient, other])
        db.flush()
        visit = Visit(
            patient_id=patient.id,
            visit_date=date(2026, 4, 1),
            status="pending_confirmation",
            confirmation_token="synthetic-token",
            reminder_generation=0,
        )
        db.add(visit)
        db.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal("123.45"),
            currency="UZS",
            method="cash",
            status="paid",
        )
        db.add(payment)
        db.commit()
        bearer = ProfileBearerContext(
            user_id=actor.id,
            auth_epoch=actor.auth_epoch,
            jti="synthetic-jti",
            expires_at=int(time.time()) + 3600,
            patient_id=None,
        )
        return bearer, patient.id, other.id, visit.id, payment.id


def _sender(monkeypatch, engine):
    import app.db.session as db_session_module
    import app.services.notification_subject_intent_service as service

    sender = SimpleNamespace(
        _patient_channel_opted_in=Mock(return_value=True),
        send_push=AsyncMock(return_value=True),
        send_email=AsyncMock(return_value=True),
        send_sms=AsyncMock(return_value=True),
        send_patient_telegram_event_notification=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(service, "notification_sender_service", sender)
    monkeypatch.setattr(
        db_session_module,
        "SessionLocal",
        lambda: Session(engine, expire_on_commit=False),
    )
    return sender


def _intent(engine, bearer, visit_id, *, purpose="visit_confirmation", payment_id=None):
    with Session(engine) as db:
        return create_patient_notification_intent(
            db, bearer=bearer, purpose=purpose, visit_id=visit_id, payment_id=payment_id
        )


@pytest.mark.asyncio
async def test_valid_intent_uses_only_neutral_transport(subject_engine, monkeypatch):
    bearer, patient_id, _, visit_id, payment_id = _seed(subject_engine)
    sender = _sender(monkeypatch, subject_engine)
    intent = _intent(
        subject_engine,
        bearer,
        visit_id,
        purpose="payment_notification",
        payment_id=payment_id,
    )
    assert intent.patient_id == patient_id
    assert set(intent.eligible_channels) == {"inbox", "email", "sms"}
    assert "123.45" not in repr(intent) and "synthetic@example.test" not in repr(intent)
    await dispatch_patient_notification_intent(intent)
    sender.send_push.assert_awaited_once()
    sender.send_email.assert_awaited_once()
    sender.send_sms.assert_awaited_once()
    for call in (
        sender.send_push.await_args,
        sender.send_email.await_args,
        sender.send_sms.await_args,
    ):
        assert "123.45" not in str(call)
        assert "2026-04-01" not in str(call)
        assert "doctor" not in str(call).lower()
    assert sender.send_push.await_args.kwargs["data"] == {"type": "notification"}
    assert sender.send_push.await_args.kwargs["subject_preference_event_type"] == "payment_notification"


@pytest.mark.asyncio
async def test_transfer_aba_invalidates_pending_intent(subject_engine, monkeypatch):
    bearer, patient_id, other_id, visit_id, _ = _seed(subject_engine)
    sender = _sender(monkeypatch, subject_engine)
    intent = _intent(subject_engine, bearer, visit_id)
    with Session(subject_engine) as db:
        visit = db.get(Visit, visit_id)
        visit.patient_id = other_id
        db.commit()
        visit.patient_id = patient_id
        db.commit()
        db.refresh(visit)
        assert visit.confirmation_context_epoch != intent.visit_epoch
    await dispatch_patient_notification_intent(intent)
    sender.send_push.assert_not_awaited()
    sender.send_email.assert_not_awaited()
    sender.send_sms.assert_not_awaited()
    sender.send_patient_telegram_event_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoked_actor_and_unpaid_payment_do_not_dispatch(
    subject_engine, monkeypatch
):
    bearer, _, _, visit_id, payment_id = _seed(subject_engine)
    sender = _sender(monkeypatch, subject_engine)
    intent = _intent(
        subject_engine,
        bearer,
        visit_id,
        purpose="payment_notification",
        payment_id=payment_id,
    )
    with Session(subject_engine) as db:
        db.get(User, bearer.user_id).auth_epoch += 1
        db.commit()
    await dispatch_patient_notification_intent(intent)
    sender.send_push.assert_not_awaited()
    sender.send_email.assert_not_awaited()
    sender.send_sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_portal_uses_contact_clinic_notice(subject_engine, monkeypatch):
    bearer, _, _, visit_id, _ = _seed(subject_engine, linked_user=False)
    sender = _sender(monkeypatch, subject_engine)
    intent = _intent(subject_engine, bearer, visit_id)
    await dispatch_patient_notification_intent(intent)
    sender.send_push.assert_not_awaited()
    assert "свяжитесь с клиникой" in sender.send_sms.await_args.args[1].lower()
    assert "кабинет" not in sender.send_sms.await_args.args[1].lower()


def test_no_channel_and_unrelated_payment_fail_closed(subject_engine, monkeypatch):
    bearer, _, _, visit_id, payment_id = _seed(
        subject_engine, linked_user=False, contacts=False
    )
    _sender(monkeypatch, subject_engine)
    with Session(subject_engine) as db, pytest.raises(HTTPException) as no_channel:
        create_patient_notification_intent(
            db, bearer=bearer, purpose="visit_confirmation", visit_id=visit_id
        )
    assert no_channel.value.status_code == 409
    with Session(subject_engine) as db, pytest.raises(HTTPException) as no_payment:
        create_patient_notification_intent(
            db,
            bearer=bearer,
            purpose="payment_notification",
            visit_id=visit_id,
            payment_id=payment_id + 9999,
        )
    assert no_payment.value.status_code == 409


@pytest.mark.parametrize("field", ["jti", "expires_at"])
def test_unrevocable_session_cannot_queue_notification(subject_engine, monkeypatch, field):
    from dataclasses import replace

    bearer, _, _, visit_id, _ = _seed(subject_engine)
    sender = _sender(monkeypatch, subject_engine)
    bearer = replace(bearer, **{field: None})
    with Session(subject_engine) as db, pytest.raises(HTTPException) as denied:
        create_patient_notification_intent(db, bearer=bearer, purpose="visit_confirmation", visit_id=visit_id)
    assert denied.value.status_code == 403
    sender.send_push.assert_not_awaited()
    sender.send_email.assert_not_awaited()
    sender.send_sms.assert_not_awaited()


def test_unverified_telegram_only_does_not_claim_delivery(subject_engine, monkeypatch):
    from app.models.telegram_config import TelegramUser

    bearer, patient_id, _, visit_id, _ = _seed(subject_engine, linked_user=False, contacts=False)
    sender = _sender(monkeypatch, subject_engine)
    with Session(subject_engine) as db:
        db.add(TelegramUser(patient_id=patient_id, chat_id=987654321, active=True,
                            blocked=False, notifications_enabled=True))
        db.commit()
    with Session(subject_engine) as db, pytest.raises(HTTPException) as denied:
        create_patient_notification_intent(db, bearer=bearer, purpose="visit_confirmation", visit_id=visit_id)
    assert denied.value.status_code == 409
    sender.send_patient_telegram_event_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_first_channel_stops_later_sends(subject_engine, monkeypatch):
    bearer, _, _, visit_id, _ = _seed(subject_engine)
    sender = _sender(monkeypatch, subject_engine)
    sender.send_email.return_value = False
    intent = _intent(subject_engine, bearer, visit_id)
    await dispatch_patient_notification_intent(intent)
    sender.send_email.assert_awaited_once()
    sender.send_sms.assert_not_awaited()
    sender.send_push.assert_not_awaited()
    sender.send_patient_telegram_event_notification.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke_after_commit", [False, True])
async def test_real_push_rechecks_after_inbox_commit(subject_engine, monkeypatch, revoke_after_commit):
    import app.db.session as session_module
    import app.services.notification_subject_intent_service as subject_service
    from app.services.notification_platform_service import NotificationPlatformService
    from app.services.notifications_pkg import NotificationSenderService

    bearer, patient_id, _, visit_id, _ = _seed(subject_engine, contacts=False)
    with Session(subject_engine) as db:
        patient = db.get(Patient, patient_id)
        user = db.get(User, patient.user_id)
        user.device_token = "synthetic-device"
        user.push_notifications_enabled = True
        db.commit()
    sender = NotificationSenderService()
    sender._patient_channel_opted_in = Mock(return_value=True)
    sender._channel_opted_in = Mock(return_value=True)
    sender.fcm_service = SimpleNamespace(active=True, send_notification=AsyncMock(
        return_value=SimpleNamespace(success=True, error_code=None)))
    broadcasts = AsyncMock(return_value=True)
    commits = []

    def platform_for(db):
        platform = NotificationPlatformService(db)
        platform._broadcast_delivery_with_policy = broadcasts
        commit = platform.repository.commit

        def commit_then_revoke():
            commit()
            commits.append("inbox")
            if revoke_after_commit:
                with Session(subject_engine) as other:
                    other.get(User, bearer.user_id).auth_epoch += 1
                    other.commit()

        platform.repository.commit = commit_then_revoke
        return platform

    sender._platform_service = platform_for
    monkeypatch.setattr(subject_service, "notification_sender_service", sender)
    monkeypatch.setattr(session_module, "SessionLocal", lambda: Session(subject_engine))
    intent = _intent(subject_engine, bearer, visit_id)
    await dispatch_patient_notification_intent(intent)
    assert commits == ["inbox"]
    if revoke_after_commit:
        broadcasts.assert_not_awaited()
        sender.fcm_service.send_notification.assert_not_awaited()
    else:
        broadcasts.assert_awaited_once()
        sender.fcm_service.send_notification.assert_awaited_once()
        payload = str(sender.fcm_service.send_notification.await_args)
        assert "123.45" not in payload and "synthetic-token" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["unknown", "timeout"])
async def test_unconfirmed_push_is_not_retried_and_locks_release(subject_engine, monkeypatch, outcome):
    import app.db.session as session_module
    import app.services.notification_subject_intent_service as subject_service
    from app.models.notification import NotificationHistory
    from app.services.notification_platform_service import NotificationPlatformService
    from app.services.notifications_pkg import NotificationSenderService

    bearer, patient_id, _, visit_id, _ = _seed(subject_engine, contacts=False)
    with Session(subject_engine) as db:
        user = db.get(User, db.get(Patient, patient_id).user_id)
        user.device_token, user.push_notifications_enabled = "synthetic-device", True
        db.commit()
    calls = []

    async def fcm_send(**_kwargs):
        calls.append("attempted")
        if outcome == "timeout":
            await asyncio.sleep(0.2)
        return SimpleNamespace(success=False, error_code=None)

    sender = NotificationSenderService()
    sender._patient_channel_opted_in = Mock(return_value=True)
    sender._channel_opted_in = Mock(return_value=True)
    sender.fcm_service = SimpleNamespace(active=True, send_notification=fcm_send)

    def platform_for(db):
        platform = NotificationPlatformService(db)
        platform._broadcast_delivery_with_policy = AsyncMock(return_value=True)
        return platform

    sender._platform_service = platform_for
    monkeypatch.setattr(subject_service, "notification_sender_service", sender)
    monkeypatch.setattr(session_module, "SessionLocal", lambda: Session(subject_engine))
    if outcome == "timeout":
        original_wait_for = asyncio.wait_for

        async def fast_timeout(coro, timeout):
            return await original_wait_for(coro, timeout=0.02)

        monkeypatch.setattr(subject_service.asyncio, "wait_for", fast_timeout)
    intent = _intent(subject_engine, bearer, visit_id)
    await dispatch_patient_notification_intent(intent)
    assert calls == ["attempted"]
    with Session(subject_engine) as db:
        actor = db.get(User, bearer.user_id)
        actor.auth_epoch += 1  # Timeout must not leave the session's locks held.
        db.commit()
        histories = db.query(NotificationHistory).filter_by(channel="mobile").all()
        if outcome == "unknown":
            assert len(histories) == 1 and histories[0].status == "unknown"
        else:
            assert not histories


def test_api_queues_only_subject_and_requires_explicit_visit_and_payment(
    client, db_session, admin_auth_headers, test_patient, monkeypatch
):
    import app.api.v1.endpoints.notifications as endpoint

    dispatched = AsyncMock()
    monkeypatch.setattr(endpoint, "dispatch_patient_notification_intent", dispatched)
    monkeypatch.setattr(
        endpoint.notification_sender_service,
        "_patient_channel_opted_in",
        Mock(return_value=True),
    )
    visit = Visit(
        patient_id=test_patient.id,
        visit_date=date(2026, 4, 1),
        status="open",
        confirmation_context_epoch=123,
    )
    db_session.add(visit)
    db_session.commit()
    response = client.post(
        "/api/v1/notifications/send-appointment-reminder",
        headers=admin_auth_headers,
        params={
            "patient_id": test_patient.id,
            "visit_id": visit.id,
            "appointment_date": "2026-04-01T10:00:00",
            "doctor_name": "SYNTHETIC-SECRET",
            "department": "SYNTHETIC-SECRET",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["queued"] is True
    assert "sms" in response.json()["eligible_channels"]
    dispatched.assert_awaited_once()
    intent = dispatched.await_args.args[0]
    assert intent.visit_id == visit.id
    assert "SYNTHETIC-SECRET" not in repr(intent)
    missing = client.post(
        "/api/v1/notifications/send-payment-notification",
        headers=admin_auth_headers,
        params={
            "visit_id": visit.id,
            "amount": 1,
            "currency": "UZS",
        },
    )
    assert missing.status_code == 409
