"""QD-2E — the surface-reuse ruling (PR review thread 3995689410, P1).

The FINAL business decision (supersedes the code comment that used to
live in ``morning_assignment.prepare_wizard_queue_assignment``):

- the doctor of a NEW record is NEVER derived from the existence of a
  queue with the same ``queue_tag``/day — the owner comes from the
  visit/service contract or from an explicitly configured QueueResource;
- one foreign queue is not a doctor assignment; several queues of
  different doctors sharing a tag are not an error per se;
- the tag-wide check of THIS patient's existing claim runs BEFORE a new
  number is issued (the claim coordinator, round-5 finding 3995689410's
  sibling 3995994584 — preserved verbatim).

Pinned matrix (morning + batch within their acting contracts):
- no claim + no valid owner -> the standard D-08 configuration error,
  no new record;
- no claim + an explicitly determined owner -> exactly that owner's
  queue;
- a compatible claim of this patient -> idempotent return of the
  previous result;
- a conflicting claim at another owner -> 409 semantics, no transfer and
  no second number;
- ambiguous existing claims -> an explicit error, never an arbitrary
  choice.
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

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_qd2e_surface_reuse.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-qd2e-surface-reuse-32c")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")

from app.crud.queue_owner_policy import QueueOwnerConfigurationError  # noqa: E402
from app.db.base_class import Base  # noqa: E402
from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import (  # noqa: E402
    DailyQueue,
    OnlineQueueEntry,
    QueueResource,
)
from app.models.patient import Patient  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit  # noqa: E402
from app.services.batch_patient_service import (  # noqa: E402
    BatchPatientService,
    EntryAction,
)
from app.services.morning_assignment import (  # noqa: E402
    MorningAssignmentClaimError,
    MorningAssignmentService,
)

# ─── Harness ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_qd2e_surface_reuse.db"
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
    return lambda: Session()


@pytest.fixture
def clean_db(db_engine):
    with db_engine.connect() as conn:
        for table in [
            "queue_entries",
            "daily_queues",
            "queue_resources",
            "visit_services",
            "visits",
            "services",
            "doctors",
            "patients",
            "users",
        ]:
            conn.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
        conn.commit()


def _make_user(session, unique: str, *, role: str = "Doctor") -> User:
    user = User(
        username=f"u_{unique}",
        full_name=f"User {unique}",
        email=f"u_{unique}@test.local",
        hashed_password="x",
        role=role,
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    return user


def _make_doctor(session, unique: str, *, specialty: str = "Cardiology") -> Doctor:
    user = _make_user(session, unique)
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    session.add(doctor)
    session.flush()
    return doctor


def _make_patient(session, unique: str, index: int) -> Patient:
    patient = Patient(
        last_name=f"Patient{index}",
        first_name="Test",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone=f"+9989100{index:02d}{unique[:4]}",
        email=f"p{index}_{unique}@test.local",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()
    return patient


def _make_visit(session, patient: Patient, *, doctor_id: int | None) -> Visit:
    unique = uuid.uuid4().hex[:8]
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor_id,
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


def _make_queue(
    session,
    *,
    tag: str,
    specialist_id: int | None = None,
    queue_resource_id: int | None = None,
) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_resource_id=queue_resource_id,
        queue_tag=tag,
        active=True,
    )
    session.add(queue)
    session.flush()
    return queue


def _make_entry(
    session,
    *,
    queue: DailyQueue,
    patient: Patient,
    number: int,
    status: str = "waiting",
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id,
        patient_name=f"{patient.last_name} {patient.first_name}",
        phone=patient.phone,
        source="online",
        status=status,
        queue_time=datetime.now(UTC),
    )
    session.add(entry)
    session.flush()
    return entry


# ─── Morning matrix ────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.queue
def test_morning_unowned_visit_never_borrows_an_existing_doctor_queue(
    session_factory, clean_db
):
    """no claim + no valid owner -> D-08. A queue opened for another
    doctor (same tag/day) is NOT an owner assignment for an unowned
    visit — the former surface_reuse borrowing is gone."""
    unique = uuid.uuid4().hex[:8]
    tag = f"cardio_{unique}"
    with session_factory() as session:
        foreign_doctor = _make_doctor(session, f"foreign_{unique}")
        patient = _make_patient(session, unique, 1)
        visit = _make_visit(session, patient, doctor_id=None)
        foreign_queue = _make_queue(session, tag=tag, specialist_id=foreign_doctor.id)
        session.commit()

        with pytest.raises(QueueOwnerConfigurationError) as excinfo:
            MorningAssignmentService(session).prepare_wizard_queue_assignment(
                visit, tag, date.today()
            )
        assert "D-08" in str(excinfo.value)

        session.rollback()
        # no new queue was created for the tag, no entry was issued
        queues = (
            session.query(DailyQueue).filter(DailyQueue.queue_tag == tag).all()
        )
        assert [q.id for q in queues] == [foreign_queue.id]
        entries = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == patient.id)
            .count()
        )
        assert entries == 0


@pytest.mark.unit
@pytest.mark.queue
def test_morning_owned_visit_gets_exactly_that_owners_queue(
    session_factory, clean_db
):
    """no claim + an explicitly determined owner -> the queue of exactly
    this owner, even when a foreign doctor queue already exists for the
    tag/day (multiple queues are not an error and are never consulted)."""
    unique = uuid.uuid4().hex[:8]
    tag = f"cardio_{unique}"
    with session_factory() as session:
        visit_doctor = _make_doctor(session, f"visit_{unique}")
        foreign_doctor = _make_doctor(session, f"other_{unique}", specialty="Dentistry")
        patient = _make_patient(session, unique, 2)
        visit = _make_visit(session, patient, doctor_id=visit_doctor.id)
        _make_queue(session, tag=tag, specialist_id=foreign_doctor.id)
        session.commit()

        prepared = MorningAssignmentService(session).prepare_wizard_queue_assignment(
            visit, tag, date.today()
        )

        assert prepared is not None
        assert prepared.create_handoff is not None
        owners_queue = prepared.create_handoff.daily_queue
        assert owners_queue.specialist_id == visit_doctor.id
        assert owners_queue.id is not None
        # the per-doctor queue contract (PR-26): a NEW queue for the
        # visit's doctor, never the foreign doctor's surface
        foreign_queue = (
            session.query(DailyQueue)
            .filter(
                DailyQueue.queue_tag == tag,
                DailyQueue.specialist_id == foreign_doctor.id,
            )
            .one()
        )
        assert owners_queue.id != foreign_queue.id


@pytest.mark.unit
@pytest.mark.queue
def test_morning_compatible_claim_returns_the_previous_result_idempotently(
    session_factory, clean_db
):
    """a compatible claim of this patient -> the idempotent return of
    the previous result (the tag-wide patient check preserved; no
    second number, queue_time/number untouched)."""
    unique = uuid.uuid4().hex[:8]
    tag = f"cardio_{unique}"
    with session_factory() as session:
        visit_doctor = _make_doctor(session, f"own_{unique}")
        patient = _make_patient(session, unique, 3)
        visit = _make_visit(session, patient, doctor_id=visit_doctor.id)
        owners_queue = _make_queue(session, tag=tag, specialist_id=visit_doctor.id)
        entry = _make_entry(session, queue=owners_queue, patient=patient, number=7)
        original_queue_time = entry.queue_time
        session.commit()

        prepared = MorningAssignmentService(session).prepare_wizard_queue_assignment(
            visit, tag, date.today()
        )

        assert prepared is not None
        assert prepared.assignment == {
            "queue_tag": tag,
            "queue_id": owners_queue.id,
            "number": 7,
            "status": "existing",
        }
        # no second number was issued
        count = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == patient.id)
            .count()
        )
        assert count == 1
        # queue_time untouched (sqlite returns the stored timestamp as
        # naive — compare the wall-clock value, not the tzinfo wrapper)
        assert entry.queue_time.replace(tzinfo=None) == original_queue_time.replace(
            tzinfo=None
        )


@pytest.mark.unit
@pytest.mark.queue
def test_morning_conflicting_claim_at_another_owner_is_rejected(
    session_factory, clean_db
):
    """a conflicting claim at another owner -> MorningAssignmentClaimError
    (409 semantics): no transfer, no second number."""
    unique = uuid.uuid4().hex[:8]
    tag = f"cardio_{unique}"
    with session_factory() as session:
        visit_doctor = _make_doctor(session, f"mine_{unique}")
        other_doctor = _make_doctor(session, f"theirs_{unique}", specialty="Dermatology")
        patient = _make_patient(session, unique, 4)
        visit = _make_visit(session, patient, doctor_id=visit_doctor.id)
        others_queue = _make_queue(session, tag=tag, specialist_id=other_doctor.id)
        _make_entry(session, queue=others_queue, patient=patient, number=3)
        session.commit()

        with pytest.raises(MorningAssignmentClaimError, match="different owner"):
            MorningAssignmentService(session).prepare_wizard_queue_assignment(
                visit, tag, date.today()
            )

        session.rollback()
        count = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == patient.id)
            .count()
        )
        assert count == 1  # the original entry only — no second number


@pytest.mark.unit
@pytest.mark.queue
def test_morning_ambiguous_claims_raise_an_explicit_error(
    session_factory, clean_db
):
    """ambiguous existing claims -> an explicit error, never an
    arbitrary choice (the claim coordinator conflict)."""
    unique = uuid.uuid4().hex[:8]
    tag = f"cardio_{unique}"
    with session_factory() as session:
        first_doctor = _make_doctor(session, f"one_{unique}")
        second_doctor = _make_doctor(session, f"two_{unique}", specialty="Neurology")
        patient = _make_patient(session, unique, 5)
        visit = _make_visit(session, patient, doctor_id=first_doctor.id)
        first_queue = _make_queue(session, tag=tag, specialist_id=first_doctor.id)
        second_queue = _make_queue(session, tag=tag, specialist_id=second_doctor.id)
        _make_entry(session, queue=first_queue, patient=patient, number=1)
        _make_entry(session, queue=second_queue, patient=patient, number=2)
        session.commit()

        with pytest.raises(MorningAssignmentClaimError, match="safely resolve"):
            MorningAssignmentService(session).prepare_wizard_queue_assignment(
                visit, tag, date.today()
            )

        session.rollback()
        count = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == patient.id)
            .count()
        )
        assert count == 2  # untouched — no arbitrary choice, no third entry


@pytest.mark.unit
@pytest.mark.queue
def test_morning_resource_axis_surface_reuse_is_preserved(
    session_factory, clean_db
):
    """The ONE sanctioned reuse: an existing RESOURCE queue of the tag
    (created by an explicitly configured QueueResource; the deactivation-
    resilient QD-2C surface) stays the surface for an unowned visit —
    no doctor is inferred, the number is issued on the resource queue."""
    unique = uuid.uuid4().hex[:8]
    tag = f"labx_{unique}"
    with session_factory() as session:
        resource_user = _make_user(session, f"res_{unique}", role="Resource")
        resource = QueueResource(
            code=f"labx_{unique}",
            queue_tag=tag,
            display_name=f"Lab {unique}",
            active=True,
        )
        session.add(resource)
        session.flush()
        resource_queue = _make_queue(
            session, tag=tag, queue_resource_id=resource.id
        )
        # the registry row is deactivated AFTER the queue was opened —
        # the QD-2C deactivation-resilient surface shape
        resource.active = False
        patient = _make_patient(session, unique, 6)
        visit = _make_visit(session, patient, doctor_id=None)
        session.commit()

        prepared = MorningAssignmentService(session).prepare_wizard_queue_assignment(
            visit, tag, date.today()
        )

        assert prepared is not None
        assert prepared.create_handoff is not None
        assert prepared.create_handoff.daily_queue.id == resource_queue.id
        assert prepared.create_handoff.daily_queue.specialist_id is None


@pytest.mark.unit
@pytest.mark.queue
def test_morning_different_patients_of_one_tag_both_get_numbers(
    session_factory, clean_db
):
    """The advisory (day, tag) lock may SERIALIZE different patients of
    the same tag — they must never receive a conflict purely from the
    tag coincidence (no false 409)."""
    unique = uuid.uuid4().hex[:8]
    tag = f"cardio_{unique}"
    with session_factory() as session:
        visit_doctor = _make_doctor(session, f"both_{unique}")
        first_patient = _make_patient(session, unique, 7)
        second_patient = _make_patient(session, unique, 8)
        first_visit = _make_visit(session, first_patient, doctor_id=visit_doctor.id)
        second_visit = _make_visit(session, second_patient, doctor_id=visit_doctor.id)
        session.commit()

        service = MorningAssignmentService(session)
        first_prepared = service.prepare_wizard_queue_assignment(
            first_visit, tag, date.today()
        )
        session.commit()
        second_prepared = service.prepare_wizard_queue_assignment(
            second_visit, tag, date.today()
        )

        assert first_prepared is not None and second_prepared is not None
        first_entry = _persist_handoff(session, first_prepared)
        second_entry = _persist_handoff(session, second_prepared)
        assert first_entry.number == 1
        assert second_entry.number == 2
        assert first_entry.queue_id == second_entry.queue_id


def _persist_handoff(session, prepared) -> OnlineQueueEntry:
    from app.services.queue_service import queue_service

    kwargs = dict(prepared.create_handoff.create_entry_kwargs)
    kwargs.pop("commit", None)
    entry = queue_service.create_queue_entry(session, **kwargs)
    session.commit()
    return entry


# ─── Batch matrix (within its acting contract) ─────────────────────────


@pytest.mark.unit
@pytest.mark.queue
def test_batch_never_adopts_a_single_existing_foreign_queue(
    session_factory, clean_db
):
    """no explicit owner + one existing foreign queue -> the owner still
    comes from the resolver contracts (the specialty match here), and
    the entry lands on THAT doctor's per-doctor queue — the former
    'single existing queue adoption' is gone."""
    unique = uuid.uuid4().hex[:8]
    tag = f"s01x_{unique}"
    with session_factory() as session:
        dentist = _make_doctor(session, f"dent_{unique}", specialty="Dentistry")
        cardiologist = _make_doctor(session, f"cardio_{unique}", specialty="Cardiology")
        patient = _make_patient(session, unique, 9)
        service = Service(
            code=f"S01X-{unique}",
            service_code=f"S01X-{unique}",
            name="S01 unresolved",
            price=100000.00,
            duration_minutes=30,
            active=True,
            requires_doctor=False,
            queue_tag=tag,
            is_consultation=False,
            allow_doctor_price_override=False,
        )
        session.add(service)
        session.flush()
        foreign_queue = _make_queue(session, tag=tag, specialist_id=dentist.id)
        session.commit()

        result = BatchPatientService(session)._create_entry(
            patient_id=patient.id,
            target_date=date.today(),
            action=EntryAction(
                action="create",
                specialty="cardiology",
                service_code=service.service_code,
            ),
        )

        assert result.status == "created"
        entry = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == result.id)
            .one()
        )
        queue = (
            session.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).one()
        )
        # the owner came from the specialty contract, NOT from the queue
        assert queue.specialist_id == cardiologist.id
        assert queue.id != foreign_queue.id


@pytest.mark.unit
@pytest.mark.queue
def test_batch_multiple_queues_of_one_tag_are_not_an_error_for_an_explicit_owner(
    session_factory, clean_db
):
    """Several doctor queues sharing a tag are NOT an error by themselves:
    with an explicit (eligible) owner the entry lands on exactly that
    owner's queue. The former 'ambiguous queue' ValueError is gone."""
    unique = uuid.uuid4().hex[:8]
    tag = f"multi_{unique}"
    with session_factory() as session:
        first = _make_doctor(session, f"m1_{unique}")
        second = _make_doctor(session, f"m2_{unique}", specialty="Neurology")
        third = _make_doctor(session, f"m3_{unique}", specialty="Dermatology")
        patient = _make_patient(session, unique, 10)
        service = Service(
            code=f"MULTI-{unique}",
            service_code=f"MULTI-{unique}",
            name="Multi consult",
            price=100000.00,
            duration_minutes=30,
            active=True,
            requires_doctor=True,
            queue_tag=tag,
            is_consultation=True,
            allow_doctor_price_override=False,
        )
        session.add(service)
        session.flush()
        _make_queue(session, tag=tag, specialist_id=first.id)
        _make_queue(session, tag=tag, specialist_id=second.id)
        session.commit()

        result = BatchPatientService(session)._create_entry(
            patient_id=patient.id,
            target_date=date.today(),
            action=EntryAction(
                action="create",
                specialty="cardiology",
                service_code=service.service_code,
                doctor_id=third.id,
            ),
        )

        assert result.status == "created"
        entry = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == result.id)
            .one()
        )
        queue = (
            session.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).one()
        )
        assert queue.specialist_id == third.id


