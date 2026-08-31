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

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.queue_profile import QueueProfile
from app.services.queue_svc import QueueBusinessService


# ===================== helpers =====================


def _make_doctor(db_session, specialty: str) -> Doctor:
    doctor = Doctor(specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.flush()
    return doctor


def _make_loaded_queue(
    db_session, doctor: Doctor, day, *, waiting: int = 0, served: int = 0
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
    db_session.flush()
    return queue


def _make_clinic_wide_token(db_session, day) -> QueueToken:
    # Tashkent local naive time — the queue machinery's _now() basis
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=f"d2-least-loaded-{db_session.query(QueueToken).count() + 1}",
        day=day,
        specialist_id=None,
        department=None,
        is_clinic_wide=True,
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.flush()
    return token


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
def test_clinic_wide_join_routes_to_least_loaded(db_session) -> None:
    """Two stomatology-profile doctors: the doctor already carrying today's
    ACTIVE queue does not take the new QR patient."""
    today = date.today()
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

    _make_loaded_queue(db_session, loaded, today, waiting=2)

    token = _make_clinic_wide_token(db_session, today)
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
        .filter(DailyQueue.day == today)
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
    loaded = _make_doctor(db_session, "dentistry")
    fresh = _make_doctor(db_session, "dentistry")
    _make_loaded_queue(db_session, loaded, today, waiting=2)

    picked = DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
        "stomatology"
    )
    assert picked.id == fresh.id


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
    assert f"Врач #{doctor_a.id}" in names and f"Врач #{doctor_b.id}" in names
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

        def get_daily_queue(self, *, day, specialist_id):
            return None

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
