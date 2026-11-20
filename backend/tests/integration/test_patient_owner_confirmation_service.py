"""Confirmation reads must serialize with changes to the patient owner."""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.visit import Visit, VisitService
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    _hash_telegram_ticket_start_token,
    _telegram_review_base_url,
    build_telegram_ticket_start_token,
    build_telegram_visit_action_token,
    consume_telegram_ticket_start_token,
)


@pytest.mark.parametrize("origin,environment,opt_in,allowed", [
    ("https://clinic.example", "production", False, True),
    ("https://clinic.example/portal", "dev", False, True),
    ("", "dev", False, False),
    ("http://clinic.example", "production", True, False),
    ("http://127.0.0.1:5173", "dev", False, False),
    ("http://127.0.0.1:5173", "dev", True, True),
    ("http://localhost:5173", "test", True, True),
    ("http://[::1]:5173", "dev", True, True),
    ("http://localhost:5173", "production", True, False),
    ("http://127.0.0.2:5173", "dev", True, False),
    ("https://localhost", "production", True, False),
    ("https://app.localhost", "production", True, False),
    ("https://0x7f000001", "production", True, False),
    ("https://127.1", "production", True, False),
    ("https://0.0.0.0", "production", True, False),
    ("https://[::]", "production", True, False),
    ("https://[fe80::1%25eth0]", "production", False, False),
    ("https://user:pass@clinic.example", "dev", False, False),
    ("https://clinic.example?redirect=bad", "dev", False, False),
    ("https://clinic.example/#token=bad", "dev", False, False),
    ("https://bad host.example", "dev", False, False),
    ("https://clinic.example:99999", "dev", False, False),
])
def test_telegram_review_requires_valid_trusted_origin(monkeypatch, origin, environment, opt_in, allowed):
    monkeypatch.setattr(settings, "FRONTEND_URL", origin)
    monkeypatch.setattr(settings, "ENV", environment)
    monkeypatch.setattr(settings, "ALLOW_INSECURE_LOCAL_TELEGRAM_REVIEW", opt_in)
    if allowed:
        assert _telegram_review_base_url() == origin.rstrip("/")
    else:
        with pytest.raises(VisitConfirmationDomainError) as exc:
            _telegram_review_base_url()
        assert exc.value.status_code == 503


def _prepare(db, visit):
    visit.status = "pending_confirmation"
    visit.confirmation_channel = "pwa"
    visit.confirmation_token = "synthetic-token-" + uuid.uuid4().hex
    visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db.commit()
    return visit.confirmation_token


def test_public_info_locks_and_rejects_deleted_subject(db_session, test_visit, test_patient):
    token = _prepare(db_session, test_visit)
    assert VisitConfirmationService(db_session).get_visit_info(token)["visit_id"] == test_visit.id
    db_session.rollback()
    test_patient.is_deleted = True
    db_session.commit()
    with pytest.raises(VisitConfirmationDomainError) as exc:
        VisitConfirmationService(db_session).get_visit_info(token)
    assert exc.value.status_code == 404


def test_shared_patient_lock_rejects_missing_or_deleted_sqlite(db_session, test_patient):
    from app.services.patient_subject_lock import lock_patient_subject

    assert lock_patient_subject(db_session, test_patient.id) is True
    assert lock_patient_subject(db_session, 2_000_000_000) is False
    db_session.rollback()
    test_patient.is_deleted = True
    db_session.commit()
    assert lock_patient_subject(db_session, test_patient.id) is False


def test_public_info_rejects_missing_expiry(db_session, test_visit):
    token = _prepare(db_session, test_visit)
    test_visit.confirmation_expires_at = None
    db_session.commit()
    with pytest.raises(VisitConfirmationDomainError) as exc:
        VisitConfirmationService(db_session).get_visit_info(token)
    assert exc.value.status_code == 400


def test_ticket_qr_rechecks_deleted_patient_before_link(db_session, test_visit, test_patient):
    expires = datetime.now(UTC) + timedelta(minutes=10)
    ticket = build_telegram_ticket_start_token(expires_at=expires)
    test_visit.status = "open"
    test_visit.confirmation_token = _hash_telegram_ticket_start_token(ticket)
    test_visit.confirmation_expires_at = expires
    db_session.commit()
    test_patient.is_deleted = True
    db_session.commit()
    assert consume_telegram_ticket_start_token(db_session, ticket) is None
    assert test_visit.confirmation_token == _hash_telegram_ticket_start_token(ticket)


