"""PostgreSQL proof for atomic save-time doctor eligibility (PR #3438 P1-2
+ round-2 P1 lock order).

The cart validates doctor eligibility BEFORE the tag prelocks with plain
SELECTs (``_assert_cart_doctor_eligibility``); between that check and the
cart's single commit an admin can commit an eligibility-changing UPDATE
(Doctor.active/specialty, owner User.is_active/role). Without a locked
revalidation the cart then creates a new Visit + queue entry for a doctor
who is already deactivated/demoted.

The fix under test (``_revalidate_cart_doctor_eligibility_locked``):

- AFTER the (day, tag) prelocks and BEFORE the first visit INSERT, the
  owner User rows are re-read ``FOR SHARE`` (sorted ids) and then the
  Doctor rows ``FOR SHARE`` (sorted ids), and eligibility is re-run on
  the locked snapshot;
- the lock MODE is FOR SHARE (never FOR UPDATE): compatible with the
  visit INSERT's FK KEY SHARE and with GraphQL joinQueue's advisory-first
  protocol;
- the lock ORDER is ``User → Doctor`` — the same users-first order the
  canonical ``UserManagementService.update_user`` uses
  (``lock_user_candidate_state`` takes ``users FOR UPDATE`` and the
  deactivation/demotion then mirrors into ``UPDATE doctors``). The
  round-1 order ``Doctor → User`` was an AB-BA inversion: a live
  registrar save concurrent with an admin deactivation deadlocked
  PostgreSQL (SQLSTATE 40P01) — T1 held Doctor FOR SHARE waiting for
  User FOR SHARE while T2 held User FOR UPDATE waiting on UPDATE
  doctors. The owner set for the User lock comes from an unlocked
  pre-read of ``Doctor.id → user_id``; a relink committed between the
  pre-read and the Doctor lock is re-checked under the lock and retried
  (bounded), so the NEW owner is never left unlocked.

Proofs (two real workers against one PostgreSQL):

1. ``..._blocks_concurrent_doctor_deactivation``: while the cart holds
   the locked revalidation snapshot, ``UPDATE doctors SET active=false``
   times out on the row lock; after the cart commits, the UPDATE lands.
2. ``..._blocks_concurrent_owner_user_deactivation``: same for the owner
   ``UPDATE users SET is_active=false`` (the User FOR SHARE half).
3. ``..._rejects_cart_when_deactivation_commits_first``: the deactivation
   commits in the window between the UNLOCKED gate and the locked
   re-read — the cart is rejected with 400 and leaves ZERO
   Visit/Invoice/QueueEntry rows (this is the exact race the unlocked
   gate alone cannot close).
4. ``..._no_deadlock_with_real_update_user``: the mixed-path pin the
   round-1 tests lacked — the REAL ``create_cart_appointments`` frozen
   between its two locked reads runs against the REAL
   ``UserManagementService.update_user`` deactivation; the serialized
   outcome (cart commits first, deactivation lands after) replaces the
   round-1 deadlock, and the statement order User FOR SHARE → Doctor
   FOR SHARE is pinned directly.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
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
def cart_eligibility_engine():
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("cart doctor-eligibility lock proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_cart_doc_elig_" + uuid.uuid4().hex
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
                # hanging the suite (mirrors test_cart_gql_lock_order_pg).
                "-cstatement_timeout=60000 -clock_timeout=60000 "
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


def _seed(engine) -> dict:
    with Session(engine) as seed:
        suffix = uuid.uuid4().hex[:8]
        admin_user = User(
            username=f"elig_admin_{suffix}",
            hashed_password="!disabled:test",
            role="Admin",
            is_active=True,
        )
        doctor_user = User(
            username=f"elig_doc_{suffix}",
            hashed_password="!disabled:test",
            role="Doctor",
            full_name="Synthetic Eligibility Doctor",
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
        patient = Patient(
            last_name=f"Elig{suffix}",
            first_name="Anna",
            phone=f"+998930000{suffix[:5]}",
            is_deleted=False,
        )
        seed.add_all([doctor, patient])
        seed.flush()
        queue_tag = f"cardio_{suffix}"
        service = Service(
            code=f"ELG-{suffix}",
            service_code=f"EL{suffix[:8]}",
            name="SYNTHETIC eligibility consult",
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
        seed.add_all(
            [
                ClinicSettings(key="timezone", value="UTC", category="queue"),
                ClinicSettings(key="queue_start_hour", value=0, category="queue"),
            ]
        )
        seed.commit()
        return {
            "admin": admin_user.id,
            "doctor": doctor.id,
            "doctor_user": doctor_user.id,
            "patient": patient.id,
            "service": service.id,
            "queue_tag": queue_tag,
        }


def _cart_request(ids: dict) -> SimpleNamespace:
    from app.api.v1.endpoints.registrar_wizard._helpers import (
        CartRequest,
        ServiceItemRequest,
        VisitRequest,
    )

    return CartRequest(
        patient_id=ids["patient"],
        visits=[
            VisitRequest(
                doctor_id=ids["doctor"],
                services=[ServiceItemRequest(service_id=ids["service"], quantity=1)],
                visit_date=date.today(),
                visit_time="10:00",
                department="cardiology",
            )
        ],
        discount_mode="none",
        payment_method="cash",
    )


def _run_cart(session_factory, ids: dict):
    """The REAL cart endpoint function, on worker A's own session."""
    from app.api.v1.endpoints.registrar_wizard._cart import (
        create_cart_appointments,
    )

    with session_factory() as session:
        return create_cart_appointments(
            cart_data=_cart_request(ids),
            db=session,
            current_user=SimpleNamespace(
                id=ids["admin"], role="Admin", is_superuser=False
            ),
        )


