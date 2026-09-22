"""Round-6 review pins (PR #3362) — refusal contract + attempt horizon.

Round-5 owner findings implemented here:

  - P2-1: a rollback-PROVEN domain refusal (the allocator batch created
    ZERO tickets and the service already executed ``db.rollback()``)
    surfaces as a structured 400 ``reason=join_session_not_executed``
    with per-specialist details — never again as the masked
    «Internal server error» that looped the patient on UNKNOWN until the
    session TTL;
  - P2-2: the 400/409 refusal contract is DECLARED on the OpenAPI path
    (responses=), the refusal DTOs exist in the schema registry, and the
    generated TypeScript contract carries them;
  - P1-3: the start responses carry the server-computed attempt-identity
    horizon — ``target_date`` (the token's queue day) and
    ``attempt_expires_at`` (end of THAT day in the clinic timezone +
    grace). A session started after the cutoff targets TOMORROW, so the
    horizon reaches beyond a fixed 24h — the client may no longer drop
    the reconcile identity while the target queue-day is still running.
"""

import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.services.queue_service import QueueBusinessService

COMPLETE_URL = "/api/v1/queue/join/complete"
START_URL = "/api/v1/queue/join/start"


def _clinic_day() -> date:
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _local_now():
    return datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)


@pytest.mark.queue
def test_single_path_domain_refusal_is_structured_not_executed(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-H (P2-1): a single-path domain refusal after a CONFIRMED
    rollback answers 400 with the machine reason and the real domain
    message — the queue-full/window-closed class is no longer masked."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "r6-not-executed-token"
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

    # Force a PROVEN domain refusal INSIDE the allocator (the deterministic
    # «queue full» class the review described). The service rolls the
    # transaction back and raises the typed refusal; the endpoint maps it
    # to the structured 400.
    def _refuse(*args, **kwargs):
        from app.services.queue_service import QueueValidationError

        raise QueueValidationError("Очередь заполнена")

    monkeypatch.setattr(QueueBusinessService, "join_queue_with_token", _refuse)

    resp = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Refused Patient",
            "phone": "+998900000701",
        },
    )
    assert resp.status_code == 400, resp.json()
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["reason"] == "join_session_not_executed"
    assert "заполнена" in detail["message"]  # the REAL domain message
    assert detail["details"][0]["specialist_id"] is None
    # nothing was created
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
        == 0
    )


@pytest.mark.queue
def test_openapi_contract_declares_refusal_responses(client, db_session):
    """PIN R6-I (P2-2): the recovery protocol is PART OF THE CONTRACT —
    the complete path declares 400 + 409 with the refusal DTO, the DTO
    schemas exist, and the generated TypeScript contract carries them."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    with open(repo_root / "backend" / "openapi.json", encoding="utf-8") as fh:
        spec = json.load(fh)

    schemas = spec["components"]["schemas"]
    assert "JoinSessionRefusalResponse" in schemas
    assert "JoinSessionRefusalDetail" in schemas

    responses = spec["paths"]["/api/v1/queue/join/complete"]["post"]["responses"]
    for code in ("400", "409"):
        assert code in responses, f"{code} must be declared on the complete path"
        ref = responses[code]["content"]["application/json"]["schema"]
        assert ref["$ref"].endswith("JoinSessionRefusalResponse")

    # The generated TypeScript contract ships the refusal DTO.
    generated = open(
        repo_root / "frontend" / "src" / "types" / "generated" / "api.ts",
        encoding="utf-8",
    ).read()
    assert "JoinSessionRefusalResponse" in generated
    assert "join_session_not_executed" in schemas["JoinSessionRefusalResponse"][
        "description"
    ]


@pytest.mark.queue
def test_start_response_carries_attempt_horizon_beyond_24h_for_tomorrow(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-J (P1-3): a token bound to TOMORROW (the after-cutoff start)
    yields attempt_expires_at = end of TOMORROW in the clinic timezone +
    grace — strictly later than the fixed 24h TTL that used to drop the
    reconcile identity while the target queue-day was still running."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    tomorrow = _clinic_day() + timedelta(days=1)
    daily_queue = DailyQueue(
        day=tomorrow,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "r6-horizon-token"
    token = QueueToken(
        token=token_value,
        day=tomorrow,
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=_local_now() + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    start_resp = client.post(START_URL, json={"token": token_value})
    assert start_resp.status_code == 200
    body = start_resp.json()

    assert body["target_date"] == tomorrow.isoformat()
    horizon = body["attempt_expires_at"]
    assert horizon
    parsed = datetime.fromisoformat(horizon.replace("Z", "+00:00"))

    tz = ZoneInfo("Asia/Tashkent")
    expected_end = (
        datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 59, 59)
        .replace(tzinfo=tz)
        + timedelta(hours=2, seconds=1)
    )
    assert parsed == expected_end
    # The review's scenario: the horizon must survive PAST submit+24h for
    # a tomorrow-targeting session.
    assert parsed > datetime.now(ZoneInfo("UTC")) + timedelta(hours=24)


@pytest.mark.queue
def test_start_response_horizon_for_today_token_covers_day_end_plus_grace(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-J2: a TODAY token yields target_date == today and the exact
    end-of-day + grace horizon — the client never drops the attempt before
    the queue-day (plus the safety grace) is truly over."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    today = _clinic_day()
    daily_queue = DailyQueue(
        day=today,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "r6-horizon-today-token"
    token = QueueToken(
        token=token_value,
        day=today,
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=_local_now() + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    start_resp = client.post(START_URL, json={"token": token_value})
    assert start_resp.status_code == 200, start_resp.json()
    body = start_resp.json()

    assert body["target_date"] == today.isoformat()
    horizon = body["attempt_expires_at"]
    assert horizon
    parsed = datetime.fromisoformat(horizon.replace("Z", "+00:00"))
    tz = ZoneInfo("Asia/Tashkent")
    expected_end = (
        datetime(today.year, today.month, today.day, 23, 59, 59)
        .replace(tzinfo=tz)
        + timedelta(hours=2, seconds=1)
    )
    assert parsed == expected_end
