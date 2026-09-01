"""D-2 QR least-loaded routing (NEEDS DECISION resolved 2026-08-31).

ADR-001 keeps queues PER DOCTOR; with several active doctors of one
specialty four spots historically assumed a single doctor:

- clinic-wide QR join picked ``.first()`` — now the new patient goes to
  the doctor with the shortest ACTIVE queue (waiting+called) for the
  day, ties to the lowest Doctor.id;
- display-board quick-call — same selection;
- registrar today-queues buckets exposed a single arbitrary doctor —
  now the payload carries a per-doctor ``specialists`` list (legacy
  single-doctor fields kept);
- admin queue-limits view compared summed usage against a single
  max_per_day — now the aggregate cap (max x N doctors) is exposed
  (``aggregate_max_per_day``); enforcement stays per doctor.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.queue_profile import QueueProfile
from app.models.user import User
from app.services.queue_svc import QueueBusinessService


# ===================== helpers =====================

# One argon2 hash for every helper user (hashing per doctor would add
# ~0.1s x N to the suite).
_D2_HASHED_PASSWORD = get_password_hash("d2load123")


def _make_doctor(db_session, specialty: str) -> Doctor:
    """A clinic-eligible doctor: active, linked to an ACTIVE Doctor-role
    owner (the owner-eligibility contract the clinic-wide join applies —
    Codex round-3 P2)."""
    user = User(
        username=f"d2_load_user_{db_session.query(User).count() + 1}",
        email=f"d2_load_user_{db_session.query(User).count() + 1}@test.com",
        hashed_password=_D2_HASHED_PASSWORD,
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.flush()
    return doctor


def _make_loaded_queue(
    db_session, doctor: Doctor, day, *, waiting: int = 0, served: int = 0,
    called: int = 0,
) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=doctor.id,
        queue_tag="stomatology",
        active=True,
    )
    db_session.add(queue)
    db_session.flush()
    number = 1
    for _ in range(waiting):
        db_session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name=f"Waiting {number}",
                status="waiting",
                source="desk",
            )
        )
        number += 1
    for _ in range(served):
        db_session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name=f"Served {number}",
                status="served",
                source="desk",
            )
        )
        number += 1
    for _ in range(called):
        db_session.add(
            OnlineQueueEntry(
                queue_id=queue.id,
                number=number,
                patient_name=f"Called {number}",
                status="called",
                source="desk",
            )
        )
        number += 1
    db_session.flush()
    return queue


def _make_clinic_wide_token(db_session, day, *, expires_at=None) -> QueueToken:
    # Tashkent local naive time — the queue machinery's _now() basis
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"d2-least-loaded-{db_session.query(QueueToken).count() + 1}",
        day=day,
        specialist_id=None,
        department=None,
        is_clinic_wide=True,
        expires_at=expires_at or (local_now + timedelta(hours=2)),
        active=True,
    )
    db_session.add(token)
    db_session.flush()
    return token


def _freeze_online_window(monkeypatch):
    """Freeze the queue machinery's clock INSIDE the online window
    (Tashkent-local 08:00 today) so the e2e joins do not depend on the
    wall-clock 07:00 window (pre-existing flake: the specialty-wide join
    raises "Онлайн-запись откроется в 07:00" when the suite runs before
    07:00 local). Returns (fixed_now, day)."""
    from app.services.queue_svc import _operations

    fixed_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(
        tzinfo=None, hour=8, minute=0, second=0, microsecond=0
    )

    def _fake_now(*args, **kwargs):
        tz = args[0] if args else kwargs.get("tz")
        return fixed_now.replace(tzinfo=tz) if tz else fixed_now

    monkeypatch.setattr(_operations, "_now", _fake_now)
    return fixed_now, fixed_now.date()


# ===================== A. least-loaded picker unit =====================


@pytest.mark.queue
def test_pick_least_loaded_prefers_fresh_doctor(db_session) -> None:
    """A doctor without a queue today beats loaded ones; ties break to
    the lowest id; served entries do not count as load."""
    today = date.today()
    loaded = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")
    tie_low = _make_doctor(db_session, "dentistry")
    tie_high = _make_doctor(db_session, "dentistry")

    _make_loaded_queue(db_session, loaded, today, waiting=3, served=10)
    # tie_low/tie_high get equal ACTIVE load; tie_low has the lower id
    _make_loaded_queue(db_session, tie_low, today, waiting=1)
    _make_loaded_queue(db_session, tie_high, today, waiting=1)

    doctors = [loaded, fresh, tie_high, tie_low]
    picked = QueueBusinessService._pick_least_loaded_doctor(db_session, doctors, today)
    assert picked.id == fresh.id

    # tie: equal load -> lowest id (tie_low.id < tie_high.id)
    picked = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [tie_high, tie_low], today
    )
    assert picked.id == tie_low.id

    # single candidate short-circuit
    assert QueueBusinessService._pick_least_loaded_doctor(
        db_session, [loaded], today
    ).id == loaded.id

    assert QueueBusinessService._pick_least_loaded_doctor(db_session, [], today) is None


# ===================== B. clinic-wide QR join routing =====================


@pytest.mark.queue
def test_clinic_wide_join_routes_to_least_loaded(db_session, monkeypatch) -> None:
    """Two stomatology-profile doctors: the doctor already carrying today's
    ACTIVE queue does not take the new QR patient."""
    fixed_now, day = _freeze_online_window(monkeypatch)
    loaded = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")

    profile = QueueProfile(
        key="stomatology",
        title="Dental",
        title_ru="Стоматология",
        queue_tags=["dental", "stomatology", "dentist", "dentistry"],
        department_key="stomatology",
        display_order=4,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    db_session.flush()

    _make_loaded_queue(db_session, loaded, day, waiting=2)

    token = _make_clinic_wide_token(
        db_session, day, expires_at=fixed_now + timedelta(hours=2)
    )
    db_session.commit()

    svc = QueueBusinessService()
    result = svc.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="D-2 Patient",
        phone="+998900000222",
        specialist_id_override=profile.id,
    )
    assert result["entry"] is not None

    routed_queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == day)
        .filter(DailyQueue.specialist_id.in_([loaded.id, fresh.id]))
        .all()
    )
    by_doctor = {q.specialist_id: q for q in routed_queue}
    # the fresh doctor got the new entry (new queue created for him)
    assert fresh.id in by_doctor
    assert by_doctor[fresh.id].id != by_doctor[loaded.id].id


# ===================== C. display quick-call =====================


def test_display_quick_call_picks_least_loaded(db_session) -> None:
    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    today = date.today()
    loaded2 = _make_doctor(db_session, "dentistry")
    loaded3 = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, loaded3, today, waiting=3)
    _make_loaded_queue(db_session, loaded2, today, waiting=2)

    picked = DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
        "stomatology"
    )
    # Round-2 P1 semantics: quick-call must CALL someone — the pick runs
    # over candidates whose queue holds waiting entries (least waiting
    # first); a queue-less doctor (load 0) never wins the pick while a
    # sibling has waiting patients.
    assert picked.id == loaded2.id


# ===================== D. today-queues per-doctor payload ===========


def test_today_queues_payload_exposes_specialists_list(db_session) -> None:
    """A specialty bucket containing entries of TWO doctors exposes both in
    the per-doctor `specialists` list (legacy single slot kept)."""
    from app.api.v1.endpoints.registrar_integration._queue_ops import (
        _build_queue_payload,
        _ensure_specialty_queue,
        _register_bucket_doctor,
    )

    doctor_a = _make_doctor(db_session, "dentistry")
    doctor_b = _make_doctor(db_session, "dentistry")

    queues_by_specialty: dict = {}
    _ensure_specialty_queue(queues_by_specialty, "stomatology", doctor_a.id)
    bucket = queues_by_specialty["stomatology"]
    bucket["doctor"] = doctor_a
    bucket["doctor_id"] = doctor_a.id
    _register_bucket_doctor(bucket, doctor_a)
    _register_bucket_doctor(bucket, doctor_b)
    _register_bucket_doctor(bucket, None)  # no-op safety

    payload = _build_queue_payload(
        queue_data=bucket,
        specialty="stomatology",
        queue_number=1,
        entries=[],
    )
    ids = [s["id"] for s in payload["specialists"]]
    assert ids == sorted([doctor_a.id, doctor_b.id])
    names = {s["name"] for s in payload["specialists"]}
    # doctors created via _make_doctor own active Doctor-role users, so
    # the payload carries the owner's username (full_name is None)
    assert f"d2_load_user_{doctor_a.id}" in names
    assert f"d2_load_user_{doctor_b.id}" in names
    # legacy fields preserved
    assert payload["specialist_id"] == doctor_a.id


# ===================== E. limits aggregate view =====================


def test_queue_limits_aggregate_max_for_multi_doctor_specialty(db_session) -> None:
    """D-2 display-fix: the admin limits view exposes the specialty
    aggregate cap (max_per_day x doctors) while enforcement stays per
    doctor."""
    from app.services.queue_limits_api_service import QueueLimitsApiService

    class _Repo:
        def __init__(self, doctors):
            self._doctors = doctors

        def list_active_doctors(self, *, specialty: str | None):
            return self._doctors

        def list_active_daily_queues(self, *, day, specialist_id):
            return []

    d1 = _make_doctor(db_session, "dentistry")
    d2 = _make_doctor(db_session, "dentistry")

    service = QueueLimitsApiService(
        db_session,
        repository=_Repo([d1, d2]),
        get_settings=lambda _db: {"max_per_day": {"dentistry": 15}, "start_numbers": {}},
    )
    rows = service.get_queue_limits(specialty="dentistry")

    assert len(rows) == 1
    row = rows[0]
    assert row["doctors_count"] == 2
    assert row["max_per_day"] == 15  # per-doctor value unchanged
    assert row["aggregate_max_per_day"] == 30  # display aggregate


# ===================== F. Codex round-1 regressions =====================


@pytest.mark.queue
def test_pick_least_loaded_skips_limit_reached_doctor(db_session) -> None:
    """Codex round-1 P1: a doctor whose (day, tag) queue already reached
    the online cap is NOT routed to — the bookable sibling takes the join
    instead of the whole specialty-wide request failing the limit check."""
    today = date.today()
    full = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, full, today, waiting=15)  # >= DEFAULT_MAX_SLOTS

    picked = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [full, fresh], today, queue_tag="stomatology"
    )
    assert picked.id == fresh.id


@pytest.mark.queue
def test_pick_least_loaded_skips_opened_reception_doctor(
    db_session, monkeypatch
) -> None:
    """Codex round-1 P1: a same-day queue whose reception already opened
    (opened_at set) is unbookable — routing goes to the bookable sibling
    even when the opened doctor has the lower id/zero load."""
    from app.services.queue_svc import _operations

    # Fixed "now": Tashkent-local 08:00 today — inside the online window
    # (>= 07:00), so the day-level check passes and the per-queue
    # opened_at rule is what decides bookability.
    fixed_now, today = _freeze_online_window(monkeypatch)

    opened = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")
    queue = _make_loaded_queue(db_session, opened, today, waiting=1)
    queue.opened_at = fixed_now
    db_session.flush()

    picked = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [opened, fresh], today, queue_tag="stomatology"
    )
    assert picked.id == fresh.id

    # Fallback preserved: when NO candidate is bookable, the legacy
    # least-loaded pick stands (lowest id) so the precise downstream
    # error still surfaces.
    opened2 = _make_doctor(db_session, "dentistry")
    queue2 = _make_loaded_queue(db_session, opened2, today, waiting=0)
    queue2.opened_at = fixed_now
    db_session.flush()
    picked = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [opened, opened2], today, queue_tag="stomatology"
    )
    # least-loaded fallback: zero-load opened2 wins (load before id)
    assert picked.id == opened2.id


@pytest.mark.queue
def test_clinic_wide_join_routes_around_limit_reached_doctor(
    db_session, monkeypatch
) -> None:
    """Codex round-1 P1 (end-to-end): the specialty-wide QR join succeeds
    on the bookable doctor even though the least-loaded-by-id candidate's
    queue already hit the cap."""
    fixed_now, today = _freeze_online_window(monkeypatch)
    full = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")

    profile = (
        db_session.query(QueueProfile).filter(QueueProfile.key == "stomatology").first()
    )
    if not profile:
        profile = QueueProfile(
            key="stomatology",
            title="Dental",
            title_ru="Стоматология",
            queue_tags=["dental", "stomatology", "dentist", "dentistry"],
            department_key="stomatology",
            display_order=4,
            is_active=True,
            show_on_qr_page=True,
        )
        db_session.add(profile)
        db_session.flush()

    _make_loaded_queue(db_session, full, today, waiting=15)
    token = _make_clinic_wide_token(
        db_session, today, expires_at=fixed_now + timedelta(hours=2)
    )
    db_session.commit()

    svc = QueueBusinessService()
    result = svc.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="D-2 Bookable Patient",
        phone="+998900000333",
        specialist_id_override=profile.id,
    )
    assert result["entry"] is not None

    routed = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == today)
        .filter(DailyQueue.specialist_id.in_([full.id, fresh.id]))
        .all()
    )
    by_doctor = {q.specialist_id: q for q in routed}
    assert fresh.id in by_doctor  # new queue created for the bookable doctor
    assert result["entry"].queue_id == by_doctor[fresh.id].id


def test_display_quick_call_prefers_doctor_with_waiting_entries(db_session) -> None:
    """Codex round-1 P1: quick-call routes to the doctor whose queue REALLY
    holds waiting entries — a queue-less/empty sibling with load 0 must not
    win the least-loaded pick and answer 404/queue_empty."""
    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    today = date.today()
    loaded = _make_doctor(db_session, "dentistry")
    empty = _make_doctor(db_session, "dentistry")
    noqueue = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, loaded, today, waiting=3)
    _make_loaded_queue(db_session, empty, today, waiting=0)

    picked = DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
        "stomatology"
    )
    assert picked.id == loaded.id


def test_queue_limits_response_model_exposes_aggregate(db_session) -> None:
    """Codex round-1 P2: QueueLimitResponse declares aggregate_max_per_day,
    so the key the service builds reaches the HTTP response and the
    OpenAPI contract instead of being silently dropped by Pydantic."""
    from app.api.v1.endpoints.queue_limits import QueueLimitResponse
    from app.services.queue_limits_api_service import QueueLimitsApiService

    class _Repo:
        def __init__(self, doctors):
            self._doctors = doctors

        def list_active_doctors(self, *, specialty: str | None):
            return self._doctors

        def list_active_daily_queues(self, *, day, specialist_id):
            return []

    d1 = _make_doctor(db_session, "dentistry")
    d2 = _make_doctor(db_session, "dentistry")

    service = QueueLimitsApiService(
        db_session,
        repository=_Repo([d1, d2]),
        get_settings=lambda _db: {"max_per_day": {"dentistry": 15}, "start_numbers": {}},
    )
    rows = service.get_queue_limits(specialty="dentistry")

    model = QueueLimitResponse(**rows[0])
    assert model.aggregate_max_per_day == 30


def test_today_queues_ecg_buckets_register_visit_doctor(db_session) -> None:
    """Codex round-1 P2: ECG-only and split (ECG + cardiology) visits hit
    the branch `continue`s — the visit's doctor must be registered in the
    echokg/cardiology buckets BEFORE the continue so the payload's
    "specialists" list is not empty while the queue holds that visit."""
    from app.api.v1.endpoints.registrar_integration._today_queues import (
        _process_visits_for_queues,
    )
    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.visit import Visit, VisitService

    doctor = _make_doctor(db_session, "cardiology")
    patient = Patient(
        first_name="ECG",
        last_name="Раунд-1",
        phone="+998901230399",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
    )
    db_session.add(visit)
    db_session.flush()
    ecg_service = Service(name="ЭКГ", queue_tag="ecg", active=True)
    db_session.add(ecg_service)
    db_session.flush()
    db_session.add(
        VisitService(visit_id=visit.id, service_id=ecg_service.id, name=ecg_service.name)
    )
    db_session.flush()

    queues_by_specialty: dict = {}
    _process_visits_for_queues(
        db_session, [visit], date.today(), queues_by_specialty, set()
    )
    db_session.flush()

    # ECG-only visit -> echokg bucket carries the doctor in "doctors"
    assert "echokg" in queues_by_specialty
    assert doctor.id in queues_by_specialty["echokg"]["doctors"]


# ===================== G. Codex round-2 regressions =====================


@pytest.mark.queue
def test_pick_least_loaded_ignores_inactive_queue_load(db_session) -> None:
    """Codex round-2 P2: historical same-day entries in an INACTIVE queue
    (a row the join would never use — get_or_create_daily_queue filters
    active) must not inflate a doctor's routing load, otherwise the QR
    join routes to a more heavily loaded sibling."""
    today = date.today()
    stale = _make_doctor(db_session, "dentistry")
    honest = _make_doctor(db_session, "dentistry")

    _make_loaded_queue(db_session, stale, today, waiting=4)  # real load
    stale_inactive = _make_loaded_queue(db_session, stale, today, waiting=5)
    stale_inactive.active = False
    db_session.flush()
    _make_loaded_queue(db_session, honest, today, waiting=5)

    picked = QueueBusinessService._pick_least_loaded_doctor(db_session, [stale, honest], today)
    # correct: 4 < 5 -> stale wins. Buggy (inactive counted): 9 > 5 -> honest.
    assert picked.id == stale.id


@pytest.mark.queue
def test_unbookable_honors_persisted_online_cap(db_session, monkeypatch) -> None:
    """Codex round-2 P2: DailyQueue persists the online cap as
    ``max_online_entries`` (never ``max_slots``) — the picker must treat a
    queue that reached ITS OWN cap as unbookable while a below-cap queue
    stays eligible regardless of the 15 default."""
    from app.services.queue_svc._operations import _unbookable_doctor_ids

    # inside the online window (pre-07:00 runs would mark EVERY doctor
    # unbookable at the day level and mask the per-queue cap assertions)
    _freeze_online_window(monkeypatch)
    today = date.today()

    # cap=2, 2 waiting -> unbookable (buggy code: 2 < 15 -> bookable)
    small = _make_doctor(db_session, "dentistry")
    q_small = _make_loaded_queue(db_session, small, today, waiting=2)
    q_small.max_online_entries = 2
    db_session.flush()
    assert _unbookable_doctor_ids(
        db_session, [small], today, queue_tag="stomatology"
    ) == {small.id}

    # cap=30, 15 waiting -> still bookable (buggy code: 15 >= 15 -> not)
    large = _make_doctor(db_session, "dentistry")
    q_large = _make_loaded_queue(db_session, large, today, waiting=15)
    q_large.max_online_entries = 30
    db_session.flush()
    assert (
        _unbookable_doctor_ids(db_session, [large], today, queue_tag="stomatology")
        == set()
    )

    # routing follows the configured caps: the capped-out doctor is skipped
    fresh = _make_doctor(db_session, "dentistry")
    picked = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [small, fresh], today, queue_tag="stomatology"
    )
    assert picked.id == fresh.id


@pytest.mark.queue
def test_check_queue_limits_honors_persisted_cap(db_session) -> None:
    """Codex round-2 P2 (enforcement side): check_queue_limits carried the
    same phantom ``max_slots`` attribute, so the admin-configured
    ``max_online_entries`` cap was never honored — a capacity-30 queue
    rejected at 15 while a capacity-2 queue accepted up to 15."""
    today = date.today()

    # capacity 30: 15 waiting still accepted (buggy: rejected with 15)
    large = _make_doctor(db_session, "dentistry")
    q_large = _make_loaded_queue(db_session, large, today, waiting=15)
    q_large.max_online_entries = 30
    db_session.flush()
    allowed, message = QueueBusinessService.check_queue_limits(db_session, q_large)
    assert allowed, message

    # capacity 2: rejected at 2 (buggy: accepted up to 15), message names 2
    small = _make_doctor(db_session, "dentistry")
    q_small = _make_loaded_queue(db_session, small, today, waiting=2)
    q_small.max_online_entries = 2
    db_session.flush()
    allowed, message = QueueBusinessService.check_queue_limits(db_session, q_small)
    assert not allowed
    assert "2" in message


@pytest.mark.queue
def test_display_quick_call_ignores_inactive_queues(db_session) -> None:
    """Codex round-2 P1: a same-day INACTIVE queue must be invisible to
    quick-call — neither the candidate selection (waiting counts) nor the
    queue lookup may touch it."""
    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    today = date.today()
    repo = DisplayWebSocketApiRepository(db_session)

    # lower-id doctor holds ONLY an inactive queue with waiting entries:
    # buggy code counted it (waiting=1 < 3) and picked him, calling a
    # patient out of the inactive queue.
    stale = _make_doctor(db_session, "dentistry")
    stale_q = _make_loaded_queue(db_session, stale, today, waiting=1)
    stale_q.active = False
    db_session.flush()
    live = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, live, today, waiting=3)

    picked = repo.get_active_doctor_by_specialty("stomatology")
    assert picked.id == live.id

    # the lookup agrees: only an inactive row -> None; both rows -> active
    assert repo.get_daily_queue_for_specialist(day=today, specialist_id=stale.id) is None
    active_q = _make_loaded_queue(db_session, stale, today, waiting=0)
    found = repo.get_daily_queue_for_specialist(day=today, specialist_id=stale.id)
    assert found is not None and found.id == active_q.id


# ===================== H. Codex round-3 regressions =====================


@pytest.mark.queue
def test_pick_least_loaded_scopes_load_to_joined_tag(db_session) -> None:
    """Codex round-3 P2: the join targets the (day, doctor, TAG) row —
    a doctor's entries under OTHER tags (a legacy 'dentistry' queue) must
    not make their empty target-tag queue look loaded."""
    today = date.today()
    multi_tag = _make_doctor(db_session, "dentistry")
    honest = _make_doctor(db_session, "dentistry")

    # multi_tag: empty target-tag queue, but a loaded LEGACY-tag queue
    _make_loaded_queue(db_session, multi_tag, today, waiting=0)
    legacy = _make_loaded_queue(db_session, multi_tag, today, waiting=5)
    legacy.queue_tag = "dentistry"
    db_session.flush()
    # honest: 1 waiting in the target tag
    _make_loaded_queue(db_session, honest, today, waiting=1)

    picked = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [multi_tag, honest], today, queue_tag="stomatology"
    )
    # correct: target-tag load 0 < 1 -> multi_tag wins.
    # Buggy (unscoped load): 5 > 1 -> honest wins.
    assert picked.id == multi_tag.id

    # without a tag (legacy callers) the cross-tag load still counts
    picked_untagged = QueueBusinessService._pick_least_loaded_doctor(
        db_session, [multi_tag, honest], today
    )
    assert picked_untagged.id == honest.id


@pytest.mark.queue
def test_clinic_wide_join_skips_owner_ineligible_ghosts(
    db_session, monkeypatch
) -> None:
    """Codex round-3 P2: the least-load ranking must not elect a legacy
    ghost — an active Doctor whose owner is deactivated — over healthy
    doctors (load 0 + lowest id would always win). The join applies the
    same owner-eligibility contract as the appointment writers."""
    fixed_now, today = _freeze_online_window(monkeypatch)

    # healthy doctor with a HIGHER id (created after the ghost)
    ghost_owner = User(
        username="d2_ghost_owner",
        email="d2_ghost_owner@test.com",
        hashed_password=_D2_HASHED_PASSWORD,
        role="Doctor",
        is_active=False,  # deactivated owner -> ghost
        is_superuser=False,
    )
    db_session.add(ghost_owner)
    db_session.flush()
    ghost = Doctor(user_id=ghost_owner.id, specialty="dentistry", active=True)
    db_session.add(ghost)
    db_session.flush()
    healthy = _make_doctor(db_session, "dentistry")
    assert healthy.id > ghost.id

    profile = QueueProfile(
        key="stomatology",
        title="Dental",
        title_ru="Стоматология",
        queue_tags=["dental", "stomatology", "dentist", "dentistry"],
        department_key="stomatology",
        display_order=4,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    token = _make_clinic_wide_token(
        db_session, today, expires_at=fixed_now + timedelta(hours=2)
    )
    db_session.commit()

    svc = QueueBusinessService()
    result = svc.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="D-2 Ghost Patient",
        phone="+998900000444",
        specialist_id_override=profile.id,
    )
    assert result["entry"] is not None
    routed = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == today)
        .filter(DailyQueue.specialist_id.in_([ghost.id, healthy.id]))
        .all()
    )
    by_doctor = {q.specialist_id: q for q in routed}
    assert healthy.id in by_doctor
    assert result["entry"].queue_id == by_doctor[healthy.id].id


@pytest.mark.queue
def test_queue_limits_aggregate_sums_per_doctor_caps(db_session) -> None:
    """Codex round-3 P2: the admin aggregate must sum the caps actually
    enforced — today's per-queue override (max_online_entries) or the
    doctor's own default (max_online_per_day) — not max_per_day x N."""
    from app.services.queue_limits_api_service import QueueLimitsApiService

    class _Repo:
        def __init__(self, doctors, queues):
            self._doctors = doctors
            self._queues = queues  # doctor_id -> list[DailyQueue]

        def list_active_doctors(self, *, specialty: str | None):
            return self._doctors

        def list_active_daily_queues(self, *, day, specialist_id):
            return self._queues.get(specialist_id, [])

        def count_entries(self, *, queue_id):
            return 0

    d1 = _make_doctor(db_session, "dentistry")
    d2 = _make_doctor(db_session, "dentistry")
    today = date.today()
    q1 = DailyQueue(
        day=today, specialist_id=d1.id, queue_tag="dentistry",
        active=True, max_online_entries=10,
    )
    q2 = DailyQueue(
        day=today, specialist_id=d2.id, queue_tag="dentistry",
        active=True, max_online_entries=30,
    )
    db_session.add_all([q1, q2])
    db_session.flush()

    d3 = _make_doctor(db_session, "derma")  # no queue: default 15

    service = QueueLimitsApiService(
        db_session,
        repository=_Repo([d1, d2, d3], {d1.id: [q1], d2.id: [q2], d3.id: []}),
        get_settings=lambda _db: {"max_per_day": {"dentistry": 15}, "start_numbers": {}},
    )
    rows = service.get_queue_limits(specialty="dentistry")
    by_spec = {r["specialty"]: r for r in rows}
    # enforced caps: 10 (override) + 30 (override) = 40, NOT 15 x 2 = 30
    assert by_spec["dentistry"]["aggregate_max_per_day"] == 40
    assert by_spec["derma"]["aggregate_max_per_day"] == d3.max_online_per_day


