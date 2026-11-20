"""PostgreSQL interleavings for authenticated patient visit actions."""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models import Patient, User, Visit
from app.models.clinic import Doctor
from app.models.encounter import Encounter
from app.models.service import Service
from app.models.telegram_config import TelegramUser
from app.models.visit import VisitService
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_visit_action_token,
)
from tests.integration.test_staff_confirmation_guard_pg import (
    _module,
    isolated_staff_guard_postgres,
)


@pytest.fixture(scope="module")
def telegram_pg():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("PostgreSQL required for row-lock interleavings")
    ci_service = (
        os.environ.get("CI", "").lower() == "true"
        and url.database == "clinicdb"
        and url.host in {"localhost", "127.0.0.1", "::1"}
    )
    if not ci_service and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test database")
    with pytest.MonkeyPatch.context() as patch, isolated_staff_guard_postgres(url, patch) as (owner, runtime, _):
        patch.setattr(settings, "FRONTEND_URL", "https://clinic.example.test")
        with owner.begin() as conn:
            quote = conn.dialect.identifier_preparer.quote
            schema_name = conn.dialect.default_schema_name
            schema, role = quote(schema_name), quote(runtime.url.username)
            links = f"{schema}.telegram_users"
            # The metadata fixture already has this column. Install the
            # actual migration and epoch trigger before any Telegram seed.
            conn.exec_driver_sql(f"ALTER TABLE {links} DROP COLUMN patient_link_epoch")
            path = Path(__file__).resolve().parents[2] / "alembic/versions/0101_telegram_patient_link_epoch.py"
            migration = _module(path)
            migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema_name}))
            migration.upgrade()
            conn.exec_driver_sql(f"ALTER TABLE {links} ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"ALTER TABLE {links} FORCE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"GRANT SELECT, UPDATE (id) ON {links} TO {role}")
            conn.exec_driver_sql(f"CREATE POLICY synthetic_telegram_read ON {links} FOR SELECT TO {role} USING (true)")
            conn.exec_driver_sql(
                f"CREATE POLICY synthetic_telegram_lock ON {links} FOR UPDATE TO {role} USING (true) WITH CHECK (false)"
            )
        yield owner, runtime


def _seed(engine):
    suffix = uuid.uuid4().hex[:12]
    with Session(engine) as db:
        patient = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC")
        user = User(username=f"SYNTHETIC-{suffix}", hashed_password="!disabled",
                    role="Doctor", is_active=True)
        service = Service(code=f"TGS{suffix}", name="Synthetic consultation", price=Decimal("10.00"))
        db.add_all([patient, user, service])
        db.flush()
        doctor = Doctor(user_id=user.id, specialty="Cardiology", active=True)
        encounter = Encounter(patient_id=patient.id, provenance="new")
        db.add_all([doctor, encounter])
        db.flush()
        token = f"SYNTHETIC-token-{suffix}"
        visit = Visit(
            patient_id=patient.id, doctor_id=doctor.id, encounter_id=encounter.id,
            visit_date=date.today() + timedelta(days=3), visit_time="10:00",
            status="pending_confirmation", source="desk", discount_mode="none", confirmation_channel="telegram",
        )
        link = TelegramUser(patient_id=patient.id, chat_id=int(uuid.uuid4().hex[:12], 16),
                            active=True, blocked=False, notifications_enabled=True, appointment_reminders=True)
        db.add_all([visit, link])
        db.flush()
        db.add(VisitService(visit_id=visit.id, service_id=service.id, name=service.name,
                            qty=1, price=service.price, currency="UZS"))
        db.flush()
        db.refresh(visit)
        visit.confirmation_token = token
        visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()
        assert visit.confirmation_context_epoch > 0 and link.patient_link_epoch > 0
        capability = build_telegram_visit_action_token(
            visit_id=visit.id, confirmation_token=token, link_id=link.id,
            chat_id=link.chat_id, patient_id=patient.id, link_epoch=link.patient_link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch,
        )
        return visit.id, token, link.chat_id, capability


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["confirm", "cancel"])
@pytest.mark.parametrize("mutation", ["token", "expiry", "channel", "status", "revoked"])
def test_mutation_after_precheck_cannot_authorize_stale_invitation(telegram_pg, operation, mutation):
    """Pause after the optimistic check, commit a real concurrent mutation,
    then prove the locked update rechecks all relevant state.
    """
    owner, runtime = telegram_pg
    visit_id, _, chat_id, capability = _seed(owner)
    runtime_sessions = sessionmaker(bind=runtime, autoflush=False)
    checked = threading.Event()
    proceed = threading.Event()

    def request_action():
        with runtime_sessions() as session:
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
            with Session(owner) as session:
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
                row = session.get(Visit, visit_id)
                writer_state = (row.status, row.confirmation_token, row.confirmation_context_epoch)
        finally:
            proceed.set()
        assert future.result(timeout=10) in (400, 403, 404, 409)

    with Session(owner) as session:
        visit = session.get(Visit, visit_id)
        assert visit.status == ("open" if mutation == "status" else "pending_confirmation")
        assert (visit.status, visit.confirmation_token, visit.confirmation_context_epoch) == writer_state


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["confirm", "cancel"])
def test_action_rejects_a_competing_visit_lock_and_rechecks_status(telegram_pg, operation):
    owner, runtime = telegram_pg
    visit_id, _, chat_id, capability = _seed(owner)
    runtime_sessions = sessionmaker(bind=runtime, autoflush=False)
    checked = threading.Event()

    def request_action(*, observe=False):
        with runtime_sessions() as session:
            service = VisitConfirmationService(session)
            validate = service.security_service.validate_confirmation_request

            def observed_validate(**kwargs):
                result = validate(**kwargs)
                assert result.allowed
                checked.set()
                return result

            if observe:
                service.security_service.validate_confirmation_request = observed_validate
            try:
                getattr(service, f"{operation}_by_telegram")(
                    token=capability, telegram_user_id=str(chat_id), source_ip=None,
                    user_agent="telegram",
                )
            except VisitConfirmationDomainError as exc:
                return exc.status_code
            return 200

    with Session(owner) as writer:
        locked = writer.query(Visit).filter_by(id=visit_id).with_for_update().one()
        locked.status = "open"
        writer.flush()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(request_action, observe=True)
            assert checked.wait(8)
            try:
                assert future.result(timeout=6) == 409
            finally:
                writer.commit()
    assert request_action() in (400, 403, 404, 409)
    with Session(owner) as session:
        visit = session.get(Visit, visit_id)
        assert visit.status == "open"
        assert visit.confirmation_token is None


