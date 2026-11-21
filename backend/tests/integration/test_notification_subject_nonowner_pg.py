"""Physical nonowner subject dispatch: no hidden revocation or stale owner."""

import asyncio
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.authentication import TokenBlacklist
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import (
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
)
from app.models.visit import Visit
from app.services.notification_subject_intent_service import (
    create_patient_notification_intent,
    dispatch_patient_notification_intent,
)
from tests.integration.test_notification_subject_transfer_pg import (
    notification_pg_engine as notification_pg_engine,
)
from tests.integration.test_notification_subject_transfer_sqlite import (
    _intent,
    _seed,
    _sender,
)


def _assert_no_send(sender):
    sender.send_push.assert_not_awaited()
    sender.send_email.assert_not_awaited()
    sender.send_sms.assert_not_awaited()
    sender.send_patient_telegram_event_notification.assert_not_awaited()


@pytest.mark.parametrize("deactivate", [False, True])
def test_assigned_doctor_nonowner_dispatch(notification_pg_engine, monkeypatch, deactivate):
    owner, runtime = notification_pg_engine
    bearer, _, _, visit_id, _ = _seed(owner)
    with Session(owner) as db:
        actor = db.get(User, bearer.user_id)
        actor.role = "Doctor"
        doctor = Doctor(user_id=actor.id, specialty="cardiology", active=True, repeat_owner_generation=1)
        db.add(doctor)
        db.flush()
        db.get(Visit, visit_id).doctor_id = doctor.id
        db.commit()
        doctor_id = doctor.id
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id)
    if deactivate:
        with Session(owner) as db:
            db.get(Doctor, doctor_id).active = False
            db.commit()
    asyncio.run(dispatch_patient_notification_intent(intent))
    if deactivate:
        _assert_no_send(sender)
    else:
        sender.send_email.assert_awaited_once()
        sender.send_sms.assert_awaited_once()
        sender.send_push.assert_awaited_once()