# ===================== I. Codex round-4 regressions =====================


@pytest.mark.queue
def test_clinic_wide_join_retry_returns_original_entry(
    db_session, monkeypatch
) -> None:
    """Codex round-4 P1: duplicates must be resolved BEFORE least-load
    routing — the first join raises the picked doctor's load, so a retry
    used to route to the sibling and create a SECOND entry for the same
    patient under another doctor (per-queue check_uniqueness saw a fresh
    queue)."""
    fixed_now, today = _freeze_online_window(monkeypatch)
    first = _make_doctor(db_session, "dentistry")
    second = _make_doctor(db_session, "dentistry")

    profile = QueueProfile(
        key="stomatology",
        title="Dental",
        title_ru="Стоматология",
        queue_tags=["dental", "stomatology", "dentist", "dentistry"],
        department_key="stomatology",
        display_order=4,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    token = _make_clinic_wide_token(
        db_session, today, expires_at=fixed_now + timedelta(hours=2)
    )
    db_session.commit()

    svc = QueueBusinessService()
    phone = "+998900000555"
    first_result = svc.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="D-2 Retry Patient",
        phone=phone,
        specialist_id_override=profile.id,
    )
    assert first_result["entry"] is not None
    assert first_result["duplicate"] is False

    # retry: least-load would now pick the OTHER doctor (the first doctor
    # carries 1 waiting entry)
    retry_result = svc.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="D-2 Retry Patient",
        phone=phone,
        specialist_id_override=profile.id,
    )
    assert retry_result["duplicate"] is True
    assert retry_result["entry"].id == first_result["entry"].id
    assert retry_result["entry"].queue_id == first_result["entry"].queue_id

    # exactly ONE entry for the patient across all of today's queues
    total = (
        db_session.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(DailyQueue.day == today, OnlineQueueEntry.phone == phone)
        .count()
    )
    assert total == 1


