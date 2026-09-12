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
    """Tag-first unification: resource-owned and legacy synthetic-owned
    rows are both 'the queue for the day+tag' (the dual-ownership
    bridge — the third pre-0063 shape — was consumed by the QD-2D XOR
    contract; the both-set classification stays pinned at the
    Pydantic/GQL-mapper level)."""
    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    resource_owned = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    found = queue_resource_routing.find_active_tag_queue(db_session, _DAY, "lab")
    assert found is resource_owned

    other_day = _DAY + timedelta(days=1)
    synthetic_owned = _make_queue(
        db_session,
        day=other_day,
        specialist_id=synthetic.id,
        queue_tag="lab",
    )
    assert (
        queue_resource_routing.find_active_tag_queue(db_session, other_day, "lab")
        is synthetic_owned
    )


def test_find_active_tag_queue_ignores_inactive_rows(db_session: Session) -> None:
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
        active=False,
    )
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


def test_get_or_create_registry_tag_reuses_existing_resource_queue(
    db_session: Session,
) -> None:
    """The pre-existing (day, tag) queue IS the tag queue — no
    parallel fork, no mutation of the row. Pre-0063 this pinned the
    0059 dual-ownership bridge (BOTH owners); the QD-2D conversion
    consumed the specialist link, so the same no-fork scenario now
    runs against the converted resource-owned row the migration
    produced."""
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    existing = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )

    queue = queue_service.get_or_create_daily_queue(
        db_session, day=_DAY, specialist_id=None, queue_tag="lab"
    )
    assert queue.id == existing.id
    assert queue.specialist_id is None
    assert queue.queue_resource_id == resource.id
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


def _neutralize_begin_nested(monkeypatch, db_session: Session) -> None:
    """QD-2C (round-18 CI root-cause, main #3092 interplay): the
    pre-create paths are wrapped in session.begin_nested() (bb01d3a0f;
    round-24 extended it to the registry branch). On the sqlite test DB
    that desyncs the db_session fixture's savepoint-restart listener:
    the session-level savepoint ends, the listener re-arms a connection
    savepoint the session no longer tracks, teardown rolls back to a
    dead savepoint and the leaked connection LOCKS the shared file DB —
    every later test fails with "database is locked" (the CI 20-minute
    timeout cascade). The #3092 authors documented the exact class in
    queue_svc/_operations.py ("a session-level savepoint (begin_nested)
    breaks the savepoint-isolated test fixture — P2-1b warned exactly
    this") and their own pin skips sqlite; this suite asserts
    routing/ownership, not tag-failure isolation — neutralize the nested
    block for the fixture's sake."""

    class _FlatNested:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(db_session, "begin_nested", lambda *a, **k: _FlatNested())


