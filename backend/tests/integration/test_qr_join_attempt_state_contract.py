"""Round-4/5 review pins (PR #3362) — join-session attempt-state contract.

Owner findings under review:
  - P2-1 (round-4): a CONFIRMED pre-execution refusal (session not found /
    expired, nothing created) must surface a machine-readable reason —
    never the masked generic 400 «Internal server error» that dead-ended
    the patient's client;
  - P1-2 (round-4 + round-5): a retry after a LOST complete response
    re-uses the ORIGINAL attempt identity (the same session token). An
    already-joined session REPLAYS its saved ticket result
    (``replayed=true``) and never creates a second business attempt — and
    (round-5) the талон and the joined outcome share ONE transaction
    boundary, so a crash mid-attempt commits nothing;
  - P1-3 (round-5): one session token = one immutable payload. The replay
    is served ONLY to the payload that created the attempt (normalized
    identity binding); a different payload is a 409
    ``join_session_payload_mismatch`` conflict;
  - P2-1 (round-5): the replay serves the EXACT original response (the
    saved snapshot) — the metrics never drift as other patients join.

The classes:
  - unknown token            -> 400 reason=join_session_not_found
  - pending but past TTL     -> 400 reason=join_session_expired
  - joined, same payload     -> 200 replayed snapshot (single + multi +
    legacy clinic-wide), original metrics verbatim
  - joined, foreign payload  -> 409 reason=join_session_payload_mismatch
  - crash after entry creation -> nothing committed, retry re-executes
  - post-commit stats failure  -> 200 success preserved
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
    """PIN B3 (round-4 P1-2 + round-5 P2-1): the retry after a lost complete
    response re-uses the ORIGINAL attempt identity — a joined session
    REPLAYS its saved ticket (replayed=true) and never creates a second
    entry. Round-5: the replayed metrics are the EXACT original numbers
    (the saved snapshot) — later joiners must not change the picture the
    patient originally received."""
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
    first_length = first.json()["queue_length"]

    # Other patients join AFTER the first attempt — the live queue picture
    # changes, the replayed one must not (round-5 P2-1).
    other_start = client.post(START_URL, json={"token": token_value})
    assert other_start.status_code == 200
    other = client.post(
        COMPLETE_URL,
        json={
            "session_token": other_start.json()["session_token"],
            "patient_name": "Later Patient",
            "phone": "+998900000299",
        },
    )
    assert other.status_code == 200, other.json()

    # The SAME session token, the same body — the lost-response retry.
    second = client.post(COMPLETE_URL, json=body)
    assert second.status_code == 200, second.json()
    payload = second.json()
    assert payload["replayed"] is True
    assert payload["queue_number"] == first_number
    # P2-1: the ORIGINAL queue_length, not a recount of the grown queue.
    assert payload["queue_length"] == first_length
    assert payload["success"] is True

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 2  # the later patient joined for real


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
def test_legacy_clinic_wide_joined_retry_replays_exact_snapshot(
    client, db_session, monkeypatch
):
    """PIN B5 (round-5 P1-3/P2-1): the response snapshot makes a legacy
    clinic-wide multi join exactly replayable — the same-body retry gets
    the ORIGINAL result verbatim, and a different-payload retry is refused
    with the machine reason join_session_payload_mismatch (409). Nothing
    is ever guessed from the session row again."""
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

    # Round-5: the same-payload retry replays the saved snapshot exactly —
    # no guessing, no second attempt.
    retry = client.post(COMPLETE_URL, json=body)
    assert retry.status_code == 200, retry.json()
    retry_payload = retry.json()
    assert retry_payload["replayed"] is True
    assert retry_payload["success"] is True
    assert (
        retry_payload["entries"][0]["queue_number"]
        == first.json()["entries"][0]["queue_number"]
    )
    assert (
        retry_payload["entries"][0]["queue_entry_id"]
        == first.json()["entries"][0]["queue_entry_id"]
    )

    # A different identity must NEVER re-use the attempt — 409 conflict.
    foreign = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Foreign Payload Patient",
            "phone": "+998900000444",
            "specialist_ids": [profile.id],
            "specialist_entity_types": ["profile"],
        },
    )
    assert foreign.status_code == 409, foreign.json()
    foreign_detail = foreign.json()["detail"]
    assert isinstance(foreign_detail, dict), foreign_detail
    assert foreign_detail["reason"] == "join_session_payload_mismatch"


@pytest.mark.queue
def test_replay_matches_despite_name_formatting(client, db_session, test_doctor, monkeypatch):
    """PIN B6 (round-5 P1-3): the payload binding is NORMALIZATION-aware —
    the same person re-typing their identity with different case/whitespace
    (or a reformatted phone) still replays the saved ticket; only a real
    change of person produces the mismatch."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "replay-normalize-token"
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

    first = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "  Replay   Normalize Patient ",
            "phone": "998900000555",
        },
    )
    assert first.status_code == 200, first.json()
    first_number = first.json()["queue_number"]

    # Same person, messier input: case + whitespace + a formatted phone
    # (the same 12 digits as 998900000555, only reformatted).
    second = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "replay normalize patient",
            "phone": "+998 (90) 000-05-55",
        },
    )
    assert second.status_code == 200, second.json()
    assert second.json()["replayed"] is True
    assert second.json()["queue_number"] == first_number

    # A genuinely different phone is a different person — refused.
    foreign = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "replay normalize patient",
            "phone": "+998900000556",
        },
    )
    assert foreign.status_code == 409
    assert foreign.json()["detail"]["reason"] == "join_session_payload_mismatch"


