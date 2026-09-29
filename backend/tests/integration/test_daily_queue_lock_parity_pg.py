"""PostgreSQL proof for the doctor day-queue creation lock parity.

Follow-up to the #3511 review (owner verdict round): four legacy
creation paths ran the check-then-insert for a doctor's day queue
outside the canonical ``pg_advisory_xct_lock`` scope that
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

Proof (real workers against one PostgreSQL, mixed legacy + canonical
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

2. ``..._gql_untagged_scope_matches_canonical``: the scope the GraphQL
   untagged branch acquires (via the same helper) is IDENTICAL to the
   canonical service's scope — asserted by taking the helper's key in
   one session and the canonical service's real lock in another, then
   proving the second BLOCKS (the historical mismatched spelling did
   not: doctor-before-day plus a trailing colon hashed to a different
   advisory id).

Bounded waits (statement/lock timeouts) keep a regression loud and
fast instead of hanging the suite — the same regime as
test_cart_doctor_eligibility_lock_pg.py.
"""

from __future__ import annotations

import os
import threading
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
                # bounded waits keep a REGRESSION loud and fast instead of
                # hanging the suite (mirrors the cart eligibility lock PG
                # proof).
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
            session.commit()
        queue_ids.append(queue.id)
    except Exception as exc:  # noqa: BLE001 — the proof collects every failure
        errors.append(("canonical", exc))


def _crud_creator(engine, day, doctor_id, barrier, errors, queue_ids):
    try:
        barrier.wait(timeout=30)
        # the queue_batch path: commits internally, exactly as in prod
        queue = crud_online_queue.get_or_create_daily_queue(
            Session(engine), day, doctor_id, queue_tag=None
        )
        queue_ids.append(queue.id)
    except Exception as exc:  # noqa: BLE001
        errors.append(("crud/queue_batch", exc))


def _visit_confirmation_creator(engine, day, doctor_id, barrier, errors, queue_ids):
    try:
        with Session(engine) as session:
            barrier.wait(timeout=30)
            repository = VisitConfirmationRepository(session)
            queue = repository.get_or_create_daily_queue(day, doctor_id, queue_tag="")
            session.commit()
        queue_ids.append(queue.id)
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
            session.commit()
        queue_ids.append(queue.id)
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
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker) for worker in workers]
        for future in futures:
            future.result(timeout=90)

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
                queue = queue_service.get_or_create_daily_queue(
                    contender,
                    day=day,
                    specialist_id=doctor_id,
                    queue_tag=None,
                )
                created_queue_id.append(queue.id)
                contender.commit()
            except Exception as exc:  # noqa: BLE001
                service_error.append(exc)
            finally:
                service_done.set()

        thread = threading.Thread(target=_contend)
        thread.start()
        # the canonical service is still blocked while the holder keeps
        # the helper scope: its own advisory acquisition must wait
        assert not service_done.wait(timeout=1.5), (
            "the canonical service acquired its scope without waiting — "
            "the helper key diverged from the canonical lock identity"
        )
        assert service_error == []
        holder.commit()  # releases the transaction-scoped advisory lock
        assert service_done.wait(
            timeout=30
        ), f"the canonical service never finished: {service_error!r}"
        thread.join(timeout=10)
        assert service_error == []
        assert len(created_queue_id) == 1
    finally:
        holder.close()
        contender.close()


@pytest.mark.integration
def test_regression_shape_without_parity_is_loud(lock_parity_engine):
    """The partial unique makes the unserialized interleaving LOUD: two
    plain check-then-insert writers for the same (day, doctor, NULL tag)
    cannot both commit. This pins WHY the parity lock exists — the
    constraint is the safety net, the advisory lock is the clean-reuse
    fix; the previous behavior was an unhandled IntegrityError."""

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
    try:
        _plain_insert(writer_a)  # holds the uncommitted unique index entry
        _plain_insert(writer_b)  # blocks on A's entry until A commits
        writer_a.commit()
        with pytest.raises(IntegrityError):
            writer_b.commit()
    finally:
        writer_a.rollback()
        writer_b.rollback()
        writer_a.close()
        writer_b.close()
