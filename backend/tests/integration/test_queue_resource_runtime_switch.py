"""QD-2C (queue resource runtime switch) — stage C regression pins.

Stage C of the QD-2 staged rollout (architecture FINAL, 2026-09-07):
stages A (0058 registry + dual-owner columns) and B (0059 lab/ecg
seeds + backfill) landed; THIS suite pins the runtime switch —
runtime paths start PREFERRING the resource axis for a doctorless
tag. The switch is CONDITIONAL on live registry data
(``resolve_tag_resource``: exact-tag, active row only), so:

- WITH a registry row (lab/ecg today): the queue for the tag is ONE
  routing surface per day — tag-first unification returns the
  existing queue (bridged or resource-owned) instead of forking a
  parallel per-doctor queue; a NEW queue is resource-owned
  (specialist NULL, queue_resource_id, caps from the registry row);
  the synthetic Doctor is no longer resolved (the QD-2E retirement
  path); numbering floors come from the registry row.
- WITHOUT a registry row (general/stomatology/doctor specialties,
  empty test DBs, the CI alembic chain): every path keeps its legacy
  behavior byte-identical (synthetic fallbacks, per-doctor queues,
  the ValueError-on-missing-doctor contract).

Output contract: ``DailyQueueOut`` grows owner_kind /
owner_display_name / queue_resource (axis derived from
queue_resource_id); the GQL ``DailyQueueType`` specialist field
becomes NULLABLE with queue_resource_id + owner_kind.

NOT in scope (later stages): the XOR/uniqueness contract (QD-2D),
retiring the synthetic pairs (QD-2E — the legacy fallback paths stay
functional until then).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.crud import online_queue as crud_queue
from app.crud import queue_resource_routing
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.service import Service
from app.models.user import User
from app.schemas.online_queue import DailyQueueOut
from app.services.queue_service import queue_service

# non-secret placeholder mirroring the 0055 seed marker — this suite
# performs no password verification
_DISABLED_HASH = "!disabled:queue-resource"
_DAY = date(2026, 9, 7)


# ===================== helpers =====================


def _make_user(db_session: Session, *, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=_DISABLED_HASH,
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(
    db_session: Session,
    *,
    user_id: int,
    specialty: str,
    active: bool = True,
) -> Doctor:
    doctor = Doctor(user_id=user_id, specialty=specialty, active=active)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _make_resource(
    db_session: Session,
    *,
    code: str,
    queue_tag: str,
    display_name: str = "Ресурс очереди",
    active: bool = True,
    start_number_online: int = 1,
    max_online_per_day: int = 15,
) -> QueueResource:
    resource = QueueResource(
        code=code,
        queue_tag=queue_tag,
        display_name=display_name,
        active=active,
        start_number_online=start_number_online,
        max_online_per_day=max_online_per_day,
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def _make_queue(
    db_session: Session,
    *,
    day: date = _DAY,
    specialist_id: int | None,
    queue_tag: str | None,
    active: bool = True,
    queue_resource_id: int | None = None,
) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=specialist_id,
        queue_resource_id=queue_resource_id,
        queue_tag=queue_tag,
        active=active,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _make_service(
    db_session: Session,
    *,
    queue_tag: str | None,
    name: str = "Услуга",
    active: bool = True,
) -> Service:
    service = Service(name=name, queue_tag=queue_tag, active=active, price=1000)
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _tag_queues(db_session: Session, day: date, tag: str) -> list[DailyQueue]:
    return (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == day, DailyQueue.queue_tag == tag)
        .order_by(DailyQueue.id.asc())
        .all()
    )


def _scope_morning_world(db_session: Session, *keep_tags: str) -> None:
    """Pre-existing suite isolation leak: some earlier tests COMMIT
    Service rows into the session-scoped file DB (e.g. a leaked
    'cardiology_common' service), which inflates the
    ensure_daily_queues_for_all_tags tag set. Scope the morning
    pre-create tests to their own tags by dropping foreign service
    rows and same-day queues first (inside the savepoint — rolled
    back with the test)."""
    db_session.query(Service).filter(Service.queue_tag.not_in(keep_tags)).delete(
        synchronize_session=False
    )
    db_session.query(DailyQueue).filter(DailyQueue.day == _DAY).delete(
        synchronize_session=False
    )
    db_session.commit()


# ===================== A. routing resolver =====================


def test_resolve_tag_resource_exact_match(db_session: Session) -> None:
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    assert queue_resource_routing.resolve_tag_resource(db_session, "lab") is resource


def test_resolve_tag_resource_rejects_alias_spelling(db_session: Session) -> None:
    """Exact-tag only — 'laboratory' must NOT resolve the lab resource
    (the 0059 seed-gate alias-skip contract)."""
    _make_resource(db_session, code="lab", queue_tag="lab")
    assert queue_resource_routing.resolve_tag_resource(db_session, "laboratory") is None


def test_resolve_tag_resource_ignores_inactive_row(db_session: Session) -> None:
    _make_resource(db_session, code="lab", queue_tag="lab", active=False)
    assert queue_resource_routing.resolve_tag_resource(db_session, "lab") is None


def test_resolve_tag_resource_none_for_unknown_and_empty(db_session: Session) -> None:
    _make_resource(db_session, code="lab", queue_tag="lab")
    assert queue_resource_routing.resolve_tag_resource(db_session, "general") is None
    assert queue_resource_routing.resolve_tag_resource(db_session, "") is None
    assert queue_resource_routing.resolve_tag_resource(db_session, None) is None


def test_find_active_tag_queue_finds_any_owner_shape(db_session: Session) -> None:
    """Tag-first unification: bridged, resource-owned and legacy
    synthetic-owned rows are all 'the queue for the day+tag'."""
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    bridged = _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    found = queue_resource_routing.find_active_tag_queue(db_session, _DAY, "lab")
    assert found is bridged

    other_day = _DAY + timedelta(days=1)
    resource_owned = _make_queue(
        db_session,
        day=other_day,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    assert (
        queue_resource_routing.find_active_tag_queue(db_session, other_day, "lab")
        is resource_owned
    )


def test_find_active_tag_queue_ignores_inactive_rows(db_session: Session) -> None:
    _make_queue(db_session, specialist_id=None, queue_tag="lab", active=False)
    assert queue_resource_routing.find_active_tag_queue(db_session, _DAY, "lab") is None


# ===================== B. queue_svc unification =====================


def test_get_or_create_registry_tag_creates_resource_owned_queue(
    db_session: Session,
) -> None:
    """QD-2C core: a NEW queue for a registry tag is resource-owned —
    specialist NULL, queue_resource_id set, caps from the registry."""
    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", max_online_per_day=11
    )
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.specialist_id is None
    assert queue.queue_resource_id == resource.id
    assert queue.queue_tag == "lab"
    assert queue.active is True
    assert queue.max_online_entries == 11


def test_get_or_create_registry_tag_reuses_bridged_queue(db_session: Session) -> None:
    """The dual-ownership bridge (0059 backfill shape: BOTH owners) IS
    the tag queue — no parallel fork, no mutation of the bridge."""
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    bridged = _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )

    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.id == bridged.id
    assert queue.specialist_id == synthetic.id  # bridge untouched
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1


def test_get_or_create_registry_tag_doctor_caller_gets_same_queue(
    db_session: Session,
) -> None:
    """A specialist-keyed caller (QR token / GQL join / visit with a
    doctor) is UNIFIED onto the tag queue instead of forking a
    doctor-owned parallel queue — the pre-QD-2 fork hazard."""
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )

    user = _make_user(db_session, username="dr_x", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="lab")

    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="lab"
    )
    assert queue.id == resource_queue.id
    assert queue.specialist_id is None
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1


def test_get_or_create_registry_tag_reuses_existing_doctor_fork(
    db_session: Session,
) -> None:
    """Pre-switch doctor-owned lab queue (created before the registry
    existed / before C): still THE tag queue — reused, not forked."""
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    legacy = _make_queue(db_session, specialist_id=synthetic.id, queue_tag="lab")
    # the registry arrives later (e.g. 0059 on an installation with
    # pre-existing rows)
    _make_resource(db_session, code="lab", queue_tag="lab")

    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.id == legacy.id
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1


def test_get_or_create_non_registry_tag_keeps_doctor_contract(
    db_session: Session,
) -> None:
    """Old path preserved: non-registry tags keep the per-doctor
    (day, specialist, tag) contract and the ValueError guard."""
    user = _make_user(db_session, username="dr_gen", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="general")

    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="general"
    )
    assert queue.specialist_id == doctor.id
    assert queue.queue_resource_id is None

    # same doctor+tag again → same queue (old SSOT)
    again = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="general"
    )
    assert again.id == queue.id

    with pytest.raises(ValueError, match="Врач с ID"):
        queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="general"
        )


def test_get_or_create_non_registry_tag_two_doctors_fork(
    db_session: Session,
) -> None:
    """PR-26 architecture fix preserved for doctor tags: two doctors of
    one specialty each get their OWN queue (no tag unification)."""
    user1 = _make_user(db_session, username="dr_c1", role="doctor")
    doctor1 = _make_doctor(db_session, user_id=user1.id, specialty="cardiology")
    user2 = _make_user(db_session, username="dr_c2", role="doctor")
    doctor2 = _make_doctor(db_session, user_id=user2.id, specialty="cardiology")

    q1 = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor1.id, queue_tag="cardiology"
    )
    q2 = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor2.id, queue_tag="cardiology"
    )
    assert q1.id != q2.id
    assert q1.specialist_id == doctor1.id
    assert q2.specialist_id == doctor2.id


# ===================== C. crud wrapper (GQL SSOT) =====================


def test_crud_get_or_create_registry_tag_unifies(db_session: Session) -> None:
    """crud_queue.get_or_create_daily_queue — the GQL joinQueue SSOT —
    honors the same tag-first unification and creates resource-owned
    queues for registry tags."""
    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", max_online_per_day=9
    )
    queue = crud_queue.get_or_create_daily_queue(db_session, _DAY, None, "lab")
    assert queue.specialist_id is None
    assert queue.queue_resource_id == resource.id
    assert queue.max_online_entries == 9

    # existing queue (whatever the owner) is reused — no fork
    again = crud_queue.get_or_create_daily_queue(db_session, _DAY, None, "lab")
    assert again.id == queue.id


def test_crud_get_or_create_registry_tag_with_doctor_arg_unifies(
    db_session: Session,
) -> None:
    """GQL joinQueue passes the synthetic/doctor id — the registry tag
    still resolves to the one tag queue (specialist ignored)."""
    _make_resource(db_session, code="lab", queue_tag="lab")
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")

    queue = crud_queue.get_or_create_daily_queue(db_session, _DAY, synthetic.id, "lab")
    assert queue.specialist_id is None
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1


def test_crud_get_or_create_non_registry_keeps_doctor_guard(
    db_session: Session,
) -> None:
    user = _make_user(db_session, username="dr_g", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="general")
    queue = crud_queue.get_or_create_daily_queue(db_session, _DAY, doctor.id, "general")
    assert queue.specialist_id == doctor.id
    with pytest.raises(ValueError, match="does not exist"):
        crud_queue.get_or_create_daily_queue(db_session, _DAY, None, "general")


# ===================== D. morning pre-create =====================


def test_morning_precreate_registry_tags_go_resource_axis(
    db_session: Session,
) -> None:
    """ensure_daily_queues_for_all_tags: lab/ecg (registry rows) are
    pre-created resource-owned — the synthetic general_resource is
    not even needed for them."""
    from app.services.morning_assignment import MorningAssignmentService

    _scope_morning_world(db_session, "lab", "ecg")
    _make_resource(db_session, code="lab", queue_tag="lab")
    _make_resource(db_session, code="ecg", queue_tag="ecg")
    _make_service(db_session, queue_tag="lab", name="Общий анализ крови")
    _make_service(db_session, queue_tag="ecg", name="ЭКГ")

    created = MorningAssignmentService(db_session).ensure_daily_queues_for_all_tags(
        _DAY
    )
    assert created == 2

    lab_queue = queue_resource_routing.find_active_tag_queue(db_session, _DAY, "lab")
    ecg_queue = queue_resource_routing.find_active_tag_queue(db_session, _DAY, "ecg")
    assert lab_queue is not None and lab_queue.specialist_id is None
    assert lab_queue.queue_resource_id is not None
    assert ecg_queue is not None and ecg_queue.specialist_id is None
    assert ecg_queue.queue_resource_id is not None


def test_morning_precreate_general_tag_keeps_synthetic_path(
    db_session: Session,
) -> None:
    """Non-registry tags keep the legacy path: the general queue is
    pre-created on the general_resource synthetic doctor."""
    from app.services.morning_assignment import MorningAssignmentService

    _scope_morning_world(db_session, "general")
    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    gen_doctor = _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    _make_service(db_session, queue_tag="general", name="Приём")

    created = MorningAssignmentService(db_session).ensure_daily_queues_for_all_tags(
        _DAY
    )
    assert created == 1
    queue = queue_resource_routing.find_active_tag_queue(db_session, _DAY, "general")
    assert queue is not None
    assert queue.specialist_id == gen_doctor.id
    assert queue.queue_resource_id is None


def test_morning_precreate_existing_queues_not_duplicated(
    db_session: Session,
) -> None:
    """The bridged queue from the 0059 backfill IS the tag queue:
    pre-create finds it and creates nothing."""
    from app.services.morning_assignment import MorningAssignmentService

    _scope_morning_world(db_session, "lab")
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    _make_service(db_session, queue_tag="lab", name="Общий анализ крови")

    created = MorningAssignmentService(db_session).ensure_daily_queues_for_all_tags(
        _DAY
    )
    assert created == 0
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1


# ===================== E. batch create resolution =====================


def test_batch_resolve_returns_none_for_registry_tag(db_session: Session) -> None:
    """_resolve_create_action_specialist_id: the registry tag needs no
    doctor — the queue will be resource-owned (None signals the
    resource axis; the synthetic map is not consulted)."""
    from app.services.batch_patient_service import BatchPatientService, EntryAction

    _make_resource(db_session, code="lab", queue_tag="lab")
    service = _make_service(db_session, queue_tag="lab", name="Общий анализ крови")
    svc = BatchPatientService(db_session)

    resolved = svc._resolve_create_action_specialist_id(
        action=EntryAction(id=None, action="create", entry_type="online_queue"),
        queue_tag="lab",
        service=service,
    )
    assert resolved is None


def test_batch_resolve_keeps_legacy_chain_without_registry(
    db_session: Session,
) -> None:
    """No registry row → the old chain: unique service doctor wins; the
    synthetic map is still consulted for the synthetic-owned tags."""
    from app.services.batch_patient_service import BatchPatientService, EntryAction

    doc_user = _make_user(db_session, username="dr_svc", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="lab")
    service = _make_service(db_session, queue_tag="lab", name="Общий анализ крови")
    service.doctor_id = doc.id
    db_session.commit()
    svc = BatchPatientService(db_session)

    resolved = svc._resolve_create_action_specialist_id(
        action=EntryAction(id=None, action="create", entry_type="online_queue"),
        queue_tag="lab",
        service=service,
    )
    assert resolved == doc.id


def test_batch_create_registry_tag_lands_on_resource_queue(
    db_session: Session,
) -> None:
    """End-to-end: _resolve_create_action_daily_queue for a registry
    tag returns the resource-owned queue."""
    from app.services.batch_patient_service import BatchPatientService, EntryAction

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    _make_service(db_session, queue_tag="lab", name="Общий анализ крови")
    svc = BatchPatientService(db_session)

    queue = svc._resolve_create_action_daily_queue(
        action=EntryAction(id=None, action="create", entry_type="online_queue"),
        target_date=_DAY,
        queue_tag="lab",
        service=None,
    )
    assert queue.specialist_id is None
    assert queue.queue_resource_id == resource.id


# ===================== F. numbering =====================


def test_get_next_queue_number_uses_resource_start(db_session: Session) -> None:
    """A resource queue's first ticket floors at the registry row's
    start_number_online (the value 0059 transferred from the LIVE
    synthetic Doctor)."""
    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", start_number_online=41
    )
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.queue_resource_id == resource.id
    number = queue_service.get_next_queue_number(
        db_session, daily_queue=queue, queue_tag="lab"
    )
    assert number == 41


def test_get_next_queue_number_advances_past_entries(db_session: Session) -> None:
    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", start_number_online=5
    )
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    db_session.add(
        OnlineQueueEntry(queue_id=queue.id, number=7, status="waiting", source="desk")
    )
    db_session.commit()
    number = queue_service.get_next_queue_number(
        db_session, daily_queue=queue, queue_tag="lab"
    )
    assert number == 8  # max(existing)+1 beats the start floor


def test_get_next_queue_number_doctor_queue_unchanged(db_session: Session) -> None:
    """Non-resource queues keep the settings-based numbering (no
    resource floor, no behavior change)."""
    user = _make_user(db_session, username="dr_num", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="general")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="general"
    )
    number = queue_service.get_next_queue_number(
        db_session, daily_queue=queue, queue_tag="general"
    )
    assert number >= 1
    assert queue.queue_resource_id is None


# ===================== G. output contract =====================


def test_daily_queue_out_owner_kinds(db_session: Session) -> None:
    """DailyQueueOut serializes both owner forms and derives the axis
    from queue_resource_id (explicit values are never overwritten)."""
    now = datetime(2026, 9, 7, 12, 0, 0)

    doctor_payload = DailyQueueOut(
        id=1, day=_DAY, specialist_id=5, active=True, created_at=now
    )
    assert doctor_payload.owner_kind == "doctor"
    assert doctor_payload.queue_resource is None

    resource_payload = DailyQueueOut(
        id=2,
        day=_DAY,
        specialist_id=None,
        queue_resource_id=9,
        active=True,
        created_at=now,
    )
    assert resource_payload.owner_kind == "resource"
    assert resource_payload.queue_resource == {"id": 9}

    bridge_payload = DailyQueueOut(
        id=3,
        day=_DAY,
        specialist_id=5,
        queue_resource_id=9,
        active=True,
        created_at=now,
    )
    # the bridge classifies as resource — the axis that owns the
    # routing going forward (same rule as the GQL type)
    assert bridge_payload.owner_kind == "resource"

    explicit = DailyQueueOut(
        id=4,
        day=_DAY,
        queue_resource_id=9,
        owner_kind="doctor",
        owner_display_name="X",
        queue_resource={"id": 99},
        active=True,
        created_at=now,
    )
    assert explicit.owner_kind == "doctor"
    assert explicit.queue_resource == {"id": 99}
    assert explicit.owner_display_name == "X"


def test_daily_queue_out_from_attributes(db_session: Session) -> None:
    """from_attributes ORM hydration carries the QD-2C fields."""
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    payload = DailyQueueOut.model_validate(queue)
    assert payload.owner_kind == "resource"
    assert payload.queue_resource_id == resource.id
    assert payload.specialist_id == synthetic.id


# ===================== H. GQL contract =====================


def test_gql_daily_queue_type_resource_nullable_specialist(
    db_session: Session,
) -> None:
    """QD-2C GQL nullable: a resource-owned queue serializes with
    specialist=None + owner_kind='resource' — no crash on the NULL
    doctor relationship."""
    from app.graphql.resolvers import daily_queue_to_type

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    gql_queue = daily_queue_to_type(queue)
    assert gql_queue.specialist is None
    assert gql_queue.owner_kind == "resource"
    assert gql_queue.queue_resource_id == resource.id
    assert gql_queue.queue_tag == "lab"


def test_gql_daily_queue_type_doctor_queue(db_session: Session) -> None:
    from app.graphql.resolvers import daily_queue_to_type

    user = _make_user(db_session, username="dr_gql", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="general")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="general"
    )
    gql_queue = daily_queue_to_type(queue)
    assert gql_queue.specialist is not None
    assert gql_queue.specialist.id == doctor.id
    assert gql_queue.owner_kind == "doctor"
    assert gql_queue.queue_resource_id is None


def test_gql_daily_queue_type_bridge_classifies_resource(
    db_session: Session,
) -> None:
    """The dual-ownership bridge (0059 backfill) reports the resource
    axis — the same rule as DailyQueueOut."""
    from app.graphql.resolvers import daily_queue_to_type

    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    gql_queue = daily_queue_to_type(queue)
    assert gql_queue.specialist is not None  # bridge keeps the doctor
    assert gql_queue.owner_kind == "resource"
    assert gql_queue.queue_resource_id == resource.id


def test_gql_type_declaration_specialist_nullable() -> None:
    """Source-level pin: the GQL type declares specialist as
    Optional (the pre-C declaration was non-nullable DoctorType)."""
    import typing

    from app.graphql.types import DailyQueueType

    hints = typing.get_type_hints(DailyQueueType)
    specialist_hint = hints["specialist"]
    # PEP 604 (X | None) gives types.UnionType; typing.Optional gives
    # typing.Union — both are null-unions, both accepted
    assert typing.get_origin(specialist_hint) in (
        typing.Union,
        __import__("types").UnionType,
    )
    assert type(None) in typing.get_args(specialist_hint)


# ===================== I. repository switch (visit confirmation) =====================


def test_confirmation_repository_registry_tag_resource_axis(
    db_session: Session,
) -> None:
    """visit_confirmation_repository.get_or_create_daily_queue:
    registry tag + no doctor → resource queue (no synthetic
    resolution, no ValueError)."""
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    repo = VisitConfirmationRepository(db_session)

    queue = repo.get_or_create_daily_queue(_DAY, None, "lab")
    assert queue.specialist_id is None
    assert queue.queue_resource_id == resource.id

    again = repo.get_or_create_daily_queue(_DAY, None, "lab")
    assert again.id == queue.id


def test_confirmation_repository_non_registry_keeps_guard(
    db_session: Session,
) -> None:
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    repo = VisitConfirmationRepository(db_session)
    with pytest.raises(ValueError, match="Врач с ID"):
        repo.get_or_create_daily_queue(_DAY, None, "general")


def test_confirmation_repository_reuses_bridged_queue(db_session: Session) -> None:
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    bridged = _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    repo = VisitConfirmationRepository(db_session)

    queue = repo.get_or_create_daily_queue(_DAY, None, "lab")
    assert queue.id == bridged.id
    assert queue.specialist_id == synthetic.id


# ===================== J. empty-registry regression =====================


def test_empty_registry_full_legacy_behavior(db_session: Session) -> None:
    """The CI alembic chain / fresh test DBs have NO registry rows:
    every surface keeps the legacy doctor behavior (the conditional
    switch is inert by construction)."""
    # resolve: nothing resolves
    assert queue_resource_routing.resolve_tag_resource(db_session, "lab") is None

    # queue_svc: doctor path with a lab tag but no registry row →
    # per-doctor queue (legacy semantics)
    user = _make_user(db_session, username="dr_legacy", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="lab"
    )
    assert queue.specialist_id == doctor.id
    assert queue.queue_resource_id is None

    # crud wrapper: same contract
    queue2 = crud_queue.get_or_create_daily_queue(db_session, _DAY, doctor.id, "lab")
    assert queue2.id == queue.id


# ===================== K. Codex round-1 P1/P2 pins =====================


def _make_waiting_entry(
    db_session: Session, queue: DailyQueue, number: int = 1
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id, number=number, status="waiting", source="desk"
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def test_qr_call_next_advances_resource_owned_queue(db_session: Session) -> None:
    """Codex round-1 P1: the staff command surface (REST
    /qr_queue/{specialist_id}/call-next, GQL callNextPatient) addresses
    the queue by the DOCTOR id — a resource-owned registry-tag queue
    (specialist NULL) was invisible to it. The resource-axis fallback
    resolves the (day, tag) surface through the synthetic's
    specialty, and the waiting patient advances through the canonical
    command."""
    from app.services.qr_queue import QRQueueService

    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.specialist_id is None  # the invisible shape
    entry = _make_waiting_entry(db_session, queue)

    service = QRQueueService(db_session)
    result = service.call_next_patient(
        synthetic.id, called_by_user_id=None, target_date=_DAY
    )
    assert result["success"] is True
    db_session.refresh(entry)
    assert entry.status == "called"


def test_qr_call_next_doctor_tag_queue_unchanged(db_session: Session) -> None:
    """The fallback fires ONLY for registry tags: a doctor queue with no
    waiting entries still raises the canonical 'queue not active' error
    (no silent cross-doctor resolution)."""
    from app.services.qr_queue import QRQueueService

    user = _make_user(db_session, username="dr_call", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardiology")
    # NO queue for this doctor on _DAY, and a registry tag exists that
    # is NOT the doctor's specialty: the fallback must not fire — the
    # canonical 'queue not active' error is raised (no cross-tag
    # resolution for non-registry specialties)
    _make_resource(db_session, code="lab", queue_tag="lab")

    service = QRQueueService(db_session)
    with pytest.raises(ValueError, match="Очередь не активна"):
        service.call_next_patient(doctor.id, called_by_user_id=None, target_date=_DAY)


def test_staff_call_next_patient_with_tag_resolves_resource_queue(
    db_session: Session,
) -> None:
    """staff_call_next_patient(specialist_id=synthetic, queue_tag='lab'):
    the tag is registry-backed → the (day, tag) surface is filtered
    instead of the specialist — the resource-owned queue's waiting
    entry is called."""
    from datetime import UTC
    from datetime import datetime as dt

    user = _make_user(db_session, username="ecg_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="ecg")
    _make_resource(db_session, code="ecg", queue_tag="ecg")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="ecg"
    )
    entry = _make_waiting_entry(db_session, queue)
    entry.queue_time = dt(2026, 9, 7, 8, 0, tzinfo=UTC)
    db_session.commit()

    result = queue_service.staff_call_next_patient(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="ecg",
        target_date=_DAY,
        actor_user_id=None,
        commit=False,
    )
    assert result["success"] is True
    assert result["queue_id"] == queue.id


def test_staff_call_next_patient_specialist_only_registry_tag(
    db_session: Session,
) -> None:
    """Specialist-keyed call WITHOUT an explicit tag: the synthetic's
    specialty resolves the registry tag → the tag queue's entry is
    called (the pre-fix behavior was 'No waiting queue entry')."""
    from datetime import UTC
    from datetime import datetime as dt

    user = _make_user(db_session, username="lab_resource2", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue)
    entry.queue_time = dt(2026, 9, 7, 8, 0, tzinfo=UTC)
    db_session.commit()

    result = queue_service.staff_call_next_patient(
        db_session,
        specialist_id=synthetic.id,
        target_date=_DAY,
        actor_user_id=None,
        commit=False,
    )
    assert result["success"] is True
    assert result["queue_id"] == queue.id


def test_first_creation_lock_is_pg_gated_noop_on_sqlite(
    db_session: Session,
) -> None:
    """The advisory lock helper (Codex round-1 P1 race fix) is a
    no-op on SQLite (tests) and carries the pg_advisory_xact_lock
    statement for PostgreSQL — source-pinned so the race fix cannot
    silently disappear."""
    import inspect

    from app.crud import queue_resource_routing as qrr

    # no-op: must not raise on the sqlite test session
    qrr.lock_registry_tag_creation(db_session, "lab", _DAY)

    source = inspect.getsource(qrr.lock_registry_tag_creation)
    assert "pg_advisory_xact_lock" in source
    assert "daily_queue:tag:{queue_tag}:{day" in source.replace(" '", "'")


def test_resource_start_number_helper(db_session: Session) -> None:
    """The QD-2C numbering SSOT helper: resource/bridged queues floor
    at the registry value; doctor queues return None."""
    from app.crud import queue_resource_routing as qrr

    user = _make_user(db_session, username="dr_floor", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    doctor_queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="cardio"
    )
    assert qrr.resource_start_number(db_session, doctor_queue) is None

    _make_resource(db_session, code="ecg", queue_tag="ecg", start_number_online=31)
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="ecg"
    )
    assert qrr.resource_start_number(db_session, resource_queue) == 31


# ===================== L. Codex round-2 P1/P2 pins =====================


def test_validate_queue_token_resolves_resource_queue(db_session: Session) -> None:
    """Codex round-2 P1: a token issued for a registry tag (the
    synthetic specialist) must validate against the resource-owned
    queue — the doctor-keyed lookup alone reported 'queue not
    created' for a live queue."""
    from app.models.online_queue import QueueToken

    user = _make_user(db_session, username="lab_resource3", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.specialist_id is None
    token = QueueToken(
        token="tok-round2-lab",
        day=_DAY,
        specialist_id=synthetic.id,
        department="lab",
        is_clinic_wide=False,
        expires_at=datetime(2026, 9, 8, 12, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    queue_token, meta = queue_service.validate_queue_token(db_session, "tok-round2-lab")
    assert meta["daily_queue"] is not None
    assert meta["daily_queue"].id == queue.id


def test_validate_queue_token_doctor_token_unchanged(db_session: Session) -> None:
    """Non-registry tokens keep the canonical error when the doctor's
    queue does not exist (no cross-doctor resolution)."""
    from app.models.online_queue import QueueToken

    user = _make_user(db_session, username="dr_tok", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardiology")
    token = QueueToken(
        token="tok-round2-doctor",
        day=_DAY,
        specialist_id=doctor.id,
        department="cardiology",
        is_clinic_wide=False,
        expires_at=datetime(2026, 9, 8, 12, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    from app.services.queue_svc._base import QueueNotFoundError

    with pytest.raises(QueueNotFoundError):
        queue_service.validate_queue_token(db_session, "tok-round2-doctor")


def test_get_queue_status_resolves_resource_queue(db_session: Session) -> None:
    """Codex round-2 P2: GET /api/v1/queue/status/{specialist_id} —
    the status lookup resolves the resource-owned queue through the
    same registry-tag fallback as call_next_patient (previously
    active=False + no entries for a live queue)."""
    from app.services.qr_queue import QRQueueService

    user = _make_user(db_session, username="ecg_resource2", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="ecg")
    _make_resource(db_session, code="ecg", queue_tag="ecg")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="ecg"
    )
    _make_waiting_entry(db_session, queue, number=3)

    status = QRQueueService(db_session).get_queue_status(synthetic.id, target_date=_DAY)
    assert status["active"] is True
    assert status["queue_length"] == 1
    assert status["entries"][0]["number"] == 3


def test_get_qr_token_info_resolves_resource_queue(db_session: Session) -> None:
    """Codex round-2 P1 (info surface): get_qr_token_info reports the
    resource-owned queue for a registry-tag token."""
    from app.models.online_queue import QueueToken
    from app.services.qr_queue import QRQueueService

    user = _make_user(db_session, username="lab_resource4", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, queue, number=1)
    token = QueueToken(
        token="tok-round2-info",
        day=_DAY,
        specialist_id=synthetic.id,
        department="lab",
        is_clinic_wide=False,
        expires_at=datetime(2026, 9, 8, 12, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    info = QRQueueService(db_session).get_qr_token_info("tok-round2-info")
    assert info is not None
    assert info.get("daily_queue") is not None or info.get("queue_length") == 1


# ===================== M. Codex round-3 P1 pins =====================


def test_deactivated_registry_keeps_resource_queue_routable(
    db_session: Session,
) -> None:
    """Codex round-3 P1: an operator deactivating a registry row
    mid-day must not make the day's routing surface vanish — the
    existing resource-owned queue stays THE surface (no parallel
    legacy fork, waiting patients stay visible to the
    specialist-keyed surfaces)."""
    from app.crud import queue_resource_routing as qrr

    user = _make_user(db_session, username="lab_res5", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, queue)

    # mid-day deactivation
    resource.active = False
    db_session.commit()

    # 1. the writers do NOT fork a parallel legacy queue — the same
    #    queue is returned whatever caller identity is used
    again = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=synthetic.id, queue_tag="lab"
    )
    assert again.id == queue.id
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1

    # 2. the staff surfaces still resolve it
    assert (
        qrr.resolve_registry_tag_queue_for_specialist(
            db_session, _DAY, synthetic.id, None
        ).id
        == queue.id
    )

    # 3. the routing helper reports the resource surface
    assert qrr.tag_routes_to_resource(db_session, "lab", _DAY).id == queue.id


def test_deactivated_registry_without_queue_takes_legacy_path(
    db_session: Session,
) -> None:
    """Deactivated registry row and NO live resource queue: the tag is
    no longer proven doctorless — new queues go to the legacy doctor
    axis (no resource creation)."""
    from app.crud import queue_resource_routing as qrr

    _make_resource(db_session, code="lab", queue_tag="lab", active=False)
    assert qrr.tag_routes_to_resource(db_session, "lab", _DAY) is None

    user = _make_user(db_session, username="dr_deact", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="lab"
    )
    assert queue.specialist_id == doctor.id
    assert queue.queue_resource_id is None


def test_open_daily_queue_opens_the_resource_queue(db_session: Session) -> None:
    """Codex round-3 P1 (/online-queue/open): opening reception with the
    synthetic identity must open THE resource queue — previously it
    created and opened a parallel doctor-owned queue while the
    resource queue stayed open for online joins."""
    from app.crud.online_queue import open_daily_queue

    user = _make_user(db_session, username="lab_res6", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )

    result = open_daily_queue(db_session, _DAY, synthetic.id)
    assert result["success"] is True
    db_session.refresh(queue)
    assert queue.opened_at is not None  # THE queue was opened
    assert len(_tag_queues(db_session, _DAY, "lab")) == 1  # no parallel fork


def test_online_queue_status_and_availability_resolve_resource(
    db_session: Session,
) -> None:
    """Codex round-3 P1 (/online-queue/status, availability): the
    specialist-keyed lookups resolve the resource queue instead of
    reporting queue_exists=False / creating ghosts."""
    from app.crud.online_queue import check_queue_availability, get_queue_status

    user = _make_user(db_session, username="lab_res7", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab", max_online_per_day=2)
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, queue, number=1)
    _make_waiting_entry(db_session, queue, number=2)

    status = get_queue_status(db_session, _DAY, synthetic.id)
    assert status["queue_exists"] is True
    assert status["queue_id"] == queue.id
    assert status["total_entries"] == 2
    assert status["waiting_entries"] == 2

    availability = check_queue_availability(
        db_session, _DAY, specialist_id=synthetic.id
    )
    # cap reached (2/2) — resolved THROUGH the resource queue, not a ghost
    assert availability["available"] is False
    assert availability.get("reason") in ("QUEUE_FULL", "QUEUE_LIMIT_REACHED")