@pytest.mark.unit
@pytest.mark.queue
def test_batch_no_owner_and_only_a_foreign_queue_is_d08(
    session_factory, clean_db
):
    """no claim + no valid owner (a foreign queue alone is NOT an owner)
    -> the standard D-08 configuration error, no new record."""
    unique = uuid.uuid4().hex[:8]
    tag = f"noown_{unique}"
    with session_factory() as session:
        dentist = _make_doctor(session, f"nd_{unique}", specialty="Dentistry")
        patient = _make_patient(session, unique, 11)
        service = Service(
            code=f"NOOWN-{unique}",
            service_code=f"NOOWN-{unique}",
            name="No owner consult",
            price=100000.00,
            duration_minutes=30,
            active=True,
            requires_doctor=False,
            queue_tag=tag,
            is_consultation=False,
            allow_doctor_price_override=False,
        )
        session.add(service)
        session.flush()
        _make_queue(session, tag=tag, specialist_id=dentist.id)
        session.commit()

        result = BatchPatientService(session)._create_entry(
            patient_id=patient.id,
            target_date=date.today(),
            action=EntryAction(
                action="create",
                specialty="neurology",
                service_code=service.service_code,
            ),
        )

        assert result.status == "error"
        assert "Конфигурационная ошибка владельца очереди" in (result.error or "")
        entries = (
            session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.patient_id == patient.id)
            .count()
        )
        assert entries == 0
