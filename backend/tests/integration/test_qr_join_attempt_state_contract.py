"""Round-4 review pins (PR #3362) — join-session attempt-state contract.

Owner findings under review:
  - P2-1: a CONFIRMED pre-execution refusal (session not found / expired,
    nothing created) must surface a machine-readable reason — never the
    masked generic 400 «Internal server error» that dead-ended the
    patient's client;
  - P1-2 (server-side hardening): a retry after a LOST complete response
    re-uses the ORIGINAL attempt identity (the same session token). An
    already-joined session must REPLAY its saved ticket result
    (``replayed=true``) instead of refusing — and must never create a
    second business attempt.

The classes:
  - unknown token            -> 400 reason=join_session_not_found
  - pending but past TTL     -> 400 reason=join_session_expired
  - joined, single path      -> 200 replayed ticket, no new entry
  - joined, direction-scoped multi path -> 200 replayed ticket
  - joined, legacy clinic-wide multi    -> 400 reason=join_session_used
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.queue_profile import QueueProfile
from app.models.user import User
from app.services.queue_service import QueueBusinessService

COMPLETE_URL = "/api/v1/queue/join/complete"
START_URL = "/api/v1/queue/join/start"


def _clinic_day() -> date:
    """Join/start classifies the token day in the CLINIC timezone —
    stamp the fixtures with the clinic-local day (same contract as
    test_qr_queue_join.py)."""
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _local_now():
    return datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)


@pytest.mark.queue
def test_complete_unknown_session_refuses_with_machine_reason(
    client, db_session, monkeypatch
):
    """PIN B1 (round-4 P2-1): an unknown session token is a PROVEN
    pre-execution refusal — the response carries the machine reason, so
    the client can offer the explicit start-over instead of a dead-end."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    resp = client.post(
        COMPLETE_URL,
        json={
            "session_token": "no-such-join-session-token",
            "patient_name": "Test Patient",
            "phone": "+998900000111",
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, dict), detail
    assert detail["reason"] == "join_session_not_found"


