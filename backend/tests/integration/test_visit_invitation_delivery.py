"""Synthetic invitation intent and crash-safety tests; no provider is contacted."""

import asyncio
import hashlib
import importlib.util
import os
import threading
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.visit import Visit
from app.models.visit_invitation_delivery import (
    VisitInvitationDelivery,
    VisitInvitationIssuerAuth,
)
from app.services.profile_contact_security import ProfileBearerContext
from app.services.visit_invitation_delivery import (
    InvitationContextChanged,
    InvitationRuntimeUnavailable,
    claim_visit_invitation,
    deliver_registrar_invitation,
    pin_invitation_runtime,
    send_claimed_visit_invitation,
)
from app.services.visit_invitation_delivery import (
    stage_visit_invitation as _stage,
)


def stage_visit_invitation(db, **kwargs):
    return _stage(db, bearer=db.info["invitation_test_bearer"], requester_type="admin", **kwargs)


@pytest.fixture
def subject(db_session):
    from tests.integration.test_derma_price_override_integrity import _create_user

    actor = _create_user(db_session, role="Admin", label="synthetic-issuer")
    db_session.info["invitation_test_bearer"] = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
    patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=7)
    db_session.add(patient)
    db_session.flush()
    visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 1), status="pending_confirmation",
                  source="desk", department="mixed", confirmation_context_epoch=9,
                  confirmation_token="synthetic-only-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add(visit)
    db_session.commit()
    return patient.id, visit.id


def test_claim_is_committed_unknown_and_cannot_repeat(db_session, subject):
    patient_id, visit_id = subject
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    row = db_session.get(VisitInvitationDelivery, delivery_id)
    assert row.state == "pending" and row.token_digest != "synthetic-only-bearer"
    assert not any("synthetic-only-bearer" in repr(value) for value in row.__dict__.values())
    claimed = claim_visit_invitation(db_session, delivery_id)
    assert claimed is not None and "synthetic-only-bearer" not in repr(claimed)
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == "unknown"
    assert claim_visit_invitation(db_session, delivery_id) is None


@pytest.mark.parametrize("mutation", ["owner", "token", "visit_patient", "expired", "status"])
def test_stale_context_cancels_without_claim(db_session, subject, mutation):
    patient_id, visit_id = subject
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    patient = db_session.get(Patient, patient_id)
    visit = db_session.get(Visit, visit_id)
    if mutation == "owner":
        patient.notification_owner_generation += 1
    elif mutation == "token":
        visit.confirmation_token = "different-synthetic-token"
    elif mutation == "visit_patient":
        other = Patient(first_name="SYNTHETIC", last_name="OTHER", notification_owner_generation=8)
        db_session.add(other)
        db_session.flush()
        visit.patient_id = other.id
    elif mutation == "expired":
        visit.confirmation_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    else:
        visit.status = "cancelled"
    db_session.commit()
    assert claim_visit_invitation(db_session, delivery_id) is None
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == "cancelled"


def test_stage_is_part_of_callers_transaction(db_session, subject):
    patient_id, visit_id = subject
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.rollback()
    assert db_session.get(VisitInvitationDelivery, delivery_id) is None


def test_no_unknown_channel_or_missing_telegram_link(db_session, subject):
    patient_id, visit_id = subject
    with pytest.raises(InvitationContextChanged):
        stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="email")
    assert stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="telegram") is None
    with pytest.raises(InvitationContextChanged):
        stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="telegram", require_deliverable=True)
    assert stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id,
                                  channel="pwa", require_deliverable=True) is not None


class FakeSender:
    def __init__(self, *, success=True):
        self.calls = 0
        self.success = success

    async def _send_pwa_invitation(self, patient, data, *, db, sms_opted_in):
        self.calls += 1
        assert sms_opted_in and data["confirmation_token"] == "synthetic-only-bearer"
        return {"success": self.success}


@pytest.mark.parametrize("success", [True, False])
def test_single_dispatch_never_repeats_after_success_or_unknown(db_session, subject, success):
    patient_id, visit_id = subject
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    sender = FakeSender(success=success)
    assert asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender)) is success
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 1
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == ("sent" if success else "unknown")


def test_subject_change_after_claim_never_sends(db_session, subject):
    patient_id, visit_id = subject
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    patient = db_session.get(Patient, patient_id)
    patient.notification_owner_generation += 1
    db_session.commit()
    sender = FakeSender()
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 0
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == "unknown"


