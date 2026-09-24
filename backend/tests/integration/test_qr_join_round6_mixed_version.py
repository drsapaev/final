"""Round-6 review pins (PR #3362) — mixed-version replay barrier.

Round-5 owner finding (P1-1): during a rolling deployment the NEW worker
commits talon + ``payload_fingerprint`` + snapshot under ``status=joined``,
the HTTP response is lost, and the retry carrying a DIFFERENT payload
lands on an OLD worker — whose ``_replay_joined_session`` checked exactly
``status == "joined"`` and knew nothing about the fingerprint, so patient
B was served patient A's saved ticket (wrong-patient disclosure).

The round-6 barrier: the joined marker is VERSIONED (``joined_v2``). The
old worker does not recognize the row as ITS replayable state and never
replays it — the talon is never served to a foreign payload by ANY
version.

Round-9 (review P1-1) — the classification side is TIGHTENED: the round-6
design let the old worker's fallback answer ``join_session_expired`` for
a ``joined_v2`` row once the original 15-minute TTL ran out, and the
frontend reads ``expired`` as PROOF that nothing was created — an honest
«Start over» on top of an ALREADY COMMITTED talon. Since this fix-round
the successful complete EXTENDS ``expires_at`` to the attempt horizon
(end of the TARGET queue-day + grace), so the old worker's verbatim
decision table stays in the SAFE ``join_session_processing`` class for
the whole recovery window. Pinned here with the EXACT copy of the old
worker's decision logic (taken from e21f6429) as the oracle:

  - old replay predicate on a round-6 joined row  -> never replays;
  - old classifier on that row                    -> ALWAYS the safe
    ``join_session_processing`` — even with the clock shifted past the
    original 15-minute TTL (never not_found / expired / not_executed);
  - new worker: payload A replays its snapshot, payload B gets 409;
  - legacy ``joined`` rows (written by old workers) replay FAIL-CLOSED
    on the new worker (no fingerprint ⇒ used refusal);
  - the token-stats successful_joins counter counts BOTH status values.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import (
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueToken,
)
from app.services.queue_service import QueueBusinessService

COMPLETE_URL = "/api/v1/queue/join/complete"
START_URL = "/api/v1/queue/join/start"


def _clinic_day() -> date:
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _local_now():
    return datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# The OLD-worker oracle — VERBATIM semantics of e21f6429's
# _replay_joined_session visibility check and _classify_unclaimed_join_session
# fallback. Pinned here so a future change that re-opens the mixed-version
# hole fails loudly.
# ---------------------------------------------------------------------------
def old_worker_replays(row: QueueJoinSession) -> bool:
    """e21f6429 `_replay_joined_session` matches exactly status == 'joined'."""
    return row.status == "joined"


def old_worker_classifies(row: QueueJoinSession) -> str:
    """e21f6429 `_classify_unclaimed_join_session` decision table (the row
    exists; expires_at was set at session creation and is long past for a
    joined row)."""
    if row is None:
        return "join_session_not_found"
    if row.status == "joined":
        return "join_session_used"
    if row.status == "joining":
        return "join_session_processing"
    if row.expires_at is not None:
        expires_cmp = row.expires_at
        if expires_cmp.tzinfo is None:
            expires_cmp = expires_cmp.replace(tzinfo=ZoneInfo("UTC"))
        if expires_cmp <= datetime.now(ZoneInfo("UTC")):
            return "join_session_expired"
    return "join_session_processing"


@pytest.mark.queue
def test_round6_joined_row_is_versioned_and_invisible_to_old_worker_replay(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-A (round-6 P1-1): a joined row written by THIS version carries
    ``joined_v2``; the OLD worker's replay predicate does NOT match it and
    its classifier answers the decisive expired refusal — patient A's talon
    can never be re-served to any other payload through an old worker."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "round6-versioned-token"
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
        "patient_name": "Boundary Patient",
        "phone": "+998900000137",
    }
    first = client.post(COMPLETE_URL, json=body)
    assert first.status_code == 200, first.json()
    assert first.json()["replayed"] is False

    row = (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .one()
    )
    # The versioned marker is on the row...
    assert row.status == "joined_v2"
    assert row.payload_fingerprint  # the binding exists
    # ...and the OLD worker can never REPLAY it. Round-9 (P1-1): its
    # classifier answers ONLY the SAFE "processing" — the successful
    # complete extended expires_at to the attempt horizon, so the row can
    # never degrade into the start-over-safe "expired" verdict on top of
    # a COMMITTED talon. The extension is real: the row's expiry now sits
    # beyond the original 15-minute TTL (in the future).
    assert old_worker_replays(row) is False
    assert old_worker_classifies(row) == "join_session_processing"
    assert old_worker_classifies(row) not in (
        "join_session_used",
        "join_session_not_found",
        "join_session_expired",
    )
    row_expires = row.expires_at
    if row_expires.tzinfo is None:
        row_expires = row_expires.replace(tzinfo=ZoneInfo("UTC"))
    assert row_expires > datetime.now(ZoneInfo("UTC")) + timedelta(minutes=15)


@pytest.mark.queue
def test_round6_foreign_payload_never_receives_talon_via_any_worker(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-B (the round-5 review's two-version regression): the new
    worker commits talon+fingerprint for payload A; the retry with payload
    B must NEVER receive A's talon — neither through the new worker (409
    payload_mismatch) nor through the old worker's logic (the oracle never
    replays a ``joined_v2`` row)."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "round6-mixed-version-token"
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
    session_token = start_resp.json()["session_token"]

    payload_a = {
        "session_token": session_token,
        "patient_name": "Patient A",
        "phone": "+998900000301",
    }
    first = client.post(COMPLETE_URL, json=payload_a)
    assert first.status_code == 200, first.json()
    talon_a_number = first.json()["queue_number"]

    # Payload B on the SAME session token, served by THIS (new) worker:
    payload_b = {
        "session_token": session_token,
        "patient_name": "Patient B",
        "phone": "+998900000302",
    }
    second = client.post(COMPLETE_URL, json=payload_b)
    assert second.status_code == 409, second.json()
    assert second.json()["detail"]["reason"] == "join_session_payload_mismatch"
    # B never sees A's talon number in any success body:
    assert second.json().get("queue_number") is None

    # And the OLD worker's decision on this row can never serve A's talon
    # to B either — the row is invisible to the old replay and its
    # classifier answers the SAFE processing (Round-9: expired is no
    # longer an admissible verdict for a row this worker version wrote).
    row = (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .one()
    )
    assert old_worker_replays(row) is False
    assert old_worker_classifies(row) == "join_session_processing"

    # The queue holds exactly ONE entry — A's.
    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1
    assert entries[0].number == talon_a_number

    # Payload A itself still replays its own snapshot (the lost-response
    # retry of the LEGITIMATE owner is served by the new worker).
    retry_a = client.post(COMPLETE_URL, json=payload_a)
    assert retry_a.status_code == 200
    assert retry_a.json()["replayed"] is True
    assert retry_a.json()["queue_number"] == talon_a_number


@pytest.mark.queue
def test_round6_legacy_joined_row_replays_fail_closed_on_new_worker(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-C: a row written by an OLD worker during the deploy window
    (status ``joined``, NO fingerprint — ownership unprovable) is never
    re-served by the new worker: the replay fails closed with the decisive
    ``join_session_used`` refusal instead of guessing."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "round6-legacy-row-token"
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
    session_token = start_resp.json()["session_token"]

    # Simulate the OLD worker's outcome: talon committed, status flipped to
    # the legacy marker, no payload binding (the old two-commit flow).
    entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        patient_name="Legacy Patient",
        phone="+998900000401",
        number=7,
        status="waiting",
        source="online",
    )
    db_session.add(entry)
    db_session.flush()
    session_row = (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .one()
    )
    session_row.status = "joined"
    session_row.queue_entry_id = entry.id
    session_row.queue_number = 7
    session_row.payload_fingerprint = None
    session_row.response_snapshot = None
    db_session.commit()

    resp = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Legacy Patient",
            "phone": "+998900000401",
        },
    )
    assert resp.status_code == 400, resp.json()
    assert resp.json()["detail"]["reason"] == "join_session_used"
    # No second talon appeared.
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .count()
        == 1
    )


@pytest.mark.queue
def test_round6_token_stats_count_both_joined_markers(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R6-D: the token stats counter (successful_joins) counts BOTH the
    versioned ``joined_v2`` rows and the legacy ``joined`` rows."""
    from app.services.qr_queue import QRQueueService

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "round6-stats-token"
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
    session_token = start_resp.json()["session_token"]
    ok = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Stats Patient",
            "phone": "+998900000501",
        },
    )
    assert ok.status_code == 200, ok.json()

    # A legacy row for the same token (deploy-window mix).
    legacy = QueueJoinSession(
        session_token="round6-stats-legacy-token",
        qr_token=token_value,
        patient_name="Legacy",
        phone="+998900000502",
        status="joined",
        expires_at=datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5),
    )
    db_session.add(legacy)
    db_session.commit()

    service = QRQueueService(db_session)
    stats = service.get_active_qr_tokens(user_id=None)
    mine = next(t for t in stats if t["token"] == token_value)
    assert mine["successful_joins"] == 2