class _CartWorkerProbe:
    """Freeze the cart worker at an exact statement boundary.

    ``freeze_on`` selects the boundary:

    - ``"unlocked_doctor_read"``: right AFTER the UNLOCKED gate's plain
      ``FROM doctors`` SELECT (before the prelocks, before the locked
      revalidation) — the mid-gate race window;
    - ``"locked_user_read"``: right AFTER the locked revalidation's
      ``FROM users ... FOR SHARE`` SELECT (advisory + User row locks
      held; with the users-first order this is BETWEEN the two locked
      reads);
    - ``"locked_doctor_read"``: right AFTER the locked revalidation's
      ``FROM doctors ... FOR SHARE`` SELECT (advisory + User + Doctor
      row locks all held, nothing written yet);
    - ``"first_locked_read"``: right AFTER the FIRST ``FOR SHARE``
      re-read on either table — whichever the implementation locks
      first. With the users-first order this equals
      ``"locked_user_read"``; a regressed doctors-first order freezes
      after the Doctor lock instead (and the mixed-path deadlock pin
      goes red).

    The role marker is thread-local and MUST be set inside the cart
    worker thread — the listener ignores every other thread (the main
    test thread, concurrent admin sessions).

    Also records worker A's statement order to prove the lock protocol.
    """

    def __init__(self) -> None:
        self.role = threading.local()
        self.freeze_on: str | None = None
        self.release = threading.Event()
        self.frozen = threading.Event()
        self.statements: list[str] = []

    def attach(self, engine) -> None:
        @event.listens_for(engine, "after_cursor_execute")
        def _probe(conn, cursor, statement, parameters, context, executemany):
            role = getattr(self.role, "value", None)
            if role != "a":
                return
            self.statements.append(statement)
            target = self.freeze_on
            if not target:
                return
            if target == "unlocked_doctor_read":
                matched = "FROM doctors" in statement and "FOR SHARE" not in statement
            elif target == "locked_user_read":
                matched = "FROM users" in statement and "FOR SHARE" in statement
            elif target == "locked_doctor_read":
                matched = "FROM doctors" in statement and "FOR SHARE" in statement
            else:  # first_locked_read
                matched = (
                    "FROM users" in statement or "FROM doctors" in statement
                ) and "FOR SHARE" in statement
            if matched and not self.frozen.is_set():
                self.frozen.set()
                if not self.release.wait(timeout=30):
                    raise AssertionError("cart worker was never released")