@pytest.fixture
def verified_telegram_subject(db_session, subject):
    patient_id, visit_id = subject
    generation = db_session.get(Patient, patient_id).notification_owner_generation
    return patient_id, visit_id, generation


def test_telegram_dispatch_uses_original_link_even_if_newer_link_exists(db_session, verified_telegram_subject, monkeypatch):
    from app.services.notifications_pkg import NotificationSenderService

    patient_id, visit_id, generation = verified_telegram_subject
    first = TelegramUser(patient_id=patient_id, chat_id=90001, active=True, blocked=False,
                         notifications_enabled=True, appointment_reminders=True, patient_link_epoch=11,
                         patient_owner_generation_snapshot=generation)
    db_session.add(first)
    db_session.flush()
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="telegram")
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    assert claimed is not None
    db_session.add(TelegramUser(patient_id=patient_id, chat_id=90002, active=True, blocked=False,
                                notifications_enabled=True, appointment_reminders=True, patient_link_epoch=12,
                                patient_owner_generation_snapshot=generation))
    db_session.commit()

    class FakeBot:
        def __init__(self):
            self.calls = []

        async def send_confirmation_invitation(self, **kwargs):
            self.calls.append(kwargs)
            return {"success": True, "message_id": 42}

    sender = NotificationSenderService(db_session)
    bot = FakeBot()
    monkeypatch.setattr(sender, "telegram_bot", bot, raising=False)
    assert asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert len(bot.calls) == 1 and bot.calls[0]["chat_id"] == 90001
    assert bot.calls[0]["message"] == "У вас новое уведомление."
    assert "synthetic-only-bearer" not in repr(bot.calls)


def test_telegram_unlink_after_claim_does_not_send(db_session, verified_telegram_subject, monkeypatch):
    from app.services.notifications_pkg import NotificationSenderService

    patient_id, visit_id, generation = verified_telegram_subject
    link = TelegramUser(patient_id=patient_id, chat_id=90003, active=True, blocked=False,
                        notifications_enabled=True, appointment_reminders=True, patient_link_epoch=13,
                        patient_owner_generation_snapshot=generation)
    db_session.add(link)
    db_session.flush()
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="telegram")
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    assert claimed is not None
    link.patient_id = None
    db_session.commit()
    sender = NotificationSenderService(db_session)

    async def fail_send(*args, **kwargs):
        raise AssertionError("must not send after unlink")

    monkeypatch.setattr(sender, "_send_telegram_invitation", fail_send)
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))


def test_sms_opt_out_after_claim_prevents_provider_call(db_session, subject):
    from app.models.user_profile import UserPreferences
    from tests.integration.test_derma_price_override_integrity import _create_user

    patient_id, visit_id = subject
    user = _create_user(db_session, role="Patient", label="synthetic-opt-out")
    patient = db_session.get(Patient, patient_id)
    patient.user_id = user.id
    db_session.commit()
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    # SQLite fixture does not install FK constraints; this isolates opt-out
    # without creating an unrelated user-profile workflow.
    db_session.add(UserPreferences(user_id=user.id, profile_id=1, sms_notifications=False))
    db_session.commit()
    with pytest.raises(InvitationContextChanged):
        stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id,
                               channel="pwa", require_deliverable=True)
    db_session.rollback()
    sender = FakeSender()
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 0 and db_session.get(VisitInvitationDelivery, delivery_id).state == "unknown"


@pytest.mark.parametrize("revocation", ["logout", "role", "expiry", "key_rotation"])
def test_issuer_revoked_after_claim_never_sends(db_session, subject, monkeypatch, revocation):
    from app.core.config import settings
    from app.models.authentication import TokenBlacklist
    from app.models.user import User

    patient_id, visit_id = subject
    bearer = db_session.info["invitation_test_bearer"]
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    auth = db_session.get(VisitInvitationIssuerAuth, delivery_id)
    assert bearer.jti not in auth.jti_ciphertext
    claimed = claim_visit_invitation(db_session, delivery_id)
    if revocation == "logout":
        db_session.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    elif revocation == "role":
        db_session.get(User, bearer.user_id).role = "Patient"
    elif revocation == "expiry":
        monkeypatch.setattr("app.services.visit_invitation_delivery.time.time", lambda: bearer.expires_at + 1)
    else:
        monkeypatch.setattr(settings, "SECRET_KEY", "synthetic-rotated-signing-key-0123456789")
    db_session.commit()
    sender = FakeSender()
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 0 and db_session.get(VisitInvitationDelivery, delivery_id).state == "unknown"


