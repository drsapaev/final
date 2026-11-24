"""PostgreSQL interleavings for Telegram patient links and visit actions."""

import asyncio
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from queue import SimpleQueue
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints.telegram_webhook import _handle_ticket_qr_start
from app.api.v1.endpoints.telegram_webhook._helpers import _localized_text
from app.core.config import settings
from app.models import Patient, User, Visit
from app.models.clinic import Doctor
from app.models.encounter import Encounter
from app.models.service import Service
from app.models.telegram_config import PatientOnboardingRequest, TelegramUser
from app.models.visit import VisitService
from app.schemas.patient_onboarding import (
    OnboardingPatientSearchRequest,
    RegistrarPatientLinkDecisionRequest,
)
from app.services.patient_onboarding_service import PatientOnboardingService
from app.services.telegram_patient_link import (
    TelegramPatientLinkConflict,
    link_telegram_patient,
)
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_ticket_start_token,
    build_telegram_visit_action_token,
    consume_telegram_ticket_start_token,
    parse_telegram_ticket_start_token,
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
            versions = Path(__file__).resolve().parents[2] / "alembic/versions"
            operations = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema_name}))
            # The scoped finance trigger also participates in owner invalidation.
            for revision in ("0101_telegram_patient_link_epoch", "0141_confirmation_financial_trigger"):
                migration = _module(versions / f"{revision}.py")
                migration.op = operations
                migration.upgrade()
            conn.exec_driver_sql(f"ALTER TABLE {links} ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"ALTER TABLE {links} FORCE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"GRANT SELECT, UPDATE (id) ON {links} TO {role}")
            conn.exec_driver_sql(
                "GRANT UPDATE (confirmation_token, confirmation_expires_at) "
                f"ON {schema}.visits TO {role}"
            )
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
            visit_id=visit.id,
            confirmation_token=token,
            link_id=link.id,
            chat_id=link.chat_id,
            patient_id=patient.id,
            link_epoch=link.patient_link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch,
        )
        return visit.id, token, link.chat_id, capability


def _assert_postgres_blocks(pg_engine, *, waiter_pid: int, blocker_pid: int) -> None:
    """Observe a real wait on the competing transaction, independent of scheduling."""
    deadline = time.monotonic() + 5
    statement = text("SELECT :blocker = ANY(pg_blocking_pids(:waiter))")
    with pg_engine.connect() as observer:
        while time.monotonic() < deadline:
            if observer.execute(
                statement, {"blocker": blocker_pid, "waiter": waiter_pid}
            ).scalar_one():
                return
            time.sleep(0.05)
    pytest.fail("Telegram linking did not wait for the competing transaction")