@pytest.mark.queue
def test_replay_refuses_changed_telegram(client, db_session, test_doctor, monkeypatch):
    """PIN B7 (round-5 P1-3): the telegram id is part of the immutable
    payload — a retry that omits/changes it never receives the ticket."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "replay-telegram-token"
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
        "patient_name": "Telegram Replay Patient",
        "phone": "+998900000666",
        "telegram_id": 424242,
    }
    first = client.post(COMPLETE_URL, json=body)
    assert first.status_code == 200, first.json()

    # Same identity INCLUDING the telegram id — replays.
    ok = client.post(COMPLETE_URL, json=body)
    assert ok.status_code == 200, ok.json()
    assert ok.json()["replayed"] is True

    # Telegram dropped — different payload, refused (409).
    dropped = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Telegram Replay Patient",
            "phone": "+998900000666",
        },
    )
    assert dropped.status_code == 409
    assert dropped.json()["detail"]["reason"] == "join_session_payload_mismatch"


@pytest.mark.queue
def test_replay_refuses_changed_specialist_type(client, db_session, monkeypatch):
    """PIN B8 (round-5 P1-3): the typed specialist selection is part of the
    immutable payload — the same numeric id under a different entity type
    is a DIFFERENT payload (Doctor.id and QueueProfile.id are different
    id spaces, RQ-09.b) and is refused."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    surface = _make_direction_surface(db_session, "typeflip")

    start_resp = client.post(START_URL, json={"token": surface["token"]})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    body = {
        "session_token": session_token,
        "patient_name": "Typed Replay Patient",
        "phone": "+998900000777",
        "specialist_ids": [surface["profile_id"]],
        "specialist_entity_types": ["profile"],
    }
    first = client.post(COMPLETE_URL, json=body)
    assert first.status_code == 200, first.json()

    flipped = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Typed Replay Patient",
            "phone": "+998900000777",
            "specialist_ids": [surface["profile_id"]],
            "specialist_entity_types": ["doctor"],
        },
    )
    assert flipped.status_code == 409, flipped.json()
    assert flipped.json()["detail"]["reason"] == "join_session_payload_mismatch"


@pytest.mark.queue
def test_complete_crash_after_entry_creation_commits_nothing(
    client, db_session, test_doctor, monkeypatch
):
    """PIN B9 (round-5 P1-2): the single transaction boundary. A failure
    AFTER the queue entry was created but BEFORE the joined outcome commit
    leaves NOTHING behind — no orphan талон, the session stays pending —
    and the same token cleanly re-executes afterwards."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "crash-boundary-token"
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
        "patient_name": "Crash Boundary Patient",
        "phone": "+998900000888",
    }

    from app.models.online_queue import QueueJoinSession

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated crash before the outcome commit")

    # Targeted patch (NOT monkeypatch.undo() — it would also drop the
    # ONLINE_QUEUE_START_TIME freeze the retry still needs).
    original_commit = db_session.commit
    db_session.commit = _boom
    try:
        client.post(COMPLETE_URL, json=body)
    except RuntimeError:
        pass  # the central handler may re-raise through the TestClient
    db_session.commit = original_commit

    # The failed attempt rolled back: no entry, no joining mid-state.
    db_session.rollback()
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
        == 0
    )
    session_row = (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .first()
    )
    assert session_row is not None
    assert session_row.status == "pending"

    # The retry executes cleanly — exactly one талон, session joined.
    retry = client.post(COMPLETE_URL, json=body)
    assert retry.status_code == 200, retry.json()
    assert retry.json()["replayed"] is False
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
        == 1
    )


@pytest.mark.queue
def test_post_commit_statistics_failure_keeps_success(
    client, db_session, test_doctor, monkeypatch
):
    """PIN B10 (round-5 P1-4): post-commit side effects are best-effort —
    a statistics failure after the durable join commit must NOT turn the
    successful attempt into a 500 the client would misclassify."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "post-commit-stats-token"
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

    from app.services.qr_queue import QRQueueService

    def _stats_boom(self, queue_id, stat_field):
        raise RuntimeError("statistics backend down")

    monkeypatch.setattr(QRQueueService, "_update_queue_statistics", _stats_boom)

    resp = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Stats Failure Patient",
            "phone": "+998900000999",
        },
    )
    assert resp.status_code == 200, resp.json()
    assert resp.json()["success"] is True
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
        == 1
    )