def test_confirmation_freezes_patient_response_before_commit(db_session, test_visit, test_patient, monkeypatch):
    test_patient.last_name = "SYNTHETIC-ORIGINAL"
    other = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC-OTHER")
    db_session.add(other)
    db_session.flush()
    other_id = other.id
    test_visit.visit_date = date.today() + timedelta(days=7)
    test_visit.created_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.add(VisitService(visit_id=test_visit.id, service_id=1, name="SYNTHETIC",
                                qty=1, price=1, currency="UZS"))
    db_session.flush()
    token = _prepare(db_session, test_visit)
    expected_name = test_patient.short_name()
    visit_id = test_visit.id
    service = VisitConfirmationService(db_session)
    commit = service.repository.commit

    def commit_then_transfer():
        commit()
        db_session.execute(text("UPDATE visits SET patient_id=:other WHERE id=:visit"), {"other": other_id, "visit": visit_id})
        db_session.commit()

    monkeypatch.setattr(service.repository, "commit", commit_then_transfer)
    result = service.confirm_by_pwa(token=token, patient_phone=None, source_ip=None, user_agent="synthetic")
    assert result["patient_name"] == expected_name
    assert "SYNTHETIC-OTHER" not in result["patient_name"]
    assert db_session.get(Visit, visit_id).patient_id == other_id


