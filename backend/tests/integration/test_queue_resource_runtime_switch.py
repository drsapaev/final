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


def _durable_cleanup(db_session: Session, *usernames: str) -> None:
    """open_daily_queue (and other crud writers) COMMIT the session —
    the per-test savepoint is broken and the rows become DURABLE in
    the shared file DB. Remove exactly the rows this test created
    (tracked usernames → their doctors → registry/queues/entries) so
    later files (e.g. the lab_reporting catalog tests) see a clean
    world."""
    for username in usernames:
        user = db_session.query(User).filter(User.username == username).first()
        if user is None:
            continue
        for doctor in db_session.query(Doctor).filter(Doctor.user_id == user.id).all():
            for queue in (
                db_session.query(DailyQueue)
                .filter(DailyQueue.specialist_id == doctor.id)
                .all()
            ):
                db_session.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.queue_id == queue.id
                ).delete(synchronize_session=False)
                db_session.delete(queue)
            db_session.delete(doctor)
        db_session.delete(user)
    # resource-owned queues + registry rows created in THIS test world
    for queue in (
        db_session.query(DailyQueue)
        .filter(DailyQueue.specialist_id.is_(None), DailyQueue.active.is_(True))
        .all()
    ):
        db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue.id
        ).delete(synchronize_session=False)
        db_session.delete(queue)
    for resource in db_session.query(QueueResource).all():
        db_session.delete(resource)
    db_session.commit()


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
        expires_at=datetime(2099, 1, 1, 12, 0, 0),
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
        expires_at=datetime(2099, 1, 1, 12, 0, 0),
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
        expires_at=datetime(2099, 1, 1, 12, 0, 0),
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
    resource queue stayed open for online joins. NOTE: open_daily_queue
    COMMITs — durable rows are cleaned in the finally (see
    _durable_cleanup)."""

    try:
        _test_open_daily_queue_opens_the_resource_queue_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res6")


def _test_open_daily_queue_opens_the_resource_queue_body(
    db_session: Session,
) -> None:
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
    reporting queue_exists=False / creating ghosts. The availability
    check rejects PAST days (DATE_PAST) — the world rides a dynamic
    future day so the pin never rots with the wall clock."""
    from app.crud.online_queue import check_queue_availability, get_queue_status

    future_day = date.today() + timedelta(days=1)
    user = _make_user(db_session, username="lab_res7", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab", max_online_per_day=2)
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=future_day, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, queue, number=1)
    _make_waiting_entry(db_session, queue, number=2)

    status = get_queue_status(db_session, future_day, synthetic.id)
    assert status["queue_exists"] is True
    assert status["queue_id"] == queue.id
    assert status["total_entries"] == 2
    assert status["waiting_entries"] == 2

    availability = check_queue_availability(
        db_session, future_day, specialist_id=synthetic.id
    )
    # cap reached (2/2) — resolved THROUGH the resource queue, not a ghost
    assert availability["available"] is False
    assert availability.get("reason") in ("QUEUE_FULL", "QUEUE_LIMIT_REACHED")


# ===================== N. Codex round-4 P1/P2 pins =====================


def test_aggregate_statistics_include_resource_owned_queue(
    db_session: Session,
) -> None:
    """Codex round-4 P1: GET /online-queue/today without specialist_id
    aggregates ALL queues — a resource-owned row (specialist NULL)
    previously crashed the response builder on q.specialist.user
    (AttributeError → 500). Now the owner label comes from the
    registry row and the resource axis is reported."""
    from app.crud.online_queue import get_queue_statistics

    user = _make_user(db_session, username="dr_agg", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=doctor.id, queue_tag="cardio"
    )
    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", display_name="Лаборатория"
    )
    lab_queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, lab_queue)

    stats = get_queue_statistics(db_session, _DAY)  # no specialist filter
    assert stats["total_queues"] >= 2
    by_resource = next(
        q for q in stats["queues"] if q["queue_resource_id"] == resource.id
    )
    assert by_resource["specialist_id"] is None
    assert by_resource["specialist_name"] == "Лаборатория"
    assert by_resource["entries_count"] == 1
    doctor_row = next(q for q in stats["queues"] if q["specialist_id"] == doctor.id)
    # doctor label unchanged (user full_name or the doctor fallback)
    assert doctor_row["specialist_name"] in ("dr_agg", f"Врач #{doctor.id}")


def test_staff_call_explicit_tag_survives_deactivation(
    db_session: Session,
) -> None:
    """Codex round-4 P1: the explicit-tag staff call form
    (specialist_id=synthetic, queue_tag='lab') keeps resolving the
    resource queue AFTER a mid-day registry deactivation — the same
    surface rule as the specialist-only form."""
    from datetime import UTC
    from datetime import datetime as dt

    user = _make_user(db_session, username="lab_res8", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue)
    entry.queue_time = dt(2026, 9, 7, 8, 0, tzinfo=UTC)
    db_session.commit()

    resource.active = False
    db_session.commit()

    result = queue_service.staff_call_next_patient(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        target_date=_DAY,
        actor_user_id=None,
        commit=False,
    )
    assert result["success"] is True
    assert result["queue_id"] == queue.id


def test_registry_recheck_after_lock_is_sourced(db_session: Session) -> None:
    """Codex round-4 P2 (source pin): every get_or_create registry
    branch re-resolves the registry row AFTER acquiring the creation
    lock — a deactivation committed between the first resolve and the
    lock must not produce a resource-owned queue for a deactivated
    tag. The TOCTOU window itself needs the PG advisory lock, so the
    recheck is source-pinned (the sqlite test path takes the no-op
    branch)."""
    import inspect

    from app.crud import online_queue as crud_online_queue
    from app.repositories import visit_confirmation_repository as vcr
    from app.services.queue_svc import _operations as queue_ops

    crud_src = inspect.getsource(crud_online_queue.get_or_create_daily_queue)
    ops_src = inspect.getsource(queue_ops.OperationsMixin.get_or_create_daily_queue)
    repo_src = inspect.getsource(
        vcr.VisitConfirmationRepository.get_or_create_daily_queue
    )
    for name, src in (
        ("crud", crud_src),
        ("queue_svc", ops_src),
        ("repository", repo_src),
    ):
        assert "lock_registry_tag_creation" in src, name
        # the recheck: resolve_tag_resource appears again AFTER the lock
        lock_pos = src.find("lock_registry_tag_creation")
        recheck = src.find("resolve_tag_resource", lock_pos)
        assert recheck > lock_pos, name


# ===================== O. Codex round-5 P1 pins =====================