@pytest.mark.queue
def test_display_lookup_resolves_waiting_queue(db_session) -> None:
    """Codex round-4 P1: the quick-call lookup must agree with the
    selection half when a doctor holds several ACTIVE queues under
    different tags — the queue holding waiting entries wins (here the
    waiting queue even has the HIGHER id, the arbitrary-.first() case)."""
    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    today = date.today()
    doctor = _make_doctor(db_session, "dentistry")
    empty = _make_loaded_queue(db_session, doctor, today, waiting=0)
    loaded = _make_loaded_queue(db_session, doctor, today, waiting=2)
    loaded.queue_tag = "dentistry"  # different tag, same doctor/day
    db_session.flush()
    assert empty.id < loaded.id  # the empty row would win a bare .first()

    found = DisplayWebSocketApiRepository(db_session).get_daily_queue_for_specialist(
        day=today, specialist_id=doctor.id
    )
    assert found.id == loaded.id


@pytest.mark.queue
def test_queue_limits_repo_prefers_active_queue(db_session) -> None:
    """Codex round-4 P2: the limits repository resolves the doctor's
    ACTIVE queue (deterministically) — an inactive historical row must not
    feed usage counts or the aggregate capacity."""
    from app.repositories.queue_limits_repository import QueueLimitsRepository

    today = date.today()
    doctor = _make_doctor(db_session, "dentistry")
    stale = DailyQueue(
        day=today, specialist_id=doctor.id, queue_tag="dentistry",
        active=False, max_online_entries=30,
    )
    live = DailyQueue(
        day=today, specialist_id=doctor.id, queue_tag="dentistry",
        active=True, max_online_entries=10,
    )
    db_session.add_all([stale, live])
    db_session.flush()

    repo = QueueLimitsRepository(db_session)
    found = repo.get_daily_queue(day=today, specialist_id=doctor.id)
    assert found.id == live.id
    assert found.max_online_entries == 10