@pytest.mark.integration
def test_postgres_login_role_pins_shadow_and_refuses_incomplete_visibility(monkeypatch):
    from app.db.capability_namespace import capability_schema_name
    from tests.integration.test_confirmation_subject_role_provision import (
        _provision_module,
    )
    from tests.integration.test_patient_owner_confirmation_migration import _setup

    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    url = make_url(raw)
    suffix = uuid.uuid4().hex
    schema, shadow, role, password = "subject_" + suffix, "shadow_" + suffix, "subject_role_" + suffix, uuid.uuid4().hex
    cap = "subject_cap_" + suffix
    private = capability_schema_name(schema)
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\''))
        conn.execute(text(f'CREATE ROLE "{cap}" NOLOGIN'))
        conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}", "{shadow}" TO "{role}"'))
    owner = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    runtime = create_engine(url.set(username=role, password=password), connect_args={"options": f"-csearch_path={schema}"})
    try:
        with owner.begin() as conn:
            _setup(conn)
            conn.execute(text(f'ALTER TABLE "{schema}".patients ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".patients FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".visits ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".visits FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'CREATE TABLE "{schema}".token_blacklist (id integer PRIMARY KEY)'))
            conn.execute(text(f'INSERT INTO "{schema}".token_blacklist VALUES (1)'))
            conn.execute(text(f'ALTER TABLE "{schema}".token_blacklist ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".token_blacklist FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'GRANT SELECT ON "{schema}".token_blacklist TO "{role}"'))
            conn.execute(text(f'GRANT SELECT ON "{schema}".users TO "{role}"'))
            conn.execute(text(f'CREATE POLICY synthetic_auth_select ON "{schema}".token_blacklist FOR SELECT TO "{role}" USING (true)'))
            conn.execute(text(f'CREATE TABLE "{shadow}".visits (id integer, confirmation_token text)'))
            conn.execute(text(f"INSERT INTO \"{shadow}\".visits VALUES (1,'synthetic-shadow')"))
        _provision_module().provision(admin, schema, cap, role, expected_owner=url.username)
        monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA", schema)
        monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA_OWNER", url.username)
        monkeypatch.setattr(settings, "TRUSTED_DB_RUNTIME_ROLE", role)
        monkeypatch.setattr(settings, "TRUSTED_DB_OWNER_MEMBERS", ())
        monkeypatch.setattr(settings, "TRUSTED_AUTH_TABLE_OWNER", url.username)
        monkeypatch.setattr(settings, "TRUSTED_AUTH_OWNER_MEMBERS", ())
        monkeypatch.setattr(settings, "TRUSTED_AUTH_READ_ROLES", ())
        monkeypatch.setattr(settings, "TRUSTED_AUTH_WRITE_ROLES", ())
        monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_OWNER", url.username)
        monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_OWNER_MEMBERS", ())
        monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_WRITE_ROLES", ())
        with Session(runtime) as db:
            from app.services.patient_subject_lock import lock_patient_subject

            VisitConfirmationService(db)._require_full_subject_visibility()
            assert lock_patient_subject(db, 1) is True
            assert lock_patient_subject(db, 2_000_000_000) is False
            db.execute(text(f'SET LOCAL search_path TO "{shadow}", "{schema}", pg_catalog'))
            VisitConfirmationService(db)._require_full_subject_visibility()
            assert db.execute(text("SELECT confirmation_token FROM visits WHERE id=1")).scalar_one() == "original-token"
            assert VisitConfirmationService(db)._lock_confirmation_patient("original-token") == 1
            with owner.connect() as competitor:
                competing = competitor.begin()
                try:
                    competitor.execute(text("SET LOCAL lock_timeout='150ms'"))
                    with pytest.raises(DBAPIError) as conflict:
                        competitor.execute(text(f'UPDATE "{schema}".patients SET user_id=2 WHERE id=1'))
                    assert conflict.value.orig.sqlstate == "55P03"
                finally:
                    competing.rollback()
            db.rollback()
        with owner.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".patients SET user_id=2 WHERE id=1'))
        with Session(runtime) as db:
            with pytest.raises(VisitConfirmationDomainError) as exc:
                VisitConfirmationService(db)._lock_confirmation_patient("original-token")
            assert exc.value.status_code == 404
        with owner.begin() as conn:
            conn.execute(text(f"UPDATE \"{schema}\".visits SET confirmation_token='original-token' WHERE id=1"))
            conn.execute(text(f'GRANT EXECUTE ON FUNCTION "{private}".lock_confirmation_patient(pg_catalog.int4) TO PUBLIC'))
        with Session(runtime) as db:
            with pytest.raises(VisitConfirmationDomainError) as exc:
                VisitConfirmationService(db)._require_full_subject_visibility()
            assert exc.value.status_code == 503
        with owner.begin() as conn:
            conn.execute(text(f'REVOKE EXECUTE ON FUNCTION "{private}".lock_confirmation_patient(pg_catalog.int4) FROM PUBLIC'))
        with owner.connect() as holder:
            held = holder.begin()
            try:
                holder.execute(text(f'SELECT id FROM "{schema}".patients WHERE id=1 FOR UPDATE'))
                with Session(runtime) as db:
                    with pytest.raises(VisitConfirmationDomainError) as exc:
                        VisitConfirmationService(db)._lock_confirmation_patient("original-token")
                    assert exc.value.status_code == 409
                    assert not db.in_transaction()
            finally:
                held.rollback()
        with Session(runtime) as db:
            assert VisitConfirmationService(db)._lock_confirmation_patient("original-token") == 1
            db.rollback()
        with owner.begin() as conn:
            conn.execute(text(f'ALTER POLICY synthetic_auth_select ON "{schema}".token_blacklist USING (false)'))
        with Session(runtime) as db:
            with pytest.raises(VisitConfirmationDomainError) as exc:
                VisitConfirmationService(db)._require_full_subject_visibility()
            assert exc.value.status_code == 503
        with owner.begin() as conn:
            conn.execute(text(f'ALTER POLICY synthetic_auth_select ON "{schema}".token_blacklist USING (true)'))
            conn.execute(text(f'GRANT UPDATE(id) ON "{schema}".users TO "{cap}"'))
        with Session(runtime) as db:
            with pytest.raises(VisitConfirmationDomainError) as exc:
                VisitConfirmationService(db)._require_full_subject_visibility()
            assert exc.value.status_code == 503
        with owner.begin() as conn:
            conn.execute(text(f'REVOKE UPDATE(id) ON "{schema}".users FROM "{cap}"'))
        with owner.begin() as conn:
            conn.execute(text(f'CREATE POLICY synthetic_restrict ON "{schema}".patients AS RESTRICTIVE FOR SELECT TO "{role}" USING (false)'))
        with Session(runtime) as db:
            with pytest.raises(VisitConfirmationDomainError) as exc:
                VisitConfirmationService(db)._require_full_subject_visibility()
            assert exc.value.status_code == 503
        with owner.begin() as conn:
            conn.execute(text(f'DROP POLICY synthetic_restrict ON "{schema}".patients'))
        with admin.begin() as conn:
            conn.execute(text(f'GRANT CREATE ON SCHEMA "{schema}" TO PUBLIC'))
        with Session(runtime) as db:
            with pytest.raises(VisitConfirmationDomainError) as exc:
                VisitConfirmationService(db)._require_full_subject_visibility()
            assert exc.value.status_code == 503
    finally:
        runtime.dispose()
        owner.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(private, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
            conn.execute(text(f'DROP ROLE "{cap}"'))
        admin.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("owner_first", [True, False])
@pytest.mark.parametrize("channel", ["pwa", "telegram"])
def test_postgres_info_and_owner_change_serialize(owner_first, channel):
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires a fully migrated disposable clinic_test PostgreSQL database")
    engine = create_engine(raw, connect_args={"options": "-clock_timeout=10000"})
    try:
        with engine.begin() as conn:
            if not conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='trg_patient_owner_confirmation_context' AND NOT tgisinternal)")).scalar_one():
                pytest.skip("requires 0116 migrated database")
        token = "synthetic-race-" + uuid.uuid4().hex
        with Session(engine) as setup:
            patient = Patient(first_name="SYNTHETIC", last_name="RACE")
            setup.add(patient)
            setup.flush()
            visit = Visit(patient_id=patient.id, status="pending_confirmation", visit_date=date.today() + timedelta(days=7), visit_time="12:00", confirmation_channel=channel)
            setup.add(visit)
            setup.flush()
            visit.confirmation_token = token
            visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
            link_id = None
            if channel == "telegram":
                setup.flush()
                setup.refresh(visit)
                link = TelegramUser(patient_id=patient.id, chat_id=1_000_000_000_000 + uuid.uuid4().int % 1_000_000_000_000,
                                    active=True, blocked=False, notifications_enabled=True, appointment_reminders=True)
                setup.add(link)
                setup.flush()
                setup.refresh(link)
                token = build_telegram_visit_action_token(
                    visit_id=visit.id, confirmation_token=visit.confirmation_token,
                    link_id=link.id, chat_id=link.chat_id, patient_id=patient.id,
                    link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch,
                    purpose="view",
                )
                link_id = link.id
            setup.commit()
            patient_id, visit_id = patient.id, visit.id

        at_patient_lock = threading.Event()
        proceed = threading.Event()

        @event.listens_for(engine, "before_cursor_execute")
        def pause_before(conn, cursor, statement, parameters, context, executemany):
            if owner_first and threading.current_thread().name.startswith("confirmation-reader") and "FROM patients" in statement and "FOR UPDATE" in statement:
                at_patient_lock.set()
                assert proceed.wait(10)

        @event.listens_for(engine, "after_cursor_execute")
        def pause_after(conn, cursor, statement, parameters, context, executemany):
            if not owner_first and threading.current_thread().name.startswith("confirmation-reader") and "FROM patients" in statement and "FOR UPDATE" in statement:
                at_patient_lock.set()
                assert proceed.wait(10)

        def reader():
            with Session(engine) as db:
                try:
                    result = VisitConfirmationService(db).get_visit_info(token)
                    db.commit()
                    return result["visit_id"]
                except VisitConfirmationDomainError as exc:
                    db.rollback()
                    return exc.status_code

        try:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="confirmation-reader") as pool:
                future = pool.submit(reader)
                assert at_patient_lock.wait(10)
                if owner_first:
                    with engine.begin() as owner:
                        owner.execute(text("UPDATE patients SET is_deleted=true WHERE id=:id"), {"id": patient_id})
                    proceed.set()
                    assert future.result(timeout=10) == 404
                else:
                    owner_started = threading.Event()

                    def change_owner():
                        with engine.begin() as owner:
                            owner_started.set()
                            owner.execute(text("UPDATE patients SET is_deleted=true WHERE id=:id"), {"id": patient_id})

                    with ThreadPoolExecutor(max_workers=1) as updater:
                        update_future = updater.submit(change_owner)
                        assert owner_started.wait(10)
                        proceed.set()
                        assert future.result(timeout=10) == visit_id
                        update_future.result(timeout=10)
        finally:
            proceed.set()
            event.remove(engine, "before_cursor_execute", pause_before)
            event.remove(engine, "after_cursor_execute", pause_after)
            with engine.begin() as cleanup:
                if link_id:
                    cleanup.execute(text("DELETE FROM telegram_users WHERE id=:id"), {"id": link_id})
                cleanup.execute(text("DELETE FROM visits WHERE id=:id"), {"id": visit_id})
                cleanup.execute(text("DELETE FROM patients WHERE id=:id"), {"id": patient_id})
    finally:
        engine.dispose()