@pytest.mark.integration
def test_migrated_context_change_invalidates_previously_viewed_action(telegram_pg):
    """The installed context triggers invalidate a changed date or service list."""
    owner, runtime = telegram_pg
    visit_id, raw_token, chat_id, _ = _seed(owner)
    with Session(runtime) as db:
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
    with owner.begin() as conn:
        conn.execute(text("UPDATE visits SET visit_date = :changed WHERE id = :id"),
                     {"changed": original_date + timedelta(days=1), "id": visit_id})
        conn.execute(text("UPDATE visits SET visit_date = :original WHERE id = :id"),
                     {"original": original_date, "id": visit_id})
    with Session(runtime) as db:
        with pytest.raises(VisitConfirmationDomainError) as refused:
            VisitConfirmationService(db).cancel_by_telegram(
                token=preview["action_token"], telegram_user_id=str(chat_id), source_ip=None, user_agent="telegram")
        assert refused.value.status_code in (400, 403, 404, 409)
    with Session(owner) as db:
        visit = db.get(Visit, visit_id)
        assert visit.status == "pending_confirmation" and visit.confirmation_token is None

    visit_id, raw_token, chat_id, _ = _seed(owner)
    with Session(runtime) as db:
        visit = db.get(Visit, visit_id)
        link = db.query(TelegramUser).filter_by(chat_id=chat_id).one()
        view = build_telegram_visit_action_token(
            visit_id=visit_id, confirmation_token=raw_token, link_id=link.id,
            chat_id=chat_id, patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch, purpose="view",
        )
        preview = VisitConfirmationService(db).preview_by_telegram(token=view, telegram_user_id=str(chat_id))
        db.rollback()
    with owner.begin() as conn:
        conn.execute(text("""
            INSERT INTO visit_services (visit_id, service_id, name, qty, price, currency, created_at)
            SELECT visit_id, service_id, 'SYNTHETIC added line', 1, 10.00, 'UZS', now()
            FROM visit_services WHERE visit_id=:id
        """), {"id": visit_id})
    with Session(runtime) as db:
        with pytest.raises(VisitConfirmationDomainError) as refused:
            VisitConfirmationService(db).confirm_by_telegram(
                token=preview["action_token"], telegram_user_id=str(chat_id), source_ip=None, user_agent="telegram")
        assert refused.value.status_code in (400, 403, 404, 409)
    with Session(owner) as db:
        assert db.get(Visit, visit_id).confirmation_token is None
