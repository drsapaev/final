from __future__ import annotations

import threading
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.services.queue_service import queue_service

pytestmark = pytest.mark.postgres_pilot


def _make_concurrency_queue(test_db, suffix: str) -> tuple[int, str, int, int]:
    SessionLocal = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        user = User(
            username=f"concurrency_user_{suffix}",
            email=f"concurrency_{suffix}@test.local",
            full_name=f"Concurrency {suffix}",
            hashed_password="hashed",
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

        doctor = Doctor(
            user_id=user_id,
            specialty="cardiology",
            active=True,
        )
        session.add(doctor)
        session.flush()
        doctor_id = doctor.id

        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor_id,
            queue_tag=f"cardiology_{suffix}",
            active=True,
        )
        session.add(queue)
        session.flush()
        queue_id = queue.id
        queue_tag = queue.queue_tag

        first_entry = OnlineQueueEntry(
            queue_id=queue_id,
            number=1,
            patient_name="Baseline",
            source="online",
            status="waiting",
        )
        session.add(first_entry)
        session.commit()
        return queue_id, queue_tag, doctor_id, user_id
    finally:
        session.close()


@pytest.mark.integration
@pytest.mark.queue
def test_parallel_allocator_read_paths_observe_same_next_number_candidate(test_db):
    queue_id, queue_tag, doctor_id, user_id = _make_concurrency_queue(
        test_db,
        suffix=uuid.uuid4().hex[:8],
    )
    SessionLocal = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def service_worker() -> None:
        session = SessionLocal()
        try:
            queue = session.query(DailyQueue).filter(DailyQueue.id == queue_id).one()
            barrier.wait()
            number = queue_service.get_next_queue_number(
                session,
                daily_queue=queue,
                queue_tag=queue_tag,
            )
            with lock:
                results.append(number)
        finally:
            session.close()

    def sql_worker() -> None:
        session = SessionLocal()
        try:
            barrier.wait()
            number = session.execute(
                text(
                    "SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid"
                ),
                {"qid": queue_id},
            ).scalar_one()
            with lock:
                results.append(number)
        finally:
            session.close()

    try:
        threads = [
            threading.Thread(target=service_worker),
            threading.Thread(target=sql_worker),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(results) == [2, 2]
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == queue_id).delete()
            cleanup.query(DailyQueue).filter(DailyQueue.id == queue_id).delete()
            cleanup.query(Doctor).filter(Doctor.id == doctor_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


@pytest.mark.integration
@pytest.mark.queue
def test_parallel_duplicate_join_read_phase_can_observe_no_existing_entry(test_db):
    queue_id, _queue_tag, doctor_id, user_id = _make_concurrency_queue(
        test_db,
        suffix=uuid.uuid4().hex[:8],
    )
    SessionLocal = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    barrier = threading.Barrier(2)
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        session = SessionLocal()
        try:
            queue = session.query(DailyQueue).filter(DailyQueue.id == queue_id).one()
            barrier.wait()
            existing_entry, _reason = queue_service.check_uniqueness(
                session,
                queue,
                phone="+998903333333",
                source="online",
            )
            with lock:
                results.append(existing_entry is None)
        finally:
            session.close()

    try:
        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert results == [True, True]
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == queue_id).delete()
            cleanup.query(DailyQueue).filter(DailyQueue.id == queue_id).delete()
            cleanup.query(Doctor).filter(Doctor.id == doctor_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