# ===================== J. Codex round-5 regressions =====================


@pytest.mark.queue
def test_display_quick_call_skips_owner_ineligible_ghosts(db_session) -> None:
    """Codex round-5 P2: the quick-call candidate query applies the same
    owner-eligibility contract as the join — an active ghost (deactivated
    owner) with a shorter waiting queue must not win the pick."""
    ghost_owner = User(
        username="d2_qc_ghost_owner",
        email="d2_qc_ghost_owner@test.com",
        hashed_password=_D2_HASHED_PASSWORD,
        role="Doctor",
        is_active=False,
        is_superuser=False,
    )
    db_session.add(ghost_owner)
    db_session.flush()
    ghost = Doctor(user_id=ghost_owner.id, specialty="dentistry", active=True)
    db_session.add(ghost)
    db_session.flush()
    ghost_queue = _make_loaded_queue(db_session, ghost, date.today(), waiting=1)

    healthy = _make_doctor(db_session, "dentistry")
    healthy_queue = _make_loaded_queue(db_session, healthy, date.today(), waiting=3)
    assert ghost.id < healthy.id  # the ghost would win waiting-count ties too

    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    picked = DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
        "stomatology"
    )
    assert picked.id == healthy.id


@pytest.mark.queue
def test_display_quick_call_ranks_waiting_candidates_by_active_load(db_session) -> None:
    """Codex round-5 P2: among doctors with waiting entries the ranking key
    is the documented D-2 load metric (waiting+called), not the waiting
    count — 1 waiting + 10 called must lose to 2 waiting + 0 called."""
    busy = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, busy, date.today(), waiting=1, called=10)
    _make_loaded_queue(db_session, fresh, date.today(), waiting=2)

    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    picked = DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
        "stomatology"
    )
    assert picked.id == fresh.id


@pytest.mark.queue
def test_queue_limits_aggregate_enumerates_all_tagged_queues(db_session) -> None:
    """Codex round-5 P2: a doctor holding several ACTIVE queues under
    different tags contributes EVERY enforced cap (and usage) to the
    aggregate — get_daily_queue's lowest-id row must not hide the rest."""
    from app.repositories.queue_limits_repository import QueueLimitsRepository

    today = date.today()
    doctor = _make_doctor(db_session, "dentistry")
    q_tag = DailyQueue(
        day=today, specialist_id=doctor.id, queue_tag="stomatology",
        active=True, max_online_entries=10,
    )
    q_legacy = DailyQueue(
        day=today, specialist_id=doctor.id, queue_tag="dentistry",
        active=True, max_online_entries=30,
    )
    db_session.add_all([q_tag, q_legacy])
    db_session.flush()

    repo = QueueLimitsRepository(db_session)
    queues = repo.list_active_daily_queues(day=today, specialist_id=doctor.id)
    assert sorted(q.id for q in queues) == sorted([q_tag.id, q_legacy.id])
    assert sum(q.max_online_entries for q in queues) == 40