@pytest.mark.queue
def test_complete_expired_session_refuses_with_machine_reason(
    client, db_session, test_doctor, monkeypatch
):
    """PIN B2 (round-4 P2-1): a session that expired BEFORE the business
    operation is a proven refusal (reason=join_session_expired) — the
    confirmed pre-execution 400 that used to dead-end the form."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "expired-session-token"
    local_now = _local_now()
    token = QueueToken(
        token=token_value,
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    start_resp = client.post(START_URL, json={"token": token_value})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    # Force-expire the pending session server-side (the client clock may
    # still believe the token is valid — the exact review scenario).
    from app.models.online_queue import QueueJoinSession

    session_row = (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .first()
    )
    assert session_row is not None
    session_row.expires_at = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=1)
    db_session.commit()

    resp = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Test Patient",
            "phone": "+998900000111",
        },
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, dict), detail
    assert detail["reason"] == "join_session_expired"
    # nothing was created
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
        == 0
    )


@pytest.mark.queue
def test_complete_retry_after_lost_response_replays_joined_ticket(
    client, db_session, test_doctor, monkeypatch
):
    """PIN B3 (round-4 P1-2): the retry after a lost complete response
    re-uses the ORIGINAL attempt identity — a joined session REPLAYS its
    saved ticket (replayed=true) and never creates a second entry."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "replay-single-token"
    token = QueueToken(
        token=token_value,
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=_local_now() + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    start_resp = client.post(START_URL, json={"token": token_value})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    body = {
        "session_token": session_token,
        "patient_name": "Replay Patient",
        "phone": "+998900000222",
    }
    first = client.post(COMPLETE_URL, json=body)
    assert first.status_code == 200
    assert first.json()["replayed"] is False
    first_number = first.json()["queue_number"]

    # The SAME session token, the same body — the lost-response retry.
    second = client.post(COMPLETE_URL, json=body)
    assert second.status_code == 200, second.json()
    payload = second.json()
    assert payload["replayed"] is True
    assert payload["queue_number"] == first_number
    assert payload["success"] is True

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1


def _make_direction_surface(db_session, suffix: str) -> dict:
    """A direction-scoped surface: visible QueueProfile + eligible doctor
    (own User row with the canonical Doctor role) + clinic-wide token
    carrying the reserved ``qdir:`` department prefix."""
    username = f"dir_replay_{suffix}"
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name="Direction Replay Doctor",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    doctor = Doctor(user_id=user.id, specialty="Кардиология", active=True)
    db_session.add(doctor)

    profile_key = f"cardio-key-{suffix}"
    profile = QueueProfile(
        key=profile_key,
        title="Кардиология (replay pin)",
        title_ru="Кардиология (replay pin)",
        queue_tags=["Кардиология"],
        department_key=profile_key,
        display_order=90,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    db_session.refresh(doctor)

    token_value = f"dir-replay-token-{suffix}"
    token = QueueToken(
        token=token_value,
        day=_clinic_day(),
        is_clinic_wide=True,
        department=f"qdir:{profile_key}",
        expires_at=_local_now() + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()
    return {"token": token_value, "profile_id": profile.id}


@pytest.mark.queue
def test_direction_session_retry_replays_saved_ticket(
    client, db_session, monkeypatch
):
    """PIN B4 (round-4 P1-2): the /q/<code> direction flow completes via
    the multi surface (one profile). After a lost response the retry with
    the SAME session token replays the saved ticket — the review's
    regression «повтор использует исходную attempt identity»."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    surface = _make_direction_surface(db_session, "a")

    start_resp = client.post(START_URL, json={"token": surface["token"]})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    body = {
        "session_token": session_token,
        "patient_name": "Direction Replay Patient",
        "phone": "+998900000333",
        "specialist_ids": [surface["profile_id"]],
        "specialist_entity_types": ["profile"],
    }
    first = client.post(COMPLETE_URL, json=body)
    assert first.status_code == 200, first.json()
    first_payload = first.json()
    assert first_payload["success"] is True
    assert first_payload["replayed"] is False
    first_number = first_payload["entries"][0]["queue_number"]

    retry = client.post(COMPLETE_URL, json=body)
    assert retry.status_code == 200, retry.json()
    retry_payload = retry.json()
    assert retry_payload["replayed"] is True
    assert retry_payload["success"] is True
    assert retry_payload["entries"][0]["queue_number"] == first_number

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_name == "Direction Replay Patient")
        .all()
    )
    assert len(entries) == 1


@pytest.mark.queue
def test_legacy_clinic_wide_joined_retry_refuses_with_used_reason(
    client, db_session, monkeypatch
):
    """PIN B5 (round-4 P1-2): a legacy clinic-wide multi join of N>1
    specialists is not exactly reconstructible from the session row — the
    retry refuses with the honest reason join_session_used (the consumed-
    advisory path), never a silent second attempt."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    from app.services.qr_queue import QRQueueService

    user = User(
        username="used_reason_doctor",
        email="used_reason@test.com",
        full_name="Used Reason Doctor",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    doctor = Doctor(user_id=user.id, specialty="Кардиология", active=True)
    db_session.add(doctor)
    profile = QueueProfile(
        key="used-reason-key",
        title="Used reason profile",
        title_ru="Used reason profile",
        queue_tags=["Кардиология"],
        department_key="used-reason-key",
        display_order=90,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    token_value = "used-reason-token"
    token = QueueToken(
        token=token_value,
        day=_clinic_day(),
        is_clinic_wide=True,
        department="used-reason-dept",
        expires_at=_local_now() + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(profile)

    service = QRQueueService(db_session)
    start = service.start_join_session(token_value)
    session_token = start["session_token"]

    body = {
        "session_token": session_token,
        "patient_name": "Used Reason Patient",
        "phone": "+998900000444",
        "specialist_ids": [profile.id],
        "specialist_entity_types": ["profile"],
    }
    first = client.post(COMPLETE_URL, json=body)
    assert first.status_code == 200, first.json()

    retry = client.post(COMPLETE_URL, json=body)
    assert retry.status_code == 400
    detail = retry.json()["detail"]
    assert isinstance(detail, dict), detail
    assert detail["reason"] == "join_session_used"
