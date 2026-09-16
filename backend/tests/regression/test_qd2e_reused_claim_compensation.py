"""Regression tests for the QD-2E review P1 (external report on 2c5ea05ce):
a previously COMMITTED QR ticket must survive the wizard cart's
compensating cleanup when a LATER direction of the same cart fails.

The defect (reproduced in isolation by the review): the reuse branch of
``prepare_wizard_queue_assignment`` binds a pre-existing committed ticket
to the visit being registered (``existing_entry.visit_id = visit.id``).
When the NEXT direction of the same cart then fails with a non-SQL error
AFTER a flush (e.g. the flush inside ``get_or_create_daily_queue`` /
entry allocation), the generic compensation branch ran
``_cleanup_visit_queue_entries``, which DELETED every entry with
``visit_id == visit.id`` — including the pre-existing ticket it had just
bound. The cart endpoint then committed the transaction: the committed
ticket №7 was gone. That is a loss of previously saved data, not a
rollback of the basket's own writes.

Fix contract (provenance-aware compensation):
    - entries CREATED by the basket are still deleted (the P2-1c
      contract: no partial queue assignment survives);
    - a REUSED pre-existing entry is RESTORED to its pre-binding links
      (patient_id/visit_id) — the id, number, queue_time, status and the
      rest of the original ticket were never touched and stay intact.

Run:
    pytest backend/tests/regression/test_qd2e_reused_claim_compensation.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_qd2e_reused_claim.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-qd2e-reused-claim-32ch")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")

from app.db.base_class import Base  # noqa: E402
from app.models import (  # noqa: F401  # noqa: F401
    appointment,
    audit,
    authentication,
    billing,
    clinic,
    department,
    emr,
    emr_v2,
    file_system,
    lab,
    online_queue,
    patient,
    payment,
    payment_invoice,
    payment_webhook,
    role_permission,
    schedule,
    user,
    user_profile,
    visit,
)
from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit, VisitService  # noqa: E402
from app.services.registrar_wizard_queue_assignment_service import (  # noqa: E402
    RegistrarWizardQueueAssignmentService,
)

_DAY = date.today()
_PRESERVED_QUEUE_TIME = datetime(2026, 9, 16, 9, 30, 0)


@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_qd2e_reused_claim.db"
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def session_factory(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _create():
        return Session()

    return _create


@pytest.fixture
def clean_db(db_engine):
    with db_engine.connect() as conn:
        for table in [
            "queue_entries", "visit_services", "visits",
            "daily_queues", "services", "doctors", "patients", "users",
        ]:
            conn.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
        conn.commit()


def _prepare_world(setup: object) -> dict:
    """The committed pre-cart world: a patient, the owning doctor, two
    services on two tags (a < b in sorted order), the doctor's queues for
    both tags — and NO visit yet (the cart creates it)."""
    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"doctor_{unique}", full_name="Dr", email=f"d_{unique}@t.local",
        hashed_password="x", role="Doctor", is_active=True, is_superuser=False,
        must_change_password=False, created_at=datetime.now(UTC),
    )
    setup.add(doctor_user)
    setup.flush()
    doctor = Doctor(user_id=doctor_user.id, specialty="General", active=True)
    setup.add(doctor)
    setup.flush()
    patient = Patient(
        last_name="Тестов", first_name="Пациент", birth_date=date(1990, 1, 1),
        sex="M", phone="+998900000000", email=f"p_{unique}@t.local",
        created_at=datetime.now(UTC), is_deleted=False,
    )
    setup.add(patient)
    setup.flush()

    tags = {}
    for label in ("a", "b"):
        tag = f"tag_{label}_{unique}"
        tags[label] = tag
        setup.add(Service(
            code=f"SVC_{label}_{unique}", name=f"Service {label}", price=10000,
            duration_minutes=30, active=True, requires_doctor=True,
            queue_tag=tag, is_consultation=True,
            allow_doctor_price_override=False,
        ))
        setup.add(DailyQueue(
            day=_DAY, specialist_id=doctor.id, queue_tag=tag, active=True,
        ))
    setup.flush()
    setup.commit()
    return {
        "doctor_id": doctor.id,
        "patient_id": patient.id,
        "patient_name": "Тестов Пациент",
        "phone": "+998900000000",
        "tag_a": tags["a"],
        "tag_b": tags["b"],
        "service_codes": [f"SVC_{label}_{unique}" for label in ("a", "b")],
    }


def _create_committed_ticket(session, world: dict, *, number: int = 7):
    """The review's ticket №7: COMMITTED, bound to the patient, still
    visit-less — exactly the pre-existing QR claim the first direction
    of the cart reuses."""
    queue = (
        session.query(DailyQueue)
        .filter(
            DailyQueue.day == _DAY,
            DailyQueue.queue_tag == world["tag_a"],
            DailyQueue.active.is_(True),
        )
        .one()
    )
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        patient_id=world["patient_id"],
        patient_name=world["patient_name"],
        phone=world["phone"],
        visit_id=None,
        number=number,
        status="waiting",
        source="online",
        queue_time=_PRESERVED_QUEUE_TIME,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry.id, number


def _create_cart_visit(session, world: dict) -> Visit:
    """The cart's single transaction: a confirmed same-day visit with the
    two directions (tag_a service + tag_b service), flushed but NOT
    committed — mirroring ``/registrar/cart`` (create_visit(commit=False)
    → assign_same_day_queue_numbers → db.commit())."""
    visit = Visit(
        patient_id=world["patient_id"], doctor_id=world["doctor_id"],
        status="confirmed", visit_date=_DAY, visit_time="10:00",
        discount_mode="none", department="general",
        confirmation_token=f"tok-{uuid.uuid4().hex[:8]}",
        confirmation_channel="desk", confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()
    for code in world["service_codes"]:
        service = session.query(Service).filter(Service.code == code).one()
        session.add(VisitService(
            visit_id=visit.id, service_id=service.id, code=service.code,
            name=service.name, qty=1, price=service.price, currency="UZS",
        ))
    session.flush()
    return visit


def _make_failing_basket(
    session, world: dict, *, fail_tag: str
):
    """The basket with the review's injected failure: processing of the
    SECOND direction performs a flush (persisting the first direction's
    binding of the pre-existing ticket) and then raises a non-SQL error
    leaving the session usable — the exact compensating-branch path."""
    from app.services.morning_assignment import MorningAssignmentService

    real_morning_service = MorningAssignmentService(session)
    service = RegistrarWizardQueueAssignmentService(
        session,
        assignment_service_factory=lambda db: real_morning_service,
    )
    original_materialize = service._materialize_prepared_assignment

    def patched_materialize(prepared_assignment):
        if (
            prepared_assignment is not None
            and prepared_assignment.create_handoff is not None
            and fail_tag in prepared_assignment.create_handoff.queue_tag
        ):
            # the review's flush: this persists the binding written by the
            # FIRST (reuse) direction before the failure strikes
            session.flush()
            raise RuntimeError(f"INJECTED non-SQL failure for {fail_tag}")
        return original_materialize(prepared_assignment)

    service._materialize_prepared_assignment = patched_materialize
    return service


def _make_failing_basket_before_flush(session, world: dict, *, fail_tag: str):
    """The c48081f03 review P2 arm: the SECOND direction fails BEFORE any
    flush follows the first direction's binding. The штатная SessionLocal
    runs ``autoflush=False`` (app/db/session.py), so the reused ticket's
    new ``visit_id`` is still IN MEMORY ONLY — the DB row keeps its
    committed NULL, and a cleanup query BY visit_id cannot find the
    entry no matter how it is filtered."""
    from app.services.morning_assignment import MorningAssignmentService

    real_morning_service = MorningAssignmentService(session)
    service = RegistrarWizardQueueAssignmentService(
        session,
        assignment_service_factory=lambda db: real_morning_service,
    )
    original_materialize = service._materialize_prepared_assignment

    def patched_materialize(prepared_assignment):
        if (
            prepared_assignment is not None
            and prepared_assignment.create_handoff is not None
            and fail_tag in prepared_assignment.create_handoff.queue_tag
        ):
            # deliberately NO flush: the binding stays in the session's
            # dirty set, never persisted before the failure
            raise RuntimeError(f"INJECTED pre-flush failure for {fail_tag}")
        return original_materialize(prepared_assignment)

    service._materialize_prepared_assignment = patched_materialize
    return service


@pytest.mark.unit
class TestQD2EReusedClaimCompensation:
    """QD-2E review P1 (2c5ea05ce): provenance-aware compensation."""

    def test_committed_ticket_survives_failure_of_next_direction(
        self, session_factory, clean_db
    ):
        """REGRESSION (the review's exact scenario): a committed QR ticket
        (patient-bound, visit-less) is reused by the first direction;
        the second direction flushes and fails with a non-SQL error; the
        cart commits. The ticket must survive with its original id,
        number, queue_time, status and RESTORED links (visit_id=None)."""
        setup = session_factory()
        world = _prepare_world(setup)
        entry_id, number = _create_committed_ticket(setup, world, number=7)
        setup.close()

        # the cart transaction
        cart = session_factory()
        visit = _create_cart_visit(cart, world)
        visit_id = visit.id
        basket = _make_failing_basket(cart, world, fail_tag=world["tag_b"])

        queue_numbers = basket.assign_same_day_queue_numbers(
            [visit], target_day=_DAY, source="desk"
        )
        # the cart endpoint commits the transaction regardless
        cart.commit()

        # no assignment survived for the failed visit (partial assignment
        # is unsupported) and the visit was NOT activated
        assert queue_numbers == {}
        cart.close()

        proof = session_factory()
        row = proof.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).one()
        assert row.id == entry_id
        assert row.number == number
        assert row.queue_time == _PRESERVED_QUEUE_TIME
        assert row.status == "waiting"
        assert row.source == "online"
        # the RESTORED pre-binding links
        assert row.patient_id == world["patient_id"]
        assert row.visit_id is None
        committed_visit = proof.query(Visit).filter(Visit.id == visit_id).one()
        assert committed_visit.status == "confirmed"
        # not a single basket-created queue entry survived
        assert (
            proof.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.visit_id == visit_id)
            .count()
            == 0
        )
        proof.close()

    def test_control_without_failure_binds_and_preserves_the_ticket(
        self, session_factory, clean_db
    ):
        """CONTROL (the review's positive arm): the same reuse without any
        failure — the ticket is linked to the visit (patient_id already
        bound, visit_id set), number and queue_time untouched."""
        setup = session_factory()
        world = _prepare_world(setup)
        entry_id, number = _create_committed_ticket(setup, world, number=7)
        setup.close()

        cart = session_factory()
        visit = _create_cart_visit(cart, world)
        visit_id = visit.id
        basket = RegistrarWizardQueueAssignmentService(cart)

        queue_numbers = basket.assign_same_day_queue_numbers(
            [visit], target_day=_DAY, source="desk"
        )
        cart.commit()

        assert queue_numbers != {}
        cart.close()

        proof = session_factory()
        row = proof.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).one()
        assert row.number == number
        assert row.queue_time == _PRESERVED_QUEUE_TIME
        assert row.patient_id == world["patient_id"]
        assert row.visit_id == visit_id
        committed_visit = proof.query(Visit).filter(Visit.id == visit_id).one()
        assert committed_visit.status == "open"
        proof.close()

    def test_basket_created_entries_are_still_deleted_on_failure(
        self, session_factory, clean_db
    ):
        """The P2-1c contract survives the provenance fix: entries CREATED
        by the basket (no pre-existing ticket) are still deleted when a
        later direction fails — nothing partial is committed."""
        setup = session_factory()
        world = _prepare_world(setup)
        setup.close()  # NO committed ticket this time

        cart = session_factory()
        visit = _create_cart_visit(cart, world)
        visit_id = visit.id
        basket = _make_failing_basket(cart, world, fail_tag=world["tag_b"])

        queue_numbers = basket.assign_same_day_queue_numbers(
            [visit], target_day=_DAY, source="desk"
        )
        cart.commit()

        assert queue_numbers == {}
        cart.close()

        proof = session_factory()
        assert (
            proof.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.visit_id == visit_id)
            .count()
            == 0
        )
        # and no orphaned entry for the patient on the failed day at all
        assert (
            proof.query(OnlineQueueEntry)
            .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
            .filter(
                OnlineQueueEntry.patient_id == world["patient_id"],
                DailyQueue.day == _DAY,
            )
            .count()
            == 0
        )
        proof.close()

    def test_committed_ticket_survives_pre_flush_failure_of_next_direction(
        self, session_factory, clean_db
    ):
        """REGRESSION (the c48081f03 review P2, the before-flush arm): the
        first direction reuses the committed ticket №7 and binds it IN
        MEMORY (autoflush=False); the second direction fails BEFORE any
        flush. The old cleanup queried BY visit_id — the DB still holds
        visit_id NULL for the old ticket, the query returned NOTHING and
        the ledger restore was never applied; the outer commit() then
        PERSISTED the binding (the review measured visit_id=501 after
        commit, cleanup found 0 rows). The basket returned assignments=[]
        while the visit kept the ticket — and the NEXT registration of
        the patient would hit the "already bound to another visit"
        guard.

        The restore must key off the LEDGER (by entry id), not off the
        visit_id query result."""
        setup = session_factory()
        world = _prepare_world(setup)
        entry_id, number = _create_committed_ticket(setup, world, number=7)
        setup.close()

        # the cart transaction
        cart = session_factory()
        visit = _create_cart_visit(cart, world)
        visit_id = visit.id
        basket = _make_failing_basket_before_flush(
            cart, world, fail_tag=world["tag_b"]
        )

        queue_numbers = basket.assign_same_day_queue_numbers(
            [visit], target_day=_DAY, source="desk"
        )
        # the cart endpoint commits the transaction regardless
        cart.commit()

        assert queue_numbers == {}
        cart.close()

        proof = session_factory()
        row = proof.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).one()
        assert row.id == entry_id
        assert row.number == number
        assert row.queue_time == _PRESERVED_QUEUE_TIME
        assert row.status == "waiting"
        assert row.source == "online"
        # the RESTORED pre-binding links — the in-memory binding must NOT
        # survive the outer commit (the review's failing arm kept 501)
        assert row.patient_id == world["patient_id"]
        assert row.visit_id is None
        committed_visit = proof.query(Visit).filter(Visit.id == visit_id).one()
        assert committed_visit.status == "confirmed"
        # not a single basket-created queue entry survived
        assert (
            proof.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.visit_id == visit_id)
            .count()
            == 0
        )
        proof.close()

    def test_pending_created_entry_is_expunged_on_pre_flush_failure(
        self, session_factory, clean_db
    ):
        """The created-entry twin of the before-flush arm: an entry the
        basket CREATED but never flushed (the allocator staged the object
        and failed before its flush) is PENDING in the session — the
        visit_id query cannot see it either, and an unexpunged pending
        object would be INSERTed by the outer commit. The compensating
        cleanup must delete it from the session (no INSERT must ever
        reach the DB)."""
        setup = session_factory()
        world = _prepare_world(setup)
        setup.close()  # no committed ticket

        cart = session_factory()
        visit = _create_cart_visit(cart, world)
        visit_id = visit.id

        staged_entries: list[OnlineQueueEntry] = []

        def staging_allocator(handoff):
            """A broken allocator: stages the entry WITHOUT flushing and
            raises — the failure point sits between the object
            construction and its INSERT (the kwargs are the exact
            prepare_wizard_queue_assignment handoff shape)."""
            entry = OnlineQueueEntry(
                queue_id=handoff.daily_queue.id,
                patient_id=handoff.create_entry_kwargs.get("patient_id"),
                patient_name=handoff.create_entry_kwargs.get("patient_name"),
                number=1,
                status="waiting",
                source="desk",
                visit_id=visit_id,
            )
            cart.add(entry)
            staged_entries.append(entry)
            raise RuntimeError("INJECTED allocator failure before flush")

        basket = RegistrarWizardQueueAssignmentService(
            cart, create_entry_allocator=staging_allocator
        )

        queue_numbers = basket.assign_same_day_queue_numbers(
            [visit], target_day=_DAY, source="desk"
        )
        assert queue_numbers == {}
        cart.commit()

        proof = session_factory()
        assert (
            proof.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.visit_id == visit_id)
            .count()
            == 0
        )
        assert (
            proof.query(OnlineQueueEntry)
            .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
            .filter(
                OnlineQueueEntry.patient_id == world["patient_id"],
                DailyQueue.day == _DAY,
            )
            .count()
            == 0
        )
        proof.close()
