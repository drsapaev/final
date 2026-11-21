"""PostgreSQL interleavings for authenticated patient visit actions."""

import importlib.util
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models import Patient, User, Visit  # noqa: F401 - model registration
from app.models.clinic import Doctor
from app.models.telegram_config import TelegramUser
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_visit_action_token,
)


@pytest.fixture(scope="module")
def pg_engine():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("PostgreSQL required for row-lock interleavings")
    if os.environ.get("CI", "").lower() != "true" and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test database")
    schema = "test_tg_visit_" + uuid.uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, pool_pre_ping=True, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=10000 -clock_timeout=8000"
    })
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _seed(engine):
    suffix = uuid.uuid4().hex[:12]
    with Session(engine) as db:
        patient = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC")
        user = User(username=f"SYNTHETIC-{suffix}", hashed_password="!disabled",
                    role="Doctor", is_active=True)
        db.add_all([patient, user])
        db.flush()
        doctor = Doctor(user_id=user.id, specialty="Cardiology", active=True)
        db.add(doctor)
        db.flush()
        token = f"SYNTHETIC-token-{suffix}"
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=date.today() + timedelta(days=3), visit_time="10:00",
                      status="pending_confirmation", confirmation_token=token,
                      confirmation_channel="telegram",
                      confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
        link = TelegramUser(patient_id=patient.id, chat_id=int(uuid.uuid4().hex[:12], 16),
                            active=True, blocked=False)
        db.add_all([visit, link])
        db.commit()
        capability = build_telegram_visit_action_token(
            visit_id=visit.id, confirmation_token=token, link_id=link.id,
            chat_id=link.chat_id, patient_id=patient.id, link_epoch=link.patient_link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch,
        )
        return visit.id, token, link.chat_id, capability


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["confirm", "cancel"])
@pytest.mark.parametrize("mutation", ["token", "expiry", "channel", "status", "revoked"])
def test_mutation_after_precheck_cannot_authorize_stale_invitation(pg_engine, operation, mutation):
    """Pause after the optimistic check, commit a real concurrent mutation,
    then prove the locked update rechecks all relevant state.
    """
    visit_id, token, chat_id, capability = _seed(pg_engine)
    SessionLocal = sessionmaker(bind=pg_engine, autoflush=False)
    checked = threading.Event()
    proceed = threading.Event()

    def request_action():
        with SessionLocal() as session:
            service = VisitConfirmationService(session)
            validate = service.security_service.validate_confirmation_request

            def paused_validate(**kwargs):
                result = validate(**kwargs)
                assert result.allowed
                checked.set()
                assert proceed.wait(8)
                return result

            service.security_service.validate_confirmation_request = paused_validate
            try:
                getattr(service, f"{operation}_by_telegram")(
                    token=capability, telegram_user_id=str(chat_id), source_ip=None,
                    user_agent="telegram",
                )
            except VisitConfirmationDomainError as exc:
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(request_action)
        assert checked.wait(8)
        try:
            with SessionLocal() as session:
                if mutation == "revoked":
                    link = session.query(TelegramUser).filter_by(chat_id=chat_id).one()
                    link.active = False
                else:
                    visit = session.get(Visit, visit_id)
                    if mutation == "token":
                        visit.confirmation_token = "SYNTHETIC-replaced-token"
                    elif mutation == "expiry":
                        visit.confirmation_expires_at = datetime.now(UTC) - timedelta(seconds=1)
                    elif mutation == "channel":
                        visit.confirmation_channel = "pwa"
                    else:
                        visit.status = "open"
                session.commit()
        finally:
            proceed.set()
        assert future.result(timeout=10) in (400, 403, 404, 409)

    with SessionLocal() as session:
        visit = session.get(Visit, visit_id)
        assert visit.status == ("open" if mutation == "status" else "pending_confirmation")
        if mutation == "token":
            assert visit.confirmation_token == "SYNTHETIC-replaced-token"
        else:
            assert visit.confirmation_token == token


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["confirm", "cancel"])
def test_action_waits_for_competing_visit_lock_and_rechecks_status(pg_engine, operation):
    visit_id, token, chat_id, capability = _seed(pg_engine)
    SessionLocal = sessionmaker(bind=pg_engine, autoflush=False)
    checked = threading.Event()
    request_pid = []

    def request_action():
        with SessionLocal() as session:
            request_pid.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            service = VisitConfirmationService(session)
            validate = service.security_service.validate_confirmation_request

            def observed_validate(**kwargs):
                result = validate(**kwargs)
                assert result.allowed
                checked.set()
                return result

            service.security_service.validate_confirmation_request = observed_validate
            try:
                getattr(service, f"{operation}_by_telegram")(
                    token=capability, telegram_user_id=str(chat_id), source_ip=None,
                    user_agent="telegram",
                )
            except VisitConfirmationDomainError as exc:
                return exc.status_code
            return 200

    with SessionLocal() as writer:
        locked = writer.query(Visit).filter_by(id=visit_id).with_for_update().one()
        locked.status = "open"
        writer.flush()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(request_action)
            assert checked.wait(8)
            try:
                # Check an actual PostgreSQL lock wait; timing alone cannot
                # establish that the second action observed the locked row.
                deadline = time.monotonic() + 8
                waiting = False
                with pg_engine.connect() as observer:
                    while time.monotonic() < deadline:
                        waiting = observer.execute(
                            text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :pid"),
                            {"pid": request_pid[0]},
                        ).scalar() is True
                        if waiting:
                            break
                        time.sleep(0.05)
                assert waiting, "patient action did not wait on competing transaction"
            finally:
                writer.commit()
            assert future.result(timeout=10) in (400, 403, 404, 409)
    with SessionLocal() as session:
        visit = session.get(Visit, visit_id)
        assert visit.status == "open"
        assert visit.confirmation_token == token


