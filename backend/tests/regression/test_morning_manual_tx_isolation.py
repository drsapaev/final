"""MORNINGMAN-BE-001 (audit #3892, group 22) — manual morning batch transaction isolation.

``manual_assignment_for_visits`` loops visit_ids in ONE shared SQLAlchemy
Session and issues ONE commit after the entire loop. Two divergences:

* **Case A (false failure + persisted partial queue):** the lower-level
  ``_assign_queues_for_visit`` re-raises ``QueueOwnerConfigurationError``
  WITHOUT rollback ("транзакцию откатит вызывающая поверхность") — but the
  calling surface catches the exception, reports ``success:false`` and the
  unconditional final commit PERSISTS the partially staged queue entries
  of the failed visit.
* **Case B (false success + lost write):** a later visit's generic tag
  failure makes the lower-level service call ``self.db.rollback()`` (a
  ROOT rollback) — silently destroying earlier visits' staged writes that
  were already reported as ``success:true``.

Fix contract (audit repair direction: per-visit transaction boundary):
per-visit SAVEPOINT isolates each visit's staging (a failure rolls back
only that visit), and a per-visit commit makes each reported success
durable BEFORE the next visit runs.

Run: pytest backend/tests/regression/test_morning_manual_tx_isolation.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_morning_manual_tx.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-morning-tx-iso-32")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")

from app.crud.queue_owner_policy import QueueOwnerConfigurationError  # noqa: E402
from app.db.base_class import Base  # noqa: E402
from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit, VisitService  # noqa: E402
from app.services.morning_assignment import MorningAssignmentService  # noqa: E402


@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_morning_manual_tx.db"
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
            conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()


def _seed_visit(session: object, *, tags: list[str]) -> int:
    """Create a confirmed visit with one service+DailyQueue per queue tag."""
    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"doctor_{unique}", full_name="Dr", email=f"d_{unique}@t.local",
        hashed_password="x", role="Doctor", is_active=True, is_superuser=False,
        must_change_password=False, created_at=datetime.now(UTC),
    )
    session.add(doctor_user)
    session.flush()
    doctor = Doctor(user_id=doctor_user.id, specialty="Cardiology", active=True)
    session.add(doctor)
    session.flush()
    patient = Patient(
        last_name="P", first_name="Patient", birth_date=date(1990, 1, 1),
        sex="M",
        # synthetic unique phone — no real-looking numbers in fixtures
        phone="+998900000000",
        email=f"p_{unique}@t.local",
        created_at=datetime.now(UTC), is_deleted=False,
    )
    session.add(patient)
    session.flush()
    visit = Visit(
        patient_id=patient.id, doctor_id=doctor.id, status="confirmed",
        visit_date=date.today(), visit_time="10:00", discount_mode="none",
        department="cardiology", confirmation_token=f"tok-{unique}",
        confirmation_channel="telegram", confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC), created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()
    for tag in tags:
        svc = Service(
            code=f"SVC_{unique}_{tag}", name="Service", price=10000,
            duration_minutes=30, active=True, requires_doctor=True,
            queue_tag=tag, is_consultation=True,
            allow_doctor_price_override=False,
        )
        session.add(svc)
        session.flush()
        session.add(
            DailyQueue(
                day=date.today(), specialist_id=doctor_user.id,
                queue_tag=tag, active=True,
            )
        )
        session.flush()
        session.add(
            VisitService(
                visit_id=visit.id, service_id=svc.id, code=svc.code,
                name=svc.name, qty=1, price=svc.price, currency="UZS",
            )
        )
        session.flush()
    session.commit()
    return visit.id


def _persisted_entries(session_factory, *, queue_tag: str) -> int:
    """Count queue entries PERSISTED (fresh session — committed state only)."""
    session = session_factory()
    try:
        return (
            session.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(DailyQueue.queue_tag == queue_tag)
            .count()
        )
    finally:
        session.close()


def _visit_status(session_factory, visit_id: int) -> str:
    session = session_factory()
    try:
        return session.query(Visit).filter(Visit.id == visit_id).first().status
    finally:
        session.close()


@pytest.mark.unit
class TestManualAssignmentTxIsolation:
    def test_owner_error_does_not_persist_partial_queue(
        self, monkeypatch, session_factory, clean_db
    ):
        """Case A: tag A stages an entry, tag Z raises
        QueueOwnerConfigurationError. The visit must be reported failed AND
        tag A's partial staging must NOT be persisted."""
        setup = session_factory()
        tag_a, tag_z = f"casea_a_{uuid.uuid4().hex[:6]}", f"casea_z_{uuid.uuid4().hex[:6]}"
        visit_id = _seed_visit(setup, tags=[tag_a, tag_z])
        setup.close()

        original = MorningAssignmentService._assign_single_queue

        def wrapped(self, visit, queue_tag, target_date, *, source="morning_assignment"):
            if queue_tag == tag_z:
                raise QueueOwnerConfigurationError(
                    "synthetic: queue owner absent for tag Z"
                )
            return original(self, visit, queue_tag, target_date, source=source)

        monkeypatch.setattr(MorningAssignmentService, "_assign_single_queue", wrapped)

        from app.repositories.morning_assignment_api_repository import (
            MorningAssignmentApiRepository,
        )
        from app.services.morning_assignment_api_service import (
            MorningAssignmentApiService,
        )

        session = session_factory()
        api_service = MorningAssignmentApiService(
            db=session, repository=MorningAssignmentApiRepository(session)
        )
        result = api_service.manual_assignment_for_visits(
            visit_ids=[visit_id], force=False
        )
        session.close()

        entry = result["results"][0]
        assert entry["success"] is False, entry

        # The visit reported failure — NO partially staged queue entry may
        # be persisted (RED on main: tag A's staged entry IS committed).
        assert _persisted_entries(session_factory, queue_tag=tag_a) == 0

    def test_later_visit_failure_keeps_earlier_reported_success(
        self, monkeypatch, session_factory, clean_db
    ):
        """Case B: V1 assigns its queue and is reported success; V2's tag
        fails generically (lower-level root rollback). V1's persisted
        queue entry and activation must SURVIVE."""
        setup = session_factory()
        tag_v1 = f"caseb_v1_{uuid.uuid4().hex[:6]}"
        tag_v2 = f"caseb_v2_{uuid.uuid4().hex[:6]}"
        v1 = _seed_visit(setup, tags=[tag_v1])
        v2 = _seed_visit(setup, tags=[tag_v2])
        setup.close()

        original = MorningAssignmentService._assign_single_queue

        def wrapped(self, visit, queue_tag, target_date, *, source="morning_assignment"):
            if queue_tag == tag_v2:
                raise RuntimeError("synthetic: flush failure on tag V2")
            return original(self, visit, queue_tag, target_date, source=source)

        monkeypatch.setattr(MorningAssignmentService, "_assign_single_queue", wrapped)

        from app.repositories.morning_assignment_api_repository import (
            MorningAssignmentApiRepository,
        )
        from app.services.morning_assignment_api_service import (
            MorningAssignmentApiService,
        )

        session = session_factory()
        api_service = MorningAssignmentApiService(
            db=session, repository=MorningAssignmentApiRepository(session)
        )
        result = api_service.manual_assignment_for_visits(
            visit_ids=[v1, v2], force=False
        )
        session.close()

        by_id = {r["visit_id"]: r for r in result["results"]}
        assert by_id[v1]["success"] is True, by_id[v1]
        assert by_id[v2]["success"] is False, by_id[v2]

        # V1 was reported success — its queue entry and activation must be
        # durably persisted (RED on main: V2's root rollback destroyed them).
        assert _persisted_entries(session_factory, queue_tag=tag_v1) == 1
        assert _visit_status(session_factory, v1) == "open"