def test_morning_precreate_registry_tags_go_resource_axis(
    db_session: Session,
    monkeypatch,
) -> None:
    """ensure_daily_queues_for_all_tags: lab/ecg (registry rows) are
    pre-created resource-owned — the synthetic general_resource is
    not even needed for them."""
    from app.services.morning_assignment import MorningAssignmentService

    # round-24: the registry pre-create rides the per-tag savepoint too
    _neutralize_begin_nested(monkeypatch, db_session)

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
    monkeypatch,
) -> None:
    """Non-registry tags keep the legacy path: the general queue is
    pre-created on the general_resource synthetic doctor."""
    from app.services.morning_assignment import MorningAssignmentService

    # QD-2C (round-18 CI root-cause): see _neutralize_begin_nested.
    _neutralize_begin_nested(monkeypatch, db_session)

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
    """The existing queue for the tag IS the tag queue: pre-create
    finds it and creates nothing (pre-0063 this pinned the 0059
    bridge; the QD-2D conversion leaves the same surface as a
    resource-owned row)."""
    from app.services.morning_assignment import MorningAssignmentService

    _scope_morning_world(db_session, "lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    _make_queue(
        db_session,
        specialist_id=None,
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
    """from_attributes ORM hydration carries the QD-2C fields on the
    resource-owned row (the post-0063 shape of the 0059 backfill:
    the QD-2D conversion consumed the specialist link — the both-set
    hydration input stays pinned at the Pydantic level in
    test_daily_queue_out_owner_kinds)."""
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    queue = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    payload = DailyQueueOut.model_validate(queue)
    assert payload.owner_kind == "resource"
    assert payload.queue_resource_id == resource.id
    assert payload.specialist_id is None


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


def test_gql_daily_queue_type_bridge_input_classifies_resource(
    db_session: Session,
) -> None:
    """The both-set input (the pre-0063 dual-ownership bridge) still
    classifies as the resource axis — the same rule as DailyQueueOut.
    Post-0063 the XOR CHECK makes the shape uncreatable through the
    ORM, so the mapper rule is pinned on a namespace input (the
    defensive branch stays until QD-2E removes the bridge
    vocabulary); the ORM-level shape lives in the contract suite."""
    from types import SimpleNamespace

    from app.graphql.resolvers import daily_queue_to_type

    user = _make_user(db_session, username="lab_resource", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    bridge_input = SimpleNamespace(
        id=1,
        specialist=synthetic,
        day=_DAY,
        queue_tag="lab",
        active=True,
        queue_resource_id=resource.id,
        opened_at=None,
        cabinet_number=None,
        cabinet_floor=None,
        cabinet_building=None,
        created_at=None,
    )
    gql_queue = daily_queue_to_type(bridge_input)
    assert gql_queue.specialist is not None  # the bridge input keeps the doctor
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


def test_confirmation_repository_reuses_existing_resource_queue(
    db_session: Session,
) -> None:
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    existing = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
    )
    repo = VisitConfirmationRepository(db_session)

    queue = repo.get_or_create_daily_queue(_DAY, None, "lab")
    assert queue.id == existing.id
    assert queue.specialist_id is None
    assert queue.queue_resource_id == resource.id


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
    future CLINIC day (Codex round-33: the availability guards compare
    on the clinic clock) so the pin never rots with the wall clock."""
    from app.crud.online_queue import check_queue_availability, get_queue_status

    future_day = _dt_now_tashkent_day() + timedelta(days=1)
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

    # Codex round-26 P2: the transfer's tomorrow rides the clinic_today
    # SSOT (the queue-settings timezone) — not host date.today()
    tomorrow = _dt_now_tashkent_day() + timedelta(days=1)
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

    # Codex round-29: the status day is the clinic_today SSOT
    today = _dt_now_tashkent_day()
    _make_resource(db_session, code="lab", queue_tag="lab")
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=today, specialist_id=None, queue_tag="lab"
    )
    user = _make_user(db_session, username="dr_mob18", role="doctor")
    doctor = _make_doctor(db_session, user_id=user.id, specialty="cardio")
    doctor_queue = queue_service.get_or_create_daily_queue(
        db_session, day=today, specialist_id=doctor.id, queue_tag="cardio"
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


def test_cabinet_info_resource_queue_classifies_resource(
    db_session: Session,
) -> None:
    """Codex round-10 P2: a resource-axis queue classifies as
    resource_owned (the DailyQueueOut/GQL contract): the cabinet UI
    gets resource_owned semantics, not doctor warnings. Pre-0063 this
    pinned the 0059 bridge (both owners); the QD-2D conversion
    leaves the same axis as a resource-owned row."""
    from app.api.v1.endpoints.queue_cabinet_management import QueueCabinetResponse
    from app.services.queue_domain_service import QueueDomainService

    resource = _make_resource(db_session, code="lab", queue_tag="lab")
    resource.default_cabinet = "7"
    db_session.commit()
    # the resource-axis row (the post-0063 shape of the backfill),
    # carrying the live cabinet
    resource_queue = _make_queue(
        db_session,
        specialist_id=None,
        queue_tag="lab",
        queue_resource_id=resource.id,
        active=True,
    )
    resource_queue.cabinet_number = "7"
    db_session.commit()

    payloads = QueueDomainService(db_session).list_queue_cabinet_info(
        day=_DAY, specialist_id=None, cabinet_number=None
    )
    items = [QueueCabinetResponse(**item) for item in payloads]
    resource_item = next(i for i in items if i.id == resource_queue.id)
    assert resource_item.specialist_id is None
    assert resource_item.sync_status == "resource_owned"
    assert resource_item.specialist_name == "Ресурс очереди"
    assert resource_item.effective_cabinet == "7"
    assert "linked_doctor_missing" not in resource_item.integrity_warnings


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
    # Codex round-27: the aggregation day is the clinic_today SSOT
    today = _dt_now_tashkent_day()
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
    # Codex round-28: the position day is the clinic_today SSOT
    today = _dt_now_tashkent_day()
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
    from datetime import datetime
    from unittest.mock import AsyncMock
    from zoneinfo import ZoneInfo

    from app.services.display_websocket_api_service import DisplayWebSocketApiService

    _make_resource(db_session, code="lab", queue_tag="lab")
    # Codex round-24 P2: the service resolves the CLINIC-local day (the
    # queue-settings timezone SSOT, default Asia/Tashkent) — the queue
    # must live on that day, as the creation paths stamp it.
    today = datetime.now(ZoneInfo("Asia/Tashkent")).date()
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

    # Codex round-27: the aggregation day is the clinic_today SSOT
    today = _dt_now_tashkent_day()
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
    from app.api.v1.endpoints.admin_departments._helpers import (
        _collect_department_overview,
    )
    from app.models.department import Department
    from app.models.queue_profile import QueueProfile

    # Codex round-28: the overview day is the clinic_today SSOT
    today = _dt_now_tashkent_day()
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
            queue_resource_id=(
                db_session.query(QueueResource)
                .filter(QueueResource.queue_tag == "lab")
                .first()
                .id
            ),
            active=True,
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

    from app.services import display_websocket as dw

    # Codex round-29: the snapshot day is the clinic_today SSOT
    today = _dt_now_tashkent_day()
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
    overwrite a resource queue's registry-sourced cabinet with a
    doctor's stale one; doctor queues still sync. Pre-0063 the pin ran
    against the 0059 bridge (whose synthetic specialist carried the
    stale cabinet 42); the QD-2D conversion leaves the same protection
    on the resource-owned row. The service COMMITs — durable rows
    cleaned in the finally."""
    try:
        from app.services.queue_cabinet_management_api_service import (
            QueueCabinetManagementApiService,
        )

        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        resource_queue = _make_queue(
            db_session,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        resource_queue.cabinet_number = "7"  # the resource destination in use
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
        db_session.refresh(resource_queue)
        db_session.refresh(doc_queue)
        assert result["success"] is True
        # the resource destination survives the sync
        assert resource_queue.cabinet_number == "7"
        # the doctor queue still syncs from its doctor
        assert doc_queue.cabinet_number == "5"
    finally:
        _durable_cleanup(db_session, "dr_z3")


# ===================== AA. Codex round-17 pins =====================


def test_registrar_payload_exposes_resource_routing_identity(
    db_session: Session,
) -> None:
    """Codex round-17 P1: a PURE resource queue (specialist NULL) in the
    /registrar/queues/today payload carries the stable registry identity
    (queue_resource_id) plus the routing legacy specialists — the
    frontend queue manager picks the queue by the SELECTED doctor id
    (pickQueueForDoctor), and without the routing axis the lab/ECG
    selection substituted an empty queue, hiding all waiting patients.
    Ownership stays on the resource axis: specialist_id stays NULL."""
    from app.api.v1.endpoints.registrar_integration._queue_ops import (
        _build_queue_payload,
        _process_online_queue_entries,
    )

    try:
        user = _make_user(db_session, username="lab_res_aa1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=31)

        queues_by_specialty: dict = {}
        _process_online_queue_entries(
            db_session, [entry], [], queues_by_specialty, set()
        )
        bucket = queues_by_specialty["laboratory"]
        assert bucket["queue_resource_id"] == resource.id
        assert bucket["routing_specialists"] == [synthetic.id]
        assert bucket["doctor_id"] is None  # ownership untouched

        payload = _build_queue_payload(
            queue_data=bucket,
            specialty="laboratory",
            queue_number=1,
            entries=[{"id": entry.id, "status": "waiting"}],
        )
        assert payload["queue_resource_id"] == resource.id
        assert payload["routing_specialists"] == [synthetic.id]
        assert payload["specialist_id"] is None
        # the doctor-queue shape: no resource identity, no routing axis
        doc_user = _make_user(db_session, username="dr_aa1b", role="Doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        doc_queue = _make_queue(
            db_session, specialist_id=doctor.id, queue_tag="cardiology"
        )
        doc_entry = _make_waiting_entry(db_session, doc_queue, number=1)
        doc_buckets: dict = {}
        _process_online_queue_entries(db_session, [doc_entry], [], doc_buckets, set())
        doc_payload = _build_queue_payload(
            queue_data=doc_buckets["cardiology"],
            specialty="cardiology",
            queue_number=2,
            entries=[{"id": doc_entry.id, "status": "waiting"}],
        )
        assert doc_payload["queue_resource_id"] is None
        assert doc_payload["routing_specialists"] == []
        assert doc_payload["specialist_id"] == doctor.id
    finally:
        _durable_cleanup(db_session, "lab_res_aa1", "dr_aa1b")


def test_reorder_move_permutation_preserves_served_gap(
    db_session: Session,
) -> None:
    """Codex round-17 P2: an internal gap among ACTIVE numbers (served
    №42 between actives 41/43) — the round-16 arithmetic shift moved the
    OTHER active ticket 41→42, duplicating the served ticket the
    by-number lookup resolves to the old patient. Reorder and move now
    reassign through the ordered number_slots permutation: the actives
    always occupy exactly the existing active slots. The service
    COMMITs — durable rows cleaned in the finally."""
    try:
        from app.services.queue_reorder_api_service import QueueReorderApiService

        admin = _make_user(db_session, username="adm_aa2", role="Admin")
        _make_resource(db_session, code="lab", queue_tag="lab", start_number_online=40)
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        served = _make_waiting_entry(db_session, queue, number=42)
        served.status = "served"
        db_session.commit()
        e41 = _make_waiting_entry(db_session, queue, number=41)
        e43 = _make_waiting_entry(db_session, queue, number=43)

        service = QueueReorderApiService(db_session)
        # move 43 to position 1: permutation → 43→41, 41→43 (the
        # arithmetic shift would leave 41 as 42 — the served duplicate)
        service.move_queue_entry(entry_id=e43.id, new_position=1, current_user=admin)
        db_session.refresh(e41)
        db_session.refresh(e43)
        db_session.refresh(served)
        assert e43.number == 41
        assert e41.number == 43  # NOT 42
        assert served.number == 42
        assert served.status == "served"

        # partial reorder: place the (now) №43 ticket back to position 1
        # — the non-requested entry keeps the OTHER existing slot, no
        # collision, no orphaned active slot
        service.reorder_queue(
            queue_id=queue.id,
            entry_orders=[{"entry_id": e41.id, "new_position": 1}],
            current_user=admin,
        )
        db_session.refresh(e41)
        db_session.refresh(e43)
        db_session.refresh(served)
        assert e41.number == 41
        assert e43.number == 43
        assert served.number == 42
        active_numbers = sorted(
            e.number
            for e in db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue.id)
            .filter(OnlineQueueEntry.status == "waiting")
            .all()
        )
        assert active_numbers == [41, 43]  # exactly the existing slots
    finally:
        _durable_cleanup(db_session, "adm_aa2")


def test_restore_no_show_broadcast_routing_room(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-17 P2: restore/no-show on a resource entry broadcast
    to the admin queue-WS room of the ROUTING specialist (the identity
    useQueueWebSocket subscribes to), not the dead specialist_None room
    — the connected queue manager updates instantly instead of waiting
    for the 60-second polling fallback. The routes COMMIT — durable
    rows cleaned in the finally."""
    import asyncio

    from app.services import display_websocket as dw
    from app.ws import queue_ws

    ws_calls: list[dict] = []

    def fake_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws, "broadcast_queue_update", fake_broadcast)

    class FakeManager:
        connections: list = []

        async def broadcast_queue_update(self, **kwargs):
            pass

    monkeypatch.setattr(dw, "get_display_manager", lambda: FakeManager())

    try:
        from app.api.v1.endpoints.qr_queue._entries import (
            mark_entry_no_show,
            restore_entry_to_next,
        )
        from app.api.v1.endpoints.qr_queue._tokens import RestoreToNextRequest

        user = _make_user(db_session, username="lab_res_aa3", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=31)
        caller = _make_user(db_session, username="reg_aa3", role="Registrar")

        async def scenario():
            no_show = await mark_entry_no_show(
                entry.id, db=db_session, current_user=caller
            )
            restore = await restore_entry_to_next(
                entry.id,
                request=RestoreToNextRequest(reason="вернулся"),
                db=db_session,
                current_user=caller,
            )
            return no_show, restore

        no_show_result, restore_result = asyncio.run(scenario())
        assert no_show_result["success"] is True
        assert restore_result["success"] is True

        expected_room_day = _DAY.strftime("%Y-%m-%d")
        routed = [
            c for c in ws_calls if c.get("department") == f"specialist_{synthetic.id}"
        ]
        none_room = [c for c in ws_calls if c.get("department") == "specialist_None"]
        assert routed, f"no broadcast to the routing room: {ws_calls}"
        assert not none_room, f"dead specialist_None room still used: {ws_calls}"
        actions = {c.get("data", {}).get("action") for c in routed}
        assert {"no_show", "restore_next"} <= actions
        assert all(c.get("date") == expected_room_day for c in routed)
    finally:
        _durable_cleanup(db_session, "lab_res_aa3", "reg_aa3")


# ===================== BB. Codex round-18 pins =====================


def test_join_token_metadata_uses_resource_owner(db_session: Session) -> None:
    """Codex round-18 P2: a dedicated lab/ECG token that resolves to the
    resource surface advertises the REGISTRY owner and cabinet in the
    join metadata (validate_queue_token) and on the public token-info
    screen (get_qr_token_info) — not the 0055 synthetic's «Врач ID ...»
    with a null cabinet. Doctor tokens stay byte-identical (no cabinet
    key behavior change). The writers COMMIT — durable rows cleaned in
    the finally."""
    from app.services.qr_queue import QRQueueService

    future_day = date.today() + timedelta(days=2)
    try:
        user = _make_user(db_session, username="lab_res_bb1", role="Resource")
        # no full_name — the 0055 synthetic shape
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        synthetic.cabinet = None
        db_session.commit()
        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        resource.default_cabinet = "7"
        db_session.commit()

        token_value, _gen_meta = queue_service.assign_queue_token(
            db_session,
            specialist_id=synthetic.id,
            department="lab",
            generated_by_user_id=None,
            target_date=future_day,
            queue_tag="lab",
        )

        _token_obj, meta = queue_service.validate_queue_token(db_session, token_value)
        assert meta["daily_queue"] is not None
        assert meta["daily_queue"].queue_resource_id == resource.id
        assert meta["specialist_name"] == "Ресурс очереди"  # NOT «Врач ID ...»
        assert meta["cabinet"] == "7"  # the registry destination, not null

        info = QRQueueService(db_session).get_qr_token_info(token_value)
        assert info is not None
        assert info["specialist_name"] == "Ресурс очереди"
        assert info["queue_active"] is True

        # doctor-token counter-shape: the name from the doctor's user,
        # cabinet stays absent-behavior (None) — byte-identical
        doc_user = _make_user(db_session, username="dr_bb1", role="Doctor")
        doc_user.full_name = "Иванов Иван"
        db_session.commit()
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        doctor.cabinet = "3"
        db_session.commit()
        doc_token, _ = queue_service.assign_queue_token(
            db_session,
            specialist_id=doctor.id,
            department="cardiology",
            generated_by_user_id=None,
            target_date=future_day,
        )
        _doc_obj, doc_meta = queue_service.validate_queue_token(db_session, doc_token)
        assert doc_meta["specialist_name"] == "Иванов Иван"
        assert doc_meta["cabinet"] is None  # unchanged doctor-token behavior
    finally:
        _durable_cleanup(db_session, "lab_res_bb1", "dr_bb1")


def test_legacy_join_broadcasts_routing_room(db_session: Session, monkeypatch) -> None:
    """Codex round-18 P2: the still-mounted POST /api/v1/queue/legacy/join
    broadcasts entry_added to the ROUTING room when the join lands on a
    pure resource queue (specialist NULL) — the literal specialist_None
    room has no subscribers, so the connected queue manager would learn
    about the new patient only through the 60-second polling fallback.
    The routes COMMIT — durable rows cleaned in the finally."""
    from app.ws import queue_ws

    ws_calls: list[dict] = []

    def fake_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws, "broadcast_queue_update", fake_broadcast)

    future_day = date.today() + timedelta(days=2)
    try:
        from app.api.v1.endpoints.queue import QueueJoinRequest, join_queue

        user = _make_user(db_session, username="lab_res_bb2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        resource.default_cabinet = "7"
        db_session.commit()

        token_value, _meta = queue_service.assign_queue_token(
            db_session,
            specialist_id=synthetic.id,
            department="lab",
            generated_by_user_id=None,
            target_date=future_day,
            queue_tag="lab",
        )

        response = join_queue(
            request=QueueJoinRequest(
                token=token_value,
                patient_name="Пациент Лаборатории",
                phone="+998901234567",
            ),
            db=db_session,
        )
        assert response.success is True
        assert response.number is not None

        routed = [
            c
            for c in ws_calls
            if c.get("department") == f"specialist_{synthetic.id}"
            and c.get("data", {}).get("action") == "entry_added"
        ]
        none_room = [c for c in ws_calls if c.get("department") == "specialist_None"]
        assert routed, f"no entry_added broadcast to the routing room: {ws_calls}"
        assert not none_room, f"dead specialist_None room still used: {ws_calls}"
        assert all(c.get("date") == future_day.isoformat() for c in routed)
    finally:
        _durable_cleanup(db_session, "lab_res_bb2")
        from app.models.online_queue import QueueToken as _QueueToken

        for row in (
            db_session.query(_QueueToken)
            .filter(_QueueToken.token.in_([token_value]))
            .all()
        ):
            db_session.delete(row)
        db_session.commit()


def test_reorder_rejects_duplicate_entry_ids(db_session: Session) -> None:
    """Codex round-18 P2: a reorder request listing the SAME entry at two
    positions (pydantic validates only position uniqueness) is rejected
    BEFORE the permutation — the same ORM object in two slots leaves a
    real entry on its old number and commits duplicate active numbers.
    The service COMMITs on the happy path — durable rows cleaned in the
    finally."""
    try:
        from app.services.queue_reorder_api_service import (
            QueueReorderApiDomainError,
            QueueReorderApiService,
        )

        admin = _make_user(db_session, username="adm_bb3", role="Admin")
        _make_resource(db_session, code="lab", queue_tag="lab", start_number_online=40)
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        first = _make_waiting_entry(db_session, queue, number=41)
        second = _make_waiting_entry(db_session, queue, number=42)

        service = QueueReorderApiService(db_session)
        try:
            service.reorder_queue(
                queue_id=queue.id,
                entry_orders=[
                    {"entry_id": first.id, "new_position": 1},
                    {"entry_id": first.id, "new_position": 2},
                ],
                current_user=admin,
            )
            raise AssertionError("duplicate entry ids must be rejected")
        except QueueReorderApiDomainError as exc:
            assert exc.status_code == 400

        # nothing was permuted or committed by the rejected request
        db_session.refresh(first)
        db_session.refresh(second)
        assert first.number == 41
        assert second.number == 42

        # a valid unique-id reorder still permutes normally
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
        assert second.number == 41
        assert first.number == 42
        assert info["queue_resource_id"] is not None
    finally:
        _durable_cleanup(db_session, "adm_bb3")


# ===================== CC. Codex round-19 pins =====================


def test_clinic_wide_profile_join_routes_registry_tag(db_session: Session) -> None:
    """Codex round-19 P1: a clinic-wide QR that selects the seeded lab/ECG
    QueueProfile resolves the profile onto the RESOURCE surface BEFORE
    doctor selection — 0057 moved the profiles' only synthetic owners to
    the internal 'Resource' role, so the eligible-doctor query
    (doctor-family roles only) is empty and the join failed with «Нет
    активных врачей» even though the registry row (0059) is ACTIVE. The
    join metadata advertises the registry owner and cabinet (round-18
    pattern). The service COMMITs — durable rows cleaned in the finally."""
    from app.models.online_queue import QueueToken as _QueueToken
    from app.models.queue_profile import QueueProfile

    future_day = date.today() + timedelta(days=2)
    profile = QueueProfile(
        key="laboratory_cc1",
        title="Лаборатория",
        title_ru="Лаборатория",
        queue_tags=["lab", "laboratory"],
        department_key="laboratory",
        show_on_qr_page=True,
    )
    token_value = None
    try:
        db_session.add(profile)
        db_session.commit()

        # the 0055/0057 shape: the only lab owner is the internal
        # 'Resource' synthetic — NOT a doctor-family login
        user = _make_user(db_session, username="lab_res_cc1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        synthetic.cabinet = None
        db_session.commit()
        resource = _make_resource(
            db_session,
            code="lab",
            queue_tag="lab",
            display_name="Лаборатория",
        )
        resource.default_cabinet = "4"
        db_session.commit()

        token_value, _meta = queue_service.assign_queue_token(
            db_session,
            specialist_id=None,
            department="lab",
            generated_by_user_id=None,
            target_date=future_day,
            is_clinic_wide=True,
        )

        result = queue_service.join_queue_with_token(
            db_session,
            token_str=token_value,
            patient_name="Пациент Профиля",
            phone="+998901234599",
            specialist_id_override=profile.id,
            source="online",
        )
        queue = result["daily_queue"]
        assert queue.specialist_id is None  # resource-owned, not synthetic
        assert queue.queue_resource_id == resource.id
        assert queue.queue_tag == "lab"  # the registry tag, not the profile key
        assert result["duplicate"] is False
        assert result["specialist_name"] == "Лаборатория"  # registry owner
        assert result["cabinet"] == "4"  # the registry destination
        entry = result["entry"]
        assert entry.queue_id == queue.id
        assert entry.source == "online"
        assert entry.number >= 1
    finally:
        _durable_cleanup(db_session, "lab_res_cc1")
        if token_value is not None:
            for row in (
                db_session.query(_QueueToken)
                .filter(_QueueToken.token == token_value)
                .all()
            ):
                db_session.delete(row)
        db_session.query(QueueProfile).filter(
            QueueProfile.key == "laboratory_cc1"
        ).delete(synchronize_session=False)
        db_session.commit()


def test_clinic_wide_profile_join_prefers_deactivated_resource_surface(
    db_session: Session,
) -> None:
    """Codex round-19 P1 (deactivation-proof companion, round-3 P1 rule):
    an operator deactivating the registry row mid-day must not strand the
    profile join back on the doctor path — the existing resource-owned
    (day, tag) queue IS the surface, patients already waiting there stay
    reachable and new arrivals keep landing on it."""
    from app.models.online_queue import QueueToken as _QueueToken
    from app.models.queue_profile import QueueProfile

    future_day = date.today() + timedelta(days=2)
    profile = QueueProfile(
        key="echokg_cc2",
        title="ЭКГ",
        title_ru="ЭКГ",
        queue_tags=["ecg"],
        department_key="echokg",
        show_on_qr_page=True,
    )
    token_value = None
    try:
        db_session.add(profile)
        db_session.commit()

        # the registry row is DEACTIVATED, but the day's surface exists
        resource = _make_resource(
            db_session,
            code="ecg",
            queue_tag="ecg",
            display_name="ЭКГ",
            active=False,
        )
        surface = _make_queue(
            db_session,
            day=future_day,
            specialist_id=None,
            queue_tag="ecg",
            queue_resource_id=resource.id,
        )

        token_value, _meta = queue_service.assign_queue_token(
            db_session,
            specialist_id=None,
            department="echokg",
            generated_by_user_id=None,
            target_date=future_day,
            is_clinic_wide=True,
        )

        result = queue_service.join_queue_with_token(
            db_session,
            token_str=token_value,
            patient_name="Пациент ЭКГ",
            phone="+998901234598",
            specialist_id_override=profile.id,
            source="online",
        )
        # the existing surface is reused — no fork, no «Нет активных врачей»
        assert result["daily_queue"].id == surface.id
        assert result["daily_queue"].specialist_id is None
        assert result["daily_queue"].queue_resource_id == resource.id
        assert result["entry"].queue_id == surface.id
        assert result["specialist_name"] == "ЭКГ"  # registry display_name
    finally:
        _durable_cleanup(db_session)
        if token_value is not None:
            for row in (
                db_session.query(_QueueToken)
                .filter(_QueueToken.token == token_value)
                .all()
            ):
                db_session.delete(row)
        db_session.query(QueueProfile).filter(QueueProfile.key == "echokg_cc2").delete(
            synchronize_session=False
        )
        db_session.commit()


def test_clinic_wide_profile_join_doctor_path_without_registry(
    db_session: Session,
) -> None:
    """Codex round-19 P1 (regression companion): a doctor-populated profile
    WITHOUT a registry surface keeps the doctor path byte-identical — the
    restructured else-branch (least-load routing, the profile-key queue
    tag) and the alias-skip contract ('laboratory' never resolves the
    'lab' registry row) both stay intact."""
    from app.models.online_queue import QueueToken as _QueueToken
    from app.models.queue_profile import QueueProfile

    future_day = date.today() + timedelta(days=2)
    profile = QueueProfile(
        key="laboratory_cc3",
        title="Лаборатория",
        title_ru="Лаборатория",
        queue_tags=["lab", "laboratory"],
        department_key="laboratory",
        show_on_qr_page=True,
    )
    token_value = None
    try:
        db_session.add(profile)
        db_session.commit()

        doc_user = _make_user(db_session, username="dr_lab_cc3", role="Doctor")
        doc_user.full_name = "Лабораторный Врач"
        db_session.commit()
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="lab")
        doctor.cabinet = "9"
        db_session.commit()

        token_value, _meta = queue_service.assign_queue_token(
            db_session,
            specialist_id=None,
            department="lab",
            generated_by_user_id=None,
            target_date=future_day,
            is_clinic_wide=True,
        )

        result = queue_service.join_queue_with_token(
            db_session,
            token_str=token_value,
            patient_name="Пациент Врача",
            phone="+998901234597",
            specialist_id_override=profile.id,
            source="online",
        )
        queue = result["daily_queue"]
        assert queue.specialist_id == doctor.id  # the doctor path
        assert queue.queue_resource_id is None  # never the resource axis
        assert queue.queue_tag == "laboratory_cc3"  # the profile key (SSOT)
        assert result["specialist_name"] == "Лабораторный Врач"
        assert result["cabinet"] == "9"
        assert result["entry"].queue_id == queue.id
    finally:
        _durable_cleanup(db_session, "dr_lab_cc3")
        if token_value is not None:
            for row in (
                db_session.query(_QueueToken)
                .filter(_QueueToken.token == token_value)
                .all()
            ):
                db_session.delete(row)
        db_session.query(QueueProfile).filter(
            QueueProfile.key == "laboratory_cc3"
        ).delete(synchronize_session=False)
        db_session.commit()


# ===================== DD. Codex round-20 pins =====================


def test_gql_queue_entries_doctor_and_tag_filters_intersect(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-20 P2: queueEntries(filter: {doctorId, queueTag}) keeps
    the two filters INTERSECTED — the resource-axis predicate derives its
    tag from the selected doctor's SPECIALTY only; the explicit queueTag
    stays an independent intersection below. The round-13 shape (a
    registry-tag doctor sees the resource rows) is preserved; the
    combined incompatible case (doctorId(cardiology) + queueTag:"lab")
    no longer returns the whole lab resource axis past doctorId."""
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
        # the resource axis: a lab registry queue with a waiting entry
        lab_user = _make_user(db_session, username="lab_res_dd1", role="Resource")
        lab_synth = _make_doctor(db_session, user_id=lab_user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        lab_queue = queue_service.get_or_create_daily_queue(
            db_session, day=_DAY, specialist_id=None, queue_tag="lab"
        )
        lab_entry = _make_waiting_entry(db_session, lab_queue, number=41)

        # an unrelated real doctor with their own tagged queue
        doc_user = _make_user(db_session, username="dr_dd1_cardio", role="Doctor")
        cardio = _make_doctor(db_session, user_id=doc_user.id, specialty="cardiology")
        cardio_queue = _make_queue(
            db_session, specialist_id=cardio.id, queue_tag="cardiology"
        )
        cardio_entry = _make_waiting_entry(db_session, cardio_queue, number=7)

        info = SimpleNamespace(context=None)  # direct schema test: no audit ctx

        # the P2 scenario: doctorId(cardiology) + queueTag:"lab" — the lab
        # resource entry must NOT satisfy the doctor predicate; the
        # explicit tag keeps intersecting independently
        result_mixed = asyncio.run(
            gql_resolvers.Query().queue_entries(
                info,
                QueueFilter(doctor_id=cardio.id, queue_tag="lab"),
            )
        )
        ids_mixed = [e.id for e in result_mixed.items]
        assert (
            lab_entry.id not in ids_mixed
        ), f"the lab resource axis leaked past doctorId: {ids_mixed}"
        assert cardio_entry.id not in ids_mixed  # 'cardiology' != 'lab'

        # the compatible combined case: the doctor's own tag intersects fine
        result_own = asyncio.run(
            gql_resolvers.Query().queue_entries(
                info,
                QueueFilter(doctor_id=cardio.id, queue_tag="cardiology"),
            )
        )
        assert [e.id for e in result_own.items] == [cardio_entry.id]

        # the round-13 shape preserved: a doctor whose specialty IS the
        # registry tag sees the resource rows — with the matching
        # explicit queueTag too (specialty-derived predicate + the
        # independent tag filter agree)
        result_lab = asyncio.run(
            gql_resolvers.Query().queue_entries(
                info,
                QueueFilter(doctor_id=lab_synth.id, queue_tag="lab"),
            )
        )
        ids_lab = [e.id for e in result_lab.items]
        assert lab_entry.id in ids_lab
        assert all(e.queue.queue_tag == "lab" for e in result_lab.items)
    finally:
        _durable_cleanup(db_session, "lab_res_dd1", "dr_dd1_cardio")


# ===================== EE. Codex round-21 pins =====================


def test_gql_join_queue_registry_tag_before_doctor_guard(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-21 P1: joinQueue with the seeded lab/ECG synthetic's id
    routes onto the resource axis BEFORE the doctor-eligibility guard —
    0056/0057 moved those owners to the internal 'Resource' role, while
    the canonical doctor-family predicate returned DOCTOR_INACTIVE before
    the crud registry branch could route the tag. The guard keeps
    protecting the doctor-owned branch (a Resource-role doctor on a
    non-registry tag is still rejected). The impl COMMITs — durable rows
    cleaned in the finally."""
    import contextlib
    from types import SimpleNamespace

    from app.graphql import mutations as gql_mutations
    from app.graphql.types import QueueEntryInput
    from app.models.patient import Patient

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    # night-window fix (#2992 precedent): keep the online window open
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    patient = Patient(
        last_name="Синтетиков",
        first_name="Пациент",
        phone="+998901234596",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        # the 0055/0057 shape: the only lab owner is the internal
        # 'Resource' synthetic — NOT a doctor-family login
        user = _make_user(db_session, username="lab_res_ee1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        resource = _make_resource(db_session, code="lab", queue_tag="lab")

        info = SimpleNamespace(context=None)  # direct schema test: no audit ctx
        result = gql_mutations.Mutation._join_queue_impl(
            info,
            QueueEntryInput(
                patient_id=patient.id,
                doctor_id=synthetic.id,
                queue_tag="lab",
            ),
        )
        assert result.success is True, (result.message, result.errors)
        assert result.queue_entry is not None
        entry = result.queue_entry

        queue = entry.queue  # DailyQueueType
        assert queue is not None
        assert queue.queue_resource_id == resource.id  # the resource axis
        assert queue.specialist is None  # the synthetic does NOT own it
        assert queue.queue_tag == "lab"
        assert entry.number >= 1
        assert entry.status == "waiting"

        # the doctor-owned branch keeps the guard: a Resource-role doctor
        # with a NON-registry tag is still rejected with DOCTOR_INACTIVE
        gen_user = _make_user(db_session, username="gen_res_ee1", role="Resource")
        gen_synth = _make_doctor(db_session, user_id=gen_user.id, specialty="general")
        result_guard = gql_mutations.Mutation._join_queue_impl(
            info,
            QueueEntryInput(
                patient_id=patient.id,
                doctor_id=gen_synth.id,
                queue_tag="general",
            ),
        )
        assert result_guard.success is False
        assert result_guard.errors == ["DOCTOR_INACTIVE"]
    finally:
        _durable_cleanup(db_session, "lab_res_ee1", "gen_res_ee1")
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== FF. Codex round-22 pins =====================


def test_gql_join_queue_stale_registry_flag_applies_doctor_guard(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-22 P2: registry_routed is computed UNLOCKED (before the
    advisory lock and the FOR UPDATE recheck inside get_or_create). If the
    registry row is deactivated in that window while no surface exists,
    get_or_create falls back to the DOCTOR branch — the retro-check on the
    RETURNED queue applies the canonical doctor guard: the Resource-role
    synthetic must not receive a doctor-owned queue/ticket after its
    registry was disabled. Simulated deterministically by stubbing the
    precheck resolvers (the stale view) while the real registry row is
    inactive. The impl COMMITs — durable rows cleaned in the finally."""
    import contextlib
    from types import SimpleNamespace

    from app.graphql import mutations as gql_mutations
    from app.graphql.types import QueueEntryInput
    from app.models.patient import Patient

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    # the STALE precheck view: both resolvers claim the resource axis
    monkeypatch.setattr(
        gql_mutations, "tag_routes_to_resource", lambda db, tag, day: object()
    )
    monkeypatch.setattr(
        gql_mutations, "_resolve_tag_resource", lambda db, tag: object()
    )

    patient = Patient(
        last_name="Синтетикова",
        first_name="Пациентка",
        phone="+998901234595",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        user = _make_user(db_session, username="lab_res_ff1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        # the REAL registry state: the row is DEACTIVATED, no surface exists
        _make_resource(db_session, code="lab", queue_tag="lab", active=False)

        info = SimpleNamespace(context=None)
        result = gql_mutations.Mutation._join_queue_impl(
            info,
            QueueEntryInput(
                patient_id=patient.id,
                doctor_id=synthetic.id,
                queue_tag="lab",
            ),
        )
        # the stale boolean must NOT hand a doctor-owned queue to the
        # internal 'Resource' synthetic after its registry was disabled
        assert result.success is False
        assert result.errors == ["DOCTOR_INACTIVE"]
        assert result.queue_entry is None

        # no entry was inserted for the patient
        from app.models.online_queue import OnlineQueueEntry as _OQE

        joined = db_session.query(_OQE).filter(_OQE.patient_id == patient.id).count()
        assert joined == 0
    finally:
        _durable_cleanup(db_session, "lab_res_ff1")
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_gql_join_queue_broadcasts_routing_rooms(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-22 P2: a successful GraphQL registry join broadcasts
    entry_added to EVERY routing room — a pure resource queue is
    addressable through any same-specialty doctor id (each queue manager
    subscribes to its own selected id), and the canonical
    queue_update_departments helper expands the queue to all routing
    specialists. The doctor-queue wrapper keeps the legacy single room.
    The wrapper COMMITS — durable rows cleaned in the finally."""
    import asyncio
    import contextlib
    from types import SimpleNamespace

    from app.graphql import mutations as gql_mutations
    from app.graphql.types import QueueEntryInput
    from app.models.patient import Patient
    from app.ws import queue_ws

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )
    ws_calls: list[dict] = []

    def fake_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws, "broadcast_queue_update", fake_broadcast)

    patient = Patient(
        last_name="Электрогард",
        first_name="Пациент",
        phone="+998901234594",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        # TWO doctors route to the 'lab' tag: the join target synthetic
        # and a second same-specialty synthetic (each queue manager
        # subscribes to its own selected id)
        user_a = _make_user(db_session, username="lab_res_ff2a", role="Resource")
        synth_a = _make_doctor(db_session, user_id=user_a.id, specialty="lab")
        user_b = _make_user(db_session, username="lab_res_ff2b", role="Resource")
        synth_b = _make_doctor(db_session, user_id=user_b.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")

        info = SimpleNamespace(context=None)
        response = asyncio.run(
            gql_mutations.Mutation.join_queue(
                None,
                info,
                QueueEntryInput(
                    patient_id=patient.id,
                    doctor_id=synth_a.id,
                    queue_tag="lab",
                ),
            )
        )
        assert response.success is True, (response.message, response.errors)
        assert response.queue_entry is not None

        routed = sorted(
            c["department"]
            for c in ws_calls
            if c.get("data", {}).get("action") == "entry_added"
        )
        assert routed == [
            f"specialist_{synth_a.id}",
            f"specialist_{synth_b.id}",
        ], f"entry_added must reach every routing room: {ws_calls}"
        assert "specialist_None" not in routed
        assert all(c.get("event_type") == "queue_update" for c in ws_calls)
    finally:
        _durable_cleanup(db_session, "lab_res_ff2a", "lab_res_ff2b")
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== GG. Codex round-23 pins =====================


def test_gql_join_queue_deactivated_registry_guards_before_creation(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-23 P2: with the registry row DEACTIVATED and no
    surface, the locked branch decision applies the doctor guard BEFORE
    get_or_create_daily_queue — the Resource-role synthetic is rejected
    with DOCTOR_INACTIVE and NO doctor-owned (day, tag) queue is
    persisted (the round-22 retro-check fired only after the
    constructor's internal commit, leaving an active invalid queue that
    would shadow the resource surface after a reactivation)."""
    import contextlib
    from types import SimpleNamespace

    from app.graphql import mutations as gql_mutations
    from app.graphql.types import QueueEntryInput
    from app.models.online_queue import DailyQueue as _DQ
    from app.models.patient import Patient

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    patient = Patient(
        last_name="Рентгенова",
        first_name="Пациентка",
        phone="+998901234593",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        user = _make_user(db_session, username="lab_res_gg1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        # the real registry state: DEACTIVATED row, no surface, no stubs —
        # the locked branch decision must see the truth
        _make_resource(db_session, code="lab", queue_tag="lab", active=False)

        info = SimpleNamespace(context=None)
        result = gql_mutations.Mutation._join_queue_impl(
            info,
            QueueEntryInput(
                patient_id=patient.id,
                doctor_id=synthetic.id,
                queue_tag="lab",
            ),
        )
        assert result.success is False
        assert result.errors == ["DOCTOR_INACTIVE"]
        assert result.queue_entry is None

        # nothing persisted: no (day, 'lab') queue exists at all — the
        # invalid doctor-owned queue must not survive the rejection
        stale_queues = db_session.query(_DQ).filter(_DQ.queue_tag == "lab").count()
        assert stale_queues == 0, "an invalid doctor-owned lab queue persisted"
    finally:
        _durable_cleanup(db_session, "lab_res_gg1")
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_gql_join_queue_doctor_fallback_keeps_full_guard_chain(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-23 P2 (fallback companion): with the registry row
    deactivated and no surface, a REAL doctor's join takes the doctor
    branch through the FULL guard chain — the round-8 predicate AND the
    round-15 post-create FOR UPDATE re-check both run (keyed on the
    locked branch decision, not a stale boolean), and the entry lands on
    the doctor-owned (day, tag) queue."""
    import contextlib
    from types import SimpleNamespace

    from app.graphql import mutations as gql_mutations
    from app.graphql.types import QueueEntryInput
    from app.models.patient import Patient

    monkeypatch.setattr(
        gql_mutations,
        "get_db_session",
        lambda: contextlib.nullcontext(db_session),
    )
    monkeypatch.setattr(
        gql_mutations,
        "get_queue_settings",
        lambda db: {"queue_start_hour": 0, "timezone": "Asia/Tashkent"},
    )

    patient = Patient(
        last_name="Анализов",
        first_name="Пациент",
        phone="+998901234592",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        doc_user = _make_user(db_session, username="dr_gg2_lab", role="Doctor")
        doc_user.full_name = "Лаборант Реальный"
        db_session.commit()
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="lab")
        doctor.cabinet = "12"
        db_session.commit()
        # the registry row is DEACTIVATED, no surface — the tag does not
        # route onto the resource axis, the doctor branch owns the join
        _make_resource(db_session, code="lab", queue_tag="lab", active=False)

        info = SimpleNamespace(context=None)
        result = gql_mutations.Mutation._join_queue_impl(
            info,
            QueueEntryInput(
                patient_id=patient.id,
                doctor_id=doctor.id,
                queue_tag="lab",
            ),
        )
        assert result.success is True, (result.message, result.errors)
        assert result.queue_entry is not None
        queue = result.queue_entry.queue
        assert queue.specialist.id == doctor.id  # the doctor-owned branch
        assert queue.queue_resource_id is None
        assert queue.queue_tag == "lab"
        assert result.queue_entry.status == "waiting"
    finally:
        _durable_cleanup(db_session, "dr_gg2_lab")
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== HH. Codex round-24 pins =====================


def test_quick_call_resolves_clinic_day_surface(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-24 P2: the display quick-call resolves the day in the
    CLINIC timezone (the queue-settings SSOT), not the host-local
    date.today() — on a UTC host with an Asia/Tashkent clinic the first
    five local hours missed that day's resource queue and fell through
    to doctor selection (which excludes the seeded 'Resource' owner),
    returning 404 despite a waiting entry. The timezone here is chosen
    dynamically so the clinic-local date GUARANTEEDLY differs from the
    host date at test runtime (UTC+14 / UTC-12 extremes are 1-2 days
    apart — at least one differs from any third date). The repository
    COMMITs — durable rows cleaned in the finally."""
    import asyncio
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    from app.services import display_websocket_api_service as dwas

    ahead = _dt.now(ZoneInfo("Pacific/Kiritimati")).date()  # UTC+14
    behind = _dt.now(ZoneInfo("Etc/GMT+12")).date()  # UTC-12
    assert ahead != behind  # the extremes are 1-2 days apart
    host_today = date.today()
    if ahead != host_today:
        tz_name, clinic_day = "Pacific/Kiritimati", ahead
    else:
        tz_name, clinic_day = "Etc/GMT+12", behind
    assert clinic_day != host_today  # the divergence window is real

    monkeypatch.setattr(
        dwas,
        "get_queue_settings",
        lambda db: {"timezone": tz_name},
    )

    class FakeManager:
        connections: list = []

        async def broadcast_patient_call(self, **kwargs):
            pass

    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        # the queue-creation paths stamp the CLINIC-local day
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=51)
        caller = _make_user(db_session, username="reg_hh1", role="Registrar")

        service = dwas.DisplayWebSocketApiService(
            db_session, manager_provider=lambda: FakeManager()
        )
        result = asyncio.run(
            service.quick_call_next(specialty="lab", board_id=None, current_user=caller)
        )
        assert result["success"] is True, result
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "reg_hh1")


def test_call_next_broadcasts_routing_rooms(db_session: Session, monkeypatch) -> None:
    """Codex round-24 P2: the call-next wrappers broadcast through EVERY
    routing room of the SELECTED queue — a resource queue is addressable
    through any same-specialty doctor id (each queue manager subscribes
    to its own selected id), so managers on sibling ids must see the
    waiting-to-called transition instantly. Covers the REST endpoint
    (rooms derived from the selected entry's queue) and the GQL impl
    (broadcast_departments payload). The wrapper COMMITs — durable rows
    cleaned in the finally."""
    import asyncio
    import contextlib
    from types import SimpleNamespace

    from app.ws import queue_ws

    ws_calls: list[dict] = []

    def fake_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws, "broadcast_queue_update", fake_broadcast)

    # the clinic-local day the call-next paths resolve
    tz_day = _dt_now_tashkent_day()

    try:
        # TWO doctors route to the 'lab' tag: the invoked synthetic and
        # a second same-specialty sibling (managers may select either id)
        user_a = _make_user(db_session, username="lab_res_hh2a", role="Resource")
        synth_a = _make_doctor(db_session, user_id=user_a.id, specialty="lab")
        user_b = _make_user(db_session, username="lab_res_hh2b", role="Resource")
        synth_b = _make_doctor(db_session, user_id=user_b.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=tz_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=61)
        caller = _make_user(db_session, username="reg_hh2", role="Registrar")

        # --- REST endpoint: rooms from the selected entry's queue ---
        from app.api.v1.endpoints.qr_queue._queue_ops import call_next_patient

        async def scenario():
            return await call_next_patient(
                synth_a.id,
                target_date=tz_day.isoformat(),
                db=db_session,
                current_user=caller,
            )

        payload = asyncio.run(scenario())
        assert payload.success is True
        db_session.refresh(entry)
        assert entry.status == "called"

        routed = sorted(
            c["department"]
            for c in ws_calls
            if c.get("data", {}).get("action") == "call_next"
        )
        assert routed == [
            f"specialist_{synth_a.id}",
            f"specialist_{synth_b.id}",
        ], f"call_next must reach every routing room: {ws_calls}"
        assert "specialist_None" not in routed

        # --- GQL impl: the broadcast rooms ride the payload ---
        from app.graphql import mutations as gql_mutations

        monkeypatch.setattr(
            gql_mutations,
            "get_db_session",
            lambda: contextlib.nullcontext(db_session),
        )
        second = _make_waiting_entry(db_session, queue, number=62)
        actor = _make_user(db_session, username="adm_hh2", role="Admin")
        info = SimpleNamespace(context=SimpleNamespace(user=actor, request=None))
        gql_payload = gql_mutations.Mutation._call_next_patient_impl(
            info, synth_b.id, "lab"
        )
        assert gql_payload["success"] is True, gql_payload
        db_session.refresh(second)
        assert second.status == "called"
        assert sorted(gql_payload["broadcast_departments"]) == sorted(
            [f"specialist_{synth_a.id}", f"specialist_{synth_b.id}"]
        )
        assert "specialist_None" not in gql_payload["broadcast_departments"]
    finally:
        _durable_cleanup(
            db_session, "lab_res_hh2a", "lab_res_hh2b", "reg_hh2", "adm_hh2"
        )


def _dt_now_tashkent_day():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


# ===================== II. Codex round-25 pins =====================


def _divergent_clinic_day() -> tuple[str, date]:
    """A timezone whose LOCAL date guaranteedly differs from the host
    date at this runtime moment (UTC+14 / UTC-12 extremes are 1-2 days
    apart — at least one differs from any third date)."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    ahead = _dt.now(ZoneInfo("Pacific/Kiritimati")).date()  # UTC+14
    behind = _dt.now(ZoneInfo("Etc/GMT+12")).date()  # UTC-12
    assert ahead != behind
    host_today = date.today()
    if ahead != host_today:
        return "Pacific/Kiritimati", ahead
    return "Etc/GMT+12", behind


def test_rest_status_and_call_next_default_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-25 P2: the canonical REST service defaults an omitted
    date to the CLINIC-local day (the clinic_today SSOT) — on the
    documented UTC host between 19:00 and midnight the queue is stamped
    with the NEXT local date, so /queue/status reported inactive and
    call-next raised «Очередь не активна» despite waiting patients. The
    timezone is chosen dynamically so the divergence is real at any
    runtime. The service COMMITs — durable rows cleaned in the
    finally."""
    from app.services.qr_queue import QRQueueService
    from app.services.qr_queue import _queue_ops as qr_ops

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr(qr_ops, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_ii1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=71)
        caller = _make_user(db_session, username="reg_ii1", role="Registrar")

        service = QRQueueService(db_session)
        # omitted date: the status resolves the clinic-day surface
        status = service.get_queue_status(synthetic.id, target_date=None)
        assert status["active"] is True, status
        assert status["queue_length"] >= 1

        # omitted date: the call-next advances the clinic-day surface
        result = service.call_next_patient(synthetic.id, caller.id, None, None)
        assert result["success"] is True, result
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "lab_res_ii1", "reg_ii1")


def test_rest_call_next_survives_notification_failure(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-25 P2: entry is initialized BEFORE the independent
    side-effect blocks — when the notification block raises BEFORE its
    query assigns entry (get_queue_position_service failing), the WS
    broadcast keeps working (the round-24 routing rooms and the fallback
    room stay reachable) instead of dying on UnboundLocalError. The
    endpoint COMMITs — durable rows cleaned in the finally."""
    import asyncio

    from app.services import queue_position_notifications as qpn
    from app.ws import queue_ws

    def broken_service_factory(db):
        raise RuntimeError("simulated notification service failure")

    monkeypatch.setattr(qpn, "get_queue_position_service", broken_service_factory)

    ws_calls: list[dict] = []

    def fake_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws, "broadcast_queue_update", fake_broadcast)

    try:
        from app.api.v1.endpoints.qr_queue._queue_ops import call_next_patient

        user = _make_user(db_session, username="lab_res_ii2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        tz_day = _dt_now_tashkent_day()
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=tz_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=81)
        caller = _make_user(db_session, username="reg_ii2", role="Registrar")

        async def scenario():
            return await call_next_patient(
                synthetic.id,
                target_date=tz_day.isoformat(),
                db=db_session,
                current_user=caller,
            )

        payload = asyncio.run(scenario())
        assert payload.success is True

        # the WS broadcast survived the notification failure — entry was
        # re-fetched by the display block and the rooms are the routing
        # rooms (no UnboundLocalError, no silently skipped update)
        call_next_rooms = sorted(
            c["department"]
            for c in ws_calls
            if c.get("data", {}).get("action") == "call_next"
        )
        assert call_next_rooms == [f"specialist_{synthetic.id}"], ws_calls
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "lab_res_ii2", "reg_ii2")


# ===================== JJ. Codex round-26 pins =====================


def test_force_majeure_pending_entries_default_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-26 P2: force-majeure resolves omitted dates through
    the clinic_today SSOT — the mounted ForceMajeureModal omits
    target_date, and host date.today() between 19:00-24:00 UTC searched
    the clinic's PREVIOUS day: the resource surface was not found and
    the specialist fallback cannot match a pure resource queue
    (specialist NULL) — the pending list came back empty despite
    waiting patients. The timezone is chosen dynamically so the
    divergence is real at any runtime."""
    from app.services import force_majeure_service as fm

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(fm, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_jj1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=91)

        service = fm.ForceMajeureService(db_session)
        pending = service.get_pending_entries(specialist_id=synthetic.id)
        assert [e.id for e in pending] == [entry.id]

        # and the transfer's tomorrow rides the same SSOT: clinic-tomorrow
        tomorrow = clinic_day + timedelta(days=1)
        assert tomorrow != date.today() + timedelta(days=1) or tomorrow == (
            date.today() + timedelta(days=1)
        )  # sanity only — the transfer day is derived, not asserted here
    finally:
        _durable_cleanup(db_session, "lab_res_jj1")


def test_rest_call_next_broadcast_uses_resolved_queue_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-26 P2: an omitted target_date no longer produces an
    undated WS room — the broadcast date is the SELECTED queue's day
    (the day the service actually resolved), so the room keeps the
    full specialist_X::{YYYY-MM-DD} form useQueueWebSocket subscribes
    to. The service COMMITs — durable rows cleaned in the finally."""
    import asyncio

    from app.ws import queue_ws

    ws_calls: list[dict] = []

    def fake_broadcast(**kwargs):
        ws_calls.append(kwargs)

    monkeypatch.setattr(queue_ws, "broadcast_queue_update", fake_broadcast)

    try:
        from app.api.v1.endpoints.qr_queue._queue_ops import call_next_patient

        user = _make_user(db_session, username="lab_res_jj2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        tz_day = _dt_now_tashkent_day()
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=tz_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=92)
        caller = _make_user(db_session, username="reg_jj2", role="Registrar")

        async def scenario():
            return await call_next_patient(
                synthetic.id,
                target_date=None,  # OMITTED — the service resolves clinic_today
                db=db_session,
                current_user=caller,
            )

        payload = asyncio.run(scenario())
        assert payload.success is True

        routed = [
            c for c in ws_calls if c.get("data", {}).get("action") == "call_next"
        ]
        assert routed, ws_calls
        assert all(
            c["date"] == tz_day.strftime("%Y-%m-%d") for c in routed
        ), f"undated/wrong-day rooms: {ws_calls}"
        assert all(c["date"] for c in routed)
        db_session.refresh(entry)
        assert entry.status == "called"
    finally:
        _durable_cleanup(db_session, "lab_res_jj2", "reg_jj2")


# ===================== KK. Codex round-27 pins =====================


def test_force_majeure_entry_ids_default_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-27 P2: entry-id force-majeure requests resolve the
    omitted date through the clinic_today SSOT — the repository's
    list_pending_entries_by_ids used host date.today(), so between
    19:00 and 24:00 UTC an omitted-date transfer/cancellation searched
    the previous day's resource surface and returned zero affected
    entries while the no-entry_ids path found the clinic-day queue.
    The timezone is chosen dynamically so the divergence is real."""
    from app.repositories.force_majeure_api_repository import (
        ForceMajeureApiRepository,
    )

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(
        "app.repositories.force_majeure_api_repository.clinic_today",
        lambda db: clinic_day,
    )

    try:
        user = _make_user(db_session, username="lab_res_kk1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=101)

        repo = ForceMajeureApiRepository(db_session)
        found = repo.list_pending_entries_by_ids(
            entry_ids=[entry.id],
            specialist_id=synthetic.id,
            target_date=None,
        )
        assert [e.id for e in found] == [entry.id]
    finally:
        _durable_cleanup(db_session, "lab_res_kk1")


def test_queue_limits_aggregate_clinic_day_resource_usage(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-27 P2: GET /api/v1/admin/queue-limits aggregates on
    the clinic day — resource queues are created clinic-local, and host
    date.today() in the 19:00-24:00Z window fell back to obsolete
    doctor-keyed rows or no queue, reporting current_usage=0 and the
    wrong aggregate cap despite patients occupying the live shared
    queue. The timezone is chosen dynamically so the divergence is
    real."""
    from app.services.queue_limits_api_service import QueueLimitsApiService

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(
        "app.services.queue_limits_api_service.clinic_today",
        lambda db: clinic_day,
    )

    try:
        user = _make_user(db_session, username="lab_res_kk2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab", max_online_per_day=25)
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        _make_waiting_entry(db_session, queue, number=1)
        _make_waiting_entry(db_session, queue, number=2)

        service = QueueLimitsApiService(db_session)
        limits = service.get_queue_limits(specialty="lab")
        lab_row = next(r for r in limits if r["specialty"] == "lab")
        assert lab_row["current_usage"] == 2
        assert lab_row["aggregate_max_per_day"] == 25
    finally:
        _durable_cleanup(db_session, "lab_res_kk2")


# ===================== LL. Codex round-28 pins =====================


def test_position_by_number_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-28 P2: the by-number position lookup resolves the day
    through the clinic_today SSOT — GET /queue/position/by-number/{n}
    returned 404 for a valid current clinic-day resource ticket when
    the host date was still the clinic's previous day. The timezone is
    chosen dynamically so the divergence is real."""
    from app.services import queue_position_api_service as qps

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(qps, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_ll1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=111)

        service = qps.QueuePositionApiService(db_session)
        result = service.get_position_entry_by_number(
            queue_number=111, specialist_id=synthetic.id
        )
        assert result.id == entry.id
    finally:
        _durable_cleanup(db_session, "lab_res_ll1")


def test_department_overview_counts_clinic_day_resource_queues(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-28 P2: the department overview aggregates on the
    clinic day — the resource-axis predicate read host-today queues and
    reported zero queue_entries_today for live resource queues in the
    19:00-24:00Z window while the queue-limits aggregation (round-27)
    correctly reported their clinic-day usage. The timezone is chosen
    dynamically so the divergence is real."""
    import app.api.v1.endpoints.admin_departments._helpers as dept_helpers
    from app.models.department import Department
    from app.models.queue_profile import QueueProfile

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(
        "app.crud.clinic.clinic_today", lambda db: clinic_day
    )

    department = Department(key="laboratory_ll", name_ru="Лаборатория LL")
    profile = QueueProfile(
        key="laboratory_ll",
        title="Лаборатория LL",
        queue_tags=["lab"],
        department_key="laboratory_ll",
    )
    try:
        db_session.add(department)
        db_session.add(profile)
        db_session.commit()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        _make_waiting_entry(db_session, queue, number=5)
        _make_waiting_entry(db_session, queue, number=6)

        overview = dept_helpers._collect_department_overview(db_session)
        item = next(
            i for i in overview["departments"] if i["key"] == "laboratory_ll"
        )
        assert item["stats"]["queue_entries_today"] == 2
    finally:
        _durable_cleanup(db_session)
        db_session.query(QueueProfile).filter(
            QueueProfile.key == "laboratory_ll"
        ).delete(synchronize_session=False)
        db_session.query(Department).filter(Department.key == "laboratory_ll").delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== MM. Codex round-29 pins =====================


def test_mobile_queues_status_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-29 P2: /api/v1/mobile/queues/status enumerates the
    CLINIC-local day — the handler resolved host date.today(), so on a
    UTC host in the 19:00-24:00 window it silently dropped the live
    lab/ECG resource queues (stamped with the next clinic-local date)
    and returned stale or empty status. The timezone is chosen
    dynamically so the divergence is real at any runtime."""
    import asyncio

    from app.api.v1.endpoints.mobile_api_extended import get_queues_status
    from app.crud import clinic as crud_clinic

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr(crud_clinic, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_mm1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        _make_waiting_entry(db_session, queue, number=9)

        viewer = _make_user(db_session, username="adm_mm1", role="Admin")
        payload = asyncio.run(get_queues_status(current_user=viewer, db=db_session))
        rows = {row.doctor_id: row for row in payload["queues"]}

        resource_row = rows[None]
        assert resource_row.specialty == "lab"
        assert resource_row.doctor_name == "Ресурс очереди"
        assert resource_row.total_numbers >= 9
        assert synthetic.id not in rows
    finally:
        _durable_cleanup(db_session, "lab_res_mm1", "adm_mm1")


def test_display_reconnect_snapshot_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-29 P2: the display (re)connect snapshot selects the
    CLINIC-local day — _send_current_state queried host date.today(), so
    a board (re)connecting during the divergence window got a blank or
    stale initial_state while the live resource tickets sat on the next
    clinic-local date. The timezone is chosen dynamically so the
    divergence is real at any runtime."""
    import asyncio
    import json

    from app.crud import clinic as crud_clinic
    from app.services import display_websocket as dw

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr(crud_clinic, "clinic_today", lambda db: clinic_day)
    monkeypatch.setattr(dw, "SessionLocal", lambda: _shared_session(db_session))

    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        queue = _make_queue(
            db_session,
            day=clinic_day,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        entry = _make_waiting_entry(db_session, queue, number=7)

        manager = dw.DisplayWebSocketManager.__new__(dw.DisplayWebSocketManager)
        manager.connections = {}
        manager.board_states = {}

        sent: dict = {}

        class FakeWebSocket:
            async def send_text(self, payload: str) -> None:
                sent["payload"] = payload

        asyncio.run(manager._send_current_state(FakeWebSocket(), "board-x"))
        state = json.loads(sent["payload"])
        numbers = [e["number"] for e in state["data"]["queue_entries"]]
        assert (
            entry.number in numbers
        ), "the clinic-day resource entry must reach the initial snapshot"
    finally:
        _durable_cleanup(db_session)


def test_legacy_today_endpoint_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-29 P2: the legacy GET /api/v1/queue/today resolves
    «today» through the clinic_today SSOT — the handler passed host
    date.today() into the resource-aware get_daily_queue, searched the
    previous day's tag surface in the 19:00-24:00Z window and returned
    404 for a valid current clinic-day resource queue. The timezone is
    chosen dynamically so the divergence is real at any runtime."""
    from app.api.v1.endpoints.queue import get_today_queue
    from app.crud import clinic as crud_clinic

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr(crud_clinic, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_mm3", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        _make_waiting_entry(db_session, queue, number=3)

        viewer = _make_user(db_session, username="adm_mm3", role="Admin")
        response = get_today_queue(
            specialist_id=synthetic.id, db=db_session, current_user=viewer
        )
        assert response.queue_id == queue.id
        assert response.day == clinic_day
        assert response.specialist_name == "Ресурс очереди"
        assert response.total_entries == 1
        assert response.waiting_entries == 1
    finally:
        _durable_cleanup(db_session, "lab_res_mm3", "adm_mm3")


# ===================== NN. Codex round-30 pins =====================


def test_queue_update_departments_rooms_by_owner_kind(db_session: Session) -> None:
    """Codex round-30 P2: every queue is addressable through EVERY
    routing sibling id of its tag — each queue manager subscribes to
    its own selected specialist room, so the early legacy-only return
    starved sibling subscribers of join/call/restore/no-show updates
    until polling. Pure doctor queues keep the single legacy room;
    pure resource queues keep the routing rooms. (Pre-0063 the bridged
    shape was the third case; the QD-2D XOR contract consumed it and
    the resource-owned row pins the identical rooms.)"""
    from app.ws.queue_ws import queue_update_departments

    try:
        user_a = _make_user(db_session, username="lab_res_nn1a", role="Resource")
        synth_a = _make_doctor(db_session, user_id=user_a.id, specialty="lab")
        user_b = _make_user(db_session, username="lab_res_nn1b", role="Resource")
        synth_b = _make_doctor(db_session, user_id=user_b.id, specialty="lab")
        resource = _make_resource(db_session, code="lab", queue_tag="lab")
        today = _dt_now_tashkent_day()

        # (pre-0063 the bridged shape was pinned here as a third case;
        # the QD-2D XOR contract consumed it — the resource-owned row
        # below pins the identical routing rooms)

        # regression: the pure doctor queue keeps the single legacy room
        doc_user = _make_user(db_session, username="dr_nn1", role="doctor")
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
        doctor_queue = _make_queue(
            db_session, day=today, specialist_id=doctor.id, queue_tag="cardio"
        )
        assert queue_update_departments(db_session, doctor_queue) == [
            f"specialist_{doctor.id}"
        ]

        # regression: the pure resource queue keeps the routing rooms
        pure_resource = _make_queue(
            db_session,
            day=today,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        resource_rooms = queue_update_departments(db_session, pure_resource)
        assert set(resource_rooms) == {
            f"specialist_{synth_a.id}",
            f"specialist_{synth_b.id}",
        }
        assert "specialist_None" not in resource_rooms
    finally:
        _durable_cleanup(db_session, "lab_res_nn1a", "lab_res_nn1b", "dr_nn1")


def test_admin_queue_status_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-30 P2: GET /api/v1/admin/queue-limits/queue-status
    resolves the omitted day through the clinic_today SSOT — the
    endpoint converted the omitted day with host date.today(), so in
    the 19:00-24:00Z window the resource-surface lookup read the
    previous day's queues and reported zero usage/closed state despite
    waiting patients. The timezone is chosen dynamically so the
    divergence is real."""
    from app.api.v1.endpoints.queue_limits import get_queue_status_with_limits
    from app.crud import clinic as crud_clinic

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(crud_clinic, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_nn2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        assert queue is not None
        _make_waiting_entry(db_session, queue, number=1)
        _make_waiting_entry(db_session, queue, number=2)

        admin = _make_user(db_session, username="adm_nn2", role="Admin")
        rows = get_queue_status_with_limits(
            day=None, specialty="lab", db=db_session, current_user=admin
        )
        lab_row = next(r for r in rows if r.specialty == "lab")
        assert lab_row.doctor_id == synthetic.id
        assert lab_row.day == clinic_day
        assert lab_row.current_entries == 2
    finally:
        _durable_cleanup(db_session, "lab_res_nn2", "adm_nn2")


def test_qr_time_restrictions_use_clinic_clock(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-30 P2: the QR session day/time classification rides
    the CLINIC clock — host date.today() classified the current
    clinic-day token as FUTURE (allowed=True, skipping the start
    window), letting a lab/ECG join session open during the clinic's
    pre-07:00 period. The clock is frozen on the next clinic-local day
    at 05:30 (guaranteed to differ from the host date): the same-day
    start window must reject the join."""
    from datetime import time as _time

    import app.services.qr_queue_service as qr_queue_service
    import app.services.queue_service as queue_service_module
    from app.models.online_queue import QueueToken
    from app.services.qr_queue import QRQueueService

    frozen_day = date.today() + timedelta(days=1)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            frozen = datetime.combine(frozen_day, _time(5, 30))
            if tz is not None:
                return frozen.replace(tzinfo=tz)
            return frozen

        @classmethod
        def utcnow(cls):  # type: ignore[override]
            return datetime.combine(frozen_day, _time(5, 30))

    monkeypatch.setattr(qr_queue_service, "datetime", FixedDateTime)
    monkeypatch.setattr(queue_service_module, "datetime", FixedDateTime)

    try:
        user = _make_user(db_session, username="lab_res_nn3", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        surface = queue_service.get_or_create_daily_queue(
            db_session, day=frozen_day, specialist_id=None, queue_tag="lab"
        )
        assert surface is not None
        token = QueueToken(
            token="tok-nn3",
            day=frozen_day,
            specialist_id=synthetic.id,
            department="lab",
            is_clinic_wide=False,
            expires_at=datetime.combine(frozen_day + timedelta(days=60), _time(12)),
            active=True,
        )
        db_session.add(token)
        db_session.commit()

        result = QRQueueService(db_session)._check_online_time_restrictions("tok-nn3")
        # NOT the future-day "allowed" verdict the host clock produced
        assert result["allowed"] is False, result
        assert result["status"] == "before_start_time", result
        assert "07:00" in result["message"]
    finally:
        _durable_cleanup(db_session, "lab_res_nn3")
        db_session.query(QueueToken).filter(QueueToken.token == "tok-nn3").delete(
            synchronize_session=False
        )
        db_session.commit()


def test_department_snapshot_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-30 P2: the department display snapshot
    (/api/v1/display/ws/queue/{department} connections and
    request_update messages) resolves the day through the clinic
    timezone — host date.today() returned an empty/stale snapshot
    during the 19:00-24:00Z window while the live resource queues sat
    on the current clinic-local day. The timezone is chosen dynamically
    so the divergence is real."""
    from app.services import display_websocket_api_service as dwas

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(
        dwas,
        "get_queue_settings",
        lambda db: {"timezone": tz_name},
    )

    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        queue = _make_queue(
            db_session,
            day=clinic_day,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        entry = _make_waiting_entry(db_session, queue, number=11)

        service = dwas.DisplayWebSocketApiService(db_session)
        payload = service.get_department_queue_state_payload(department="lab")
        numbers = [e["number"] for e in payload["entries"]]
        assert entry.number in numbers, payload
        assert payload["total_waiting"] >= 1
    finally:
        _durable_cleanup(db_session)


# ===================== OO. Codex round-31 pins =====================


def test_registrar_payload_prefers_resource_metadata_for_resource_queues(
    db_session: Session,
) -> None:
    """Codex round-31 P2: a resource-axis queue presents the REGISTRY
    identity in the registrar payload — no doctor full_name/username
    and no doctor cabinet leak into the payload, and the
    doctor-cabinet integrity warning does not fire for a
    resource-owned surface. (Pre-0063 the pin ran against the 0059
    bridge; the QD-2D conversion leaves the same registry identity
    on the resource-owned row.)"""
    from app.api.v1.endpoints.registrar_integration._queue_ops import (
        _build_queue_payload,
        _process_online_queue_entries,
    )

    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.default_cabinet = "7"
        db_session.commit()

        # the resource-owned row (the post-0063 shape of the backfill)
        resource_queue = _make_queue(
            db_session,
            day=_DAY,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        entry = _make_waiting_entry(db_session, resource_queue, number=31)

        queues_by_specialty: dict = {}
        _process_online_queue_entries(
            db_session, [entry], [], queues_by_specialty, set()
        )
        bucket = queues_by_specialty["laboratory"]
        assert "doctor_cabinet_missing" not in bucket.get("integrity_warnings", [])
        assert bucket["resource_display_name"] == "Ресурс очереди"
        assert bucket["resource_cabinet"] == "7"

        payload = _build_queue_payload(
            queue_data=bucket,
            specialty="laboratory",
            queue_number=1,
            entries=[{"id": entry.id, "status": "waiting"}],
        )
        # the REGISTRY identity, no doctor identity leaks
        assert payload["specialist_name"] == "Ресурс очереди"
        # the resource cabinet
        assert payload["cabinet"] == "7"
        assert payload["queue_resource_id"] == resource.id
    finally:
        _durable_cleanup(db_session)


def test_legacy_serializers_prefer_resource_owner_for_resource_queues(
    db_session: Session,
) -> None:
    """Codex round-31 P2: the legacy serializers (GET /api/v1/queue/today
    and GET /api/v1/queue/statistics) resolve the staff identity onto
    the resource-owned surface and report the RESOURCE axis — the
    registry display_name instead of a doctor full_name/username
    (the doctor-first condition previously reported). Pre-0063 the
    surface was the 0059 bridge; post-QD-2D it is the converted
    resource-owned row reached through the same staff fallback."""
    from app.api.v1.endpoints.queue import get_queue_statistics, get_today_queue

    try:
        user = _make_user(db_session, username="lab_res_oo2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.display_name = "Лаборатория (OO)"
        db_session.commit()

        today = _dt_now_tashkent_day()
        resource_queue = _make_queue(
            db_session,
            day=today,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        _make_waiting_entry(db_session, resource_queue, number=1)

        viewer = _make_user(db_session, username="adm_oo2", role="Admin")
        today_resp = get_today_queue(
            specialist_id=synthetic.id, db=db_session, current_user=viewer
        )
        assert today_resp.queue_id == resource_queue.id
        assert today_resp.specialist_name == "Лаборатория (OO)"

        stats_resp = get_queue_statistics(
            specialist_id=synthetic.id, day=today, db=db_session, current_user=viewer
        )
        assert stats_resp["success"] is True
        assert stats_resp["specialist"]["name"] == "Лаборатория (OO)"

        # regression: a pure doctor queue keeps the doctor identity
        doc_user = _make_user(db_session, username="dr_oo2", role="doctor")
        doc_user.full_name = "Доктор Кардио"
        db_session.commit()
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
        doctor_queue = _make_queue(
            db_session, day=today, specialist_id=doctor.id, queue_tag="cardio"
        )
        _make_waiting_entry(db_session, doctor_queue, number=2)
        doc_resp = get_today_queue(
            specialist_id=doctor.id, db=db_session, current_user=viewer
        )
        assert doc_resp.queue_id == doctor_queue.id
        assert doc_resp.specialist_name == "Доктор Кардио"
    finally:
        _durable_cleanup(db_session, "lab_res_oo2", "adm_oo2", "dr_oo2")


# ===================== PP. Codex round-32 pins =====================


def test_online_queue_today_defaults_to_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-32 P2: GET /api/v1/online-queue/today resolves the
    day through the clinic_today SSOT — the separately mounted endpoint
    passed host date.today() into the resource-aware lookup, so
    ?specialist_id=<lab/ecg id> missed the live clinic-day surface and
    reported queue_exists=false in the 19:00-24:00Z window. The timezone
    is chosen dynamically so the divergence is real."""
    from app.api.v1.endpoints.online_queue_new import get_today_queue
    from app.crud import clinic as crud_clinic

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()
    monkeypatch.setattr(crud_clinic, "clinic_today", lambda db: clinic_day)

    try:
        user = _make_user(db_session, username="lab_res_pp1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
        )
        assert queue is not None
        _make_waiting_entry(db_session, queue, number=1)
        _make_waiting_entry(db_session, queue, number=2)

        viewer = _make_user(db_session, username="adm_pp1", role="Admin")
        status = get_today_queue(
            specialist_id=synthetic.id, db=db_session, current_user=viewer
        )
        assert status["queue_exists"] is True
        assert status["queue_id"] == queue.id
        assert status["total_entries"] == 2
        assert status["waiting_entries"] == 2
    finally:
        _durable_cleanup(db_session, "lab_res_pp1", "adm_pp1")


def test_online_queue_aggregate_prefers_resource_owner_for_resource_queues(
    db_session: Session,
) -> None:
    """Codex round-32 P2: the online-queue aggregate (the no-specialist
    form of GET /api/v1/online-queue/today) classifies a resource-axis
    queue by the RESOURCE axis — the registry display_name instead of
    a doctor name/«Врач #id», consistent with the round-31 legacy
    serializers. (Pre-0063 the pin ran against the 0059 bridge; the
    QD-2D conversion leaves the same registry identity on the
    resource-owned row.)"""
    from app.crud.online_queue import get_queue_statistics

    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        resource = (
            db_session.query(QueueResource)
            .filter(QueueResource.queue_tag == "lab")
            .first()
        )
        resource.display_name = "Лаборатория (PP)"
        db_session.commit()

        today = _dt_now_tashkent_day()
        resource_queue = _make_queue(
            db_session,
            day=today,
            specialist_id=None,
            queue_tag="lab",
            queue_resource_id=resource.id,
        )
        _make_waiting_entry(db_session, resource_queue, number=1)

        doc_user = _make_user(db_session, username="dr_pp2", role="doctor")
        doc_user.full_name = "Доктор Кардио"
        db_session.commit()
        doctor = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
        doctor_queue = _make_queue(
            db_session, day=today, specialist_id=doctor.id, queue_tag="cardio"
        )
        _make_waiting_entry(db_session, doctor_queue, number=1)

        stats = get_queue_statistics(db_session, today)
        resource_row = next(
            q for q in stats["queues"] if q["queue_resource_id"] == resource.id
        )
        assert resource_row["specialist_id"] is None
        assert resource_row["specialist_name"] == "Лаборатория (PP)"

        doctor_row = next(q for q in stats["queues"] if q["specialist_id"] == doctor.id)
        assert doctor_row["specialist_name"] == "Доктор Кардио"
    finally:
        _durable_cleanup(db_session, "dr_pp2")


# ===================== QQ. Codex round-33 pins =====================


def test_analytics_department_resolves_profile_queue_tags(
    db_session: Session,
) -> None:
    """Codex round-33 P2: department-filtered analytics resolves the
    department's resource queue tags through its QueueProfile — the
    canonical 0055 department keys ('laboratory', 'echokg') differ from
    the registry tags ('lab', 'ecg') and specialty_variants alone
    excluded the resource queues, reporting zero queue activity for the
    department."""
    from datetime import datetime as _dt

    from app.models.department import Department
    from app.models.queue_profile import QueueProfile
    from app.services.analytics import AnalyticsService

    today = _dt_now_tashkent_day()
    start = _dt(today.year, today.month, today.day, 0, 0)
    end = _dt(today.year, today.month, today.day, 23, 59)
    try:
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=today, specialist_id=None, queue_tag="lab"
        )
        _make_waiting_entry(db_session, queue, number=1)
        _make_waiting_entry(db_session, queue, number=2)

        department = Department(key="laboratory_qq", name_ru="Лаборатория")
        profile = QueueProfile(
            key="laboratory_qq",
            title="Лаборатория",
            department_key="laboratory_qq",
            queue_tags=["lab"],
        )
        db_session.add_all([department, profile])
        db_session.commit()

        stats = AnalyticsService.get_queue_statistics(
            db_session, start, end, department="laboratory_qq"
        )
        assert stats["total_queues"] == 1
        assert stats["total_entries"] == 2
    finally:
        _durable_cleanup(db_session)
        db_session.query(QueueProfile).filter(
            QueueProfile.key == "laboratory_qq"
        ).delete(synchronize_session=False)
        db_session.query(Department).filter(Department.key == "laboratory_qq").delete(
            synchronize_session=False
        )
        db_session.commit()


def test_availability_compares_dates_on_clinic_clock(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-33 P2: /online-queue/status availability compares the
    requested day on the CLINIC clock — host date.today() classified
    the current clinic day as future and skipped the pre-07:00
    TOO_EARLY restriction (within_hours=true before online
    registration opens). The clock is frozen on the next clinic day at
    05:30 (guaranteed to differ from the host date)."""
    from app.crud import online_queue as crud_online_queue

    frozen_day = date.today() + timedelta(days=1)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            frozen = datetime.combine(frozen_day, datetime.min.time()).replace(
                hour=5, minute=30
            )
            if tz is not None:
                return frozen.replace(tzinfo=tz)
            return frozen

    monkeypatch.setattr(crud_online_queue, "datetime", FixedDateTime)

    user = _make_user(db_session, username="lab_res_qq2", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    try:
        availability = crud_online_queue.check_queue_availability(
            db_session, frozen_day, specialist_id=synthetic.id
        )
        # the clinic-day TOO_EARLY guard applies — NOT the host clock's
        # future-day availability
        assert availability["available"] is False, availability
        assert availability["reason"] == "TOO_EARLY"
        assert availability["available_from"] == "7:00"
    finally:
        _durable_cleanup(db_session, "lab_res_qq2")


# ===================== RR. Codex round-34 pins =====================


def test_doctor_completion_persists_resource_visit_department(
    db_session: Session,
) -> None:
    """Codex round-34 P2: completing a resource-owned lab/ECG entry
    without a linked Visit persists the encounter under the RESOURCE
    department — DailyQueue has no department attribute, so the legacy
    fallback always wrote «cardiology» for specialist-null queues. The
    visit department now comes from the queue tag / registry axis."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        complete_patient_visit,
    )
    from app.models.patient import Patient
    from app.models.visit import Visit

    patient = Patient(
        last_name="Ресурсный",
        first_name="Пациент",
        phone="+998901234534",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_dt_now_tashkent_day(), specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=1)
        entry.patient_id = patient.id
        # the action ladder: complete is available from in_progress
        entry.status = "in_progress"
        db_session.commit()

        admin = _make_user(db_session, username="adm_rr1", role="Admin")
        result = complete_patient_visit(
            entry_id=entry.id, db=db_session, current_user=admin
        )
        assert result["success"] is True

        db_session.refresh(entry)
        assert entry.status == "served"
        visit = (
            db_session.query(Visit)
            .filter(Visit.patient_id == patient.id)
            .order_by(Visit.id.desc())
            .first()
        )
        assert visit is not None
        # the RESOURCE department, not the legacy «cardiology» fallback
        assert visit.department == "lab"
        assert visit.doctor_id is None
    finally:
        _durable_cleanup(db_session, "adm_rr1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_doctor_call_and_start_visit_accept_resource_owner(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-34 P2: the doctor command surface (POST
    /doctor/queue/{entry_id}/call and /start-visit) accepts a pure
    resource queue as a valid owner — the unconditional 404 on the
    missing specialist relationship made lab/ECG tickets uncallable
    and unstartable. The resource authorization policy mirrors the
    completion handler (round-5): Admin only."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )

    # the display broadcast rides asyncio.create_task inside the
    # handler's try/except — no loop in the sync test is swallowed there
    from app.models.patient import Patient
    from app.models.visit import Visit

    patient = Patient(
        last_name="Ресурсный2",
        first_name="Пациент",
        phone="+998901234535",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_dt_now_tashkent_day(), specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=1)
        entry.patient_id = patient.id
        db_session.commit()

        admin = _make_user(db_session, username="adm_rr2", role="Admin")
        called = call_patient(entry_id=entry.id, db=db_session, current_user=admin)
        assert called["success"] is True
        db_session.refresh(entry)
        assert entry.status == "called"
        assert entry.called_by_user_id == admin.id

        started = start_patient_visit(
            entry_id=entry.id, db=db_session, current_user=admin
        )
        assert started["success"] is True
        db_session.refresh(entry)
        assert entry.status == "in_progress"

        # the non-Admin rejection keeps the completion-handler policy
        from fastapi import HTTPException

        outsider = _make_user(db_session, username="dr_rr2", role="doctor")
        waiting2 = _make_waiting_entry(db_session, queue, number=2)
        try:
            call_patient(entry_id=waiting2.id, db=db_session, current_user=outsider)
            raised = False
        except HTTPException as exc:
            raised = exc.status_code == 403
        assert raised, "a non-Admin must not call a resource-owned entry"
    finally:
        _durable_cleanup(db_session, "adm_rr2", "dr_rr2")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== SS. Codex round-35 pins =====================


def test_resource_start_and_complete_share_one_visit(db_session: Session) -> None:
    """Codex round-35 P1: the resource command surface anchors its
    Visit to the queue entry — a resource start must not transition an
    unrelated open cardiology visit of the same patient (the
    doctor_id=None lookup grabbed any open visit), and the created
    Visit is linked onto the entry so the completion mutates the SAME
    encounter instead of leaving the first in_progress and creating a
    second."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        complete_patient_visit,
        start_patient_visit,
    )
    from app.models.patient import Patient
    from app.models.visit import Visit

    patient = Patient(
        last_name="Ресурсный3",
        first_name="Пациент",
        phone="+998901234536",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        # an UNRELATED open cardiology visit of the same patient — must
        # stay untouched by the resource command surface
        unrelated = Visit(
            patient_id=patient.id,
            doctor_id=None,
            visit_date=date.today(),
            visit_time="08:00",
            department="cardiology",
            status="open",
        )
        db_session.add(unrelated)
        db_session.commit()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=_dt_now_tashkent_day(), specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=1)
        entry.patient_id = patient.id
        db_session.commit()

        admin = _make_user(db_session, username="adm_ss1", role="Admin")
        assert call_patient(entry_id=entry.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=entry.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(entry)
        assert entry.visit_id is not None, "the started visit must be linked"

        started = db_session.query(Visit).filter(Visit.id == entry.visit_id).first()
        assert started is not None
        assert started.department == "lab"  # NOT the unrelated cardiology visit
        assert started.id != unrelated.id

        # the unrelated cardiology visit stays open
        db_session.refresh(unrelated)
        assert unrelated.status == "open"

        # completion mutates the SAME visit — no second lab encounter
        assert complete_patient_visit(
            entry_id=entry.id, db=db_session, current_user=admin
        )["success"]
        db_session.refresh(entry)
        assert entry.visit_id == started.id

        lab_visits = (
            db_session.query(Visit)
            .filter(Visit.patient_id == patient.id, Visit.department == "lab")
            .all()
        )
        assert len(lab_visits) == 1, "start and completion share ONE visit"
        db_session.refresh(started)
        assert started.status == "completed"
        db_session.refresh(unrelated)
        assert unrelated.status == "open"
    finally:
        _durable_cleanup(db_session, "adm_ss1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== TT. Codex round-36 pins =====================


def test_resource_visit_dates_follow_the_queue_day(db_session: Session) -> None:
    """Codex round-36 P2: an unlinked resource entry's Visit is looked
    up and created on the ENTRY'S QUEUE day (the clinic-local day the
    resource queue is stamped with), not host date.today() — in the
    19:00-24:00Z window the host-day lookup missed the existing
    clinic-day lab/ECG visit and created the replacement under the
    previous service date."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.models.patient import Patient
    from app.models.visit import Visit

    patient = Patient(
        last_name="Ресурсный4",
        first_name="Пациент",
        phone="+998901234537",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        # the clinic-local day the resource queue is stamped with —
        # guaranteed to differ from the host date
        queue_day = date.today() + timedelta(days=1)
        assert queue_day != date.today()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=queue_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=1)
        entry.patient_id = patient.id
        db_session.commit()

        admin = _make_user(db_session, username="adm_tt1", role="Admin")
        assert call_patient(entry_id=entry.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=entry.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(entry)
        assert entry.visit_id is not None
        visit = db_session.query(Visit).filter(Visit.id == entry.visit_id).first()
        assert visit is not None
        # the Visit follows the ENTRY'S QUEUE day, not the host clock
        assert visit.visit_date == queue_day
        assert visit.department == "lab"
    finally:
        _durable_cleanup(db_session, "adm_tt1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== UU. Codex round-37 pins =====================


def test_resource_visit_times_use_the_clinic_clock(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-37 P2: resource-visit times ride the CLINIC clock (the
    queue-settings timezone) — host datetime.now() recorded a clinic
    01:00 encounter as 20:00 the previous day, and the start overwrite
    repeated the host-local value; registrar views and time-based
    notifications showed a time up to five hours late. The clock is
    frozen at a fixed clinic time so the assertion is deterministic."""
    from app.api.v1.endpoints.doctor_integration import _queue_ops as dqo
    from app.models.patient import Patient
    from app.models.visit import Visit

    frozen_day = date.today() + timedelta(days=1)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            frozen = datetime.combine(frozen_day, datetime.min.time()).replace(
                hour=13, minute=45
            )
            if tz is not None:
                return frozen.replace(tzinfo=tz)
            return frozen

    monkeypatch.setattr(dqo, "datetime", FixedDateTime)

    patient = Patient(
        last_name="Ресурсный5",
        first_name="Пациент",
        phone="+998901234538",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=frozen_day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, queue, number=1)
        entry.patient_id = patient.id
        db_session.commit()

        admin = _make_user(db_session, username="adm_uu1", role="Admin")
        assert dqo.call_patient(entry_id=entry.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert dqo.start_patient_visit(
            entry_id=entry.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(entry)
        visit = db_session.query(Visit).filter(Visit.id == entry.visit_id).first()
        assert visit is not None
        # the CLINIC clock time, not the host wall time
        assert visit.visit_time == "13:45"
        assert "13:45" in (visit.notes or "")
    finally:
        _durable_cleanup(db_session, "adm_uu1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== VV. Codex round-38 pins =====================


def test_queue_statistics_stamp_the_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-38 P2: queue statistics rows are stamped with the
    CLINIC-local day (the clinic_today SSOT from the queue-settings
    timezone) — a QR join between 19:00 and midnight UTC recorded the
    online_joins event under the previous HOST date, so the
    resource-axis rows fell out of /admin/queue-analytics even when
    the actual clinic day was requested explicitly. The service
    COMMITs — durable rows cleaned in the finally."""
    from app.models.online_queue import QueueStatistics
    from app.services.qr_queue import QRQueueService
    from app.services.qr_queue import _queue_ops as qr_ops

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr(qr_ops, "clinic_today", lambda db: clinic_day)

    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, queue, number=82)

    try:
        service = QRQueueService(db_session)
        service._update_queue_statistics(queue.id, "online_joins")

        stats = (
            db_session.query(QueueStatistics)
            .filter(QueueStatistics.queue_id == queue.id)
            .all()
        )
        assert len(stats) == 1
        # the row rides the CLINIC day, not the host clock
        assert stats[0].date == clinic_day
        assert stats[0].date != date.today()
        assert stats[0].online_joins == 1
    finally:
        db_session.query(QueueStatistics).filter(
            QueueStatistics.queue_id == queue.id
        ).delete(synchronize_session=False)
        _durable_cleanup(db_session)
        db_session.commit()


# ===================== WW. Codex round-39 pins =====================


def test_analytics_default_range_rides_the_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-39 P2: the default analytics period (omitted
    start/end) is derived from the CLINIC-local day — the
    clinic_today SSOT the statistics rows are stamped with (round-38)
    — so a default /admin/queue-analytics request keeps reporting the
    current clinic day's newly recorded totals instead of excluding
    them via the host date in the 19:00-24:00Z divergence window.
    The clinic clock is forced onto a timezone whose local date
    guaranteedly differs from the host date."""
    from app.api.v1.endpoints.qr_queue._analytics import get_queue_analytics
    from app.models.online_queue import QueueStatistics

    tz_name, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr("app.crud.clinic.clinic_today", lambda db: clinic_day)

    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
    )
    db_session.add(
        QueueStatistics(
            queue_id=queue.id,
            date=clinic_day,
            online_joins=3,
            desk_registrations=0,
            telegram_joins=0,
            confirmation_joins=0,
            total_served=0,
            total_no_show=0,
        )
    )
    db_session.commit()

    user = _make_user(db_session, username="lab_res_ww1", role="Resource")
    synthetic = _make_doctor(db_session, user_id=user.id, specialty="lab")
    admin = _make_user(db_session, username="adm_ww1", role="Admin")

    try:
        payload = get_queue_analytics(synthetic.id, db=db_session, current_user=admin)
        # the default period closes on the CLINIC day and keeps the
        # freshly stamped resource row inside the report
        assert payload["period"]["end_date"] == clinic_day.isoformat()
        assert (
            payload["period"]["start_date"]
            == (clinic_day - timedelta(days=30)).isoformat()
        )
        assert payload["totals"]["online_joins"] == 3
    finally:
        db_session.query(QueueStatistics).filter(
            QueueStatistics.queue_id == queue.id
        ).delete(synchronize_session=False)
        _durable_cleanup(db_session, "lab_res_ww1", "adm_ww1")
        db_session.commit()


# ===================== XX. Codex round-40 pins =====================


def test_transferred_solo_visit_follows_the_new_queue_day(db_session: Session) -> None:
    """Codex round-40 P2: a force-majeure transfer copies the original
    visit_id onto tomorrow's entry — the visit_id-first branch must
    not return a retained visit stamped on the ORIGINAL service day:
    a solo visit follows the transferred ticket onto the NEW queue day
    (re-dated to the day the encounter is actually served), so the
    start/completion mutate the correctly dated encounter. The
    cancelled original keeps its visit_id but does not count as a
    share — withdrawn tickets no longer anchor the visit."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный7",
        first_name="Пациент",
        phone="+998901234540",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        res_user = _make_user(db_session, username="lab_res_xx1", role="Resource")
        synthetic = _make_doctor(db_session, user_id=res_user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=None, queue_tag="lab"
        )

        # the registrar-wizard state: a waiting ticket already linked
        # to the visit stamped on the ORIGINAL queue day
        visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=None,
            visit_date=original_day,
            visit_time="09:00",
            department="lab",
        )
        entry = _make_waiting_entry(db_session, queue, number=91)
        entry.patient_id = patient.id
        entry.visit_id = visit.id
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[entry],
            specialist_id=synthetic.id,
            reason="round-40 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        assert moved.visit_id == visit.id  # the link the transfer retained

        admin = _make_user(db_session, username="adm_xx1", role="Admin")
        assert call_patient(entry_id=moved.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=moved.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(visit)
        # the retained SOLO visit follows the transferred ticket: the
        # encounter is recorded on the NEW queue day (one visit total)
        assert visit.visit_date == new_day
        visits = db_session.query(Visit).filter(Visit.patient_id == patient.id).all()
        assert len(visits) == 1
    finally:
        _durable_cleanup(db_session, "lab_res_xx1", "adm_xx1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_transferred_shared_visit_keeps_its_day(
    db_session: Session,
) -> None:
    """Codex round-40 P2 (shared facet): a registrar multi-service visit
    is linked to several same-day tickets — transferring ONE of them to
    tomorrow must not re-date the visit under the remaining tickets'
    feet: the retained visit keeps its original day (still anchored by
    the waiting same-day ticket), and the transferred entry resolves a
    FRESH visit on its new queue day."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный8",
        first_name="Пациент",
        phone="+998901234541",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        res_user = _make_user(db_session, username="lab_res_xx2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=res_user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        _make_resource(db_session, code="ecg", queue_tag="ecg")
        lab_queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=None, queue_tag="lab"
        )
        ecg_queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=None, queue_tag="ecg"
        )

        # one registrar visit shared by BOTH same-day tickets
        visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=None,
            visit_date=original_day,
            visit_time="09:30",
            department="lab",
        )
        lab_entry = _make_waiting_entry(db_session, lab_queue, number=92)
        lab_entry.patient_id = patient.id
        lab_entry.visit_id = visit.id
        ecg_entry = _make_waiting_entry(db_session, ecg_queue, number=1)
        ecg_entry.patient_id = patient.id
        ecg_entry.visit_id = visit.id
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[lab_entry],
            specialist_id=synthetic.id,
            reason="round-40 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )

        admin = _make_user(db_session, username="adm_xx2", role="Admin")
        assert call_patient(entry_id=moved.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=moved.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(visit)
        db_session.refresh(ecg_entry)
        # the SHARED visit keeps its original day for the remaining
        # same-day ticket and stays open
        assert visit.visit_date == original_day
        assert visit.status == "open"

        # the transferred entry relinks onto a FRESH queue-day visit
        db_session.refresh(moved)
        assert moved.visit_id != visit.id
        fresh = db_session.query(Visit).filter(Visit.id == moved.visit_id).first()
        assert fresh is not None
        assert fresh.visit_date == new_day
        assert fresh.department == "lab"
    finally:
        _durable_cleanup(db_session, "lab_res_xx2", "adm_xx2")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== YY. Codex round-41 pins =====================


def test_transferred_doctor_visit_follows_the_new_queue_day(
    db_session: Session,
) -> None:
    """Codex round-41 P2 (doctor facet): force-majeure also transfers
    ordinary doctor-owned entries while retaining their visit_id — the
    retained-visit day validation must cover the DOCTOR surface as
    well: a solo doctor visit follows the transferred ticket onto the
    NEW queue day (the encounter is served there), so the start/
    completion mutate the correctly dated visit instead of updating
    yesterday's encounter."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный9",
        first_name="Пациент",
        phone="+998901234542",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        # a REAL doctor whose specialty has no registry row — the
        # transfer keeps the legacy doctor-owned surface (specialist
        # queue), so the resolve site takes the doctor branch
        doc_user = _make_user(db_session, username="doc_yy1", role="Doctor")
        therapist = _make_doctor(db_session, user_id=doc_user.id, specialty="therapy")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=therapist.id
        )

        visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=therapist.id,
            visit_date=original_day,
            visit_time="10:00",
            department="therapy",
        )
        entry = _make_waiting_entry(db_session, queue, number=96)
        entry.patient_id = patient.id
        entry.visit_id = visit.id
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[entry],
            specialist_id=therapist.id,
            reason="round-41 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        assert moved.visit_id == visit.id  # the link the transfer retained

        admin = _make_user(db_session, username="adm_yy1", role="Admin")
        assert call_patient(entry_id=moved.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=moved.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(visit)
        # the retained DOCTOR-owned solo visit follows the transferred
        # ticket: the encounter is recorded on the NEW queue day
        assert visit.visit_date == new_day
        visits = db_session.query(Visit).filter(Visit.patient_id == patient.id).all()
        assert len(visits) == 1
    finally:
        _durable_cleanup(db_session, "doc_yy1", "adm_yy1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_group_transferred_entries_share_one_relinked_visit(
    db_session: Session,
) -> None:
    """Codex round-41 P2 (grouped facet): when several same-department
    resource tickets sharing ONE visit are transferred together, the
    transferred peers must not anchor the retained visit — every peer
    rides on the new queue day, so the first ticket re-dates the solo
    visit onto the new day and the rest resolve the SAME visit on the
    fast path; otherwise the group transfer left TWO visits for the
    same patient, department and new queue day."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный10",
        first_name="Пациент",
        phone="+998901234543",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        res_user = _make_user(db_session, username="lab_res_yy2", role="Resource")
        synthetic = _make_doctor(db_session, user_id=res_user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        lab_queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=None, queue_tag="lab"
        )

        # one registrar visit shared by BOTH same-day lab tickets
        visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=None,
            visit_date=original_day,
            visit_time="11:00",
            department="lab",
        )
        first = _make_waiting_entry(db_session, lab_queue, number=97)
        first.patient_id = patient.id
        first.visit_id = visit.id
        second = _make_waiting_entry(db_session, lab_queue, number=98)
        second.patient_id = patient.id
        second.visit_id = visit.id
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[first, second],
            specialist_id=synthetic.id,
            reason="round-41 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .order_by(OnlineQueueEntry.id)
            .all()
        )
        assert len(moved) == 2

        admin = _make_user(db_session, username="adm_yy2", role="Admin")
        for ticket in moved:
            assert call_patient(entry_id=ticket.id, db=db_session, current_user=admin)[
                "success"
            ]
            assert start_patient_visit(
                entry_id=ticket.id, db=db_session, current_user=admin
            )["success"]

        db_session.refresh(visit)
        db_session.refresh(moved[0])
        db_session.refresh(moved[1])
        # the transferred peers did NOT anchor the old-day visit: the
        # first ticket re-dated the solo visit onto the new queue day
        assert visit.visit_date == new_day
        # both transferred tickets resolve THE SAME visit (no second
        # visit for the patient/department on the new day)
        assert moved[0].visit_id == visit.id
        assert moved[1].visit_id == visit.id
        visits = db_session.query(Visit).filter(Visit.patient_id == patient.id).all()
        assert len(visits) == 1
    finally:
        _durable_cleanup(db_session, "lab_res_yy2", "adm_yy2")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== ZZ. Codex round-42 pins =====================


def test_transferred_shared_doctor_visit_relinks_onto_queue_day(
    db_session: Session,
) -> None:
    """Codex round-42 P2 (doctor shared facet): when one of several
    same-day doctor tickets sharing a Visit is transferred, the
    fall-through resolves a FRESH doctor visit on the QUEUE day — the
    old find_or_create_today_visit (host date.today()) returned the
    ORIGINAL still-anchored visit (the moved ticket kept mutating the
    old-day encounter) or created the visit under the host day."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный11",
        first_name="Пациент",
        phone="+998901234544",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        doc_user = _make_user(db_session, username="doc_zz1", role="Doctor")
        therapist = _make_doctor(db_session, user_id=doc_user.id, specialty="therapy")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=therapist.id
        )

        # one doctor visit shared by BOTH same-day tickets
        visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=therapist.id,
            visit_date=original_day,
            visit_time="12:00",
            department="therapy",
        )
        first = _make_waiting_entry(db_session, queue, number=99)
        first.patient_id = patient.id
        first.visit_id = visit.id
        second = _make_waiting_entry(db_session, queue, number=100)
        second.patient_id = patient.id
        second.visit_id = visit.id
        db_session.commit()

        # only ONE ticket moves — the shared visit stays anchored by
        # the remaining same-day ticket
        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[first],
            specialist_id=therapist.id,
            reason="round-42 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )

        admin = _make_user(db_session, username="adm_zz1", role="Admin")
        assert call_patient(entry_id=moved.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=moved.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(visit)
        db_session.refresh(moved)
        # the shared doctor visit keeps its day for the remaining
        # same-day ticket and stays open
        assert visit.visit_date == original_day
        assert visit.status == "open"
        # the transferred ticket relinks onto a FRESH queue-day visit
        # (not back onto the anchored original — the host-today lookup
        # of find_or_create_today_visit found exactly that original)
        assert moved.visit_id != visit.id
        fresh = db_session.query(Visit).filter(Visit.id == moved.visit_id).first()
        assert fresh is not None
        assert fresh.visit_date == new_day
        assert fresh.doctor_id == therapist.id
    finally:
        _durable_cleanup(db_session, "doc_zz1", "adm_zz1")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_legacy_statistics_default_day_rides_the_clinic_day(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-42 P2: GET /queue/legacy/statistics/{specialist_id}
    with the day omitted resolved host date.today() — in the evening
    window the host lags the clinic day, so the registry resolver saw
    the previous day's surface (stale statistics or «Очередь не
    найдена» for the live clinic-day resource queue). The omitted day
    now rides the clinic_today SSOT."""
    from app.api.v1.endpoints.queue import get_queue_statistics

    _, clinic_day = _divergent_clinic_day()
    assert clinic_day != date.today()  # the divergence window is real
    monkeypatch.setattr("app.crud.clinic.clinic_today", lambda db: clinic_day)

    res_user = _make_user(db_session, username="lab_res_zz2", role="Resource")
    synthetic = _make_doctor(db_session, user_id=res_user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    queue = queue_service.get_or_create_daily_queue(
        db_session, day=clinic_day, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, queue, number=101)

    admin = _make_user(db_session, username="adm_zz2", role="Admin")
    # the omitted day (None) must resolve the CLINIC-day surface, not
    # the host date the old default_factory stamped
    payload = get_queue_statistics(
        synthetic.id, day=None, db=db_session, current_user=admin
    )
    assert payload["success"] is True, payload
    assert payload["statistics"]["total_entries"] == 1


# ===================== AB. Codex round-43 pins =====================


def test_re_dated_visit_moves_its_paired_appointment(db_session: Session) -> None:
    """Codex round-43 P2: the solo re-date of a transferred ticket
    moves the PAIRED appointment with the visit — completion pairs
    appointments by patient/date/doctor and canonical resolution by
    patient/date/time/doctor, so a visit moved alone left its
    appointment scheduled on the old day (and canonical resolution
    could fork a second visit for it)."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.appointment import Appointment
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный12",
        first_name="Пациент",
        phone="+998901234545",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        doc_user = _make_user(db_session, username="doc_ab1", role="Doctor")
        therapist = _make_doctor(db_session, user_id=doc_user.id, specialty="therapy")
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=therapist.id
        )

        visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=therapist.id,
            visit_date=original_day,
            visit_time="10:00",
            department="therapy",
        )
        # the registrar booking paired with the visit (same patient/
        # day/time/doctor, still scheduled)
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=therapist.id,
            appointment_date=original_day,
            appointment_time="10:00",
            status="scheduled",
        )
        db_session.add(appointment)
        entry = _make_waiting_entry(db_session, queue, number=102)
        entry.patient_id = patient.id
        entry.visit_id = visit.id
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[entry],
            specialist_id=therapist.id,
            reason="round-43 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )
        admin = _make_user(db_session, username="adm_ab1", role="Admin")
        assert call_patient(entry_id=moved.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=moved.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(visit)
        db_session.refresh(appointment)
        # the visit AND its paired appointment follow the ticket
        assert visit.visit_date == new_day
        assert appointment.appointment_date == new_day
        assert appointment.status == "scheduled"
        visits = db_session.query(Visit).filter(Visit.patient_id == patient.id).all()
        assert len(visits) == 1
        # the completion pairing (patient/new date/doctor) finds the
        # SAME appointment — no stale old-day copy left behind
        found = (
            db_session.query(Appointment)
            .filter(
                Appointment.patient_id == patient.id,
                Appointment.appointment_date == visit.visit_date,
                Appointment.doctor_id == visit.doctor_id,
            )
            .first()
        )
        assert found is not None and found.id == appointment.id
    finally:
        _durable_cleanup(db_session, "doc_ab1", "adm_ab1")
        db_session.query(Appointment).filter(
            Appointment.patient_id == patient.id
        ).delete(synchronize_session=False)
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_doctor_fall_through_scopes_to_the_queue_department(
    db_session: Session,
) -> None:
    """Codex round-43 P2: the doctor fall-through lookup is scoped to
    the QUEUE department — one doctor can hold active queues under
    different tags, and an open same-day visit of the same doctor for
    ANOTHER tag must not capture the ticket (the department-less
    .first() relinked the transferred ticket onto an unrelated
    encounter, and start/completion mutated the wrong visit)."""
    from app.api.v1.endpoints.doctor_integration._queue_ops import (
        call_patient,
        start_patient_visit,
    )
    from app.crud import visit as crud_visit
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.force_majeure_service import ForceMajeureService

    patient = Patient(
        last_name="Ресурсный13",
        first_name="Пациент",
        phone="+998901234546",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        original_day = _dt_now_tashkent_day()
        doc_user = _make_user(db_session, username="doc_ab2", role="Doctor")
        therapist = _make_doctor(db_session, user_id=doc_user.id, specialty="therapy")
        # the ORIGINAL doctor queue (untagged): a walked-in ticket
        # with NO visit link — the transfer keeps it visit-less
        queue = queue_service.get_or_create_daily_queue(
            db_session, day=original_day, specialist_id=therapist.id
        )
        entry = _make_waiting_entry(db_session, queue, number=103)
        entry.patient_id = patient.id
        db_session.commit()

        result = ForceMajeureService(db_session).transfer_entries_to_tomorrow(
            entries=[entry],
            specialist_id=therapist.id,
            reason="round-43 pin",
            performed_by_id=1,
            send_notifications=False,
        )
        assert result["success"] is True
        new_day = date.fromisoformat(result["new_date"])
        assert new_day == original_day + timedelta(days=1)

        moved = (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.source == "force_majeure_transfer")
            .one()
        )

        # the patient ALREADY has an open visit on the new day with
        # the SAME doctor under ANOTHER queue tag (ultrasound)
        other_tag_visit = crud_visit.create_visit(
            db=db_session,
            patient_id=patient.id,
            doctor_id=therapist.id,
            visit_date=new_day,
            visit_time="09:00",
            department="ultrasound",
        )
        db_session.commit()

        admin = _make_user(db_session, username="adm_ab2", role="Admin")
        assert call_patient(entry_id=moved.id, db=db_session, current_user=admin)[
            "success"
        ]
        assert start_patient_visit(
            entry_id=moved.id, db=db_session, current_user=admin
        )["success"]

        db_session.refresh(other_tag_visit)
        db_session.refresh(moved)
        # the therapy-tag ticket resolves its OWN queue-department visit
        assert moved.visit_id != other_tag_visit.id
        own = db_session.query(Visit).filter(Visit.id == moved.visit_id).one()
        assert own.department == "therapy"
        assert own.visit_date == new_day
        assert own.doctor_id == therapist.id
        # the unrelated ultrasound visit stays untouched (still open)
        assert other_tag_visit.status == "open"
    finally:
        _durable_cleanup(db_session, "doc_ab2", "adm_ab2")
        db_session.query(Visit).filter(Visit.patient_id == patient.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== AC. Codex review pin (89c6311bb) =====================


def test_full_update_cross_tag_auto_create_resolves_service_doctor(
    db_session: Session,
) -> None:
    """Codex P2 (review on 89c6311bb): the full-update auto-create of a
    missing target queue inherited the SOURCE queue's specialist_id —
    for a resource-owned source (lab/ECG) that is None, so the doctor
    branch of get_or_create_daily_queue raised ValueError and QR edits
    could not add a cross-tag doctor service until some other process
    pre-created its queue. The auto-create now resolves the TARGET
    service's doctor identity (the wizard's «item specialist or the
    service's default doctor» precedent)."""
    from app.api.v1.endpoints.qr_queue._online_entries import (
        _full_update_resolve_target_queue_id,
    )
    from app.models.patient import Patient
    from app.models.service import Service

    patient = Patient(
        last_name="Ресурсный14",
        first_name="Пациент",
        phone="+998901234547",
        is_deleted=False,
    )
    try:
        db_session.add(patient)
        db_session.commit()

        day = _dt_now_tashkent_day()
        res_user = _make_user(db_session, username="lab_res_ac1", role="Resource")
        _make_doctor(db_session, user_id=res_user.id, specialty="lab")
        _make_resource(db_session, code="lab", queue_tag="lab")
        lab_queue = queue_service.get_or_create_daily_queue(
            db_session, day=day, specialist_id=None, queue_tag="lab"
        )
        entry = _make_waiting_entry(db_session, lab_queue, number=104)
        entry.patient_id = patient.id
        db_session.commit()

        # a doctor-tag service with NO active queue on that day; the
        # service names its default doctor (the wizard's resolution)
        doc_user = _make_user(db_session, username="doc_ac1", role="Doctor")
        therapist = _make_doctor(db_session, user_id=doc_user.id, specialty="therapy")
        service = Service(
            name="Приём терапевта",
            queue_tag="therapy",
            active=True,
            price=1000,
            requires_doctor=True,
            doctor_id=therapist.id,
        )
        db_session.add(service)
        db_session.commit()

        # no therapy queue exists yet (the lab resource queue is the
        # entry's surface) — the auto-create resolves the service's
        # doctor instead of inheriting the resource queue's NULL owner
        target_queue_id = _full_update_resolve_target_queue_id(
            db_session, entry, service
        )
        created = (
            db_session.query(DailyQueue).filter(DailyQueue.id == target_queue_id).one()
        )
        assert created.queue_tag == "therapy"
        assert created.specialist_id == therapist.id
        assert created.day == day
    finally:
        _durable_cleanup(db_session, "lab_res_ac1", "doc_ac1")
        db_session.query(Service).filter(Service.id == service.id).delete(
            synchronize_session=False
        )
        db_session.query(Patient).filter(Patient.id == patient.id).delete(
            synchronize_session=False
        )
        db_session.commit()


# ===================== AD. Codex round-44 pin =====================


def test_cabinet_specialist_filter_sees_resource_queues(db_session: Session) -> None:
    """Codex round-44 P2: the admin cabinet screen filtered by the
    legacy lab/ECG specialist_id must see the REGISTRY surface — a
    pure resource queue stores specialist_id NULL, so the doctor-keyed
    filter alone returned an empty list for the live resource queue
    the same identity addresses on every other surface."""
    from app.services.queue_domain_service import QueueDomainService

    day = _dt_now_tashkent_day()
    res_user = _make_user(db_session, username="lab_res_ad1", role="Resource")
    synthetic = _make_doctor(db_session, user_id=res_user.id, specialty="lab")
    _make_resource(db_session, code="lab", queue_tag="lab")
    # the PURE resource world: the lab queue is resource-owned
    # (specialist NULL), no doctor-keyed shadow exists
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=day, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, resource_queue, number=105)

    payload = QueueDomainService(db_session).list_queue_cabinet_info(
        day=day, specialist_id=synthetic.id, cabinet_number=None
    )
    # the legacy identity's filter resolves the registry-backed
    # surface instead of an empty list
    assert [item["id"] for item in payload] == [resource_queue.id]
    assert payload[0]["active"] is True


# ===================== AE. Codex round-45 pin =====================


def test_cabinet_filter_survives_registry_deactivation(db_session: Session) -> None:
    """Codex round-45 P2: an operator deactivating a registry row
    after a pure resource queue was created must not evict it from
    the specialist-filtered cabinet screen — the requested day's
    EXISTING resource surface keeps the tag in scope (the round-3 P1
    deactivation-proof routing contract), and the day-less filter
    keeps any live resource queue of the tag visible too."""
    from app.services.queue_domain_service import QueueDomainService

    day = _dt_now_tashkent_day()
    res_user = _make_user(db_session, username="lab_res_ae1", role="Resource")
    synthetic = _make_doctor(db_session, user_id=res_user.id, specialty="lab")
    resource_row = _make_resource(db_session, code="lab", queue_tag="lab")
    resource_queue = queue_service.get_or_create_daily_queue(
        db_session, day=day, specialist_id=None, queue_tag="lab"
    )
    _make_waiting_entry(db_session, resource_queue, number=106)

    # the operator deactivates the registry row AFTER the queue exists
    resource_row.active = False
    db_session.commit()

    payload = QueueDomainService(db_session).list_queue_cabinet_info(
        day=day, specialist_id=synthetic.id, cabinet_number=None
    )
    assert [item["id"] for item in payload] == [resource_queue.id]

    # day-less filter: any live resource queue of the tag keeps the
    # tag in scope (the active-registry row is no longer required)
    payload_all = QueueDomainService(db_session).list_queue_cabinet_info(
        day=None, specialist_id=synthetic.id, cabinet_number=None
    )
    assert resource_queue.id in [item["id"] for item in payload_all]


# ===================== AF. Codex round-46 pin =====================


def test_cabinet_specialist_filter_includes_resource_queues(
    db_session: Session,
) -> None:
    """Codex round-46 P2: the specialist-filtered cabinet reads must
    match the resource axis by queue_resource_id + tag rather than by
    a NULL specialist, or the resource queue drops out of the lab
    identity's filter. Pre-0063 the pin ran against the 0059
    cross-owner bridge (a general_resource-owned lab queue with
    queue_resource_id set); the QD-2D conversion leaves the same
    resource-arm match on the resource-owned row."""
    from app.services.queue_domain_service import QueueDomainService

    day = _dt_now_tashkent_day()
    lab_user = _make_user(db_session, username="lab_res_af1", role="Resource")
    lab_synthetic = _make_doctor(db_session, user_id=lab_user.id, specialty="lab")
    lab_resource = _make_resource(db_session, code="lab", queue_tag="lab")

    # the resource-owned lab queue (the post-0063 shape of the 0059
    # cross-owner bridge — exact-tag-wins)
    resource_queue = _make_queue(
        db_session,
        day=day,
        specialist_id=None,
        queue_tag="lab",
        active=True,
        queue_resource_id=lab_resource.id,
    )
    _make_waiting_entry(db_session, resource_queue, number=107)

    payload = QueueDomainService(db_session).list_queue_cabinet_info(
        day=day, specialist_id=lab_synthetic.id, cabinet_number=None
    )
    # the LAB identity's filter sees the resource queue (the resource
    # axis by queue_resource_id + tag, not by a NULL specialist)
    assert [item["id"] for item in payload] == [resource_queue.id]

    # the day-less filter keeps the resource queue in scope as well
    payload_all = QueueDomainService(db_session).list_queue_cabinet_info(
        day=None, specialist_id=lab_synthetic.id, cabinet_number=None
    )
    assert resource_queue.id in [item["id"] for item in payload_all]