def _legacy_then_resource_world(db_session: Session) -> tuple:
    """The round-5 P1 scenario world: a DEACTIVATED legacy
    synthetic-owned queue (operator cleanup after the switch) + the
    live resource-owned queue for the same day/tag."""
    user = _make_user(db_session, username="lab_res9", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    legacy = _make_queue(
        db_session, specialist_id=synthetic.id, queue_tag="lab", active=False
    )
    live = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    return synthetic, legacy, live


def test_token_validation_prefers_active_surface(db_session: Session) -> None:
    """Codex round-5 P1: the doctor-keyed lookup (no active filter)
    returned the DEACTIVATED legacy row and the join accepted the
    disabled queue while staff worked the live resource queue. The
    token validation now prefers the active registry surface."""
    from app.models.online_queue import QueueToken

    synthetic, legacy, live = _legacy_then_resource_world(db_session)
    _make_waiting_entry(db_session, live)
    token = QueueToken(
        token="tok-round5",
        day=_DAY,
        specialist_id=synthetic.id,
        department="lab",
        is_clinic_wide=False,
        expires_at=datetime(2099, 1, 1, 12, 0, 0),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    queue_token, meta = queue_service.validate_queue_token(db_session, "tok-round5")
    assert meta["daily_queue"].id == live.id  # NOT the inactive legacy


def test_status_prefers_active_surface_over_inactive_legacy(
    db_session: Session,
) -> None:
    """The status surfaces (qr + crud) prefer the active resource
    queue over the inactive legacy row."""
    from app.crud.online_queue import get_queue_status as crud_status
    from app.services.qr_queue import QRQueueService

    synthetic, legacy, live = _legacy_then_resource_world(db_session)
    _make_waiting_entry(db_session, live)

    status = QRQueueService(db_session).get_queue_status(synthetic.id, target_date=_DAY)
    assert status["active"] is True
    assert status["queue_length"] == 1

    crud = crud_status(db_session, _DAY, synthetic.id)
    assert crud["queue_exists"] is True
    assert crud["queue_id"] == live.id


def test_open_daily_queue_prefers_active_surface(db_session: Session) -> None:
    """Opening reception opens the LIVE resource queue when an
    inactive legacy row shadows it in the no-filter lookup.
    open_daily_queue COMMITs — durable rows cleaned in the finally."""
    try:
        _test_open_daily_queue_prefers_active_surface_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res9")


def _test_open_daily_queue_prefers_active_surface_body(
    db_session: Session,
) -> None:
    from app.crud.online_queue import open_daily_queue

    synthetic, legacy, live = _legacy_then_resource_world(db_session)

    result = open_daily_queue(db_session, _DAY, synthetic.id)
    assert result["success"] is True
    db_session.refresh(live)
    db_session.refresh(legacy)
    assert live.opened_at is not None
    assert legacy.opened_at is None  # the disabled row stays untouched


def test_doctor_complete_rejects_resource_entry_for_non_admin(
    db_session: Session,
) -> None:
    """Codex round-5 P1: POST /doctor/queue/{entry_id}/complete — the
    ownership guard skipped when specialist was NULL, admitting any
    routed role (Cashier/Registrar/foreign Doctor). The resource entry
    is completable ONLY by Admin through this doctor command — the
    same effective policy the pre-C synthetic owner enforced (the
    synthetic's user_id matched no human caller)."""
    from fastapi import HTTPException

    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        complete_patient_visit,
    )

    user = _make_user(db_session, username="dr_res10", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue)
    entry.status = "called"
    db_session.commit()

    def _attempt(role: str) -> HTTPException | None:
        caller = _make_user(db_session, username=f"usr_{role}", role=role)
        try:
            complete_patient_visit(
                entry.id,
                visit_data=None,
                db=db_session,
                current_user=caller,
            )
            return None
        except HTTPException as exc:
            return exc

    # a doctor (not admin, not the owner — the queue HAS no owner):
    exc = _attempt("Doctor")
    assert exc is not None and exc.status_code == 403
    # the doctor-family role spellings equally rejected
    exc = _attempt("Registrar")
    assert exc is not None and exc.status_code == 403


# ===================== P. Codex round-6 pins =====================


def _shadow_world(db_session: Session) -> tuple:
    """The round-6 P1 scenario world: the live resource surface for a
    registry tag + an ACTIVE UNTAGGED doctor-keyed shadow row (what
    the pre-fix POST /queue/legacy/open writer created for the
    synthetic specialist next to the resource queue)."""
    user = _make_user(db_session, username="lab_res11", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    surface = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    shadow = _make_queue(
        db_session, specialist_id=synthetic.id, queue_tag=None, active=True
    )
    return synthetic, surface, shadow


def test_prefer_registry_surface_over_active_legacy_shadow(
    db_session: Session,
) -> None:
    """Codex round-6 P1 (read side): an ACTIVE untagged legacy row
    must not shadow the live registry surface — token validation and
    the canonical status/open paths report the ONE (day, tag) surface
    the tag-based arrivals use."""
    synthetic, surface, shadow = _shadow_world(db_session)

    resolved = queue_resource_routing.prefer_registry_surface(
        db_session, shadow, _DAY, synthetic.id
    )
    assert resolved is not None and resolved.id == surface.id

    # a candidate already on the resource axis passes through unchanged
    passthrough = queue_resource_routing.prefer_registry_surface(
        db_session, surface, _DAY, synthetic.id
    )
    assert passthrough is not None and passthrough.id == surface.id


def test_prefer_registry_surface_doctor_row_without_surface_unchanged(
    db_session: Session,
) -> None:
    """Guard: an active doctor-keyed row for a NON-registry specialty
    is returned as-is — the switch never touches doctor routing."""
    user = _make_user(db_session, username="dr_real11", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    queue = _make_queue(
        db_session, specialist_id=doctor.id, queue_tag="cardio", active=True
    )

    resolved = queue_resource_routing.prefer_registry_surface(
        db_session, queue, _DAY, doctor.id
    )
    assert resolved is queue


def test_legacy_open_routes_to_registry_surface(db_session: Session) -> None:
    """Codex round-6 P1 (write side): /queue/legacy/open for the
    synthetic specialist returns the live resource surface instead of
    the doctor-keyed shadow — no new doctor row is forked."""
    from app.services.queue_api_service import QueueApiService

    synthetic, surface, _shadow = _shadow_world(db_session)

    resolved = QueueApiService(db_session).get_or_create_daily_queue(
        day=_DAY, specialist_id=synthetic.id
    )
    assert resolved.id == surface.id
    # the (day, lab) tag surface is the ONLY tagged queue — no fork
    tagged = _tag_queues(db_session, _DAY, "lab")
    assert [q.id for q in tagged] == [surface.id]


def test_legacy_open_creates_resource_queue_when_none_exists(
    db_session: Session,
) -> None:
    """Codex round-6 P1 (write side, first creation): the registry
    queue is created resource-owned (specialist NULL, caps from the
    registry row) — NOT as a doctor-keyed row for the synthetic."""
    from app.services.queue_api_service import QueueApiService

    user = _make_user(db_session, username="lab_res12", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", max_online_per_day=17
    )

    resolved = QueueApiService(db_session).get_or_create_daily_queue(
        day=_DAY, specialist_id=synthetic.id
    )
    assert resolved.specialist_id is None
    assert resolved.queue_resource_id == resource.id
    assert resolved.queue_tag == "lab"
    assert resolved.max_online_entries == 17
    doctor_rows = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == _DAY, DailyQueue.specialist_id == synthetic.id)
        .all()
    )
    assert doctor_rows == []


def test_legacy_get_daily_queue_prefers_registry_surface(
    db_session: Session,
) -> None:
    """Codex round-6 P1 (close/today/statistics path): the legacy
    doctor-keyed LOOKUP resolves the registry surface — open and close
    address the same queue, no 404 on the resource surface."""
    from app.services.queue_api_service import QueueApiService

    synthetic, surface, _shadow = _shadow_world(db_session)

    resolved = QueueApiService(db_session).get_daily_queue(
        day=_DAY, specialist_id=synthetic.id
    )
    assert resolved is not None and resolved.id == surface.id


def test_legacy_open_close_coherence_on_resource_surface(
    db_session: Session,
) -> None:
    """open addresses the resource surface; close finds the SAME queue
    (get_daily_queue surface-first) — opened_at toggles on one row,
    never on a doctor shadow. open/close COMMIT — durable rows
    cleaned in the finally."""
    try:
        _test_legacy_open_close_coherence_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res15")


def _test_legacy_open_close_coherence_body(db_session: Session) -> None:
    from app.services.queue_api_service import QueueApiService

    user = _make_user(db_session, username="lab_res15", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    service = QueueApiService(db_session)

    opened = service.get_or_create_daily_queue(day=_DAY, specialist_id=synthetic.id)
    assert opened.specialist_id is None  # the resource surface, no fork

    service.open_daily_queue(opened)
    db_session.refresh(opened)
    assert opened.opened_at is not None

    closed = service.get_daily_queue(day=_DAY, specialist_id=synthetic.id)
    assert closed is not None and closed.id == opened.id  # same surface
    service.close_daily_queue(closed)
    db_session.refresh(opened)
    assert opened.opened_at is None

    doctor_rows = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == _DAY, DailyQueue.specialist_id == synthetic.id)
        .all()
    )
    assert doctor_rows == []


def test_legacy_statistics_label_registry_display_name(
    db_session: Session,
) -> None:
    """Codex round-6 P1 (label): the legacy statistics endpoint for a
    resource surface reports the registry display_name — not
    \"Врач #None\" — and counts the surface entries."""
    from app.api.v1.endpoints.queue import get_queue_statistics

    synthetic, surface, _shadow = _shadow_world(db_session)
    _make_waiting_entry(db_session, surface, number=2)
    admin = _make_user(db_session, username="admin_stats", role="Admin")

    payload = get_queue_statistics(
        synthetic.id, day=_DAY, db=db_session, current_user=admin
    )
    assert payload["success"] is True
    assert payload["specialist"]["name"] == "Ресурс очереди"
    assert payload["statistics"]["total_entries"] == 1


def test_force_majeure_pending_entries_see_resource_queue(
    db_session: Session,
) -> None:
    """Codex round-6 P1-2: the force-majeure pending list for the
    synthetic specialist sees the resource-owned queue (specialist
    NULL) through the tag surface — the doctor-keyed filter alone
    would return nothing to transfer or cancel."""
    from app.services.force_majeure_service import ForceMajeureService

    user = _make_user(db_session, username="lab_res13", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue, number=3)

    entries = ForceMajeureService(db_session).get_pending_entries(
        specialist_id=synthetic.id, target_date=_DAY
    )
    assert [e.id for e in entries] == [entry.id]


def test_force_majeure_entry_ids_select_resource_entries(
    db_session: Session,
) -> None:
    """Codex round-6 P1-2: entry-id transfer/cancel requests select
    the resource entries for the synthetic specialist (the
    ForceMajeureApiRepository doctor filter never matches
    specialist NULL)."""
    from app.repositories.force_majeure_api_repository import (
        ForceMajeureApiRepository,
    )

    user = _make_user(db_session, username="lab_res16", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue, number=4)

    entries = ForceMajeureApiRepository(db_session).list_pending_entries_by_ids(
        [entry.id], specialist_id=synthetic.id, target_date=_DAY
    )
    assert [e.id for e in entries] == [entry.id]


def test_force_majeure_transfer_moves_to_resource_tomorrow_queue(
    db_session: Session,
) -> None:
    """Codex round-6 P1-2 (transfer): the entries move to the TOMORROW
    registry surface (resource-owned), not to a doctor-owned fork —
    Admin/Registrar can actually operate the interruption. transfer
    COMMITs — durable rows cleaned in the finally."""
    try:
        _test_force_majeure_transfer_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res14")


def _test_force_majeure_transfer_body(db_session: Session) -> None:
    from app.services.force_majeure_service import ForceMajeureService

    user = _make_user(db_session, username="lab_res14", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue, number=5)

    service = ForceMajeureService(db_session)
    pending = service.get_pending_entries(specialist_id=synthetic.id, target_date=_DAY)
    assert [e.id for e in pending] == [entry.id]

    tomorrow = date.today() + timedelta(days=1)
    result = service.transfer_entries_to_tomorrow(
        entries=pending,
        specialist_id=synthetic.id,
        reason="round-6 pin",
        performed_by_id=1,
        send_notifications=False,
    )
    assert result["success"] is True
    assert result["transferred"] == 1

    tomorrow_queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == tomorrow, DailyQueue.queue_tag == "lab")
        .first()
    )
    assert tomorrow_queue is not None
    assert tomorrow_queue.queue_resource_id == resource.id
    assert tomorrow_queue.specialist_id is None
    doctor_tomorrow = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == tomorrow, DailyQueue.specialist_id == synthetic.id)
        .all()
    )
    assert doctor_tomorrow == []

    db_session.refresh(entry)
    assert entry.status == "cancelled"
    moved = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == tomorrow_queue.id)
        .all()
    )
    assert len(moved) == 1
    assert moved[0].priority == ForceMajeureService.TRANSFER_PRIORITY
    assert moved[0].patient_id == entry.patient_id