@pytest.mark.parametrize("revocation", ["jti", "epoch", "inactive", "role", "expiry"])
def test_nonowner_dispatch_rechecks_issuer(notification_pg_engine, monkeypatch, revocation):
    owner, runtime = notification_pg_engine
    bearer, _, _, visit_id, payment_id = _seed(owner)
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id, purpose="payment_notification", payment_id=payment_id)
    if revocation == "expiry":
        intent = replace(intent, bearer=replace(bearer, expires_at=int(time.time()) - 1))
    else:
        with Session(owner) as db:
            actor = db.get(User, bearer.user_id)
            if revocation == "jti":
                db.add(TokenBlacklist(jti=bearer.jti, user_id=actor.id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            elif revocation == "epoch":
                actor.auth_epoch += 1
            elif revocation == "inactive":
                actor.is_active = False
            else:
                actor.role = "Registrar"
            db.commit()
    asyncio.run(dispatch_patient_notification_intent(intent))
    _assert_no_send(sender)


def test_hidden_blacklist_cannot_authorize_creation_or_dispatch(notification_pg_engine, monkeypatch):
    owner, runtime = notification_pg_engine
    bearer, _, _, visit_id, _ = _seed(owner)
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id)
    with Session(owner) as db:
        db.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                              expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        db.commit()
    schema = owner.dialect.default_schema_name
    with owner.begin() as conn:
        conn.exec_driver_sql(f'ALTER POLICY synthetic_subject_select ON "{schema}".token_blacklist USING (false)')
    with Session(runtime) as db, pytest.raises(HTTPException) as denied:
        create_patient_notification_intent(db, bearer=bearer, purpose="visit_confirmation", visit_id=visit_id)
    assert denied.value.status_code == 503
    asyncio.run(dispatch_patient_notification_intent(intent))
    _assert_no_send(sender)


@pytest.mark.parametrize("table", ["user_preferences", "user_notification_settings"])
@pytest.mark.parametrize("defect", ["hidden_select", "hidden_lock", "unvalidated_fk", "disabled_fk", "missing_unique",
                                   "public_reader", "public_writer", "grantable", "missing_config", "wrong_owner"])
def test_untrusted_preference_visibility_never_authorizes_send(notification_pg_engine, monkeypatch, table, defect):
    owner, runtime = notification_pg_engine
    bearer, patient_id, _, visit_id, _ = _seed(owner)
    sender = _sender(monkeypatch, runtime)
    with Session(owner) as db:
        patient = db.get(Patient, patient_id)
        profile = UserProfile(user_id=patient.user_id)
        db.add(profile)
        db.flush()
        if table == "user_preferences":
            db.add(UserPreferences(user_id=patient.user_id, profile_id=profile.id, email_notifications=False))
        else:
            db.add(UserNotificationSettings(user_id=patient.user_id, profile_id=profile.id,
                                            sms_appointment_confirmation=False))
        db.commit()
    schema = owner.dialect.default_schema_name
    if defect == "missing_config":
        from app.core.config import settings

        monkeypatch.setattr(settings, "NOTIFY_PREFERENCES_DB_OWNER", None)
    elif defect == "wrong_owner":
        from app.core.config import settings

        monkeypatch.setattr(settings, "NOTIFY_PREFERENCES_DB_OWNER", "synthetic-wrong-owner")
    with owner.begin() as conn:
        if defect == "hidden_select":
            conn.exec_driver_sql(f'ALTER POLICY synthetic_notify_preference ON "{schema}"."{table}" USING (false)')
        elif defect == "hidden_lock":
            conn.exec_driver_sql(f'ALTER POLICY synthetic_notify_preference_lock ON "{schema}"."{table}" USING (false)')
        elif defect == "public_writer":
            conn.exec_driver_sql(f'GRANT UPDATE ON "{schema}"."{table}" TO PUBLIC')
        elif defect == "public_reader":
            conn.exec_driver_sql(f'GRANT SELECT ON "{schema}"."{table}" TO PUBLIC')
        elif defect == "grantable":
            conn.exec_driver_sql(f'GRANT UPDATE (id) ON "{schema}"."{table}" TO "{runtime.url.username}" WITH GRANT OPTION')
        elif defect == "missing_unique":
            name = conn.execute(text("""
              SELECT c.conname FROM pg_catalog.pg_constraint c
              JOIN pg_catalog.pg_attribute a ON a.attrelid=c.conrelid AND a.attname='user_id'
              WHERE c.conrelid=pg_catalog.to_regclass(:table) AND c.contype='u'
                AND c.conkey=ARRAY[a.attnum]::pg_catalog.int2[]
            """), {"table": f'"{schema}"."{table}"'}).scalar_one()
            conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" DROP CONSTRAINT {owner.dialect.identifier_preparer.quote_identifier(name)}')
        elif defect in {"unvalidated_fk", "disabled_fk"}:
            name = conn.execute(text("""
              SELECT conname FROM pg_catalog.pg_constraint
              WHERE conrelid=pg_catalog.to_regclass(:table) AND contype='f'
                AND confrelid=pg_catalog.to_regclass(:users)
            """), {"table": f'"{schema}"."{table}"', "users": f'"{schema}".users'}).scalar_one()
            quote = owner.dialect.identifier_preparer.quote_identifier
            if defect == "unvalidated_fk":
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" DROP CONSTRAINT {quote(name)}')
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" ADD CONSTRAINT {quote(name)} FOREIGN KEY (user_id) REFERENCES "{schema}".users(id) NOT VALID')
            else:
                trigger = conn.execute(text("""
                  SELECT t.tgname FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_constraint c ON c.oid=t.tgconstraint
                  WHERE c.conrelid=pg_catalog.to_regclass(:table) AND c.conname=:name AND t.tgrelid=c.conrelid LIMIT 1
                """), {"table": f'"{schema}"."{table}"', "name": name}).scalar_one()
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" DISABLE TRIGGER {quote(trigger)}')
    with Session(runtime) as db, pytest.raises(HTTPException) as denied:
        create_patient_notification_intent(db, bearer=bearer, purpose="visit_confirmation", visit_id=visit_id)
    assert denied.value.status_code == 503
    _assert_no_send(sender)


@pytest.mark.parametrize("table", ["user_preferences", "user_notification_settings"])
def test_locked_optout_fails_closed_then_current_consent_works(notification_pg_engine, monkeypatch, table):
    from app.services.notifications_pkg import NotificationSenderService

    owner, runtime = notification_pg_engine
    bearer, patient_id, _, visit_id, _ = _seed(owner)
    with Session(owner) as db:
        patient = db.get(Patient, patient_id)
        profile = UserProfile(user_id=patient.user_id)
        db.add(profile)
        db.flush()
        db.add(UserPreferences(user_id=patient.user_id, profile_id=profile.id,
                               email_notifications=True, sms_notifications=True))
        db.add(UserNotificationSettings(user_id=patient.user_id, profile_id=profile.id,
                                        sms_appointment_confirmation=True))
        db.commit()
        subject_user_id = patient.user_id
    sender = _sender(monkeypatch, runtime)
    sender._patient_channel_opted_in = NotificationSenderService()._patient_channel_opted_in
    intent = _intent(runtime, bearer, visit_id)
    sqlstates = []

    @event.listens_for(runtime, "handle_error")
    def observe_error(context):
        sqlstates.append(getattr(context.original_exception, "sqlstate", None))

    model = UserPreferences if table == "user_preferences" else UserNotificationSettings
    with Session(owner) as writer:
        row = writer.query(model).filter_by(user_id=subject_user_id).with_for_update().one()
        if table == "user_preferences":
            row.email_notifications = False
        else:
            row.sms_appointment_confirmation = False
        writer.flush()
        asyncio.run(dispatch_patient_notification_intent(intent))
        assert "55P03" in sqlstates
        _assert_no_send(sender)
        writer.commit()
    asyncio.run(dispatch_patient_notification_intent(intent))
    sender.send_push.assert_awaited_once()
    if table == "user_preferences":
        sender.send_email.assert_not_awaited()
        sender.send_sms.assert_awaited_once()
    else:
        sender.send_sms.assert_not_awaited()
        sender.send_email.assert_awaited_once()


@pytest.mark.parametrize("writer_first", [False, True])
def test_new_optout_and_dispatch_serialize_via_user_fk(notification_pg_engine, monkeypatch, writer_first):
    from app.services.notifications_pkg import NotificationSenderService

    owner, runtime = notification_pg_engine
    bearer, patient_id, _, visit_id, _ = _seed(owner)
    with Session(owner) as db:
        patient = db.get(Patient, patient_id)
        profile = UserProfile(user_id=patient.user_id)
        db.add(profile)
        db.flush()
        user_id, profile_id = patient.user_id, profile.id
        db.commit()
    sender = _sender(monkeypatch, runtime)
    sender._patient_channel_opted_in = NotificationSenderService()._patient_channel_opted_in
    intent = _intent(runtime, bearer, visit_id)
    entered, release, lock_query, writer_committed = (threading.Event() for _ in range(4))
    errors, blocked_pids = [], []
    original = sender._patient_channel_opted_in

    async def wait_for_writer_on_email(*_args, **_kwargs):
        if not writer_first:
            assert await asyncio.to_thread(writer_committed.wait, 5)
        return True

    sender.send_email.side_effect = wait_for_writer_on_email

    def pause_after_lock(**kwargs):
        result = original(**kwargs)
        if not writer_first and not entered.is_set():
            entered.set()
            assert release.wait(5)
        return result

    sender._patient_channel_opted_in = pause_after_lock

    @event.listens_for(runtime, "before_cursor_execute")
    def observe(conn, _cursor, statement, _parameters, _context, _executemany):
        if writer_first and threading.current_thread() is not threading.main_thread() and "FROM users" in statement and "FOR UPDATE" in statement:
            blocked_pids.append(conn.connection.driver_connection.info.backend_pid)
            lock_query.set()

    def run_dispatch():
        try:
            asyncio.run(dispatch_patient_notification_intent(intent))
        except BaseException as exc:
            errors.append(exc)

    def insert_optout():
        try:
            with Session(owner) as db:
                blocked_pids.append(db.execute(text("SELECT pg_catalog.pg_backend_pid()" )).scalar_one())
                lock_query.set()
                db.add(UserPreferences(user_id=user_id, profile_id=profile_id,
                                       email_notifications=True, sms_notifications=False))
                db.commit()
                writer_committed.set()
        except BaseException as exc:
            errors.append(exc)

    def assert_waiting():
        assert lock_query.wait(5)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            with owner.connect() as db:
                blocked = db.execute(text("SELECT pg_catalog.cardinality(pg_catalog.pg_blocking_pids(:pid)) > 0"),
                                     {"pid": blocked_pids[0]}).scalar_one()
            if blocked:
                return
            time.sleep(0.01)
        pytest.fail("Expected a PostgreSQL User/FK lock wait")

    if writer_first:
        with Session(owner) as writer:
            writer.add(UserPreferences(user_id=user_id, profile_id=profile_id,
                                       email_notifications=True, sms_notifications=False))
            writer.flush()
            thread = threading.Thread(target=run_dispatch)
            thread.start()
            assert_waiting()
            writer.commit()
            writer_committed.set()
            thread.join(10)
        assert not thread.is_alive()
    else:
        thread = threading.Thread(target=run_dispatch)
        thread.start()
        assert entered.wait(5)
        writer_thread = threading.Thread(target=insert_optout)
        writer_thread.start()
        try:
            assert_waiting()
        finally:
            release.set()
        thread.join(10)
        writer_thread.join(10)
        assert not thread.is_alive() and not writer_thread.is_alive()
    assert not errors
    sender.send_sms.assert_not_awaited()
    sender.send_email.assert_awaited_once()
    sender.send_push.assert_awaited_once()


def test_owner_aba_invalidates_preexisting_intent(notification_pg_engine, monkeypatch):
    owner, runtime = notification_pg_engine
    bearer, patient_id, _, visit_id, _ = _seed(owner)
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id)
    with Session(owner) as db:
        patient = db.get(Patient, patient_id)
        original = patient.user_id
        replacement = User(username="synthetic-owner-" + uuid4().hex, hashed_password="!", role="Patient", is_active=True)
        db.add(replacement)
        db.flush()
        patient.user_id = replacement.id
        db.commit()
        patient.user_id = original
        db.commit()
    asyncio.run(dispatch_patient_notification_intent(intent))
    _assert_no_send(sender)