@pytest.mark.integration
@pytest.mark.parametrize("shared_row", ["patient", "chat"])
def test_concurrent_patient_links_commit_only_one_association(telegram_pg, shared_row):
    owner, _ = telegram_pg
    with Session(owner) as db:
        patients = [
            Patient(first_name="SYNTHETIC", last_name=f"SYNTHETIC-{uuid.uuid4().hex}")
            for _ in range(2)
        ]
        profiles = [
            TelegramUser(
                chat_id=int(uuid.uuid4().hex[:12], 16),
                active=True,
                blocked=False,
                language_code="uz",
                notifications_enabled=True,
                appointment_reminders=False,
                lab_notifications=True,
            )
            for _ in range(2)
        ]
        db.add_all(patients + profiles)
        db.commit()
        patient_ids = [patient.id for patient in patients]
        profile_ids = [profile.id for profile in profiles]
        chat_ids = [profile.chat_id for profile in profiles]

    winning_patient_id, winning_chat_id = patient_ids[0], chat_ids[0]
    losing_patient_id = patient_ids[0 if shared_row == "patient" else 1]
    losing_profile_id = profile_ids[1 if shared_row == "patient" else 0]
    losing_pid: SimpleQueue[int] = SimpleQueue()

    def competing_link():
        with Session(owner) as db:
            # Keep a stale ORM row alive while the other transaction commits.
            profile = db.get(TelegramUser, losing_profile_id)
            assert profile.patient_id is None
            losing_pid.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            with pytest.raises(TelegramPatientLinkConflict):
                link_telegram_patient(
                    db, patient_id=losing_patient_id, chat_id=profile.chat_id
                )
            db.rollback()

    with Session(owner) as winner, ThreadPoolExecutor(max_workers=1) as executor:
        winner_pid = winner.execute(text("SELECT pg_backend_pid()")).scalar_one()
        link_telegram_patient(
            winner, patient_id=winning_patient_id, chat_id=winning_chat_id
        )
        competitor = executor.submit(competing_link)
        try:
            _assert_postgres_blocks(
                owner, waiter_pid=losing_pid.get(timeout=5), blocker_pid=winner_pid
            )
        finally:
            winner.commit()
        competitor.result(timeout=10)

    with Session(owner) as db:
        (linked,) = (
            db.query(TelegramUser)
            .filter(TelegramUser.patient_id.in_(patient_ids))
            .all()
        )
        assert (linked.chat_id, linked.patient_id) == (
            winning_chat_id,
            winning_patient_id,
        )
        epoch = linked.patient_link_epoch
        link_telegram_patient(
            db, patient_id=winning_patient_id, chat_id=winning_chat_id
        )
        db.commit()
        assert linked.patient_link_epoch == epoch
        assert linked.language_code == "uz"
        assert linked.notifications_enabled is True
        assert linked.appointment_reminders is False
        assert linked.lab_notifications is True


@pytest.mark.integration
def test_ticket_qr_rolls_back_consumption_when_concurrent_registrar_link_wins(
    telegram_pg,
):
    owner, runtime = telegram_pg
    visit_id, _, registrar_chat_id, _ = _seed(owner)
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    ticket = build_telegram_ticket_start_token(expires_at=expires_at)
    token_hash = parse_telegram_ticket_start_token(ticket)["token_hash"]
    qr_chat_id = int(uuid.uuid4().hex[:12], 16)
    candidate_name = f"SYNTHETIC-{uuid.uuid4().hex}"

    with Session(owner) as db:
        visit = db.get(Visit, visit_id)
        patient_id = visit.patient_id
        db.get(Patient, patient_id).last_name = candidate_name
        visit.confirmation_token = token_hash
        visit.confirmation_expires_at = expires_at
        profile = db.query(TelegramUser).filter_by(chat_id=registrar_chat_id).one()
        profile.patient_id = None
        request = PatientOnboardingRequest(
            telegram_user_id=profile.id,
            telegram_chat_id=registrar_chat_id,
            status="pending_review",
        )
        registrar = User(
            username=candidate_name,
            hashed_password="!disabled",
            role="Registrar",
            is_active=True,
        )
        db.add_all([request, registrar, TelegramUser(chat_id=qr_chat_id)])
        db.commit()
        request_id, registrar_id = request.id, registrar.id
        stored_expiry = visit.confirmation_expires_at
        search = PatientOnboardingService(db).search_candidates_for_request(
            request_id=request_id,
            actor=registrar,
            search_payload=OnboardingPatientSearchRequest(name=candidate_name),
        )
        (candidate,) = search["candidates"]
        decision = RegistrarPatientLinkDecisionRequest(
            candidate_id=candidate["candidateId"]
        )

    committing = threading.Event()
    qr_pid: SimpleQueue[int] = SimpleQueue()
    bot = SimpleNamespace(_send_message=AsyncMock())
    update = {
        "message": {
            "text": f"/start {ticket}",
            "chat": {"id": qr_chat_id, "type": "private"},
            "from": {"id": qr_chat_id, "language_code": "ru"},
        }
    }

    def process_qr():
        assert committing.wait(8)
        with Session(runtime) as db:
            qr_pid.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            return asyncio.run(_handle_ticket_qr_start(update, db, bot))

    with Session(owner) as winner, ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(process_qr)
        winner_pid = winner.execute(text("SELECT pg_backend_pid()")).scalar_one()

        def observe_qr_wait(_session):
            committing.set()
            _assert_postgres_blocks(
                owner, waiter_pid=qr_pid.get(timeout=5), blocker_pid=winner_pid
            )

        event.listen(winner, "before_commit", observe_qr_wait, once=True)
        result = PatientOnboardingService(winner).link_existing_patient(
            request_id=request_id,
            payload=decision,
            actor=winner.get(User, registrar_id),
        )
        assert future.result(timeout=10)

    assert result["request"]["status"] == "linked_existing"
    bot._send_message.assert_awaited_once()
    assert bot._send_message.await_args.args[:2] == (
        qr_chat_id,
        _localized_text("ticket_qr_link_failed", "ru"),
    )
    with Session(owner) as db:
        (linked,) = db.query(TelegramUser).filter_by(patient_id=patient_id).all()
        assert linked.chat_id == registrar_chat_id
        assert (
            db.query(TelegramUser).filter_by(chat_id=qr_chat_id).one().patient_id
            is None
        )
        visit = db.get(Visit, visit_id)
        assert (visit.confirmation_token, visit.confirmation_expires_at) == (
            token_hash,
            stored_expiry,
        )