@pytest.mark.queue
def test_round9_joined_v2_past_original_ttl_is_never_start_over_safe(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R9-A (round-9 review P1-1): the review's EXACT scenario.

    A new worker commits the talon under ``joined_v2`` and the HTTP
    response is lost. MORE THAN 15 MINUTES later (the original session
    TTL is long past) a retry lands on an OLD worker. The old worker does
    not know ``joined_v2``, so its verdict is decided by ``expires_at``
    alone — and the frontend reads ``join_session_expired`` as PROOF that
    the business operation never ran (an honest «Start over» on top of a
    COMMITTED talon). Since the round-9 fix the successful complete
    extends ``expires_at`` to the attempt horizon, so the verbatim
    e21f6429 oracle — even with its clock shifted past the original
    15-minute TTL — answers the SAFE ``join_session_processing`` and
    NEVER not_found / expired / not_executed.
    """
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=_clinic_day(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    token_value = "round9-horizon-extend-token"
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
            "patient_name": "Horizon Patient",
            "phone": "+998900000901",
        },
    )
    assert first.status_code == 200, first.json()

    row = (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .one()
    )
    assert row.status == "joined_v2"
    original_expires = row.expires_at
    if original_expires.tzinfo is None:
        original_expires = original_expires.replace(tzinfo=ZoneInfo("UTC"))
    # The complete EXTENDED the row's expiry (it is no longer the
    # start-time 15-minute TTL: it sits beyond now + 15 min).
    assert original_expires > datetime.now(ZoneInfo("UTC")) + timedelta(minutes=15)

    # Simulate the retry arriving >15 minutes after the complete: shift
    # the oracle's clock 20 minutes forward — past the original session
    # TTL, still inside the attempt horizon (end of the target queue-day
    # + 2h grace). The verbatim old-worker decision table must answer
    # ONLY the safe processing class.
    import sys

    real_datetime = datetime

    class _ShiftedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return real_datetime.now(tz) + timedelta(minutes=20)

    # Patch THIS module's datetime — the oracle resolves it from its own
    # module globals; sys.modules[__name__] is robust to pytest import
    # naming (rootdir vs package).
    monkeypatch.setattr(sys.modules[__name__], "datetime", _ShiftedDateTime)
    verdict = old_worker_classifies(row)

    assert verdict == "join_session_processing"
    assert verdict not in (
        "join_session_not_found",
        "join_session_expired",
        "join_session_not_executed",
    )

    # The new worker itself keeps the decisive replay: the LEGITIMATE
    # owner's retry (same payload) re-serves the saved snapshot.
    retry = client.post(
        COMPLETE_URL,
        json={
            "session_token": session_token,
            "patient_name": "Horizon Patient",
            "phone": "+998900000901",
        },
    )
    assert retry.status_code == 200
    assert retry.json()["replayed"] is True
    assert retry.json()["queue_number"] == first.json()["queue_number"]