def test_issuer_logout_before_claim_marks_pending_cancelled(db_session, subject):
    from app.models.authentication import TokenBlacklist

    patient_id, visit_id = subject
    bearer = db_session.info["invitation_test_bearer"]
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa")
    db_session.commit()
    db_session.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    db_session.commit()
    assert claim_visit_invitation(db_session, delivery_id) is None
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == "cancelled"


def test_legacy_session_without_jti_does_not_enqueue_delivery(db_session, subject):
    patient_id, visit_id = subject
    original = db_session.info["invitation_test_bearer"]
    bearer = ProfileBearerContext(original.user_id, original.auth_epoch, None, original.expires_at, None)
    assert _stage(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa",
                  bearer=bearer, requester_type="admin") is None
    with pytest.raises(InvitationContextChanged):
        _stage(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa",
               bearer=bearer, requester_type="admin", require_deliverable=True)


def test_doctor_owner_rebind_aba_after_claim_never_sends(db_session, subject):
    from app.models.clinic import Doctor
    from tests.integration.test_derma_price_override_integrity import (
        _create_doctor,
        _create_user,
    )

    patient_id, visit_id = subject
    actor = _create_user(db_session, role="Doctor", label="synthetic-doctor")
    other = _create_user(db_session, role="Doctor", label="synthetic-other")
    doctor = _create_doctor(db_session, actor, specialty="dermatology")
    visit = db_session.get(Visit, visit_id)
    visit.doctor_id = doctor.id
    db_session.commit()
    bearer = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
    delivery_id = _stage(db_session, patient_id=patient_id, visit_id=visit_id, channel="pwa", bearer=bearer,
                         requester_type="doctor", doctor_id=doctor.id, doctor_generation=doctor.price_owner_generation)
    db_session.commit()
    claimed = claim_visit_invitation(db_session, delivery_id)
    doctor = db_session.get(Doctor, doctor.id)
    doctor.user_id = other.id
    doctor.price_owner_generation += 1
    db_session.flush()
    doctor.user_id = actor.id
    doctor.price_owner_generation += 1
    db_session.commit()
    sender = FakeSender()
    assert not asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sender.calls == 0


@pytest.mark.parametrize("revocation", ["logout", "role", "epoch", "expiry"])
def test_phone_issuer_revocation_cancels_without_inbox(db_session, subject, monkeypatch, revocation):
    from app.models.authentication import TokenBlacklist
    from app.models.notification import NotificationEvent
    from app.models.user import User
    from app.services.notification_service import NotificationService
    from tests.integration.test_derma_price_override_integrity import _create_user

    patient_id, visit_id = subject
    _create_user(db_session, role="Registrar", label="synthetic-recipient")
    bearer = db_session.info["invitation_test_bearer"]
    delivery_id = stage_visit_invitation(db_session, patient_id=patient_id, visit_id=visit_id, channel="phone")
    db_session.commit()
    if revocation == "logout":
        db_session.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
    elif revocation == "role":
        db_session.get(User, bearer.user_id).role = "Patient"
    elif revocation == "epoch":
        db_session.get(User, bearer.user_id).auth_epoch += 1
    else:
        monkeypatch.setattr("app.services.visit_invitation_delivery.time.time", lambda: bearer.expires_at + 1)
    db_session.commit()
    assert not asyncio.run(deliver_registrar_invitation(db_session, delivery_id, NotificationService(db_session)))
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == "cancelled"
    assert db_session.query(NotificationEvent).filter(NotificationEvent.source_module == "visit_confirmation_secure").count() == 0