def test_locked_recheck_helper_pg_gated_and_refreshing(
    db_session: Session,
) -> None:
    """Codex round-6 P2: the post-lock recheck helper carries the row
    lock (FOR UPDATE — pg-gated like the advisory lock) and the
    identity-map refresh (populate_existing). Sequential sqlite: the
    same verdicts as the plain resolve (active row → row; deactivated
    or unknown → None)."""
    import inspect

    from app.crud import queue_resource_routing as qrr

    resource = _make_resource(db_session, code="lab", queue_tag="lab")

    row = qrr.resolve_tag_resource_locked(db_session, "lab")
    assert row is not None and row.id == resource.id and row.active is True
    assert qrr.resolve_tag_resource_locked(db_session, "ecg") is None

    source = inspect.getsource(qrr.resolve_tag_resource_locked)
    assert "populate_existing" in source
    assert "with_for_update" in source
    assert "postgresql" in source

    resource.active = False
    db_session.commit()
    assert qrr.resolve_tag_resource_locked(db_session, "lab") is None


def test_registry_recheck_uses_locked_resolve(db_session: Session) -> None:
    """Codex round-6 P2 (source pin): every creation branch rechecks
    the registry row AFTER the lock with the ROW-LOCKED helper — a
    deactivation committing while a creator holds the advisory lock
    cannot slip a new resource queue past the disable."""
    import inspect

    from app.crud import online_queue as crud_online_queue
    from app.repositories import queue_api_repository as qar
    from app.repositories import visit_confirmation_repository as vcr
    from app.services.queue_svc import _operations as queue_ops

    targets = (
        ("crud", inspect.getsource(crud_online_queue.get_or_create_daily_queue)),
        (
            "queue_svc",
            inspect.getsource(queue_ops.OperationsMixin.get_or_create_daily_queue),
        ),
        (
            "repository",
            inspect.getsource(
                vcr.VisitConfirmationRepository.get_or_create_daily_queue
            ),
        ),
        (
            "legacy-repo",
            inspect.getsource(qar.QueueApiRepository.get_or_create_registry_queue),
        ),
    )
    for name, src in targets:
        lock_pos = src.find("lock_registry_tag_creation")
        assert lock_pos != -1, name
        recheck = src.find("resolve_tag_resource_locked", lock_pos)
        assert recheck > lock_pos, name


# ===================== Q. Codex round-7 pins =====================


def test_registry_queue_cabinet_comes_from_registry_not_doctor_defaults(
    db_session: Session,
) -> None:
    """Codex round-7 P1: the shared tag queue must NOT inherit the
    referring doctor's cabinet (morning assignment / registrar batch
    pass the doctor's room in ``defaults`` — whichever doctor creates
    the queue first would direct every lab/ecg ticket to that room).
    The cabinet comes from the registry row (0059 seeds NULL — no
    canonical source); floor/building stay unset."""
    user = _make_user(db_session, username="dr_cab17", role="doctor")
    referring = _make_doctor(db_session, user_id=user.id, specialty="lab")
    referring.cabinet = "42"
    db_session.commit()
    _make_resource(db_session, code="lab", queue_tag="lab")
    _make_resource(
        db_session,
        code="ecg",
        queue_tag="ecg",
        display_name="ЭКГ",
    )
    db_session.query(QueueResource).filter(QueueResource.queue_tag == "ecg").update(
        {"default_cabinet": "7"}, synchronize_session=False
    )
    db_session.commit()

    # the registrar-batch shape: doctor-keyed call with the referring
    # doctor's cabinet in defaults for a REGISTRY tag
    queue = queue_service.get_or_create_daily_queue(
        db_session,
        day=_DAY,
        specialist_id=referring.id,
        queue_tag="lab",
        defaults={
            "max_online_entries": 5,
            "cabinet_number": referring.cabinet,
            "cabinet_floor": 3,
            "cabinet_building": "B",
        },
    )
    assert queue.queue_resource_id is not None
    assert queue.cabinet_number is None  # NOT the referring doctor's "42"
    assert queue.cabinet_floor is None
    assert queue.cabinet_building is None

    # the registry's canonical cabinet transfers when it is set
    ecg_queue = queue_service.get_or_create_daily_queue(
        db_session,
        day=_DAY,
        specialist_id=referring.id,
        queue_tag="ecg",
        defaults={"cabinet_number": referring.cabinet},
    )
    assert ecg_queue.cabinet_number == "7"


def test_analytics_department_filter_includes_resource_queues(
    db_session: Session,
) -> None:
    """Codex round-7 P2: department-filtered queue analytics must not
    drop resource-owned queues (specialist NULL) — the queue tag is
    the department axis for resource rows, so lab reports count the
    live resource queue's entries instead of returning zero."""
    from datetime import datetime

    from app.services.analytics import AnalyticsService

    _make_resource(db_session, code="lab", queue_tag="lab")
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    served = _make_waiting_entry(db_session, resource_queue, number=1)
    served.status = "served"
    _make_waiting_entry(db_session, resource_queue, number=2)
    db_session.commit()

    user = _make_user(db_session, username="dr_anl17", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    doctor_queue = _make_queue(
        db_session, specialist_id=doctor.id, queue_tag="cardio", active=True
    )
    _make_waiting_entry(db_session, doctor_queue, number=1)

    start = datetime(2026, 9, 6, 0, 0, 0)
    end = datetime(2026, 9, 8, 23, 59, 59)

    lab_stats = AnalyticsService.get_queue_statistics(
        db_session, start_date=start, end_date=end, department="lab"
    )
    assert lab_stats["total_queues"] == 1
    assert lab_stats["total_entries"] == 2
    assert lab_stats["total_served"] == 1
    assert "lab" in lab_stats["by_department"]

    cardio_stats = AnalyticsService.get_queue_statistics(
        db_session, start_date=start, end_date=end, department="cardio"
    )
    assert cardio_stats["total_queues"] == 1  # the doctor queue only
    assert cardio_stats["total_entries"] == 1


# ===================== R. Codex round-8 pins =====================


def test_mobile_queues_status_represents_resource_axis(
    db_session: Session,
) -> None:
    """Codex round-8 P1: /api/v1/mobile/queues/status enumerates the
    morning-pre-created lab row (specialist NULL) — the DTO carried
    doctor_id: int, so the builder raised ValidationError and the
    handler returned 500. The response now represents the resource
    axis: doctor_id NULL, the registry display_name, the tag as the
    specialty; doctor rows are unchanged."""
    try:
        _test_mobile_queues_status_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res18", "dr_mob18")


def _test_mobile_queues_status_body(db_session: Session) -> None:
    import asyncio

    from app.api.v1.endpoints.mobile_api_extended import get_queues_status

    _make_resource(db_session, code="lab", queue_tag="lab")
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=date.today(), specialist_id=None, queue_tag="lab"
    )
    user = _make_user(db_session, username="dr_mob18", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    doctor_queue = queue_service.get_or_create_daily_queue(
        db_session, day=date.today(), specialist_id=doctor.id, queue_tag="cardio"
    )

    viewer = _make_user(db_session, username="lab_res18", role="Admin")
    payload = asyncio.run(get_queues_status(current_user=viewer, db=db_session))
    rows = {row.doctor_id: row for row in payload["queues"]}

    resource_row = rows[None]
    assert resource_row.doctor_name == "Ресурс очереди"
    assert resource_row.specialty == "lab"

    doctor_row = rows[doctor.id]
    assert doctor_row.specialty == "cardio"

    # both axes enumerated — the resource queue is not dropped
    assert resource_queue is not None
    assert doctor_queue is not None


def test_cabinet_info_represents_resource_axis(db_session: Session) -> None:
    """Codex round-8 P1: /api/v1/admin/queues/cabinet-info required
    specialist_id: int — a resource-owned row failed the DTO and the
    handler 500'd. The payload now represents the resource axis
    (specialist_id NULL, registry display_name, sync_status
    resource_owned — no missing-doctor integrity noise) and the DTO
    accepts every payload row."""
    from app.api.v1.endpoints.queue_cabinet_management import QueueCabinetResponse
    from app.services.queue_domain_service import QueueDomainService

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    resource.default_cabinet = "7"
    db_session.commit()
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, resource_queue, number=1)

    payloads = QueueDomainService(db_session).list_queue_cabinet_info(
        day=_DAY, specialist_id=None, cabinet_number=None
    )
    # every payload row must construct the DTO without a ValidationError
    items = [QueueCabinetResponse(**item) for item in payloads]

    resource_item = next(i for i in items if i.id == resource_queue.id)
    assert resource_item.specialist_id is None
    assert resource_item.specialist_name == "Ресурс очереди"
    assert resource_item.sync_status == "resource_owned"
    assert resource_item.cabinet_number == "7"
    assert resource_item.effective_cabinet == "7"
    assert resource_item.doctor_cabinet is None
    assert resource_item.linked_doctor_found is False
    assert "linked_doctor_missing" not in resource_item.integrity_warnings
    assert resource_item.entries_count == 1


def test_registry_cabinet_persisted_in_every_creation_path(
    db_session: Session,
) -> None:
    """Codex round-8 P2: the registry's canonical cabinet must land on
    the resource queue whichever writer creates it first — the GQL
    joinQueue SSOT copy, the visit-confirmation repository and the
    round-6 legacy-writer branch, with the same parity as the
    queue_svc constructor (round-7)."""
    from app.repositories.queue_api_repository import QueueApiRepository
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    _make_resource(db_session, code="lab", queue_tag="lab", max_online_per_day=5)
    _make_resource(db_session, code="ecg", queue_tag="ecg", max_online_per_day=5)
    _make_resource(db_session, code="bio", queue_tag="bio", max_online_per_day=5)
    db_session.query(QueueResource).update(
        {"default_cabinet": "7"}, synchronize_session=False
    )
    db_session.commit()

    gql_queue = crud_queue.get_or_create_daily_queue(db_session, _DAY, None, "lab")
    confirmation_queue = VisitConfirmationRepository(
        db_session
    ).get_or_create_daily_queue(_DAY, None, "ecg")
    legacy_queue = QueueApiRepository(db_session).get_or_create_registry_queue(
        day=_DAY, queue_tag="bio"
    )

    for queue, path in (
        (gql_queue, "gql"),
        (confirmation_queue, "confirmation"),
        (legacy_queue, "legacy-writer"),
    ):
        assert queue.cabinet_number == "7", path
        assert queue.specialist_id is None, path