def _statement_index(probe: _CartWorkerProbe, needle: str) -> int | None:
    for index, statement in enumerate(probe.statements):
        if needle in statement:
            return index
    return None


def _users_for_share_index(probe: _CartWorkerProbe) -> int | None:
    """First ``FROM users ... FOR SHARE`` statement of the cart worker."""
    for index, statement in enumerate(probe.statements):
        if "FROM users" in statement and "FOR SHARE" in statement:
            return index
    return None


def _first_doctors_for_share_index(probe: _CartWorkerProbe) -> int | None:
    """First ``FROM doctors ... FOR SHARE`` statement of the cart worker."""
    for index, statement in enumerate(probe.statements):
        if "FROM doctors" in statement and "FOR SHARE" in statement:
            return index
    return None


@pytest.mark.integration
@pytest.mark.queue
def test_cart_locked_eligibility_blocks_concurrent_doctor_deactivation(
    cart_eligibility_engine,
) -> None:
    engine = cart_eligibility_engine
    ids = _seed(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    probe = _CartWorkerProbe()
    probe.freeze_on = "locked_doctor_read"
    probe.attach(engine)

    def worker_a():
        probe.role.value = "a"
        try:
            return _run_cart(session_factory, ids)
        finally:
            probe.role.value = None

    with ThreadPoolExecutor(max_workers=1) as executor:
        future_a = executor.submit(worker_a)
        assert probe.frozen.wait(
            timeout=30
        ), "cart never reached the locked eligibility re-read"

        # The cart holds Doctor FOR SHARE + User FOR SHARE through its
        # single commit: a concurrent deactivation must block on the row
        # lock (bounded by a short lock_timeout so a MISSING lock is a
        # loud, fast failure instead of a hang).
        blocked = False
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL lock_timeout = '2s'"))
                try:
                    conn.execute(
                        text("UPDATE doctors SET active = false WHERE id = :id"),
                        {"id": ids["doctor"]},
                    )
                except OperationalError:
                    blocked = True
        assert blocked is True, (
            "UPDATE doctors SET active=false was NOT blocked — the cart does "
            "not hold the doctor row lock through its commit"
        )

        probe.release.set()
        outcome_a = future_a.result(timeout=60)

    assert outcome_a.success is True

    # after the cart committed, the deactivation lands
    with Session(engine) as verify:
        verify.execute(
            text("UPDATE doctors SET active = false WHERE id = :id"),
            {"id": ids["doctor"]},
        )
        verify.commit()
        doctor = verify.get(Doctor, ids["doctor"])
        assert doctor.active is False
        # the cart's visit was created while the doctor was still eligible
        visit = verify.query(Visit).filter(Visit.patient_id == ids["patient"]).one()
        assert visit.doctor_id == ids["doctor"]

    # lock protocol: tag prelock BEFORE any row lock; the users-first
    # re-read (User FOR SHARE) BEFORE the Doctor FOR SHARE re-read —
    # the global users -> doctors order shared with update_user(); FOR
    # SHARE, not FOR UPDATE, on both re-reads
    advisory_index = _statement_index(probe, "pg_advisory_xact_lock")
    users_share_index = _users_for_share_index(probe)
    doctors_share_index = _first_doctors_for_share_index(probe)
    assert advisory_index is not None, "no tag claim prelock captured"
    assert doctors_share_index is not None, "no Doctor FOR SHARE re-read captured"
    assert advisory_index < doctors_share_index, (
        "doctor row lock was taken BEFORE the (day, tag) prelock — "
        "lock-order inversion"
    )
    assert users_share_index is not None, "no User FOR SHARE re-read captured"
    assert users_share_index < doctors_share_index, (
        "User row lock was taken AFTER the Doctor row lock — AB-BA "
        "inversion against update_user() (users FOR UPDATE then UPDATE "
        "doctors) deadlocks the save against an admin deactivation"
    )
    # the eligibility re-reads themselves are FOR SHARE, never FOR UPDATE
    # (FK KEY SHARE + joinQueue Doctor FOR SHARE compatibility); other
    # statements (e.g. the queue assignment's DailyQueue locking) are out
    # of this fix's scope.
    for statement in probe.statements:
        if "FROM doctors" in statement or "FROM users" in statement:
            if "FOR SHARE" in statement:
                assert "FOR UPDATE" not in statement, statement


@pytest.mark.integration
@pytest.mark.queue
def test_cart_locked_eligibility_blocks_concurrent_owner_user_deactivation(
    cart_eligibility_engine,
) -> None:
    engine = cart_eligibility_engine
    ids = _seed(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    probe = _CartWorkerProbe()
    probe.freeze_on = "locked_user_read"
    probe.attach(engine)

    def worker_a():
        probe.role.value = "a"
        try:
            return _run_cart(session_factory, ids)
        finally:
            probe.role.value = None

    with ThreadPoolExecutor(max_workers=1) as executor:
        future_a = executor.submit(worker_a)
        assert probe.frozen.wait(
            timeout=30
        ), "cart never reached the locked eligibility re-read"

        blocked = False
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL lock_timeout = '2s'"))
                try:
                    conn.execute(
                        text("UPDATE users SET is_active = false WHERE id = :id"),
                        {"id": ids["doctor_user"]},
                    )
                except OperationalError:
                    blocked = True
        assert blocked is True, (
            "UPDATE users SET is_active=false was NOT blocked — the cart does "
            "not hold the owner User row lock through its commit"
        )

        probe.release.set()
        outcome_a = future_a.result(timeout=60)

    assert outcome_a.success is True


@pytest.mark.integration
@pytest.mark.queue
def test_cart_rejects_when_deactivation_commits_between_gate_and_revalidation(
    cart_eligibility_engine,
) -> None:
    """The exact race the unlocked gate alone cannot close.

    The deactivation commits in the window between the UNLOCKED gate's
    plain doctor read and the locked revalidation; the re-read must see it
    and reject the cart BEFORE any write.
    """
    engine = cart_eligibility_engine
    ids = _seed(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    probe = _CartWorkerProbe()
    probe.freeze_on = "unlocked_doctor_read"
    probe.attach(engine)

    def worker_a():
        probe.role.value = "a"
        try:
            return _run_cart(session_factory, ids)
        finally:
            probe.role.value = None

    with ThreadPoolExecutor(max_workers=1) as executor:
        future_a = executor.submit(worker_a)
        assert probe.frozen.wait(
            timeout=30
        ), "cart never reached the unlocked gate's doctor read"

        # the admin deactivation commits INSIDE the race window
        with Session(engine) as admin_session:
            admin_session.execute(
                text("UPDATE doctors SET active = false WHERE id = :id"),
                {"id": ids["doctor"]},
            )
            admin_session.commit()

        probe.release.set()
        with pytest.raises(HTTPException) as exc_info:
            future_a.result(timeout=60)

    assert exc_info.value.status_code == 400, exc_info.value.detail
    assert "неактивен" in exc_info.value.detail

    with Session(engine) as verify:
        assert (
            verify.query(Visit).filter(Visit.patient_id == ids["patient"]).count() == 0
        )
        assert (
            verify.query(PaymentInvoice)
            .filter(PaymentInvoice.patient_id == ids["patient"])
            .count()
            == 0
        )
        assert verify.query(OnlineQueueEntry).count() == 0
        assert verify.query(DailyQueue).count() == 0


@pytest.mark.integration
@pytest.mark.queue
def test_cart_locked_revalidation_no_deadlock_with_real_update_user(
    cart_eligibility_engine,
) -> None:
    """Round-2 P1 mixed-path pin: the REAL cart save ↔ the REAL update_user.

    The round-1 proofs exercised raw ``UPDATE doctors`` / ``UPDATE users``
    in isolation — neither worker ever HELD a User lock and then touched
    Doctor rows, so the AB-BA deadlock the round-1 order created against
    the canonical ``UserManagementService.update_user`` could not fire.
    This pin runs the two REAL command paths concurrently:

    - worker A: ``create_cart_appointments`` frozen BETWEEN its two
      locked re-reads (after the FIRST ``FOR SHARE`` statement);
    - worker B: ``UserManagementService.update_user(is_active=False)``
      for the doctor's owner — ``lock_user_candidate_state`` takes
      ``users FOR UPDATE`` and the deactivation mirrors into
      ``UPDATE doctors``.

    With the users-first cart order B parks on the User row lock until
    the cart commits (serialized outcome: the visit is created while the
    doctor is still eligible, THEN the account is deactivated). With the
    regressed doctors-first order the interleaving is the round-1
    deadlock: A waits for User FOR SHARE, B waits on UPDATE doctors —
    PostgreSQL resolves it with SQLSTATE 40P01 and this test goes red
    (either worker raises OperationalError / the cart endpoint fails).
    """
    engine = cart_eligibility_engine
    ids = _seed(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    probe = _CartWorkerProbe()
    probe.freeze_on = "first_locked_read"
    probe.attach(engine)

    def worker_a():
        probe.role.value = "a"
        try:
            return _run_cart(session_factory, ids)
        finally:
            probe.role.value = None

    def worker_b():
        from app.schemas.user_management import UserUpdateRequest
        from app.services.user_mgmt import UserManagementService

        with session_factory() as session:
            service = UserManagementService()
            return service.update_user(
                db=session,
                user_id=ids["doctor_user"],
                user_data=UserUpdateRequest(is_active=False),
                updated_by=ids["admin"],
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(worker_a)
        assert probe.frozen.wait(
            timeout=30
        ), "cart never reached the locked eligibility re-read"

        future_b = executor.submit(worker_b)
        # B must actually park on the cart's row locks — a save that
        # finished before the release would mean the paths never truly
        # interleaved (the deadlock window was not exercised).
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if future_b.done():
                break
            time.sleep(0.1)
        assert future_b.done() is False, (
            "update_user completed while the cart still held the frozen "
            "revalidation snapshot — the paths did not interleave"
        )

        probe.release.set()
        outcome_a = future_a.result(timeout=60)
        outcome_b = future_b.result(timeout=60)

    assert outcome_a.success is True
    assert outcome_b[0] is True, outcome_b[1]

    # serialized outcome: the visit was created while the doctor was
    # still eligible; the deactivation (and its Doctor mirror) landed
    # only after the cart's commit.
    with Session(engine) as verify:
        visit = verify.query(Visit).filter(Visit.patient_id == ids["patient"]).one()
        assert visit.doctor_id == ids["doctor"]
        owner = verify.get(User, ids["doctor_user"])
        assert owner.is_active is False
        doctor = verify.get(Doctor, ids["doctor"])
        assert doctor.active is False

    # direct order pin: the User FOR SHARE re-read precedes the Doctor
    # FOR SHARE re-read in the cart worker's statement stream.
    users_share_index = _users_for_share_index(probe)
    doctors_share_index = _first_doctors_for_share_index(probe)
    assert users_share_index is not None, "no User FOR SHARE re-read captured"
    assert doctors_share_index is not None, "no Doctor FOR SHARE re-read captured"
    assert users_share_index < doctors_share_index, (
        "cart locked Doctor rows before User rows — AB-BA inversion "
        "against update_user() (users FOR UPDATE → UPDATE doctors)"
    )
