"""PostgreSQL proof for tag-wide visit-confirmation claim serialization."""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.clinic import clinic_today
from app.db.base_class import Base
from app.models import (  # noqa: F401 - register the complete metadata
    Doctor,
    Patient,
    Service,
    User,
    Visit,
    VisitService,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)


@pytest.fixture
def confirmation_claim_engine():
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("tag claim concurrency proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_confirmation_claim_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=10000 -clock_timeout=8000"
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
@pytest.mark.confirmation
def test_different_visits_cannot_create_parallel_claims_for_same_patient_tag(
    confirmation_claim_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = sessionmaker(
        bind=confirmation_claim_engine,
        autocommit=False,
        autoflush=False,
    )

    with Session(confirmation_claim_engine) as seed:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            username=f"confirm_claim_{suffix}",
            hashed_password="!disabled:test",
            role="doctor",
            is_active=True,
        )
        seed.add(user)
        seed.flush()
        doctor = Doctor(
            user_id=user.id,
            specialty=f"confirm_claim_{suffix}",
            active=True,
        )
        patient = Patient(
            last_name="SYNTHETIC-Claim",
            first_name="SYNTHETIC-Patient",
        )
        seed.add_all([doctor, patient])
        seed.flush()
        queue_tag = f"claim_{suffix}"
        service = Service(
            code=f"CC-{suffix}",
            name="SYNTHETIC confirmation claim",
            price=0,
            active=True,
            requires_doctor=True,
            doctor_id=doctor.id,
            queue_tag=queue_tag,
        )
        seed.add(service)
        seed.flush()
        queue = DailyQueue(
            day=clinic_today(seed),
            specialist_id=doctor.id,
            queue_tag=queue_tag,
            active=True,
        )
        seed.add(queue)
        seed.flush()
        visits = [
            Visit(
                patient_id=patient.id,
                doctor_id=doctor.id,
                visit_date=queue.day,
                status="confirmed",
            )
            for _ in range(2)
        ]
        seed.add_all(visits)
        seed.flush()
        seed.add_all(
            [
                VisitService(
                    visit_id=visit.id,
                    service_id=service.id,
                    code=service.code,
                    name=service.name,
                )
                for visit in visits
            ]
        )
        seed.commit()
        visit_ids = [visit.id for visit in visits]
        patient_id = patient.id
        queue_id = queue.id

    # Observe the shared coordinator boundary rather than relying on two
    # threads happening to overlap. Worker A pauses after the transaction lock
    # is acquired but before the resolver can query. Worker B must block inside
    # the same lock and cannot return from it until A commits.
    from app.services import queue_claim_service as claim_module

    thread_role = threading.local()
    a_after_lock_before_query = threading.Event()
    release_a_to_query = threading.Event()
    a_ready_to_commit = threading.Event()
    allow_a_commit = threading.Event()
    b_lock_attempted = threading.Event()
    b_lock_returned = threading.Event()
    b_after_lock_before_query = threading.Event()
    b_backend_pid_ready = threading.Event()
    b_backend_pid: list[int] = []

    real_lock = claim_module.lock_queue_tag_claim_scope

    def observed_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        role = getattr(thread_role, "value", None)
        if role == "b":
            b_lock_attempted.set()
        real_lock(db, queue_tag, day)
        if role == "a":
            a_after_lock_before_query.set()
            if not release_a_to_query.wait(timeout=10):
                raise AssertionError("worker A was not released to query the claim")
        elif role == "b":
            b_lock_returned.set()
            b_after_lock_before_query.set()

    monkeypatch.setattr(
        claim_module,
        "lock_queue_tag_claim_scope",
        observed_lock,
    )

    def confirm(role: str, visit_id: int) -> tuple[str, int]:
        thread_role.value = role
        with session_factory() as session:
            if role == "b":
                b_backend_pid.append(
                    int(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
                )
                b_backend_pid_ready.set()
            visit = session.get(Visit, visit_id)
            assert visit is not None
            try:
                VisitConfirmationService(
                    session
                )._assign_queue_numbers_on_confirmation(visit)
                if role == "a":
                    a_ready_to_commit.set()
                    if not allow_a_commit.wait(timeout=10):
                        raise AssertionError("worker A was not released to commit")
                session.commit()
                return "created", visit_id
            except VisitConfirmationDomainError as error:
                session.rollback()
                return "conflict", error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(confirm, "a", visit_ids[0])
        assert a_after_lock_before_query.wait(timeout=10)

        future_b = executor.submit(confirm, "b", visit_ids[1])
        assert b_backend_pid_ready.wait(timeout=10)
        assert b_lock_attempted.wait(timeout=10)

        try:
            # A owns the PostgreSQL xact lock and has not queried or written
            # the claim yet. B's lock call cannot return, so B cannot execute
            # the tag-wide claim query.
            waiting_on_advisory = False
            deadline = time.monotonic() + 10
            with confirmation_claim_engine.connect() as monitor:
                while time.monotonic() < deadline:
                    waiting_on_advisory = bool(
                        monitor.execute(
                            text(
                                "SELECT wait_event_type = 'Lock' "
                                "AND lower(COALESCE(wait_event, '')) "
                                "LIKE 'advisory%' "
                                "FROM pg_stat_activity WHERE pid = :pid"
                            ),
                            {"pid": b_backend_pid[0]},
                        ).scalar_one_or_none()
                    )
                    if waiting_on_advisory:
                        break
                    time.sleep(0.02)
            assert waiting_on_advisory is True
            assert not b_lock_returned.is_set()
            assert not b_after_lock_before_query.is_set()

            release_a_to_query.set()
            assert a_ready_to_commit.wait(timeout=10)

            # The allocator only flushed A's entry.  commit=False is part of
            # the contract: the transaction lock must still be held until the
            # caller commits the complete confirmation transaction.
            assert not b_lock_returned.wait(timeout=0.5)
            assert not b_after_lock_before_query.is_set()
        finally:
            release_a_to_query.set()
            allow_a_commit.set()

        outcome_a = future_a.result(timeout=15)
        assert b_lock_returned.wait(timeout=10)
        assert b_after_lock_before_query.wait(timeout=10)
        outcome_b = future_b.result(timeout=15)

    assert outcome_a == ("created", visit_ids[0])
    assert outcome_b == ("conflict", 409)

    with Session(confirmation_claim_engine) as verify:
        entries = (
            verify.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(("waiting", "called")),
            )
            .all()
        )
        assert len(entries) == 1
        assert entries[0].visit_id in visit_ids
