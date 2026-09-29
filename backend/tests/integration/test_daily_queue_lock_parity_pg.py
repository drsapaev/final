"""PostgreSQL proof for the doctor day-queue creation lock parity.

Follow-up to the #3511 review (owner verdict round): four legacy
creation paths ran the check-then-insert for a doctor's day queue
outside the canonical ``pg_advisory_xact_lock`` scope that
``queue_service.get_or_create_daily_queue`` holds — the GraphQL untagged
join even used a different key spelling and serialized only against
itself. Two concurrent writers could both observe "no queue for this
doctor today" and insert; the ``uq_daily_queues_active_doctor_day_tag``
partial unique then failed the loser with an UNHANDLED IntegrityError
(a 500 to the operator) instead of a clean block → re-read → reuse.

The fix routes every creation path through
``queue_resource_routing.lock_daily_queue_creation`` — one canonical
``daily_queue:{day}:{doctor}`` scope, taken BEFORE the existing-queue
lookup.

Proofs (real workers against one PostgreSQL, mixed legacy + canonical
paths for the same fresh (day, doctor)):

1. ``..._serialize_on_one_canonical_scope``: four concurrent creators —
   the canonical queue service, the crud get_or_create (the queue_batch
   path), the visit-confirmation repository and the queue-limits
   repository — race for the same (day, doctor) with no seeded queue.
   Every worker returns a queue, NO worker raises, exactly ONE active
   queue row exists afterwards, and every worker saw the SAME queue id
   (block → re-read → reuse). Without the parity lock the interleaving
   ends in an IntegrityError on the partial unique (the constraint is
   what makes the regression loud rather than silent).
2. ``..._gql_untagged_scope_matches_canonical``: the scope the helper
   acquires is IDENTICAL to the canonical service's scope — the helper
   lock in one session blocks the REAL canonical service in another
   until the first commits (the historical mismatched spelling did not:
   doctor-before-day plus a trailing colon hashed to a different
   advisory id).
3. ``..._without_parity_is_loud``: the unserialized interleaving shape
   — a second INSERT of the same key blocks behind the first writer's
   uncommitted unique index entry and fails with IntegrityError once
   that writer commits. This pins WHY the parity lock exists: the
   constraint is the safety net, the advisory lock is the clean-reuse
   fix; the previous behavior was an unhandled IntegrityError.

Harness hardening (the first CI run hung 27 minutes at this file before
the 30-minute job timeout cancelled it — the local repro found the
shape): every session is context-managed with a rollback on error (a
raised creator must NEVER leak a transaction-scoped advisory lock
through a traceback-held session); queue ids are read BEFORE the commit
expires the instance (DetachedInstanceError); the blocking INSERT of
proof 3 runs in a background thread (two same-thread INSERTs would
self-deadlock the single test thread until the statement timeout);
every worker wait is bounded (barrier + future timeouts + the engine's
statement/lock timeouts — advisory waits respect the statement timeout,
verified experimentally); the executor is shut down without waiting so
a stuck worker can never wedge the suite.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud import online_queue as crud_online_queue
from app.crud.queue_resource_routing import lock_daily_queue_creation
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
from app.models.online_queue import DailyQueue
from app.repositories.queue_limits_repository import QueueLimitsRepository
from app.repositories.visit_confirmation_repository import (
    VisitConfirmationRepository,
)
from app.services.queue_service import queue_service

# bounded waits keep a REGRESSION loud and fast instead of hanging the
# suite (mirrors the cart eligibility lock PG proof; advisory waits
# respect the statement timeout — verified against a live PostgreSQL)
_PG_TIMEOUTS_MS = 15000


@pytest.fixture
def lock_parity_engine():
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("daily-queue lock-parity proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_dq_lock_parity_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                f"-cstatement_timeout={_PG_TIMEOUTS_MS} "
                f"-clock_timeout={_PG_TIMEOUTS_MS} "
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


def _seed_doctor(engine) -> int:
    with Session(engine) as seed:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=f"parity_doc_{suffix}",
            full_name=f"Паритетный Врач {suffix[:4]}",
            hashed_password="!disabled:test",
            role="Doctor",
            is_active=True,
        )
        seed.add(user)
        seed.flush()
        doctor = Doctor(
            user_id=user.id,
            specialty="cardiology",
            active=True,
            cabinet="101",
        )
        seed.add(doctor)
        # one settings row: the legacy constructors read clinic settings
        seed.add(ClinicSettings(key="queue_settings", value="{}"))
        seed.commit()
        return int(doctor.id)


def _canonical_creator(engine, day, doctor_id, barrier, errors, queue_ids):
    try:
        with Session(engine) as session:
            barrier.wait(timeout=30)
            queue = queue_service.get_or_create_daily_queue(
                session,
                day=day,
                specialist_id=doctor_id,
                queue_tag=None,
            )
            queue_id = int(queue.id)  # read before commit expires the instance
            session.commit()
        queue_ids.append(queue_id)
    except Exception as exc:  # noqa: BLE001 — the proof collects every failure
        errors.append(("canonical", exc))


def _crud_creator(engine, day, doctor_id, barrier, errors, queue_ids):
    try:
        barrier.wait(timeout=30)
        # the queue_batch path: commits internally, exactly as in prod.
        # Context-managed so a mid-path failure rolls back and releases
        # the transaction-scoped advisory lock instead of leaking it.
        with Session(engine) as session:
            queue = crud_online_queue.get_or_create_daily_queue(
                session, day, doctor_id, queue_tag=None
            )
            queue_ids.append(int(queue.id))
    except Exception as exc:  # noqa: BLE001
        errors.append(("crud/queue_batch", exc))


def _visit_confirmation_creator(engine, day, doctor_id, barrier, errors, queue_ids):
    try:
        with Session(engine) as session:
            barrier.wait(timeout=30)
            repository = VisitConfirmationRepository(session)
            queue = repository.get_or_create_daily_queue(day, doctor_id, queue_tag="")
            queue_id = int(queue.id)  # read before commit expires the instance
            session.commit()
        queue_ids.append(queue_id)
    except Exception as exc:  # noqa: BLE001
        errors.append(("visit_confirmation", exc))


def _limits_creator(engine, day, doctor_id, barrier, errors, queue_ids):
    try:
        with Session(engine) as session:
            barrier.wait(timeout=30)
            repository = QueueLimitsRepository(session)
            queue = repository.get_or_create_daily_queue(
                day=day, specialist_id=doctor_id, max_online_entries=15
            )
            session.flush()  # assign the PK before the commit expires it
            queue_id = int(queue.id)
            session.commit()
        queue_ids.append(queue_id)
    except Exception as exc:  # noqa: BLE001
        errors.append(("queue_limits", exc))


@pytest.mark.integration
def test_mixed_creators_serialize_on_one_canonical_scope(lock_parity_engine):
    """Four real creation paths, one fresh (day, doctor): one queue row,
    one shared id, zero exceptions."""

    from datetime import date

    day = date(2026, 9, 29)
    doctor_id = _seed_doctor(lock_parity_engine)

    errors: list[tuple[str, Exception]] = []
    queue_ids: list[int] = []
    barrier = threading.Barrier(4)

    workers = [
        lambda: _canonical_creator(
            lock_parity_engine, day, doctor_id, barrier, errors, queue_ids
        ),
        lambda: _crud_creator(
            lock_parity_engine, day, doctor_id, barrier, errors, queue_ids
        ),
        lambda: _visit_confirmation_creator(
            lock_parity_engine, day, doctor_id, barrier, errors, queue_ids
        ),
        lambda: _limits_creator(
            lock_parity_engine, day, doctor_id, barrier, errors, queue_ids
        ),
    ]
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        futures = [pool.submit(worker) for worker in workers]
        for future in futures:
            future.result(timeout=120)
    finally:
        # never wedge the suite on a stuck worker: every DB wait in the
        # workers is bounded by the engine timeouts, and the executor is
        # shut down without joining stragglers
        pool.shutdown(wait=False, cancel_futures=True)

    assert errors == [], f"concurrent creators failed: {errors!r}"
    assert len(queue_ids) == 4

    with Session(lock_parity_engine) as verify:
        rows = (
            verify.query(DailyQueue)
            .filter(
                DailyQueue.day == day,
                DailyQueue.specialist_id == doctor_id,
                DailyQueue.active.is_(True),
            )
            .all()
        )
        assert len(rows) == 1, (
            f"forked {len(rows)} active queues for one (day, doctor): "
            f"{[(r.id, r.queue_tag) for r in rows]}"
        )
        assert set(queue_ids) == {
            rows[0].id
        }, f"workers saw different queues: {sorted(queue_ids)} vs {rows[0].id}"


@pytest.mark.integration
def test_helper_scope_blocks_the_canonical_service_scope(lock_parity_engine):
    """The helper's advisory scope IS the canonical service's scope: while
    one session holds the HELPER lock, a second session running the REAL
    canonical ``queue_service.get_or_create_daily_queue`` blocks inside its
    own advisory acquisition until the first commits. Drift-proof: if the
    canonical service's key spelling ever diverges from the helper again
    (the historical GQL mismatch: doctor-before-day, trailing colon), this
    pin goes red — the contender would no longer wait."""

    from datetime import date

    day = date(2026, 9, 29)
    doctor_id = _seed_doctor(lock_parity_engine)

    holder = Session(lock_parity_engine)
    contender = Session(lock_parity_engine)
    created_queue_id: list[int] = []
    service_done = threading.Event()
    service_error: list[Exception] = []

    try:
        lock_daily_queue_creation(holder, day, doctor_id)

        def _contend():
            try:
                with contender:
                    queue = queue_service.get_or_create_daily_queue(
                        contender,
                        day=day,
                        specialist_id=doctor_id,
                        queue_tag=None,
                    )
                    queue_id = int(queue.id)
                    contender.commit()
                created_queue_id.append(queue_id)
            except Exception as exc:  # noqa: BLE001
                service_error.append(exc)
            finally:
                service_done.set()

        thread = threading.Thread(target=_contend, daemon=True)
        thread.start()
        # the canonical service is still blocked while the holder keeps
        # the helper scope: its own advisory acquisition must wait
        assert not service_done.wait(timeout=2.0), (
            "the canonical service acquired its scope without waiting — "
            "the helper key diverged from the canonical lock identity"
        )
        assert service_error == []
        holder.commit()  # releases the transaction-scoped advisory lock
        assert service_done.wait(
            timeout=60
        ), f"the canonical service never finished: {service_error!r}"
        thread.join(timeout=30)
        assert service_error == []
        assert len(created_queue_id) == 1
    finally:
        holder.rollback()
        contender.rollback()
        holder.close()
        contender.close()


@pytest.mark.integration
def test_regression_shape_without_parity_is_loud(lock_parity_engine):
    """The partial unique makes the unserialized interleaving LOUD: a
    second INSERT of the same (day, doctor, NULL tag) blocks behind the
    first writer's uncommitted unique index entry and fails with
    IntegrityError once that writer commits. This pins WHY the parity
    lock exists — the constraint is the safety net, the advisory lock is
    the clean-reuse fix; the previous behavior was an unhandled
    IntegrityError. The second INSERT runs in a background thread: in
    the SAME thread it would self-deadlock until the statement timeout
    (the writer's commit is the very next line of this test)."""

    from datetime import date

    day = date(2026, 9, 29)
    doctor_id = _seed_doctor(lock_parity_engine)

    def _plain_insert(session: Session) -> None:
        # ORM-level defaults (online_start_time & co.) do not apply to a
        # raw INSERT — the explicit columns keep the statement valid.
        session.execute(
            text(
                "INSERT INTO daily_queues "
                "(day, specialist_id, queue_tag, active, "
                "online_start_time, online_end_time, max_online_entries) "
                "VALUES (:day, :doctor, NULL, TRUE, '07:00', '09:00', 15)"
            ),
            {"day": day.isoformat(), "doctor": doctor_id},
        )

    writer_a = Session(lock_parity_engine)
    writer_b = Session(lock_parity_engine)
    outcome: dict[str, str] = {}
    try:
        _plain_insert(writer_a)  # holds the uncommitted unique index entry

        def _second_insert():
            try:
                _plain_insert(writer_b)  # blocks behind A's entry
                outcome["b"] = "inserted"
            except IntegrityError:
                outcome["b"] = "integrity"

        thread = threading.Thread(target=_second_insert, daemon=True)
        thread.start()
        # give the second writer time to queue behind the first's entry
        assert "b" not in outcome or outcome["b"] == "inserted"
        time.sleep(1.5)
        assert "b" not in outcome, (
            f"the second writer finished early: {outcome!r} — the proof "
            "assumes it blocks behind the uncommitted unique entry"
        )
        writer_a.commit()  # the conflict materializes for the second writer
        thread.join(timeout=60)
        assert (
            outcome.get("b") == "integrity"
        ), f"the unserialized duplicate insert did not fail loudly: {outcome!r}"
    finally:
        writer_a.rollback()
        writer_b.rollback()
        writer_a.close()
        writer_b.close()