# ===================== S. Codex round-9 pins =====================


def test_queue_limits_route_to_registry_surface(db_session: Session) -> None:
    """Codex round-9 P1: PUT /admin/doctor-queue-limit for the synthetic
    lab/ecg doctor applies the limit to the (day, tag) RESOURCE surface
    (the queue joins actually use), not to a doctor-keyed shadow row
    the repository would otherwise create. set_doctor_queue_limit
    COMMITs — durable rows cleaned in the finally."""
    try:
        _test_queue_limits_route_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res19")


def _test_queue_limits_route_body(db_session: Session) -> None:
    from app.api.v1.endpoints.queue_limits import DoctorQueueLimit
    from app.services.queue_limits_api_service import QueueLimitsApiService

    user = _make_user(db_session, username="lab_res19", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab", max_online_per_day=15)
    surface = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )

    payload = QueueLimitsApiService(db_session).set_doctor_queue_limit(
        limit_data=DoctorQueueLimit(
            doctor_id=synthetic.id, day=_DAY, max_online_entries=7
        )
    )
    assert payload["success"] is True

    db_session.refresh(surface)
    assert surface.max_online_entries == 7  # the limit lands on the surface
    # no doctor-keyed shadow row was forked
    doctor_rows = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == _DAY, DailyQueue.specialist_id == synthetic.id)
        .all()
    )
    assert doctor_rows == []


def test_force_majeure_transfer_floors_at_resource_start(
    db_session: Session,
) -> None:
    """Codex round-9 P2: a transfer onto an EMPTY tomorrow resource
    surface numbers the moved entries from
    QueueResource.start_number_online — the same canonical sequence
    every resource allocation path uses — instead of 1."""
    try:
        _test_force_majeure_floor_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res20")


def _test_force_majeure_floor_body(db_session: Session) -> None:
    from app.services.force_majeure_service import ForceMajeureService

    user = _make_user(db_session, username="lab_res20", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab", start_number_online=31)
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue, number=31)

    service = ForceMajeureService(db_session)
    pending = service.get_pending_entries(specialist_id=synthetic.id, target_date=_DAY)
    assert [e.id for e in pending] == [entry.id]

    result = service.transfer_entries_to_tomorrow(
        entries=pending,
        specialist_id=synthetic.id,
        reason="round-9 pin",
        performed_by_id=1,
        send_notifications=False,
    )
    assert result["success"] is True
    assert result["transferred"] == 1
    # the moved entry carries the registry floor number, not 1
    assert result["details"][0]["new_number"] == 31


def test_mobile_my_position_labels_resource_queue(db_session: Session) -> None:
    """Codex round-9 P2: /api/v1/mobile/queues/my-position for a
    patient waiting on a resource-owned queue reports the registry
    display_name and the queue tag — not «Неизвестно» for both."""
    import asyncio

    from app.api.v1.endpoints.mobile_api_extended import get_my_queue_position
    from app.models.patient import Patient

    try:
        patient_user = _make_user(db_session, username="pat_res21", role="Patient")
        patient = Patient(
            user_id=patient_user.id, last_name="Пациентов", first_name="Пациент"
        )
        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=31,
            status="waiting",
            source="desk",
            patient_id=patient.id,
        )
        db_session.add(entry)
        db_session.commit()

        payload = asyncio.run(
            get_my_queue_position(current_user=patient_user, db=db_session)
        )
        assert len(payload["positions"]) == 1
        row = payload["positions"][0]
        assert row["doctor_name"] == "Ресурс очереди"
        assert row["specialty"] == "lab"
        assert row["my_number"] == 31
    finally:
        db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.patient_id == patient.id
        ).delete(synchronize_session=False)
        db_session.delete(patient)
        db_session.commit()
        _durable_cleanup(db_session, "pat_res21")


# ===================== T. Codex round-10 pins =====================


def test_display_call_patient_uses_resource_cabinet(db_session: Session) -> None:
    """Codex round-10 P1: /display/call-patient on a resource queue
    announces the registry owner and the queue's registry-sourced
    cabinet — not a doctor-less «Врач» with no destination. The
    service COMMITs — durable rows cleaned in the finally."""
    from unittest.mock import AsyncMock

    try:
        _test_display_call_body(db_session, AsyncMock)
    finally:
        _durable_cleanup(db_session, "lab_res22")


def _test_display_call_body(db_session: Session, async_mock_cls) -> None:
    import asyncio

    from app.services.display_websocket_api_service import DisplayWebSocketApiService

    _make_resource(db_session, code="lab", queue_tag="lab", max_online_per_day=15)
    resource = (
        db_session.query(QueueResource).filter(QueueResource.queue_tag == "lab").first()
    )
    resource.default_cabinet = "7"
    db_session.commit()
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    db_session.refresh(queue)
    assert queue.cabinet_number == "7"
    entry = _make_waiting_entry(db_session, queue, number=31)

    broadcast = async_mock_cls()
    service = DisplayWebSocketApiService(
        db_session,
        manager_provider=lambda: type(
            "M", (), {"broadcast_patient_call": broadcast, "connections": []}
        )(),
    )
    admin = _make_user(db_session, username="lab_res22", role="Admin")
    result = asyncio.run(
        service.call_patient(entry_id=entry.id, board_ids=[], current_user=admin)
    )

    assert result["success"] is True
    assert result["call_data"]["cabinet"] == "7"
    assert result["call_data"]["doctor"] == "Ресурс очереди"
    broadcast.assert_awaited_once()
    _, kwargs = broadcast.call_args
    assert kwargs["cabinet"] == "7"
    assert kwargs["doctor_name"] == "Ресурс очереди"


def test_cabinet_info_bridged_queue_classifies_resource(
    db_session: Session,
) -> None:
    """Codex round-10 P2: a BRIDGED queue (the 0059 backfill shape —
    specialist_id AND queue_resource_id both set) classifies as the
    resource axis (the DailyQueueOut/GQL contract): the cabinet UI
    gets resource_owned semantics, not doctor warnings."""
    from app.api.v1.endpoints.queue_cabinet_management import QueueCabinetResponse
    from app.services.queue_domain_service import QueueDomainService

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    resource.default_cabinet = "7"
    db_session.commit()
    user = _make_user(db_session, username="lab_res23", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    # the bridge: BOTH owners set (carrying the live cabinet the
    # backfilled row would have)
    bridged = _make_queue(
        db_session,
        specialist_id=synthetic.id,
        queue_tag="lab",
        queue_resource_id=resource.id,
        active=True,
    )
    bridged.cabinet_number = "7"
    db_session.commit()

    payloads = QueueDomainService(db_session).list_queue_cabinet_info(
        day=_DAY, specialist_id=None, cabinet_number=None
    )
    items = [QueueCabinetResponse(**item) for item in payloads]
    bridged_item = next(i for i in items if i.id == bridged.id)
    assert bridged_item.specialist_id == synthetic.id  # the bridge keeps both
    assert bridged_item.sync_status == "resource_owned"
    assert bridged_item.specialist_name == "Ресурс очереди"
    assert bridged_item.effective_cabinet == "7"
    assert "linked_doctor_missing" not in bridged_item.integrity_warnings


def test_queue_limits_reads_surface_usage(db_session: Session) -> None:
    """Codex round-10 P2: after the limit write lands on the resource
    surface, the limits READS report that surface's usage and cap —
    not zero usage with the doctor/global cap. Unique tag 'bio' keeps
    the pin independent of leaked lab worlds. get_queue_limits reads
    today's queues — durable rows cleaned in the finally."""
    try:
        _test_queue_limits_reads_body(db_session)
    finally:
        _durable_cleanup(db_session, "bio_res24")


def _test_queue_limits_reads_body(db_session: Session) -> None:
    from app.api.v1.endpoints.queue_limits import DoctorQueueLimit
    from app.services.queue_domain_service import QueueDomainService
    from app.services.queue_limits_api_service import QueueLimitsApiService

    user = _make_user(db_session, username="bio_res24", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="bio")
    _make_resource(db_session, code="bio", queue_tag="bio", max_online_per_day=15)
    today = date.today()
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=today, specialist_id=None, queue_tag="bio"
    )
    _make_waiting_entry(db_session, queue, number=31)
    _make_waiting_entry(db_session, queue, number=32)

    QueueLimitsApiService(db_session).set_doctor_queue_limit(
        limit_data=DoctorQueueLimit(
            doctor_id=synthetic.id, day=today, max_online_entries=7
        )
    )

    blocks = {
        block["specialty"]: block
        for block in QueueLimitsApiService(db_session).get_queue_limits(specialty="bio")
    }
    bio = blocks["bio"]
    assert bio["current_usage"] == 2  # the surface's entries
    assert bio["aggregate_max_per_day"] == 7  # the enforced surface cap

    status_rows = QueueDomainService(db_session).get_queue_limits_status(
        day=today, specialty="bio"
    )
    row = next(r for r in status_rows if r["doctor_id"] == synthetic.id)
    assert row["current_entries"] == 2
    assert row["max_entries"] == 7
    assert row["queue_opened"] is False


def test_position_by_number_resolves_resource_queue(
    db_session: Session,
) -> None:
    """Codex round-10 P2: GET /queue/position/by-number/{n} accepts the
    legacy specialist id — the queue lookup resolves the (day, tag)
    surface, so a valid resource ticket is found instead of 404. Uses
    today's queue (the flow is today-keyed) — durable rows cleaned in
    the finally."""
    try:
        _test_position_by_number_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res25")