@pytest.mark.integration
def test_migrated_context_change_invalidates_previously_viewed_action(pg_engine):
    """Use the actual 0102 trigger, then change date and restore it via bulk SQL."""
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0102_visit_confirmation_context.py"
    spec = importlib.util.spec_from_file_location("test_visit_context_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with pg_engine.begin() as conn:
        conn.execute(text("ALTER TABLE visits DROP COLUMN confirmation_context_epoch"))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
    visit_id, raw_token, chat_id, _ = _seed(pg_engine)
    with Session(pg_engine) as db:
        visit = db.get(Visit, visit_id)
        link = db.query(TelegramUser).filter_by(chat_id=chat_id).one()
        view = build_telegram_visit_action_token(
            visit_id=visit_id, confirmation_token=raw_token, link_id=link.id,
            chat_id=chat_id, patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch, purpose="view",
        )
        preview = VisitConfirmationService(db).preview_by_telegram(token=view, telegram_user_id=str(chat_id))
        original_date = visit.visit_date
        db.rollback()
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE visits SET visit_date = :changed WHERE id = :id"),
                     {"changed": original_date + timedelta(days=1), "id": visit_id})
        conn.execute(text("UPDATE visits SET visit_date = :original WHERE id = :id"),
                     {"original": original_date, "id": visit_id})
    with Session(pg_engine) as db:
        with pytest.raises(VisitConfirmationDomainError):
            VisitConfirmationService(db).cancel_by_telegram(
                token=preview["action_token"], telegram_user_id=str(chat_id), source_ip=None, user_agent="telegram")
        visit = db.get(Visit, visit_id)
        assert visit.status == "pending_confirmation" and visit.confirmation_token is None

    visit_id, raw_token, chat_id, _ = _seed(pg_engine)
    with Session(pg_engine) as db:
        visit = db.get(Visit, visit_id)
        link = db.query(TelegramUser).filter_by(chat_id=chat_id).one()
        view = build_telegram_visit_action_token(
            visit_id=visit_id, confirmation_token=raw_token, link_id=link.id,
            chat_id=chat_id, patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch, purpose="view",
        )
        preview = VisitConfirmationService(db).preview_by_telegram(token=view, telegram_user_id=str(chat_id))
        db.rollback()
    with pg_engine.begin() as conn:
        conn.execute(text("INSERT INTO visit_services (visit_id, service_id, name, qty, created_at) VALUES (:id, 1, 'SYNTHETIC', 1, now())"), {"id": visit_id})
    with Session(pg_engine) as db:
        with pytest.raises(VisitConfirmationDomainError):
            VisitConfirmationService(db).confirm_by_telegram(
                token=preview["action_token"], telegram_user_id=str(chat_id), source_ip=None, user_agent="telegram")
        assert db.get(Visit, visit_id).confirmation_token is None
