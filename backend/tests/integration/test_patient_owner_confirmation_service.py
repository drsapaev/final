"""Confirmation reads must serialize with changes to the patient owner."""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from queue import SimpleQueue

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.service import Service
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
from tests.integration.test_telegram_visit_concurrency_pg import (
    _assert_postgres_blocks,
    telegram_pg as telegram_pg,
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
def test_postgres_info_and_owner_change_serialize(telegram_pg, owner_first, channel):
    owner, runtime = telegram_pg
    suffix = uuid.uuid4().hex
    token = f"synthetic-race-{suffix}"
    with Session(owner) as setup:
        patient = Patient(first_name="SYNTHETIC", last_name="RACE")
        service = Service(
            code=f"RACE{suffix[:16]}", name="Synthetic consultation", price=Decimal("10.00")
        )
        setup.add_all([patient, service])
        setup.flush()
        encounter = Encounter(patient_id=patient.id, provenance="new")
        setup.add(encounter)
        setup.flush()
        visit = Visit(
            patient_id=patient.id,
            encounter_id=encounter.id,
            visit_date=date.today() + timedelta(days=7),
            visit_time="12:00",
            status="pending_confirmation",
            confirmation_channel=channel,
            discount_mode="none",
            source="desk",
        )
        setup.add(visit)
        setup.flush()
        setup.add(
            VisitService(
                visit_id=visit.id, service_id=service.id, name=service.name,
                qty=1, price=service.price, currency="UZS",
            )
        )
        setup.flush()
        setup.refresh(visit)
        visit.confirmation_token = token
        visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
        if channel == "telegram":
            link = TelegramUser(
                patient_id=patient.id,
                chat_id=1_000_000_000_000 + uuid.uuid4().int % 1_000_000_000_000,
                active=True, blocked=False, notifications_enabled=True, appointment_reminders=True,
            )
            setup.add(link)
            setup.flush()
            setup.refresh(link)
            token = build_telegram_visit_action_token(
                visit_id=visit.id,
                confirmation_token=visit.confirmation_token,
                link_id=link.id,
                chat_id=link.chat_id,
                patient_id=patient.id,
                link_epoch=link.patient_link_epoch,
                visit_context_epoch=visit.confirmation_context_epoch,
                purpose="view",
            )
        patient_id, visit_id = patient.id, visit.id
        setup.commit()

    at_patient_lock = threading.Event()
    proceed = threading.Event()
    reader_pid: SimpleQueue[int] = SimpleQueue()
    writer_pid: SimpleQueue[int] = SimpleQueue()
    hook = "before_cursor_execute" if owner_first else "after_cursor_execute"

    def pause_at_patient_lock(_conn, _cursor, statement, _parameters, _context, _executemany):
        if ".lock_confirmation_patient(" in statement:
            at_patient_lock.set()
            assert proceed.wait(8)

    def reader():
        with Session(runtime) as db:
            reader_pid.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                result = VisitConfirmationService(db).get_visit_info(token)
                db.commit()
                return result["visit_id"]
            except VisitConfirmationDomainError as exc:
                db.rollback()
                return exc.status_code

    def change_owner():
        with owner.begin() as conn:
            writer_pid.put(conn.scalar(text("SELECT pg_backend_pid()")))
            conn.execute(text("UPDATE patients SET is_deleted=true WHERE id=:id"), {"id": patient_id})

    event.listen(runtime, hook, pause_at_patient_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            read_result = pool.submit(reader)
            try:
                assert at_patient_lock.wait(5)
                if owner_first:
                    change_owner()
                else:
                    change_result = pool.submit(change_owner)
                    _assert_postgres_blocks(
                        owner, waiter_pid=writer_pid.get(timeout=5), blocker_pid=reader_pid.get(timeout=5)
                    )
            finally:
                proceed.set()
            assert read_result.result(timeout=10) == (404 if owner_first else visit_id)
            if not owner_first:
                change_result.result(timeout=10)
    finally:
        event.remove(runtime, hook, pause_at_patient_lock)