def test_phone_doctor_rebind_aba_cancels_without_inbox(db_session, subject):
    from app.models.notification import NotificationEvent
    from app.services.notification_service import NotificationService
    from tests.integration.test_derma_price_override_integrity import (
        _create_doctor,
        _create_user,
    )

    patient_id, visit_id = subject
    _create_user(db_session, role="Registrar", label="synthetic-recipient")
    actor = _create_user(db_session, role="Doctor", label="synthetic-doctor")
    other = _create_user(db_session, role="Doctor", label="synthetic-other")
    doctor = _create_doctor(db_session, actor, specialty="dermatology")
    db_session.get(Visit, visit_id).doctor_id = doctor.id
    db_session.commit()
    bearer = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
    delivery_id = _stage(db_session, patient_id=patient_id, visit_id=visit_id, channel="phone", bearer=bearer,
                         requester_type="doctor", doctor_id=doctor.id, doctor_generation=doctor.price_owner_generation)
    db_session.commit()
    doctor.user_id = other.id
    doctor.price_owner_generation += 1
    db_session.flush()
    doctor.user_id = actor.id
    doctor.price_owner_generation += 1
    db_session.commit()
    assert not asyncio.run(deliver_registrar_invitation(db_session, delivery_id, NotificationService(db_session)))
    assert db_session.get(VisitInvitationDelivery, delivery_id).state == "cancelled"
    assert db_session.query(NotificationEvent).filter(NotificationEvent.source_module == "visit_confirmation_secure").count() == 0


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0117_visit_invitation_delivery.py"
    spec = importlib.util.spec_from_file_location("invitation_migration_0117", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _issuer_migration(conn):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0126_invitation_issuer_auth.py"
    spec = importlib.util.spec_from_file_location("synthetic_invitation_issuer_0126", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    module.upgrade()
    return module


def _approval_migration(conn):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0128_invitation_price_approval.py"
    spec = importlib.util.spec_from_file_location("synthetic_invitation_approval_0128", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    module.upgrade()
    return module


def _nonce_guard_migration(conn):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0130_invitation_nonce_guard.py"
    spec = importlib.util.spec_from_file_location("invitation_nonce_guard_0130", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    module.upgrade()
    return module


def _claim_and_consume_once(conn, delivery_id):
    params = {"id": delivery_id, "nonce": "b" * 64}
    conn.execute(sa.text("""UPDATE visit_invitation_deliveries
       SET state='unknown', dispatch_nonce_digest=:nonce WHERE id=:id AND state='pending'"""), params)
    with pytest.raises(sa.exc.DBAPIError, match="invalid invitation transition"), conn.begin_nested():
        conn.execute(sa.text("""UPDATE visit_invitation_deliveries
           SET state='sent', dispatch_nonce_digest=NULL WHERE id=:id"""), params)
    consume = sa.text("""UPDATE visit_invitation_deliveries SET dispatch_nonce_digest=NULL
       WHERE id=:id AND state='unknown' AND dispatch_nonce_digest=:nonce""")
    assert conn.execute(consume, params).rowcount == 1
    assert conn.execute(consume, params).rowcount == 0
    with pytest.raises(sa.exc.DBAPIError, match="invalid invitation transition"), conn.begin_nested():
        conn.execute(sa.text("UPDATE visit_invitation_deliveries SET dispatch_nonce_digest=:nonce WHERE id=:id"), params)
    conn.execute(sa.text("UPDATE visit_invitation_deliveries SET state='sent' WHERE id=:id"), params)


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_issuer_migration_downgrade_fails_closed(tmp_path, database):
    raw = os.environ.get("DATABASE_URL", "")
    if database == "postgresql":
        if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
            pytest.skip("requires disposable clinic_test PostgreSQL")
        schema = "invite_issuer_down_" + uuid4().hex
        admin = sa.create_engine(raw)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema}"})
    else:
        admin = schema = None
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'issuer.db'}")
    try:
        with engine.begin() as conn:
            for table in ("patients", "visits", "users", "doctors"):
                conn.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
                conn.execute(sa.text(f"INSERT INTO {table} (id) VALUES (1)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            issuer = _issuer_migration(conn)
            issuer.downgrade()
            issuer.upgrade()
            conn.execute(sa.text("""INSERT INTO visit_invitation_deliveries
              (id,visit_id,visit_id_snapshot,patient_id,patient_id_snapshot,owner_generation,context_epoch,token_digest,channel,state)
              VALUES (1,1,1,1,1,7,9,:digest,'pwa','pending')"""), {"digest": "a" * 64})
            conn.execute(sa.text("""INSERT INTO visit_invitation_issuer_auth
              (delivery_id,actor_user_id,actor_user_id_snapshot,actor_auth_epoch,requester_type,expires_at,cipher_version,jti_ciphertext)
              VALUES (1,1,1,0,'admin',9999999999,1,:cipher)"""), {"cipher": "x" * 100})
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                issuer.downgrade()
            assert conn.execute(sa.text("SELECT count(*) FROM visit_invitation_issuer_auth")).scalar_one() == 1
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_migration_rejects_rewind_and_preserves_evidence(tmp_path, database):
    raw = os.environ.get("DATABASE_URL", "")
    if database == "postgresql":
        if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
            pytest.skip("requires disposable clinic_test PostgreSQL")
        schema = "invitation_test_" + uuid4().hex
        admin = sa.create_engine(raw)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema}"})
    else:
        admin = schema = None
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'invitations.db'}")
    try:
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE patients (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE visits (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("INSERT INTO patients (id) VALUES (1)"))
            conn.execute(sa.text("INSERT INTO visits (id) VALUES (1)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(sa.text("""INSERT INTO visit_invitation_deliveries
                (id,visit_id,visit_id_snapshot,patient_id,patient_id_snapshot,owner_generation,context_epoch,token_digest,channel,state)
                VALUES (1,1,1,1,1,7,9,:digest,'pwa','pending')"""), {"digest": "a" * 64})
            row = sa.text("SELECT state, dispatch_nonce_digest, token_digest FROM visit_invitation_deliveries WHERE id=1")
            saved = conn.execute(row).one()
            nonce = _nonce_guard_migration(conn)
            assert conn.execute(row).one() == saved
            nonce.downgrade()
            assert conn.execute(row).one() == saved
            nonce.upgrade()
            assert conn.execute(row).one() == saved
            _claim_and_consume_once(conn, delivery_id=1)
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text("UPDATE visit_invitation_deliveries SET state='pending' WHERE id=1"))
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text("UPDATE visit_invitation_deliveries SET patient_id_snapshot=2 WHERE id=1"))
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text("DELETE FROM visit_invitation_deliveries WHERE id=1"))
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                migration.downgrade()
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


@pytest.mark.integration
def test_postgres_nonowner_login_provisioning():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, role, password = f"invitation_acl_{suffix}", f"invite_user_{suffix}", "synthetic-" + suffix
    admin = sa.create_engine(raw)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
    owner = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema}"})
    runtime = None
    try:
        with owner.begin() as conn:
            conn.execute(sa.text("CREATE TABLE patients (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE visits (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE doctors (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE visit_services (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("INSERT INTO patients (id) VALUES (1)"))
            conn.execute(sa.text("INSERT INTO visits (id) VALUES (1)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            _issuer_migration(conn)
            _approval_migration(conn)
            _nonce_guard_migration(conn)
        path = Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py"
        spec = importlib.util.spec_from_file_location("invitation_provision", path)
        provisioner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provisioner)
        provisioner.provision(owner, schema, role)
        provisioner.provision(owner, schema, role)  # exact same policies are idempotent
        runtime = sa.create_engine(make_url(raw).set(username=role, password=password),
                                   connect_args={"options": f"-csearch_path={schema}"})
        with runtime.begin() as conn:
            assert conn.execute(sa.text("SELECT current_user")).scalar_one() == role
            assert conn.execute(sa.text("SELECT count(*) FROM visit_invitation_deliveries")).scalar_one() == 0
            row = conn.execute(sa.text("""INSERT INTO visit_invitation_deliveries
              (visit_id,visit_id_snapshot,patient_id,patient_id_snapshot,owner_generation,context_epoch,token_digest,channel,state)
              VALUES (1,1,1,1,7,9,:digest,'pwa','pending') RETURNING id"""), {"digest": "a" * 64}).scalar_one()
            _claim_and_consume_once(conn, delivery_id=row)
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text("UPDATE visit_invitation_deliveries SET state='pending' WHERE id=:id"), {"id": row})
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text("DELETE FROM visit_invitation_deliveries WHERE id=:id"), {"id": row})
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text("""INSERT INTO visit_invitation_deliveries
                  (visit_id,visit_id_snapshot,patient_id,patient_id_snapshot,owner_generation,context_epoch,token_digest,channel,state)
                  VALUES (1,1,1,1,7,10,:digest,'pwa','sent')"""), {"digest": "b" * 64})
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            conn.exec_driver_sql(f'DROP ROLE "{role}"')
        admin.dispose()


@pytest.mark.integration
def test_postgres_distinct_schema_and_table_owners_are_explicit(monkeypatch):
    from app.core.config import settings
    from app.services.visit_invitation_delivery import _pin_invitation_storage

    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, schema_owner, table_owner = "invite_diff_" + suffix, "invite_schema_" + suffix, "invite_table_" + suffix
    role, password = "invite_login_" + suffix, "synthetic-" + suffix
    admin = sa.create_engine(raw)
    with admin.begin() as conn:
        conn.exec_driver_sql(f'CREATE ROLE "{schema_owner}" NOLOGIN')
        conn.exec_driver_sql(f'CREATE ROLE "{table_owner}" NOLOGIN')
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}" AUTHORIZATION "{schema_owner}"')
    owner = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema}"})
    runtime = None
    try:
        with owner.begin() as conn:
            conn.execute(sa.text("CREATE TABLE patients (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE visits (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE doctors (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
            conn.execute(sa.text("CREATE TABLE visit_services (id INTEGER PRIMARY KEY)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            _issuer_migration(conn)
            _approval_migration(conn)
            _nonce_guard_migration(conn)
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".visit_invitation_deliveries OWNER TO "{table_owner}"')
            conn.exec_driver_sql(f'ALTER FUNCTION "{schema}".protect_visit_invitation_delivery() OWNER TO "{table_owner}"')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".visit_invitation_issuer_auth OWNER TO "{table_owner}"')
            conn.exec_driver_sql(f'ALTER FUNCTION "{schema}".protect_visit_invitation_issuer_auth() OWNER TO "{table_owner}"')
            for table in ("visit_invitation_price_approval_auth", "visit_invitation_approval_recoveries"):
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" OWNER TO "{table_owner}"')
            for function in ("protect_invite_price_auth", "protect_invite_recovery"):
                conn.exec_driver_sql(f'ALTER FUNCTION "{schema}"."{function}"() OWNER TO "{table_owner}"')
        path = Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py"
        spec = importlib.util.spec_from_file_location("invite_distinct_owner_provision", path)
        provisioner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provisioner)
        provisioner.provision(owner, schema, role)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA", schema)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", schema_owner)
        monkeypatch.setattr(settings, "INVITATION_DB_TABLE_OWNER", table_owner)
        runtime = sa.create_engine(make_url(raw).set(username=role, password=password), connect_args={"options": f"-csearch_path={schema}"})
        with Session(runtime) as db:
            _pin_invitation_storage(db)
            db.rollback()
            with owner.begin() as conn:
                conn.exec_driver_sql(f'ALTER TABLE "{schema}".visit_invitation_deliveries DISABLE TRIGGER trg_protect_visit_invitation')
            with pytest.raises(InvitationRuntimeUnavailable):
                _pin_invitation_storage(db)
            db.rollback()
            with owner.begin() as conn:
                conn.exec_driver_sql(f'ALTER TABLE "{schema}".visit_invitation_deliveries ENABLE TRIGGER trg_protect_visit_invitation')
                original = conn.execute(sa.text("SELECT pg_catalog.pg_get_functiondef(pg_catalog.to_regprocedure(:function))"),
                                        {"function": f'"{schema}".protect_visit_invitation_delivery()'}).scalar_one()
                conn.exec_driver_sql(f'''CREATE OR REPLACE FUNCTION "{schema}".protect_visit_invitation_delivery()
                    RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$''')
            with pytest.raises(InvitationRuntimeUnavailable):
                _pin_invitation_storage(db)
            db.rollback()
            with owner.begin() as conn:
                conn.exec_driver_sql(original)
            _pin_invitation_storage(db)
            db.rollback()
            monkeypatch.setattr(settings, "INVITATION_DB_TABLE_OWNER", schema_owner)
            with pytest.raises(InvitationRuntimeUnavailable):
                _pin_invitation_storage(db)
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            for name in (role, table_owner, schema_owner):
                conn.exec_driver_sql(f'DROP ROLE "{name}"')
        admin.dispose()


@pytest.mark.integration
def test_postgres_claim_race_and_owner_change_waits_for_send(monkeypatch):
    from app.db.capability_namespace import capability_schema_name
    from app.models.authentication import TokenBlacklist
    from app.models.clinic import Doctor
    from app.models.user import User
    from app.models.visit import VisitService
    from tests.integration.test_invitation_subject_nonowner_pg import (
        install_invitation_subject_fence,
    )
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, role, password = "invitation_race_" + suffix, "invite_race_" + suffix, "synthetic-" + suffix
    cap = "invite_race_cap_" + suffix
    admin = sa.create_engine(raw)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
        owner_name = conn.execute(sa.text("SELECT current_user")).scalar_one()
    engine = sa.create_engine(raw, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    runtime = None
    try:
        with engine.begin() as conn:
            # Full ORM columns, deliberately isolated from unrelated schemas.
            conn.execute(sa.schema.CreateTable(User.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.schema.CreateTable(Doctor.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.schema.CreateTable(TokenBlacklist.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.schema.CreateTable(Patient.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.schema.CreateTable(Visit.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.schema.CreateTable(VisitService.__table__, include_foreign_key_constraints=[]))
            conn.execute(sa.text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            _issuer_migration(conn)
            _approval_migration(conn)
            _nonce_guard_migration(conn)
            conn.exec_driver_sql(f'GRANT SELECT ON "{schema}".doctors TO "{role}"')
        install_invitation_subject_fence(engine, schema=schema, owner_name=owner_name,
                                         runtime_role=role, subject_cap_role=cap, monkeypatch=monkeypatch)
        path = Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py"
        spec = importlib.util.spec_from_file_location("invitation_provision_race", path)
        provisioner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(provisioner)
        provisioner.provision(engine, schema, role)
        from app.core.config import settings
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA", schema)
        monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", owner_name)
        monkeypatch.setattr(settings, "INVITATION_DB_TABLE_OWNER", owner_name)
        runtime = sa.create_engine(make_url(raw).set(username=role, password=password),
                                   connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
        with Session(engine) as db:
            actor = User(username="synthetic-issuer", email="synthetic-issuer@example.invalid", hashed_password="synthetic", role="Admin", is_active=True, is_superuser=False)
            db.add(actor)
            db.flush()
            issuer_bearer = ProfileBearerContext(actor.id, actor.auth_epoch, str(uuid4()), int(time.time()) + 3600, None)
            patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998900000000", notification_owner_generation=7)
            db.add(patient)
            db.flush()
            visit = Visit(patient_id=patient.id, visit_date=date(2030, 1, 1), status="pending_confirmation",
                          source="desk", department="mixed", confirmation_context_epoch=9,
                          confirmation_token="synthetic-only-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
            db.add(visit)
            db.flush()
            patient_id = patient.id
            visit_id = visit.id
            db.commit()
        with Session(runtime) as db:
            db.info["invitation_test_bearer"] = issuer_bearer
            monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", "SYNTHETIC_wrong_owner")
            with pytest.raises(InvitationRuntimeUnavailable):
                stage_visit_invitation(db, patient_id=patient_id, visit_id=visit_id, channel="pwa")
            db.rollback()
            monkeypatch.setattr(settings, "INVITATION_DB_SCHEMA_OWNER", owner_name)
            # An attacker-writable temp schema must never shadow ORM targets.
            db.execute(sa.text("CREATE TEMP TABLE patients (id integer)"))
            db.execute(sa.text("CREATE TEMP TABLE visits (id integer)"))
            for path in (f'pg_temp, "{schema}", pg_catalog', f'pg_catalog, "{schema}", pg_temp'):
                db.execute(sa.text(f"SET LOCAL search_path TO {path}"))
                pin_invitation_runtime(db)
                resolved = db.execute(sa.text("SELECT pg_catalog.current_schemas(true)")).scalar_one()
                assert resolved[0:2] == ["pg_catalog", schema] and resolved[-1].startswith("pg_temp_")
            attempt = stage_visit_invitation(db, patient_id=patient_id, visit_id=visit_id, channel="pwa")
            db.commit()
        start = threading.Barrier(2)
        claims, errors = [], []

        def claim():
            try:
                with Session(runtime) as db:
                    start.wait(timeout=5)
                    claims.append(claim_visit_invitation(db, attempt))
            except Exception as exc:
                errors.append(exc)

        workers = [threading.Thread(target=claim) for _ in range(2)]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join(timeout=10)
        assert not errors and all(not thread.is_alive() for thread in workers)
        claimed, = [value for value in claims if value is not None]
        assert len(claims) == 2
        entered, release, transfer_started, transfer_done = (threading.Event() for _ in range(4))

        class PausingSender:
            async def _send_pwa_invitation(self, patient, data, *, db, sms_opted_in):
                entered.set()
                assert release.wait(5)
                return {"success": True}

        send_result = []

        def send():
            try:
                with Session(runtime) as db:
                    send_result.append(asyncio.run(send_claimed_visit_invitation(db, claimed, PausingSender())))
            except Exception as exc:
                errors.append(exc)

        def transfer():
            try:
                with Session(engine) as db:
                    transfer_started.set()
                    db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=issuer_bearer.user_id))
                    db.commit()
                    transfer_done.set()
            except Exception as exc:
                errors.append(exc)

        sender_thread = threading.Thread(target=send)
        sender_thread.start()
        assert entered.wait(5)
        transfer_thread = threading.Thread(target=transfer)
        transfer_thread.start()
        assert transfer_started.wait(5) and not transfer_done.wait(0.25)
        release.set()
        sender_thread.join(10)
        transfer_thread.join(10)
        assert not errors and send_result == [True] and transfer_done.is_set()
        # Individual logout holds the issuer User lock before blacklist commit.
        # A competing send fails closed on NOWAIT and cannot call a provider.
        with Session(engine) as db:
            later = Visit(patient_id=patient_id, visit_date=date(2030, 1, 2), status="pending_confirmation",
                          source="desk", department="mixed", confirmation_context_epoch=10,
                          confirmation_token="synthetic-second-bearer", confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
            db.add(later)
            db.flush()
            later_id = later.id
            db.commit()
        with Session(runtime) as db:
            db.info["invitation_test_bearer"] = issuer_bearer
            second = stage_visit_invitation(db, patient_id=patient_id, visit_id=later_id, channel="pwa")
            db.commit()
            claimed_second = claim_visit_invitation(db, second)
        logout = Session(engine)
        try:
            logout.query(User).filter(User.id == issuer_bearer.user_id).with_for_update().one()
            logout.add(TokenBlacklist(jti=issuer_bearer.jti, user_id=issuer_bearer.user_id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            logout.flush()
            no_send = FakeSender()
            with Session(runtime) as db:
                assert not asyncio.run(send_claimed_visit_invitation(db, claimed_second, no_send))
            assert no_send.calls == 0
            logout.commit()
        finally:
            logout.close()
        # A backend database role cannot restore a consumed claim after an
        # uncertain outcome and thereby make the same capability usable again.
        nonce = hashlib.sha256(claimed_second.dispatch_nonce.encode("utf-8")).hexdigest()
        with runtime.begin() as conn:
            with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
                conn.execute(sa.text(f'UPDATE "{schema}".visit_invitation_deliveries SET dispatch_nonce_digest=:nonce WHERE id=:id'),
                             {"nonce": nonce, "id": second})
            assert conn.execute(sa.text(f'SELECT state,dispatch_nonce_digest FROM "{schema}".visit_invitation_deliveries WHERE id=:id'),
                                {"id": second}).one() == ("unknown", None)
        # Weakened RLS policy is detected before ORM reads or side effects.
        with engine.begin() as conn:
            conn.exec_driver_sql(f'ALTER POLICY invitation_backend_insert ON "{schema}".visit_invitation_deliveries WITH CHECK (true)')
        with Session(runtime) as db:
            db.info["invitation_test_bearer"] = issuer_bearer
            with pytest.raises(InvitationRuntimeUnavailable):
                stage_visit_invitation(db, patient_id=patient_id, visit_id=visit_id, channel="pwa")
        with engine.begin() as conn:
            conn.exec_driver_sql(f"ALTER POLICY invitation_backend_insert ON \"{schema}\".visit_invitation_deliveries WITH CHECK (state='pending' AND dispatch_nonce_digest IS NULL)")
            conn.exec_driver_sql(f'ALTER POLICY invitation_issuer_backend_select ON "{schema}".visit_invitation_issuer_auth USING (false)')
        with Session(runtime) as db:
            with pytest.raises(InvitationRuntimeUnavailable):
                pin_invitation_runtime(db)
    finally:
        if runtime is not None:
            runtime.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.exec_driver_sql(f'DROP ROLE "{role}"')
            conn.exec_driver_sql(f'DROP ROLE "{cap}"')
        admin.dispose()