@pytest.mark.integration
def test_ticket_qr_waits_for_patient_before_locking_visit(telegram_pg):
    owner, runtime = telegram_pg
    visit_id, _, _, _ = _seed(owner)
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    ticket = build_telegram_ticket_start_token(expires_at=expires_at)
    token_hash = parse_telegram_ticket_start_token(ticket)["token_hash"]
    with Session(owner) as db:
        visit = db.get(Visit, visit_id)
        patient_id = visit.patient_id
        visit.confirmation_token = token_hash
        visit.confirmation_expires_at = expires_at
        db.commit()

    consumer_pid: SimpleQueue[int] = SimpleQueue()

    def consume_ticket():
        with Session(runtime) as db:
            consumer_pid.put(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            return consume_telegram_ticket_start_token(db, ticket)

    with ThreadPoolExecutor(max_workers=1) as executor:
        with Session(owner) as writer:
            writer.query(Patient.id).filter_by(id=patient_id).with_for_update(
                key_share=True
            ).one()
            writer_pid = writer.execute(text("SELECT pg_backend_pid()")).scalar_one()
            consumer = executor.submit(consume_ticket)
            _assert_postgres_blocks(
                owner,
                waiter_pid=consumer_pid.get(timeout=5),
                blocker_pid=writer_pid,
            )

            # A phone change invalidates invitations while holding the patient lock.
            # The waiting QR consumer must leave the visit available to that writer.
            visit = (
                writer.query(Visit)
                .filter_by(id=visit_id)
                .with_for_update(nowait=True)
                .one()
            )
            visit.confirmation_token = None
            visit.confirmation_expires_at = None
            writer.commit()
        assert consumer.result(timeout=10) is None


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
                    token=capability,
                    telegram_user_id=str(chat_id),
                    source_ip=None,
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
                        visit.confirmation_expires_at = datetime.now(UTC) - timedelta(
                            seconds=1
                        )
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
                    token=capability,
                    telegram_user_id=str(chat_id),
                    source_ip=None,
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
            visit_id=visit_id,
            confirmation_token=raw_token,
            link_id=link.id,
            chat_id=chat_id,
            patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch,
            purpose="view",
        )
        preview = VisitConfirmationService(db).preview_by_telegram(
            token=view, telegram_user_id=str(chat_id)
        )
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
        assert (
            visit.status == "pending_confirmation" and visit.confirmation_token is None
        )

    visit_id, raw_token, chat_id, _ = _seed(owner)
    with Session(runtime) as db:
        visit = db.get(Visit, visit_id)
        link = db.query(TelegramUser).filter_by(chat_id=chat_id).one()
        view = build_telegram_visit_action_token(
            visit_id=visit_id,
            confirmation_token=raw_token,
            link_id=link.id,
            chat_id=chat_id,
            patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch,
            visit_context_epoch=visit.confirmation_context_epoch,
            purpose="view",
        )
        preview = VisitConfirmationService(db).preview_by_telegram(
            token=view, telegram_user_id=str(chat_id)
        )
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
