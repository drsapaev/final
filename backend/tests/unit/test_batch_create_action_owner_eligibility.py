"""QD-2E — batch create-action owner eligibility (PR review thread 3995711803, P2).

The specialty fallback (and the explicit assignment sources feeding
``_resolve_create_action_daily_queue``) must apply the COMPLETE shared
``eligible_real_doctor`` contract — an active Doctor whose linked User is
missing or inactive, an inactive Doctor and an internal 'Resource' account
must never become the owner of a new doctor-owned queue. Before the fix
``is_internal_resource_doctor()`` only rejected internal roles and returned
``False`` when no user existed, so an active Doctor with an inactive/missing
User silently owned the queue nobody could operate.

Every refusal is proven to leave NO orphan behind: no DailyQueue row for
the tag, no OnlineQueueEntry for the patient (the fail-closed raise happens
before any queue row is written).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.service import Service
from app.models.user import User
from app.services.batch_patient_service import BatchPatientService, EntryAction

_TAG = "cardiology-elig"
_SPECIALTY = "cardiology"


@pytest.fixture
def eligible_patient(test_patient):
    return test_patient


def _make_user(db_session, *, username: str, role: str = "Doctor", active: bool = True) -> User:
    user = User(
        username=username,
        email=f"{username}@elig.test",
        full_name=username,
        hashed_password="test-hash",
        role=role,
        is_active=active,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(
    db_session,
    *,
    user_id: int | None,
    specialty: str = _SPECIALTY,
    active: bool = True,
) -> Doctor:
    doctor = Doctor(user_id=user_id, specialty=specialty, active=active)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _make_service(db_session, *, code: str, doctor_id: int | None) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"Service {code}",
        active=True,
        queue_tag=_TAG,
        doctor_id=doctor_id,
        requires_doctor=doctor_id is not None,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_action(service: Service, *, doctor_id: int | None = None) -> EntryAction:
    return EntryAction(
        action="create",
        specialty=_SPECIALTY,
        service_code=service.service_code,
        doctor_id=doctor_id,
    )


def _assert_refusal_left_no_orphans(db_session, patient_id: int, result) -> None:
    """The refusal must be honest: an error item, no queue row for the
    tag, no queue-entry for the patient."""
    assert result.status == "error"
    assert result.id == 0
    assert "Конфигурационная ошибка владельца очереди" in (result.error or "")
    assert (
        db_session.query(DailyQueue).filter(DailyQueue.queue_tag == _TAG).count() == 0
    )
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == patient_id)
        .count()
        == 0
    )


@pytest.mark.unit
@pytest.mark.queue
def test_specialty_fallback_rejects_active_doctor_with_inactive_user(
    db_session, eligible_patient
):
    user = _make_user(db_session, username="elig_inactive_user", active=False)
    _make_doctor(db_session, user_id=user.id)
    service = _make_service(db_session, code="ELIG-1", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_specialty_fallback_rejects_active_doctor_without_user_link(
    db_session, eligible_patient
):
    _make_doctor(db_session, user_id=None)
    service = _make_service(db_session, code="ELIG-2", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_specialty_fallback_rejects_internal_resource_account(
    db_session, eligible_patient
):
    user = _make_user(db_session, username="elig_resource", role="Resource")
    _make_doctor(db_session, user_id=user.id, specialty=_SPECIALTY)
    service = _make_service(db_session, code="ELIG-3", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_specialty_fallback_rejects_inactive_doctor(db_session, eligible_patient):
    user = _make_user(db_session, username="elig_inactive_doc")
    _make_doctor(db_session, user_id=user.id, active=False)
    service = _make_service(db_session, code="ELIG-4", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_explicit_action_doctor_with_inactive_user_fails_closed(
    db_session, eligible_patient
):
    user = _make_user(db_session, username="elig_explicit", active=False)
    doctor = _make_doctor(db_session, user_id=user.id)
    service = _make_service(db_session, code="ELIG-5", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service, doctor_id=doctor.id),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_service_doctor_with_inactive_user_fails_closed(
    db_session, eligible_patient
):
    user = _make_user(db_session, username="elig_svc_doctor", active=False)
    doctor = _make_doctor(db_session, user_id=user.id)
    service = _make_service(db_session, code="ELIG-6", doctor_id=doctor.id)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_tags_single_service_doctor_with_inactive_user_fails_closed(
    db_session, eligible_patient
):
    """The service-doctor branch of the resolver: the tag's single
    distinct service doctor is ineligible (inactive User) — a stale
    catalog assignment fails closed, it does not silently build a queue."""
    user = _make_user(db_session, username="elig_single_svc", active=False)
    doctor = _make_doctor(db_session, user_id=user.id)
    # the action's own service carries no doctor; ANOTHER active service
    # of the tag carries the single (ineligible) doctor
    _make_service(db_session, code="ELIG-7-CARRIER", doctor_id=doctor.id)
    service = _make_service(db_session, code="ELIG-7", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_refusal_left_no_orphans(db_session, eligible_patient.id, result)


@pytest.mark.unit
@pytest.mark.queue
def test_positive_control_valid_doctor_via_service_is_still_selected(
    db_session, eligible_patient
):
    """Positive control: an acting valid doctor named by the agreed
    assignment source (service.doctor_id, active user) is still
    selected — the eligibility gate must not over-block."""
    user = _make_user(db_session, username="elig_positive")
    doctor = _make_doctor(db_session, user_id=user.id)
    service = _make_service(db_session, code="ELIG-8", doctor_id=doctor.id)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    assert result.status == "created"
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == result.id)
        .first()
    )
    assert entry is not None
    queue = db_session.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
    assert queue is not None
    assert queue.specialist_id == doctor.id
    assert queue.queue_tag == _TAG


@pytest.mark.unit
@pytest.mark.queue
def test_positive_control_valid_doctor_via_specialty_is_still_selected(
    db_session, eligible_patient
):
    """Positive control: the specialty fallback still picks the single
    eligible real doctor when every shared-contract condition holds."""
    user = _make_user(db_session, username="elig_positive_spec")
    doctor = _make_doctor(db_session, user_id=user.id)
    service = _make_service(db_session, code="ELIG-9", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    assert result.status == "created"
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == result.id)
        .first()
    )
    assert entry is not None
    queue = db_session.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
    assert queue is not None
    assert queue.specialist_id == doctor.id
    assert queue.queue_tag == _TAG


# ===================== review round 4 — resource axis first (P2) =============

_RESOURCE_TAG = "elig-lab"


def _make_registry_resource(db_session) -> QueueResource:
    resource = QueueResource(
        code=_RESOURCE_TAG,
        queue_tag=_RESOURCE_TAG,
        display_name="ELIG Lab",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def _make_resource_service(db_session, *, code: str, doctor_id: int | None) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"Lab {code}",
        active=True,
        queue_tag=_RESOURCE_TAG,
        doctor_id=doctor_id,
        requires_doctor=doctor_id is not None,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _assert_created_on_resource_axis(
    db_session, patient_id: int, result, resource: QueueResource
) -> None:
    """The entry was created on the RESOURCE axis: the queue is
    resource-owned (specialist NULL, queue_resource_id set), never
    doctor-owned by the stale/invalid doctor binding."""
    assert result.status == "created", result.error
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == result.id)
        .first()
    )
    assert entry is not None
    queue = db_session.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
    assert queue is not None
    assert queue.queue_resource_id == resource.id
    assert queue.specialist_id is None
    assert queue.queue_tag == _RESOURCE_TAG


@pytest.mark.unit
@pytest.mark.queue
def test_resource_tag_with_stale_service_doctor_creates_on_resource_axis(
    db_session, eligible_patient
):
    """Review round 4 (P2): the resource path is decided BEFORE the doctor
    guard. An ACTIVE QueueResource tag whose service still carries a
    stale doctor binding (a deactivated owner) must create the entry on
    the RESOURCE axis: the canonical get_or_create_daily_queue IGNORES
    specialist_id for a registry tag, so an ineligible doctor that never
    owns the resulting queue must not fail the whole operation. Before
    the fix the early guard rejected the batch create as a configuration
    error before the resource routing was ever consulted."""
    stale_user = _make_user(
        db_session, username="elig_stale_resource_doc", active=False
    )
    stale_doctor = _make_doctor(db_session, user_id=stale_user.id)
    resource = _make_registry_resource(db_session)
    service = _make_resource_service(
        db_session, code="ELIG-RES-1", doctor_id=stale_doctor.id
    )

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service),
    )

    _assert_created_on_resource_axis(
        db_session, eligible_patient.id, result, resource
    )


@pytest.mark.unit
@pytest.mark.queue
def test_resource_tag_with_explicit_action_doctor_creates_on_resource_axis(
    db_session, eligible_patient
):
    """Review round 4 (P2), the action-side variant: an unnecessary
    action.doctor_id pointing at an ineligible doctor must not fail a
    resource-tagged create either — the resource is the real owner."""
    stale_user = _make_user(db_session, username="elig_stale_action_doc", active=False)
    stale_doctor = _make_doctor(db_session, user_id=stale_user.id)
    resource = _make_registry_resource(db_session)
    service = _make_resource_service(db_session, code="ELIG-RES-2", doctor_id=None)

    result = BatchPatientService(db_session)._create_entry(
        patient_id=eligible_patient.id,
        target_date=date.today(),
        action=_create_action(service, doctor_id=stale_doctor.id),
    )

    _assert_created_on_resource_axis(
        db_session, eligible_patient.id, result, resource
    )
