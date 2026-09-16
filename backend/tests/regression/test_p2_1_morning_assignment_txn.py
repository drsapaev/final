"""Regression tests for the morning_assignment transaction boundary.

QD-2E P1 contract (REPLACES the former P2-1 «один commit на весь batch»
requirement — that boundary held one transaction across the whole visit
batch, so every (day, queue_tag) advisory lock taken by the batch survived
until the final commit and blocked QR/GraphQL/confirmation writers on
those tags for the entire run):

1. Pre-create runs in its OWN SHORT transaction: the tags are processed
   in sorted order and the phase is committed (or rolled back)
   immediately — before any visit is processed.
2. One commit per SUCCESSFUL visit: a visit is re-read with FOR UPDATE,
   its (day, tag) scopes are locked in sorted order before any
   routing/owner lookup/write, entries + activation are committed
   together, exactly once per visit.
3. A failed visit rolls back ONLY itself: earlier visits stay durable
   (hard invariant — they are already committed), the failed visit is
   not activated and leaves no queue entries.
4. A multi-tag visit is atomic: a tag failure rolls back the whole
   visit, leaving no partial entries for its other tags.

The tests use SQLite (sufficient for commit-order counting and rollback
semantics). ``with_for_update()`` and advisory locks are PG-specific and
are covered by the PostgreSQL concurrency proof
(tests/integration/test_visit_confirmation_claim_concurrency_pg.py).

Run:
    pytest backend/tests/regression/test_p2_1_morning_assignment_txn.py -v
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

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

# Set env BEFORE app imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p2_1_regression.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-p2-1-regression-32-chars")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")

import app.services.morning_assignment as morning_assignment_module  # noqa: E402
from app.db.base_class import Base  # noqa: E402
from app.models import (  # noqa: E401,F401
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
from app.services.morning_assignment import MorningAssignmentService  # noqa: E402

# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_engine():
    """Real SQLite engine with FK enforcement enabled."""
    db_path = BACKEND_DIR / "test_p2_1_regression.db"
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
    """Factory for creating independent sessions."""
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _create():
        return Session()

    return _create


@pytest.fixture
def clean_db(db_engine):
    """Wipe all rows from relevant tables before each test."""
    with db_engine.connect() as conn:
        for table in [
            "queue_entries",
            "visit_services",
            "visits",
            "daily_queues",
            "services",
            "doctors",
            "patients",
            "users",
        ]:
            conn.execute(
                __import__("sqlalchemy").text(f"DELETE FROM {table}")
            )
        conn.commit()


# ─── Helpers ───────────────────────────────────────────────────────────

def _make_doctor_world(session, unique: str) -> tuple[User, Doctor]:
    doctor_user = User(
        username=f"doctor_{unique}",
        full_name="Reg Doctor",
        email=f"doctor_{unique}@test.local",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        created_at=datetime.now(UTC),
    )
    session.add(doctor_user)
    session.flush()

    doctor = Doctor(user_id=doctor_user.id, specialty="Cardiology", active=True)
    session.add(doctor)
    session.flush()
    return doctor_user, doctor


def _make_patient(session, unique: str, index: int) -> Patient:
    # PatientService treats phone as a unique patient identity. Keep
    # this transaction-boundary fixture valid so visits do not
    # intentionally exercise the queue identity-conflict path.
    patient = Patient(
        last_name=f"Patient{index}",
        first_name="Reg",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone=f"+9989100{index:02d}{unique[:4]}",
        email=f"patient{index}_{unique}@test.local",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()
    return patient


def _make_visit(session, patient: Patient, doctor: Doctor) -> Visit:
    unique = uuid.uuid4().hex[:8]
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        status="confirmed",
        visit_date=date.today(),
        visit_time="10:00",
        discount_mode="none",
        department="cardiology",
        confirmation_token=f"token-{unique}",
        confirmation_channel="telegram",
        confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()
    return visit


def _setup_confirmed_visits(session, n: int = 3) -> tuple[list[int], int]:
    """Create n confirmed visits with one VisitService each.

    Returns (visit_ids, doctor_user_id).
    """
    unique = uuid.uuid4().hex[:8]
    doctor_user, doctor = _make_doctor_world(session, unique)

    service = Service(
        code=f"REG_{unique}",
        name="Reg Consultation",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag=f"reg_cardio_{unique}",
        is_consultation=True,
        allow_doctor_price_override=False,
    )
    session.add(service)
    session.flush()

    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor_user.id,
        queue_tag=service.queue_tag,
        active=True,
    )
    session.add(daily_queue)
    session.flush()

    visit_ids: list[int] = []
    for i in range(n):
        patient = _make_patient(session, unique, i)
        visit = _make_visit(session, patient, doctor)

        vs = VisitService(
            visit_id=visit.id,
            service_id=service.id,
            code=service.code,
            name=service.name,
            qty=1,
            price=service.price,
            currency="UZS",
        )
        session.add(vs)
        session.flush()

        visit_ids.append(visit.id)

    session.commit()
    return visit_ids, doctor_user.id


def _setup_multi_tag_visit(session, tags: list[str]) -> tuple[int, list[str]]:
    """One confirmed visit whose services carry the given queue_tags.

    No DailyQueues are pre-created here: the run's own pre-create phase
    (and per-visit get_or_create) builds the queues, exercising the
    full QD-2E P1 flow. Returns (visit_id, tags).
    """
    unique = uuid.uuid4().hex[:8]
    doctor_user, doctor = _make_doctor_world(session, unique)
    assert doctor_user.id is not None

    services: list[Service] = []
    for i, tag in enumerate(tags):
        service = Service(
            code=f"REG_{unique}_{i}",
            name=f"Reg Service {i}",
            price=100000.00,
            duration_minutes=30,
            active=True,
            requires_doctor=True,
            queue_tag=tag,
            doctor_id=doctor.id,
            is_consultation=True,
            allow_doctor_price_override=False,
        )
        session.add(service)
        session.flush()
        services.append(service)

    patient = _make_patient(session, unique, 0)
    visit = _make_visit(session, patient, doctor)

    for service in services:
        session.add(
            VisitService(
                visit_id=visit.id,
                service_id=service.id,
                code=service.code,
                name=service.name,
                qty=1,
                price=service.price,
                currency="UZS",
            )
        )
        session.flush()

    session.commit()
    return visit.id, tags


def _count_entries(session, visit_id: int) -> int:
    return (
        session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .count()
    )


# ─── Regression Tests ──────────────────────────────────────────────────

class TestP21MorningAssignmentTxn:
    """QD-2E P1: morning_assignment transaction boundary regression tests."""

    def test_short_precreate_transaction_then_one_commit_per_successful_visit(
        self, session_factory, clean_db
    ):
        """REGRESSION: the batch commits (1 pre-create) + (1 per visit).

        Old boundary (P2-1): exactly ONE commit for the whole batch —
        that held every (day, tag) advisory lock until the end and
        blocked concurrent writers for the whole run.

        QD-2E P1 boundary:
        - commit #1 ends the SHORT pre-create transaction BEFORE any
          visit is processed (locks of pre-create do not survive);
        - each successful visit is committed exactly once, right after
          its own processing;
        - nothing is committed between visits except those per-visit
          commits.
        """
        setup_session = session_factory()
        visit_ids, _ = _setup_confirmed_visits(setup_session, n=3)
        setup_session.close()

        # Clean any queue entries from setup
        clean_session = session_factory()
        clean_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id.in_(visit_ids)
        ).delete(synchronize_session=False)
        clean_session.commit()
        clean_session.close()

        # Instrument commits AND per-visit assignment starts, in one
        # ordered event log.
        repro_session = session_factory()
        events: list[tuple[str, object]] = []
        original_commit = repro_session.commit

        def counting_commit(*args, **kwargs):
            events.append(("commit", None))
            return original_commit(*args, **kwargs)

        repro_session.commit = counting_commit  # type: ignore[method-assign]

        service_obj = MorningAssignmentService(repro_session)
        original_assign = service_obj._assign_queues_for_visit

        def recording_assign(visit, target_date, *, source="morning_assignment"):
            events.append(("assign", visit.id))
            return original_assign(visit, target_date, source=source)

        service_obj._assign_queues_for_visit = recording_assign  # type: ignore[method-assign]

        result = service_obj.run_morning_assignment(date.today())

        repro_session.close()

        assert result["success"] is True, f"Batch failed: {result}"
        assert result["processed_visits"] == 3, (
            f"Expected 3 processed visits, got {result['processed_visits']}"
        )

        # ─── THE REGRESSION ASSERTIONS ─────────────────────────────
        commit_positions = [
            index for index, (kind, _) in enumerate(events) if kind == "commit"
        ]
        assign_positions = [
            index for index, (kind, _) in enumerate(events) if kind == "assign"
        ]

        # 1 pre-create commit + exactly one commit per successful visit.
        assert len(commit_positions) == 1 + 3, (
            f"Expected 1 pre-create commit + 3 per-visit commits, got "
            f"{len(commit_positions)} commits in {events}. The QD-2E P1 "
            f"boundary is one atomic transaction per successful visit."
        )
        # Every visit was picked up exactly once.
        assert len(assign_positions) == 3, events

        # The pre-create commit precedes ALL visit processing, and the
        # events alternate strictly per visit:
        #   commit(pre-create) < assign < commit(visit) < assign < ...
        first_commit = commit_positions[0]
        assert first_commit < min(assign_positions), (
            f"The pre-create transaction must end (commit) before any "
            f"visit is processed; events: {events}"
        )
        assert (
            commit_positions[0]
            < assign_positions[0]
            < commit_positions[1]
            < assign_positions[1]
            < commit_positions[2]
            < assign_positions[2]
            < commit_positions[3]
        ), (
            f"Expected strict per-visit alternation [commit-precreate, "
            f"assign, commit, assign, commit, assign, commit], got "
            f"events: {events}"
        )

    def test_mid_batch_failure_rolls_back_only_failed_visit(
        self, session_factory, clean_db
    ):
        """REGRESSION: a failed visit is rolled back alone; visits
        committed before it stay durable.

        QD-2E P1 makes this a HARD invariant (P2-1b only allowed V1/V3
        to survive): V1 is committed by its own per-visit transaction
        BEFORE V2 runs, so V2's failure cannot destroy it. V2 itself
        must not be activated and must leave no queue entries.
        """
        setup_session = session_factory()
        visit_ids, _ = _setup_confirmed_visits(setup_session, n=3)
        setup_session.close()

        # Clean any queue entries from setup
        clean_session = session_factory()
        clean_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id.in_(visit_ids)
        ).delete(synchronize_session=False)
        clean_session.commit()
        clean_session.close()

        # Reproducer run: V2 fails
        repro_session = session_factory()
        service_obj = MorningAssignmentService(repro_session)

        fail_visit_id = visit_ids[1]
        original_assign_single = service_obj._assign_single_queue

        def failing_assign_single(visit, queue_tag, target_date, *, source="morning_assignment"):
            if visit.id == fail_visit_id:
                raise RuntimeError(f"INJECTED FAILURE for visit {visit.id}")
            return original_assign_single(visit, queue_tag, target_date, source=source)

        service_obj._assign_single_queue = failing_assign_single  # type: ignore[method-assign]

        result = service_obj.run_morning_assignment(date.today())
        repro_session.close()

        # ─── Verify in NEW independent session ──────────────────────
        verify_session = session_factory()
        try:
            v1 = verify_session.query(Visit).filter(Visit.id == visit_ids[0]).first()
            v2 = verify_session.query(Visit).filter(Visit.id == visit_ids[1]).first()
            v3 = verify_session.query(Visit).filter(Visit.id == visit_ids[2]).first()
            q1 = _count_entries(verify_session, visit_ids[0])
            q2 = _count_entries(verify_session, visit_ids[1])
            q3 = _count_entries(verify_session, visit_ids[2])

            # The failed visit must NOT be activated nor leave entries.
            assert v2.status != "open", (
                f"V2 (failed visit) should NOT be 'open'. "
                f"V2: status={v2.status!r}, queue_entries={q2}. "
                f"The failed visit must not be activated."
            )
            assert q2 == 0, (
                f"V2 (failed visit) must leave 0 queue entries, got {q2}"
            )

            # QD-2E P1 HARD invariant: V1 and V3 were committed by their
            # own per-visit transactions before/after the failure — they
            # are durable (open, with entries), and the honest counters
            # reflect them.
            assert v1.status == "open" and q1 > 0, (
                f"V1 must stay durable after V2's failure: "
                f"status={v1.status!r}, entries={q1}"
            )
            assert v3.status == "open" and q3 > 0, (
                f"V3 must stay durable after V2's failure: "
                f"status={v3.status!r}, entries={q3}"
            )
        finally:
            verify_session.close()

        # Counters describe durable DB state: 2 of 3 visits processed.
        assert result["success"] is True, result
        assert result["processed_visits"] == 2, (
            f"Expected honest processed_visits=2 (V1, V3 durable), got "
            f"{result['processed_visits']}"
        )
        assert result["assigned_queues"] == 2, result

    def test_multi_tag_visit_failure_leaves_no_partial_entries(
        self, session_factory, clean_db
    ):
        """REGRESSION (QD-2E P1): one visit, two tags; the second tag's
        failure rolls back the WHOLE visit transaction — no partial
        entry may survive for the first tag.
        """
        tags = ["reg_alpha_partial", "reg_beta_partial"]
        setup_session = session_factory()
        visit_id, tags = _setup_multi_tag_visit(setup_session, tags)
        setup_session.close()

        repro_session = session_factory()
        service_obj = MorningAssignmentService(repro_session)

        failing_tag = sorted(tags)[1]
        original_assign_single = service_obj._assign_single_queue

        def failing_assign_single(visit, queue_tag, target_date, *, source="morning_assignment"):
            if queue_tag == failing_tag:
                raise RuntimeError(f"INJECTED FAILURE for tag {queue_tag}")
            return original_assign_single(visit, queue_tag, target_date, source=source)

        service_obj._assign_single_queue = failing_assign_single  # type: ignore[method-assign]

        result = service_obj.run_morning_assignment(date.today())
        repro_session.close()

        assert result["success"] is True, result
        assert result["processed_visits"] == 0, result

        # ─── Verify in NEW independent session ──────────────────────
        verify_session = session_factory()
        try:
            visit = verify_session.query(Visit).filter(Visit.id == visit_id).first()
            entries = (
                verify_session.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.visit_id == visit_id)
                .all()
            )
            assert visit.status != "open", (
                f"The partially-failed visit must not be activated: "
                f"status={visit.status!r}"
            )
            assert entries == [], (
                f"A multi-tag visit must be atomic: found {len(entries)} "
                f"orphan entries after the failed tag "
                f"({[e.number for e in entries]}) — the successful first "
                f"tag was not rolled back with the visit transaction."
            )
        finally:
            verify_session.close()

    def test_multi_tag_visit_locks_scopes_in_sorted_order_before_processing(
        self, session_factory, clean_db, monkeypatch
    ):
        """QD-2E P1: a multi-tag visit takes ALL its (day, tag) claim
        scopes in SORTED order BEFORE the first routing/owner lookup or
        write — the raw-set iteration could take them in any order and
        deadlock PostgreSQL against a concurrent writer holding the
        scopes in the opposite order.
        """
        tags = ["reg_zeta_lock", "reg_alpha_lock", "reg_mid_lock"]
        setup_session = session_factory()
        visit_id, tags = _setup_multi_tag_visit(setup_session, tags)
        setup_session.close()

        events: list[tuple[str, str]] = []
        monkeypatch.setattr(
            morning_assignment_module,
            "lock_queue_tag_claim_scope",
            lambda _db, queue_tag, _day: events.append(("lock", queue_tag)),
        )

        repro_session = session_factory()
        service_obj = MorningAssignmentService(repro_session)
        original_assign_single = service_obj._assign_single_queue

        def recording_assign_single(visit, queue_tag, target_date, *, source="morning_assignment"):
            events.append(("assign", queue_tag))
            return original_assign_single(visit, queue_tag, target_date, source=source)

        service_obj._assign_single_queue = recording_assign_single  # type: ignore[method-assign]

        result = service_obj.run_morning_assignment(date.today())
        repro_session.close()

        assert result["success"] is True, result
        assert result["processed_visits"] == 1, result
        assert result["assigned_queues"] == len(tags), result

        lock_events = [queue_tag for kind, queue_tag in events if kind == "lock"]
        assign_events = [
            queue_tag for kind, queue_tag in events if kind == "assign"
        ]

        # All scopes of the visit are acquired in SORTED order...
        assert lock_events == sorted(tags), (
            f"(day, tag) scopes must be locked in sorted order for the "
            f"whole visit, got {lock_events}"
        )
        # ...and every lock precedes the first routing/owner lookup
        # (observed here as the first per-tag assignment call).
        first_assign_index = next(
            index for index, (kind, _) in enumerate(events) if kind == "assign"
        )
        assert first_assign_index >= len(lock_events), (
            f"All {len(lock_events)} sorted lock events must precede the "
            f"first tag processing; events: {events}"
        )
        # Tag processing itself is deterministic (sorted) as well.
        assert assign_events == sorted(tags), events

        # The flow completed: entries exist for every tag.
        verify_session = session_factory()
        try:
            assert _count_entries(verify_session, visit_id) == len(tags)
        finally:
            verify_session.close()

    def test_morning_precreate_processes_tags_in_sorted_order(
        self, session_factory, clean_db, monkeypatch
    ):
        """QD-2E P1: the pre-create phase processes Service.queue_tag
        values in deterministic sorted order (the DISTINCT result order
        is undefined, and each created queue takes a (day, tag)
        advisory lock — an unordered phase could deadlock a concurrent
        one).
        """
        tags = ["reg_zeta_pre", "reg_alpha_pre", "reg_mid_pre"]
        setup_session = session_factory()
        _visit_id, tags = _setup_multi_tag_visit(setup_session, tags)
        setup_session.close()

        created: list[str] = []
        original_get_or_create = (
            morning_assignment_module.queue_service.get_or_create_daily_queue
        )

        def recording_get_or_create(db, **kwargs):
            created.append(kwargs["queue_tag"])
            return original_get_or_create(db, **kwargs)

        monkeypatch.setattr(
            morning_assignment_module.queue_service,
            "get_or_create_daily_queue",
            recording_get_or_create,
        )

        repro_session = session_factory()
        created_count = MorningAssignmentService(
            repro_session
        ).ensure_daily_queues_for_all_tags(date.today())
        repro_session.rollback()
        repro_session.close()

        assert created_count == len(tags), created
        assert created == sorted(tags), (
            f"Pre-create must process queue_tags in sorted order, got "
            f"{created}"
        )