def test_nonowner_logout_wins_while_dispatch_waits_on_user(notification_pg_engine, monkeypatch):
    owner, runtime = notification_pg_engine
    bearer, _, _, visit_id, _ = _seed(owner)
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id)
    entered, pids, errors = threading.Event(), [], []

    @event.listens_for(runtime, "before_cursor_execute")
    def observe(conn, _cursor, statement, _parameters, _context, _executemany):
        if threading.current_thread() is not threading.main_thread() and "FROM users" in statement and "FOR UPDATE" in statement:
            pids.append(conn.connection.driver_connection.info.backend_pid)
            entered.set()

    def dispatch():
        try:
            asyncio.run(dispatch_patient_notification_intent(intent))
        except BaseException as exc:
            errors.append(exc)

    with Session(owner) as logout:
        logout.query(User).filter_by(id=bearer.user_id).with_for_update().one()
        logout.add(TokenBlacklist(jti=bearer.jti, user_id=bearer.user_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        logout.flush()
        thread = threading.Thread(target=dispatch)
        thread.start()
        assert entered.wait(5)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            with owner.connect() as conn:
                blocked = conn.execute(text("SELECT pg_catalog.cardinality(pg_catalog.pg_blocking_pids(:pid)) > 0"),
                                       {"pid": pids[0]}).scalar_one()
            if blocked:
                break
            time.sleep(0.01)
        else:
            pytest.fail("Dispatcher never reached a PostgreSQL row-lock wait")
        logout.commit()
        thread.join(10)
    assert not thread.is_alive() and not errors
    _assert_no_send(sender)
