"""PostgreSQL proof for the /registrar/cart vs GraphQL joinQueue lock order.

QD-2E review P1 (cart/GQL lock-order inversion): the cart inserts its
visits BEFORE taking the tag/day advisory locks, and the visit INSERT
fires the ``visits.doctor_id`` FK check — a FOR KEY SHARE row lock on the
doctor held until the cart's single commit. GraphQL joinQueue takes the
tag/day advisory lock FIRST and then ``Doctor ... FOR UPDATE``. Run
concurrently for the same doctor and tag:

    cart A: holds KEY SHARE(doctor)      -> waits for advisory(tag)
    GQL  B: holds advisory(tag)          -> waits for FOR UPDATE(doctor)

PostgreSQL must break the cycle by aborting one business operation
(SQLSTATE 40P01) — neither handler retries, so one registration or one
online join fails with an internal error.

The fix pair under test:
- the cart pre-acquires EVERY (day, tag) scope from the request payload
  BEFORE its first write (RegistrarWizardQueueAssignmentService
  .prelock_cart_tag_claim_scopes), so it waits for a scope while holding
  no doctor row lock at all;
- joinQueue takes the doctor row with FOR SHARE instead of FOR UPDATE —
  compatible with FK KEY SHARE holders while still blocking every
  concurrent eligibility-changing row UPDATE (an UPDATE takes at least
  FOR NO KEY UPDATE, which conflicts with FOR SHARE).

The proof runs two real workers against one PostgreSQL with barriers:
worker B (the GraphQL mutation) acquires the tag lock and pauses before
the doctor row; worker A (the real cart endpoint function) then runs and
must block on the tag scope BEFORE writing a single row (pinned via
pg_stat_activity + an empty visits table); after both continue, both
operations must complete correctly with no deadlock.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models import (  # noqa: F401 - register the complete metadata
    Doctor,
    Patient,
    Service,
    User,
    Visit,
    VisitService,
)
from app.models.clinic import ClinicSettings
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment_invoice import PaymentInvoice


@pytest.fixture
def cart_gql_engine():
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("cart/GQL lock-order proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_cart_gql_lock_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                # bounded waits keep a REGRESSION loud and fast instead of
                # hanging the suite; deadlock_timeout well below the
                # barriers' own timeouts so an unfixed inversion aborts
                # quickly instead of stalling the workers.
                "-cstatement_timeout=20000 -clock_timeout=20000 "
                "-cdeadlock_timeout=500ms"
            )
        },
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.mark.integration
@pytest.mark.queue
def test_cart_and_graphql_join_complete_without_deadlock(
    cart_gql_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = sessionmaker(
        bind=cart_gql_engine,
        autocommit=False,
        autoflush=False,
    )

    with Session(cart_gql_engine) as seed:
        suffix = uuid.uuid4().hex[:8]
        admin_user = User(
            username=f"cart_admin_{suffix}",
            hashed_password="!disabled:test",
            role="Admin",
            is_active=True,
        )
        doctor_user = User(
            username=f"cart_doc_{suffix}",
            hashed_password="!disabled:test",
            role="Doctor",
            is_active=True,
        )
        seed.add_all([admin_user, doctor_user])
        seed.flush()
        doctor = Doctor(
            user_id=doctor_user.id,
            specialty="Cardiology",
            active=True,
            cabinet="101",
            max_online_per_day=20,
            start_number_online=1,
        )
        cart_patient = Patient(
            last_name=f"Cart{suffix}",
            first_name="Anna",
            phone=f"+998910000{suffix[:5]}",
            is_deleted=False,
        )
        gql_patient = Patient(
            last_name=f"Join{suffix}",
            first_name="Bee",
            phone=f"+998920000{suffix[:5]}",
            is_deleted=False,
        )
        seed.add_all([doctor, cart_patient, gql_patient])
        seed.flush()
        queue_tag = f"cardio_{suffix}"
        service = Service(
            code=f"DL-{suffix}",
            name="SYNTHETIC cart/GQL lock-order consult",
            price=100000.00,
            duration_minutes=30,
            active=True,
            requires_doctor=True,
            queue_tag=queue_tag,
            is_consultation=True,
            allow_doctor_price_override=False,
        )
        seed.add(service)
        seed.flush()
        # clinic day == host UTC day and an always-open online window: the
        # cart computes its scope from date.today() while joinQueue uses the
        # configured timezone — both must agree on the SAME (day, tag).
        seed.add_all(
            [
                ClinicSettings(key="timezone", value="UTC", category="queue"),
                ClinicSettings(key="queue_start_hour", value=0, category="queue"),
            ]
        )
        seed.commit()
        ids = {
            "admin": admin_user.id,
            "doctor": doctor.id,
            "cart_patient": cart_patient.id,
            "gql_patient": gql_patient.id,
            "service": service.id,
        }

    # ── barriers ────────────────────────────────────────────────────────
    thread_role = threading.local()
    b_tag_lock_held = threading.Event()
    release_b = threading.Event()
    a_prelock_requested = threading.Event()
    a_backend_pid: list[int] = []

    from app.services import queue_claim_service as claim_module
    from app.services import registrar_wizard_queue_assignment_service as wizard_module

    real_claim_lock = claim_module.lock_queue_tag_claim_scope
    real_wizard_lock = wizard_module.lock_queue_tag_claim_scope

    def observed_claim_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        role = getattr(thread_role, "value", None)
        if role == "b" and not b_tag_lock_held.is_set():
            real_claim_lock(db, queue_tag, day)
            # B now HOLDS the (day, tag) xact advisory lock and has not
            # touched the doctor row yet.
            b_tag_lock_held.set()
            if not release_b.wait(timeout=20):
                raise AssertionError("worker B was not released to continue joinQueue")
            return
        real_claim_lock(db, queue_tag, day)

    def observed_wizard_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        role = getattr(thread_role, "value", None)
        if role == "a" and not a_prelock_requested.is_set():
            a_prelock_requested.set()
            a_backend_pid.append(
                int(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            )
        real_wizard_lock(db, queue_tag, day)

    monkeypatch.setattr(claim_module, "lock_queue_tag_claim_scope", observed_claim_lock)
    monkeypatch.setattr(
        wizard_module, "lock_queue_tag_claim_scope", observed_wizard_lock
    )

    # The GraphQL mutation owns its session — hand it worker B's session.
    from app.graphql import mutations as mutations_module

    b_session = session_factory()

    @contextlib.contextmanager
    def b_db_session():
        try:
            yield b_session
        finally:
            b_session.close()

    monkeypatch.setattr(mutations_module, "get_db_session", b_db_session)

    # Pin the doctor lock MODE the mutation actually emits (FOR SHARE —
    # the FK-KEY-SHARE-compatible half of the fix pair).
    doctor_row_locks: list[str] = []

    @event.listens_for(cart_gql_engine, "before_cursor_execute")
    def _capture_doctor_row_locks(
        conn, cursor, statement, parameters, context, executemany
    ):  # pragma: no cover - observation only
        if "FROM doctors" in statement and (
            "FOR SHARE" in statement or "FOR UPDATE" in statement
        ):
            doctor_row_locks.append(statement)

    # ── worker B: the REAL GraphQL join (DB part) ──────────────────────
    def run_graphql_join():  # type: ignore[no-untyped-def]
        from app.graphql.mutations import Mutation
        from app.graphql.types import QueueEntryInput

        thread_role.value = "b"
        try:
            return Mutation._join_queue_impl(
                SimpleNamespace(context=None),
                QueueEntryInput(
                    patient_id=ids["gql_patient"],
                    doctor_id=ids["doctor"],
                    queue_tag=queue_tag,
                ),
            )
        finally:
            thread_role.value = None

    # ── worker A: the REAL cart endpoint function ───────────────────────
    def run_cart():  # type: ignore[no-untyped-def]
        from app.api.v1.endpoints.registrar_wizard._cart import (
            create_cart_appointments,
        )
        from app.api.v1.endpoints.registrar_wizard._helpers import (
            CartRequest,
            ServiceItemRequest,
            VisitRequest,
        )

        thread_role.value = "a"
        cart_request = CartRequest(
            patient_id=ids["cart_patient"],
            visits=[
                VisitRequest(
                    doctor_id=ids["doctor"],
                    services=[
                        ServiceItemRequest(service_id=ids["service"], quantity=1)
                    ],
                    visit_date=date.today(),
                    visit_time="10:00",
                    department="cardiology",
                )
            ],
            discount_mode="none",
            payment_method="cash",
        )
        with session_factory() as session:
            try:
                return create_cart_appointments(
                    cart_data=cart_request,
                    db=session,
                    current_user=SimpleNamespace(
                        id=ids["admin"], role="Admin", is_superuser=False
                    ),
                )
            finally:
                thread_role.value = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_b = executor.submit(run_graphql_join)
        assert b_tag_lock_held.wait(timeout=20), "joinQueue never took the tag lock"

        future_a = executor.submit(run_cart)
        assert a_prelock_requested.wait(
            timeout=20
        ), "cart never requested its tag claim scope"

        try:
            # THE ordering proof: the cart waits for the (day, tag) scope
            # BEFORE it has written a single row — the visit INSERT (and
            # its doctor FK KEY SHARE) must not have happened yet.
            a_waiting_on_scope = False
            deadline = time.monotonic() + 10
            with cart_gql_engine.connect() as monitor:
                while time.monotonic() < deadline:
                    waiting = monitor.execute(
                        text(
                            "SELECT wait_event_type = 'Lock' "
                            "AND lower(COALESCE(wait_event, '')) "
                            "LIKE 'advisory%' "
                            "FROM pg_stat_activity WHERE pid = :pid"
                        ),
                        {"pid": a_backend_pid[0]},
                    ).scalar_one_or_none()
                    if waiting:
                        a_waiting_on_scope = True
                        break
                    time.sleep(0.02)
            assert a_waiting_on_scope is True, (
                "cart did not block on the tag claim scope while joinQueue "
                "holds it (pre-lock missing?)"
            )
            with cart_gql_engine.connect() as monitor:
                written_visits = monitor.execute(
                    text("SELECT count(*) FROM visits")
                ).scalar_one()
            assert written_visits == 0, (
                "cart wrote rows before acquiring its tag claim scope — "
                "the FK KEY SHARE would precede the advisory lock and "
                "re-open the inversion"
            )
        finally:
            release_b.set()

        outcome_b = future_b.result(timeout=60)
        outcome_a = future_a.result(timeout=60)

    # ── both operations completed and are correct ───────────────────────
    assert outcome_b.success is True, outcome_b.message
    gql_number = outcome_b.queue_entry.number

    assert outcome_a.success is True
    assert len(outcome_a.visit_ids) == 1
    visit_id = outcome_a.visit_ids[0]
    cart_assignments = outcome_a.queue_numbers[visit_id]
    assert len(cart_assignments) == 1
    cart_assignment = cart_assignments[0]
    assert cart_assignment["queue_tag"] == queue_tag
    assert cart_assignment["number"] != gql_number

    # the doctor row lock the mutation emitted is FOR SHARE, never
    # FOR UPDATE (FK KEY SHARE compatibility is part of the fix contract)
    assert doctor_row_locks, "no doctor row lock was captured for joinQueue"
    for statement in doctor_row_locks:
        assert "FOR SHARE" in statement, statement
        assert "FOR UPDATE" not in statement, statement

    with Session(cart_gql_engine) as verify:
        queue = (
            verify.query(DailyQueue)
            .filter(
                DailyQueue.day == date.today(),
                DailyQueue.specialist_id == ids["doctor"],
                DailyQueue.queue_tag == queue_tag,
            )
            .one()
        )
        entries = (
            verify.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue.id)
            .all()
        )
        # exactly the two tickets — the cart's and the online join's
        assert len(entries) == 2
        by_patient = {entry.patient_id: entry for entry in entries}
        gql_entry = by_patient[ids["gql_patient"]]
        cart_entry = by_patient[ids["cart_patient"]]
        assert gql_entry.status == "waiting"
        assert cart_entry.status == "waiting"
        # the cart ticket is linked to the registration's visit
        assert cart_entry.visit_id == visit_id
        visit = verify.get(Visit, visit_id)
        assert visit is not None
        assert visit.patient_id == ids["cart_patient"]
        assert visit.status == "open"
        # the cart's invoice was committed with the same transaction
        assert (
            verify.query(PaymentInvoice)
            .filter(PaymentInvoice.patient_id == ids["cart_patient"])
            .count()
            == 1
        )