def _test_position_by_number_body(db_session: Session) -> None:
    from app.repositories.queue_position_api_repository import (
        QueuePositionApiRepository,
    )
    from app.services.queue_position_api_service import (
        QueuePositionApiDomainError,
        QueuePositionApiService,
    )

    user = _make_user(db_session, username="lab_res25", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    today = date.today()
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=today, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue, number=31)

    found = QueuePositionApiRepository(db_session).get_today_queue_by_specialist(
        specialist_id=synthetic.id, day=today
    )
    assert found is not None and found.id == queue.id

    service = QueuePositionApiService(db_session)
    resolved = service.get_position_entry_by_number(
        queue_number=31, specialist_id=synthetic.id
    )
    assert resolved.id == entry.id

    # the doctor-keyed-only lookup would have 404'd (no doctor rows)
    with pytest.raises(QueuePositionApiDomainError):
        service.get_position_entry_by_number(
            queue_number=99, specialist_id=synthetic.id
        )


# ===================== U. Codex round-11 pins =====================


def test_display_quick_call_resolves_resource_surface(
    db_session: Session,
) -> None:
    """Codex round-11 P1: /display/quick/call-next?specialty=lab for a
    non-doctor operator resolves the (today, tag) resource surface
    BEFORE the doctor selection (the pure resource row has no
    specialist; the bridged synthetic holds the Resource role the
    doctor selection excludes) — the waiting patient is called, not a
    404. The call COMMITs — durable rows cleaned in the finally."""
    try:
        _test_quick_call_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res26")


def _test_quick_call_body(db_session: Session) -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from app.services.display_websocket_api_service import DisplayWebSocketApiService

    _make_resource(db_session, code="lab", queue_tag="lab")
    today = date.today()
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=today, specialist_id=None, queue_tag="lab"
    )
    entry = _make_waiting_entry(db_session, queue, number=31)

    broadcast = AsyncMock()
    service = DisplayWebSocketApiService(
        db_session,
        manager_provider=lambda: type(
            "M", (), {"broadcast_patient_call": broadcast, "connections": []}
        )(),
    )
    admin = _make_user(db_session, username="lab_res26", role="Admin")
    result = asyncio.run(
        service.quick_call_next(specialty="lab", board_id=None, current_user=admin)
    )

    assert result["success"] is True
    assert result["call_data"]["number"] == 31
    db_session.refresh(entry)
    assert entry.status == "called"


def test_queue_limits_dedupe_shared_surface(db_session: Session) -> None:
    """Codex round-11 P2: two active doctors of the same registry-backed
    specialty resolve ONE shared (today, tag) surface — the aggregate
    counts its usage and cap exactly once; doctors_count stays 2.
    Unique tag 'bio' keeps the pin independent of leaked worlds; the
    write COMMITs — durable rows cleaned in the finally."""
    try:
        _test_limits_dedupe_body(db_session)
    finally:
        _durable_cleanup(db_session, "bio_res27", "bio_res28")


def _test_limits_dedupe_body(db_session: Session) -> None:
    from app.api.v1.endpoints.queue_limits import DoctorQueueLimit
    from app.services.queue_limits_api_service import QueueLimitsApiService

    u1 = _make_user(db_session, username="bio_res27", role="Resource")
    d1 = _make_doctor(db_session, user_id=u1.id, specialty="bio")
    u2 = _make_user(db_session, username="bio_res28", role="doctor")
    _make_doctor(db_session, user_id=u2.id, specialty="bio")
    _make_resource(db_session, code="bio", queue_tag="bio", max_online_per_day=15)

    today = date.today()
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=today, specialist_id=None, queue_tag="bio"
    )
    _make_waiting_entry(db_session, queue, number=31)
    _make_waiting_entry(db_session, queue, number=32)

    QueueLimitsApiService(db_session).set_doctor_queue_limit(
        limit_data=DoctorQueueLimit(doctor_id=d1.id, day=today, max_online_entries=7)
    )

    blocks = {
        block["specialty"]: block
        for block in QueueLimitsApiService(db_session).get_queue_limits(specialty="bio")
    }
    bio = blocks["bio"]
    assert bio["doctors_count"] == 2
    assert bio["current_usage"] == 2  # ONCE, not doubled
    assert bio["aggregate_max_per_day"] == 7  # ONCE, not doubled


def test_queue_analytics_includes_resource_rows(db_session: Session) -> None:
    """Codex round-11 P2: GET /queue/admin/queue-analytics/{specialist}
    includes the resource-axis rows (specialist NULL) for the
    specialist's registry tag — the legacy specialist id keeps its
    totals instead of returning zeros despite recorded activity."""
    from app.api.v1.endpoints.qr_queue._analytics import get_queue_analytics
    from app.models.online_queue import QueueStatistics

    try:
        _test_queue_analytics_body(db_session, get_queue_analytics, QueueStatistics)
    finally:
        _durable_cleanup(db_session, "lab_res29", "admin_anl29", "dr_anl30")


def _test_queue_analytics_body(
    db_session, get_queue_analytics, QueueStatistics
) -> None:
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    db_session.add(
        QueueStatistics(
            queue_id=queue.id,
            date=_DAY,
            online_joins=3,
            desk_registrations=2,
            telegram_joins=1,
            confirmation_joins=0,
            total_served=4,
            total_no_show=1,
        )
    )
    db_session.commit()

    user = _make_user(db_session, username="lab_res29", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    admin = _make_user(db_session, username="admin_anl29", role="Admin")

    payload = get_queue_analytics(synthetic.id, db=db_session, current_user=admin)
    assert payload["totals"]["online_joins"] == 3
    assert payload["totals"]["total_served"] == 4

    # a non-registry doctor's analytics stay doctor-keyed
    other_user = _make_user(db_session, username="dr_anl30", role="doctor")
    other = _make_doctor(db_session, user_id=other_user.id, specialty="cardio")
    cardio = _make_queue(
        db_session, specialist_id=other.id, queue_tag="cardio", active=True
    )
    db_session.add(
        QueueStatistics(
            queue_id=cardio.id,
            date=_DAY,
            online_joins=9,
            desk_registrations=0,
            telegram_joins=0,
            confirmation_joins=0,
            total_served=1,
            total_no_show=0,
        )
    )
    db_session.commit()
    other_payload = get_queue_analytics(other.id, db=db_session, current_user=admin)
    assert other_payload["totals"]["online_joins"] == 9


# ===================== V. Codex round-12 pins =====================


def test_legacy_call_broadcasts_resource_owner(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-12 P1: POST /queue/call/{entry_id} on a resource
    queue broadcasts the registry owner and the queue's registry-sourced
    cabinet to the display/voice announcement — not «Специалист #None»
    with no cabinet. The route COMMITs — durable rows cleaned in the
    finally."""
    import asyncio

    from app.services import display_websocket as dw

    broadcast_calls: dict = {}

    class FakeManager:
        connections: list = []

        async def broadcast_patient_call(self, **kwargs):
            broadcast_calls.update(kwargs)

    monkeypatch.setattr(dw, "get_display_manager", lambda: FakeManager())

    try:
        from app.api.v1.endpoints.queue import call_patient

        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.default_cabinet = "7"
        db_session.commit()
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        db_session.refresh(queue)
        entry = _make_waiting_entry(db_session, queue, number=31)
        caller = _make_user(db_session, username="lab_res31", role="Registrar")

        async def scenario():
            result = call_patient(entry.id, db=db_session, current_user=caller)
            await asyncio.sleep(0.05)  # let the fire-and-forget task run
            return result

        payload = asyncio.run(scenario())
        assert payload["success"] is True
        assert broadcast_calls["doctor_name"] == "Ресурс очереди"
        assert broadcast_calls["cabinet"] == "7"
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "lab_res31")


def test_registrar_cards_build_from_resource_owner(db_session: Session) -> None:
    """Codex round-12 P2: GET /registrar/queues/today marks resource
    queues as their own owner — no linked_doctor_missing warning, the
    registry display_name as the specialist identity and the queue's
    cabinet instead of «Специалист #None» / N/A."""
    from app.api.v1.endpoints.registrar_integration._queue_ops import (
        _build_queue_payload,
        _process_online_queue_entries,
    )

    _make_resource(db_session, code="lab", queue_tag="lab")
    resource = (
        db_session.query(QueueResource).filter(QueueResource.queue_tag == "lab").first()
    )
    resource.default_cabinet = "7"
    db_session.commit()
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    db_session.refresh(queue)
    assert queue.cabinet_number == "7"
    entry = _make_waiting_entry(db_session, queue, number=31)

    queues_by_specialty: dict = {}
    _process_online_queue_entries(db_session, [entry], [], queues_by_specialty, set())
    bucket = queues_by_specialty["laboratory"]  # the tag->specialty mapping
    assert "linked_doctor_missing" not in bucket.get("integrity_warnings", [])
    assert bucket["resource_display_name"] == "Ресурс очереди"
    assert bucket["resource_cabinet"] == "7"

    payload = _build_queue_payload(
        queue_data=bucket,
        specialty="laboratory",
        queue_number=1,
        entries=[{"id": entry.id, "status": "waiting"}],
    )
    assert payload["specialist_name"] == "Ресурс очереди"
    assert payload["cabinet"] == "7"
    assert payload["has_integrity_warnings"] is False


def test_assign_queue_token_metadata_resource_cabinet(
    db_session: Session,
) -> None:
    """Codex round-12 P2: the QR token metadata advertises the registry
    owner and the queue's registry-sourced cabinet (not the synthetic
    doctor's stale one) once the surface is resource-owned. The token
    COMMITs — durable rows cleaned in the finally."""
    try:
        _test_qr_metadata_body(db_session)
    finally:
        _durable_cleanup(db_session, "lab_res32")


def _test_qr_metadata_body(db_session: Session) -> None:
    user = _make_user(db_session, username="lab_res32", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    synthetic.cabinet = "42"  # the STALE legacy cabinet
    db_session.commit()
    _make_resource(db_session, code="lab", queue_tag="lab")
    resource = (
        db_session.query(QueueResource).filter(QueueResource.queue_tag == "lab").first()
    )
    resource.default_cabinet = "7"
    db_session.commit()

    _token_value, metadata = queue_service.assign_queue_token(
        db_session,
        specialist_id=synthetic.id,
        department="lab",
        generated_by_user_id=None,
        target_date=_DAY,
        queue_tag="lab",
        commit=False,
    )
    assert metadata["cabinet"] == "7"  # NOT the synthetic's stale "42"
    assert metadata["specialist_name"] == "Ресурс очереди"
    assert metadata["queue_id"] is not None


# ===================== W. Codex round-13 pins =====================


def test_gql_queue_entries_filter_sees_resource_axis(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-13 P2: queueEntries(filter: {doctorId}) for the
    selected registry-tag specialist returns the entries joinQueue
    placed onto the pure resource queue — the doctor-keyed predicate
    alone saw NULL specialist rows as invisible."""
    import asyncio
    import contextlib
    from types import SimpleNamespace

    from app.graphql import resolvers as gql_resolvers
    from app.graphql.types import QueueFilter

    monkeypatch.setattr(
        gql_resolvers,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )

    try:
        user = _make_user(db_session, username="lab_res_w1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        assert queue.specialist_id is None  # the invisible shape
        entry = _make_waiting_entry(db_session, queue, number=41)

        # a doctor-queue entry (regression: the doctor axis stays)
        doc_user = _make_user(db_session, username="dr_w1_axis", role="Doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        doc_queue = _make_queue(
            db_session, specialist_id=doctor.id, queue_tag="cardiology"
        )
        doc_entry = _make_waiting_entry(db_session, doc_queue, number=7)

        info = SimpleNamespace(context=None)  # direct schema test: no audit ctx
        result = asyncio.run(
            gql_resolvers.Query().queue_entries(
                info, QueueFilter(doctor_id=synthetic.id, queue_date=_DAY)
            )
        )
        ids = [e.id for e in result.items]
        assert entry.id in ids  # the resource-axis entry is now visible
        joined = next(e for e in result.items if e.id == entry.id)
        assert joined.queue is not None
        assert joined.queue.queue_resource_id == resource.id
        # the doctor-tag filter keeps its per-doctor contract
        result_doc = asyncio.run(
            gql_resolvers.Query().queue_entries(
                info, QueueFilter(doctor_id=doctor.id, queue_date=_DAY)
            )
        )
        assert [e.id for e in result_doc.items] == [doc_entry.id]
    finally:
        _durable_cleanup(db_session, "lab_res_w1", "dr_w1_axis")


def test_gql_queue_entries_filter_tag_axis_doctor_without_resource_rows(
    db_session: Session, monkeypatch
) -> None:
    """Negative: a doctor whose specialty has NO resource rows — the
    tag-axis predicate matches nothing, the filter is the plain
    doctor predicate (self-gated by the data invariant)."""
    import asyncio
    import contextlib
    from types import SimpleNamespace

    from app.graphql import resolvers as gql_resolvers
    from app.graphql.types import QueueFilter

    monkeypatch.setattr(
        gql_resolvers,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )

    user = _make_user(db_session, username="dr_w1_neg", role="Doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardiology")
    queue = _make_queue(db_session, specialist_id=doctor.id, queue_tag="cardiology")
    entry = _make_waiting_entry(db_session, queue, number=9)

    try:
        info = SimpleNamespace(context=None)
        result = asyncio.run(
            gql_resolvers.Query().queue_entries(info, QueueFilter(doctor_id=doctor.id))
        )
        assert [e.id for e in result.items] == [entry.id]
    finally:
        _durable_cleanup(db_session, "dr_w1_neg")


def test_reorder_snapshot_resolves_registry_surface(db_session: Session) -> None:
    """Codex round-13 P2: get_queue_snapshot_by_specialist_day for a
    registry-tag specialist resolves the (day, tag) surface — a pure
    resource queue is no longer a 404, and the surface wins over a
    doctor-keyed legacy shadow. Doctor tags without a surface keep
    the 404 contract."""
    from app.services.queue_domain_service import (
        QueueDomainReadError,
        QueueDomainService,
    )

    try:
        user = _make_user(db_session, username="lab_res_w2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        assert queue.specialist_id is None
        entry = _make_waiting_entry(db_session, queue, number=3)

        service = QueueDomainService(db_session)
        snapshot = service.get_queue_snapshot_by_specialist_day(
            specialist_id=synthetic.id, day=_DAY
        )
        assert snapshot.queue.id == queue.id  # was a 404 before the fix
        assert [e.id for e in snapshot.entries] == [entry.id]

        # a doctor-keyed legacy shadow (created AFTER the surface) loses
        # to the registry surface — the same prefer-registry semantics
        # as the limit-status read
        shadow = _make_queue(db_session, specialist_id=synthetic.id, queue_tag="lab")
        assert shadow.id > queue.id
        snapshot = service.get_queue_snapshot_by_specialist_day(
            specialist_id=synthetic.id, day=_DAY
        )
        assert snapshot.queue.id == queue.id

        # doctor tag without a queue: the 404 contract is unchanged
        other_user = _make_user(db_session, username="dr_w2_plain", role="Doctor")
        other = _make_doctor(db_session, user_id=other_user.id, specialty="cardiology")
        with pytest.raises(QueueDomainReadError) as exc_info:
            service.get_queue_snapshot_by_specialist_day(
                specialist_id=other.id, day=_DAY
            )
        assert exc_info.value.status_code == 404
    finally:
        _durable_cleanup(db_session, "lab_res_w2", "dr_w2_plain")


def test_qr_call_next_rest_broadcasts_registry_owner(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-13 P2: POST /qr_queue/{specialist_id}/call-next on a
    resource queue announces the registry owner (display_name) and the
    registry-sourced cabinet on the TV broadcast — not «Врач» with no
    cabinet. The service COMMITs — durable rows cleaned in the
    finally."""
    import asyncio

    from app.services import display_websocket as dw

    broadcast_calls: dict = {}

    class FakeManager:
        connections: list = []

        async def broadcast_patient_call(self, **kwargs):
            broadcast_calls.update(kwargs)

    monkeypatch.setattr(dw, "get_display_manager", lambda: FakeManager())

    try:
        from app.api.v1.endpoints.qr_queue._queue_ops import call_next_patient

        user = _make_user(db_session, username="lab_res_w3a", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.default_cabinet = "7"
        db_session.commit()
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        db_session.refresh(queue)
        assert queue.cabinet_number == "7"  # copied at creation (round-8)
        entry = _make_waiting_entry(db_session, queue, number=21)
        caller = _make_user(db_session, username="reg_w3a", role="Registrar")

        async def scenario():
            return await call_next_patient(
                synthetic.id,
                target_date=_DAY.isoformat(),
                db=db_session,
                current_user=caller,
            )

        payload = asyncio.run(scenario())
        assert payload.success is True
        assert broadcast_calls["doctor_name"] == "Ресурс очереди"
        assert broadcast_calls["cabinet"] == "7"
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "lab_res_w3a", "reg_w3a")


def test_gql_call_next_announces_registry_owner(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-13 P2: the GraphQL callNextPatient wrapper derives
    the display payload owner from the ownership axis — a resource
    queue broadcasts the registry display_name and the registry-sourced
    cabinet (payload.cabinet + display_message), not «Врач»/None. The
    impl COMMITs — durable rows cleaned in the finally."""
    import contextlib
    from datetime import datetime
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from app.graphql import mutations as gql_mutations

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )

    try:
        user = _make_user(db_session, username="lab_res_w3b", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.default_cabinet = "7"
        db_session.commit()
        # the impl picks the queue day from the configured TZ (round-9)
        tz_day = datetime.now(ZoneInfo("Asia/Tashkent")).date()
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=tz_day, specialist_id=None, queue_tag="lab"
        )
        db_session.refresh(queue)
        entry = _make_waiting_entry(db_session, queue, number=33)
        actor = _make_user(db_session, username="adm_w3b", role="Admin")

        info = SimpleNamespace(context=SimpleNamespace(user=actor, request=None))
        payload = gql_mutations.Mutation._call_next_patient_impl(
            info, synthetic.id, None
        )
        assert payload["success"] is True, payload
        assert payload["cabinet"] == "7"
        message = payload["display_message"]
        assert message is not None
        assert message["data"]["doctor_name"] == "Ресурс очереди"
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "lab_res_w3b", "adm_w3b")


def test_department_overview_counts_resource_entries(
    db_session: Session,
) -> None:
    """Codex round-13 P2: _collect_department_overview counts entries
    from resource-owned queues through the tag/profile department
    axis (QueueProfile.department_key == department.key → 'lab' under
    'laboratory') while the doctor axis keeps counting its own
    entries. Commits (get_or_create) — cleaned in the finally."""
    from datetime import datetime

    from app.api.v1.endpoints.admin_departments._helpers import (
        _collect_department_overview,
    )
    from app.models.department import Department
    from app.models.queue_profile import QueueProfile

    today = datetime.now().date()
    department = Department(key="laboratory", name_ru="Лаборатория")
    profile = QueueProfile(
        key="laboratory",
        title="Лаборатория",
        queue_tags=["lab", "laboratory"],
        department_key="laboratory",
    )
    try:
        db_session.add(department)
        db_session.add(profile)
        db_session.commit()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=today, specialist_id=None, queue_tag="lab"
        )
        assert queue.specialist_id is None
        _make_waiting_entry(db_session, queue, number=5)

        # doctor axis: a doctor of THIS department with its own queue
        doc_user = _make_user(db_session, username="dr_w4_lab", role="Doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="biochem")
        doctor.department_id = department.id
        db_session.commit()
        doc_queue = _make_queue(
            db_session, day=today, specialist_id=doctor.id, queue_tag="biochem"
        )
        _make_waiting_entry(db_session, doc_queue, number=2)

        overview = _collect_department_overview(db_session)
        item = next(i for i in overview["departments"] if i["key"] == "laboratory")
        assert item["stats"]["queue_entries_today"] == 2  # both axes
        # the aggregate total absorbs the resource axis too
        assert overview["totals"]["queue_entries_today"] >= 2
    finally:
        _durable_cleanup(db_session, "dr_w4_lab")
        db_session.query(QueueProfile).filter(
            QueueProfile.department_key == "laboratory"
        ).delete(synchronize_session=False)
        db_session.query(Department).filter(Department.key == "laboratory").delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== X. Codex round-14 pins =====================


def test_call_next_prefers_surface_over_untagged_shadow(db_session: Session) -> None:
    """Codex round-14 P1: the canonical call-next selector prefers the
    registry surface BEFORE accepting doctor-keyed candidates — an
    active untagged synthetic-doctor shadow must not win the selection
    while patients wait on the live resource queue. The service COMMITs
    — durable rows cleaned in the finally."""
    try:
        from app.services.qr_queue import QRQueueService

        user = _make_user(db_session, username="lab_res_x1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        assert queue.specialist_id is None
        surface_entry = _make_waiting_entry(db_session, queue, number=5)

        # the ACTIVE UNTAGGED doctor-keyed shadow with its own waiting
        # patient — the legacy-writer artifact (round-6 shape)
        shadow = _make_queue(db_session, specialist_id=synthetic.id, queue_tag=None)
        assert shadow.queue_tag is None
        shadow_entry = _make_waiting_entry(db_session, shadow, number=99)

        service = QRQueueService(db_session)
        result = service.call_next_patient(synthetic.id, None, target_date=_DAY)
        assert result["success"] is True
        db_session.refresh(surface_entry)
        db_session.refresh(shadow_entry)
        # the SURFACE patient advances; the shadow patient stays waiting
        assert surface_entry.status == "called"
        assert shadow_entry.status == "waiting"
    finally:
        _durable_cleanup(db_session, "lab_res_x1")


def test_qr_time_restrictions_prefer_surface_over_shadow(
    db_session: Session,
) -> None:
    """Codex round-14 P2: _check_online_time_restrictions prefers the
    registry surface (prefer_registry_surface) — an active doctor-keyed
    shadow with opened_at set must not close the reception while the
    live resource surface is still accepting. Future-day token keeps
    the verdict deterministic. The service COMMITs — durable rows
    cleaned in the finally."""
    try:
        from datetime import datetime, timedelta

        from app.models.online_queue import QueueToken
        from app.services.qr_queue import QRQueueService

        future_day = datetime.now().date() + timedelta(days=30)
        user = _make_user(db_session, username="lab_res_x2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        surface = _make_queue(
            db_session,
            day=future_day,
            specialist_id=None,
            queue_tag="lab",
            active=True,
        )
        surface.queue_resource_id = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
            .id
        )
        db_session.commit()

        # the shadow: opened reception on the same future day
        shadow = _make_queue(
            db_session,
            day=future_day,
            specialist_id=synthetic.id,
            queue_tag=None,
            active=True,
        )
        shadow.opened_at = datetime.now()
        db_session.commit()

        token = QueueToken(
            token="tok-x2",
            day=future_day,
            specialist_id=synthetic.id,
            department="lab",
            is_clinic_wide=False,
            expires_at=datetime.now() + timedelta(days=60),
        )
        db_session.add(token)
        db_session.commit()

        service = QRQueueService(db_session)
        result = service._check_online_time_restrictions("tok-x2")
        # the SURFACE is evaluated (not opened, future date → allowed),
        # not the shadow (which would say closed_reception_opened)
        assert result["allowed"] is True, result
        assert result["status"] != "closed_reception_opened"
    finally:
        _durable_cleanup(db_session, "lab_res_x2")
        db_session.query(QueueToken).filter(QueueToken.token == "tok-x2").delete(
            synchronize_session=False
        )
        db_session.commit()


def test_position_info_reports_resource_owner(db_session: Session) -> None:
    """Codex round-14 P2: get_queue_position_info builds queue_info
    from the ownership axis — a resource ticket reachable through the
    by-number fallback reports the registry display_name (and the
    default_cabinet when the queue row carries none), not a position
    with no destination name."""
    from app.services.queue_position_notifications import (
        get_queue_position_service,
    )

    _make_resource(db_session, code="lab", queue_tag="lab")
    resource = (
        db_session.query(QueueResource).filter(QueueResource.queue_tag == "lab").first()
    )
    resource.default_cabinet = "7"
    db_session.commit()
    queue = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    assert queue.cabinet_number is None  # exercise the registry fallback
    entry = _make_waiting_entry(db_session, queue, number=12)
    entry.queue_time = datetime(2026, 9, 7, 8, 0)  # _count_people_ahead needs it
    db_session.commit()

    info = get_queue_position_service(db_session).get_queue_position_info(entry)
    assert info["queue_info"]["specialist_name"] == "Ресурс очереди"
    assert info["queue_info"]["cabinet_number"] == "7"  # default_cabinet fallback
    assert info["queue_number"] == 12

    # doctor-queue regression: the specialist axis is unchanged
    doc_user = _make_user(db_session, username="dr_x3_axis", role="Doctor")
    doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
    doc_queue = _make_queue(db_session, specialist_id=doctor.id, queue_tag="cardiology")
    doc_entry = _make_waiting_entry(db_session, doc_queue, number=3)
    doc_entry.queue_time = datetime(2026, 9, 7, 8, 30)
    db_session.commit()
    doc_info = get_queue_position_service(db_session).get_queue_position_info(doc_entry)
    assert doc_info["queue_info"]["specialist_name"] == "dr_x3_axis"


def _shared_session(inner: Session):
    """Delegates to the test session; close() is a no-op (the fixture
    owns the lifecycle) — for manager code that opens SessionLocal()."""

    class _Shared:
        def __getattr__(self, name):
            return getattr(inner, name)

        def close(self) -> None:  # noqa: D102 — see docstring
            pass

    return _Shared()


def test_display_state_snapshots_use_resource_owner(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-14 P2: the display state snapshots carry the registry
    owner — broadcast_daily_queue_state reports display_name + the
    registry-sourced cabinet, and _send_current_state labels the
    resource queue entries with display_name instead of «Врач #None»."""
    import asyncio
    import json
    from datetime import datetime

    from app.services import display_websocket as dw

    today = datetime.now().date()
    monkeypatch.setattr(dw, "SessionLocal", lambda: _shared_session(db_session))

    _make_resource(db_session, code="lab", queue_tag="lab")
    resource = (
        db_session.query(QueueResource).filter(QueueResource.queue_tag == "lab").first()
    )
    resource.display_name = "Лаборатория (X4)"
    resource.default_cabinet = "7"
    db_session.commit()
    queue = _make_queue(
        db_session,
        day=today,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    db_session.refresh(queue)
    entry = _make_waiting_entry(db_session, queue, number=4)

    manager = dw.DisplayWebSocketManager.__new__(dw.DisplayWebSocketManager)
    manager.connections = {}
    manager.board_states = {}

    captured: dict = {}

    async def record_board(board_id: str, message: dict) -> None:
        captured.setdefault("broadcasts", []).append(message)

    manager.broadcast_to_board = record_board  # type: ignore[method-assign]

    asyncio.run(manager.broadcast_daily_queue_state(queue, board_ids=["board-x"]))
    message = captured["broadcasts"][0]
    assert message["type"] == "queue_update"
    assert message["data"]["doctor_name"] == "Лаборатория (X4)"
    assert message["data"]["cabinet"] == "7"
    assert message["data"]["specialty"] == "lab"

    # the reconnect snapshot (initial_state) labels the resource queue
    # entries with the registry owner, not «Врач #None»
    sent: dict = {}

    class FakeWebSocket:
        async def send_text(self, payload: str) -> None:
            sent["payload"] = payload

    asyncio.run(manager._send_current_state(FakeWebSocket(), "board-x"))
    state = json.loads(sent["payload"])
    resource_rows = [
        e for e in state["data"]["queue_entries"] if e["specialist_id"] is None
    ]
    assert resource_rows, "resource entry expected in the initial state"
    assert all(e["specialist_name"] == "Лаборатория (X4)" for e in resource_rows)
    target = next(e for e in resource_rows if e["id"] == entry.id)
    assert target["number"] == 4


# ===================== Y. Codex round-15 pins =====================


def test_reorder_preserves_resource_number_floor(db_session: Session) -> None:
    """Codex round-15 P2: reorder/move operate on POSITIONS (1..N) but
    a resource queue stores NUMBERS from the registry floor — tickets
    40/41 must not become 1/2 (the next allocation would reprint №40).
    Doctor queues without a floor keep the legacy numbering. The
    service COMMITs — durable rows cleaned in the finally."""
    try:
        from app.services.queue_reorder_api_service import QueueReorderApiService

        admin = _make_user(db_session, username="adm_y1", role="Admin")
        _make_resource(db_session, code="lab", queue_tag="lab", start_number_online=40)
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        first = _make_waiting_entry(db_session, queue, number=40)
        second = _make_waiting_entry(db_session, queue, number=41)

        service = QueueReorderApiService(db_session)
        # swap the two tickets by position: 41→pos1, 40→pos2
        updated, info = service.reorder_queue(
            queue_id=queue.id,
            entry_orders=[
                {"entry_id": second.id, "new_position": 1},
                {"entry_id": first.id, "new_position": 2},
            ],
            current_user=admin,
        )
        assert updated == 2
        db_session.refresh(first)
        db_session.refresh(second)
        # numbers stay in the registry floor space — no 1/2
        assert {first.number, second.number} == {40, 41}
        assert first.number == 41
        assert second.number == 40
        assert info["specialist_name"] == "Ресурс очереди"
        assert info["queue_resource_id"] is not None

        # move: the ticket now at number 40 back to position 2
        moved = _make_waiting_entry(db_session, queue, number=42)
        message, count, _ = service.move_queue_entry(
            entry_id=moved.id, new_position=1, current_user=admin
        )
        assert count >= 1
        db_session.refresh(moved)
        assert moved.number == 40  # position 1 → the floor, not 1

        # doctor-queue regression: no floor → positions are the numbers
        doc_user = _make_user(db_session, username="dr_y1_axis", role="Doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        doc_queue = _make_queue(db_session, specialist_id=doctor.id, queue_tag=None)
        doc_first = _make_waiting_entry(db_session, doc_queue, number=1)
        doc_second = _make_waiting_entry(db_session, doc_queue, number=2)
        _, doc_info = service.reorder_queue(
            queue_id=doc_queue.id,
            entry_orders=[
                {"entry_id": doc_second.id, "new_position": 1},
                {"entry_id": doc_first.id, "new_position": 2},
            ],
            current_user=admin,
        )
        db_session.refresh(doc_first)
        db_session.refresh(doc_second)
        assert (doc_first.number, doc_second.number) == (2, 1)  # legacy semantics
        assert doc_info["specialist_name"] == "dr_y1_axis"
        assert doc_info["queue_resource_id"] is None
    finally:
        _durable_cleanup(db_session, "adm_y1", "dr_y1_axis")


def test_reorder_status_serializes_resource_owner(db_session: Session) -> None:
    """Codex round-15 P2: /queue/reorder/status/by-specialist for a
    registry-tag specialist serializes the registry owner — the
    display_name and the resource identity, not «Неизвестно» with a
    null doctor."""
    from app.services.queue_reorder_api_service import QueueReorderApiService

    user = _make_user(db_session, username="lab_res_y2", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    _make_waiting_entry(db_session, queue, number=40)

    info = QueueReorderApiService(db_session).get_queue_status_by_specialist(
        specialist_id=synthetic.id, day=_DAY
    )
    assert info["queue_id"] == queue.id  # the round-13 surface resolve
    assert info["specialist_name"] == "Ресурс очереди"
    assert info["specialist_id"] is None
    assert info["queue_resource_id"] == resource.id
    assert info["total_entries"] == 1


def test_morning_summary_labels_resource_rows(db_session: Session) -> None:
    """Codex round-15 P2: /admin/morning-assignment/queue-summary labels
    resource queues with the registry display_name (and the resource
    identity), not «ID:None» with a null doctor; doctor rows are
    unchanged. Commits (get_or_create) — cleaned in the finally."""
    from datetime import datetime

    from app.services.morning_assignment_api_service import (
        MorningAssignmentApiService,
    )

    today = datetime.now().date()
    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.display_name = "Лаборатория (Y3)"
        db_session.commit()
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=today, specialist_id=None, queue_tag="lab"
        )
        _make_waiting_entry(db_session, queue, number=40)

        doc_user = _make_user(db_session, username="dr_y3_axis", role="Doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        doc_queue = _make_queue(
            db_session, day=today, specialist_id=doctor.id, queue_tag="cardiology"
        )
        _make_waiting_entry(db_session, doc_queue, number=1)

        payload = MorningAssignmentApiService(db_session).get_queue_summary_payload(
            target_date=today
        )
        rows = {row["queue_id"]: row for row in payload["queues"]}
        resource_row = rows[queue.id]
        assert resource_row["doctor_name"] == "Лаборатория (Y3)"
        assert resource_row["doctor_id"] is None
        assert resource_row["queue_resource_id"] == resource.id
        assert resource_row["entries_count"] == 1

        doctor_row = rows[doc_queue.id]
        assert doctor_row["doctor_name"] == "dr_y3_axis"
        assert doctor_row["doctor_id"] == doctor.id
        assert doctor_row["queue_resource_id"] is None
    finally:
        _durable_cleanup(db_session, "dr_y3_axis")


# ===================== Z. Codex round-16 pins =====================


def test_reorder_slots_preserve_served_numbers(db_session: Session) -> None:
    """Codex round-16 P2: reorder/move map positions onto the EXISTING
    active number slots — a served (terminal) ticket 40 is neither
    duplicated nor reused: the by-number lookup accepts served rows,
    so a rebuilt 40 would resolve a fresh patient to the old entry.
    The service COMMITs — durable rows cleaned in the finally."""
    try:
        from app.services.queue_reorder_api_service import QueueReorderApiService

        admin = _make_user(db_session, username="adm_z1", role="Admin")
        _make_resource(db_session, code="lab", queue_tag="lab", start_number_online=40)
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        served = _make_waiting_entry(db_session, queue, number=40)
        served.status = "served"
        db_session.commit()
        first = _make_waiting_entry(db_session, queue, number=41)
        second = _make_waiting_entry(db_session, queue, number=42)

        service = QueueReorderApiService(db_session)
        _, info = service.reorder_queue(
            queue_id=queue.id,
            entry_orders=[
                {"entry_id": second.id, "new_position": 1},
                {"entry_id": first.id, "new_position": 2},
            ],
            current_user=admin,
        )
        db_session.refresh(first)
        db_session.refresh(second)
        db_session.refresh(served)
        # the ACTIVE numbers stay 41/42 — the served 40 is untouched
        assert {first.number, second.number} == {41, 42}
        assert served.number == 40
        assert served.status == "served"
        assert info["queue_resource_id"] is not None

        # move: position 1 maps onto the smallest ACTIVE slot (41),
        # not the served 40 and not a floor rebuild
        third = _make_waiting_entry(db_session, queue, number=43)
        service.move_queue_entry(entry_id=third.id, new_position=1, current_user=admin)
        db_session.refresh(third)
        assert third.number == 41
    finally:
        _durable_cleanup(db_session, "adm_z1")


def test_full_update_independent_entry_uses_resource_floor(
    db_session: Session,
) -> None:
    """Codex round-16 P2: the independent-entry allocator (registrar
    full-update, additional lab/ECG service) routes through the
    numbering SSOT — an empty resource queue issues the registry floor
    (40), not the raw MAX+1 = 1. Doctor queues keep MAX+1."""
    from types import SimpleNamespace

    from app.api.v1.endpoints.qr_queue._online_entries import (
        _full_update_create_single_independent_entry,
    )

    doc_user = _make_user(db_session, username="dr_z2", role="Doctor")
    doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
    source_queue = _make_queue(
        db_session, specialist_id=doctor.id, queue_tag="cardiology"
    )
    source = _make_waiting_entry(db_session, source_queue, number=5)

    resource = _make_resource(
        db_session, code="lab", queue_tag="lab", start_number_online=40
    )
    target_queue = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    assert target_queue.id != source_queue.id

    from datetime import datetime as _dt

    queue_time = _dt(2026, 9, 7, 8, 0)
    request = SimpleNamespace(discount_mode=None, all_free=False)
    service_stub = SimpleNamespace(
        id=1,
        name="Лабораторная панель",
        queue_tag="lab",
        price=1000,
        is_consultation=False,
        service_code="LAB1",
    )
    created = _full_update_create_single_independent_entry(
        db_session, source, request, service_stub, None, queue_time
    )
    assert created.queue_id == target_queue.id
    assert created.number == 40  # the registry floor, not MAX+1 = 1
    assert created.status == "waiting"

    # a doctor-target queue keeps the raw MAX+1 sequence
    doctor_target = _make_queue(db_session, specialist_id=doctor.id, queue_tag="cardio")
    service_stub_cardio = SimpleNamespace(
        id=2,
        name="Консультация",
        queue_tag="cardio",
        price=500,
        is_consultation=True,
        service_code="CARD1",
    )
    created_doctor = _full_update_create_single_independent_entry(
        db_session, source, request, service_stub_cardio, None, queue_time
    )
    assert created_doctor.queue_id == doctor_target.id
    assert created_doctor.number == 1  # empty doctor queue: MAX+1


def test_cabinet_sync_skips_resource_rows(db_session: Session) -> None:
    """Codex round-16 P2: POST /admin/queues/sync-cabinet-info does not
    overwrite a bridged (0059) queue's registry-sourced cabinet with
    the synthetic doctor's stale one; doctor queues still sync. The
    service COMMITs — durable rows cleaned in the finally."""
    try:
        from app.services.queue_cabinet_management_api_service import (
            QueueCabinetManagementApiService,
        )

        user = _make_user(db_session, username="lab_res_z3", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        synthetic.cabinet = "42"  # the STALE synthetic cabinet
        db_session.commit()
        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        bridged = _make_queue(
            db_session,
            specialist_id=synthetic.id,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        bridged.cabinet_number = "7"  # the resource destination in use
        db_session.commit()

        doc_user = _make_user(db_session, username="dr_z3", role="Doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        doctor.cabinet = "5"
        db_session.commit()
        doc_queue = _make_queue(
            db_session, specialist_id=doctor.id, queue_tag="cardiology"
        )
        doc_queue.cabinet_number = None
        db_session.commit()

        result = QueueCabinetManagementApiService(
            db_session
        ).sync_cabinet_info_from_doctors(
            day=_DAY.isoformat(), specialist_id=None, synced_by="admin"
        )
        db_session.refresh(bridged)
        db_session.refresh(doc_queue)
        assert result["success"] is True
        # the bridged resource destination survives the sync
        assert bridged.cabinet_number == "7"  # NOT the synthetic's 42
        # the doctor queue still syncs from its doctor
        assert doc_queue.cabinet_number == "5"
    finally:
        _durable_cleanup(db_session, "lab_res_z3", "dr_z3")
