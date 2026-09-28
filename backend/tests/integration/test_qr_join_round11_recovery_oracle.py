"""Round-11 review pins (PR #3362) — the READ-ONLY recovery oracle.

Round-10 owner finding (P1-2): the ownerless-ambiguity resolution used the
MUTATING ``/join/complete`` as the «check» of each outstanding attempt.
UNKNOWN means, among other things, that the original complete request may
NEVER have reached the backend — the session is then still ``pending`` with
``payload_fingerprint = NULL``. Patient A «checking» candidate B with
A's typed data therefore CLAIMED the pending session and EXECUTED the
business join for it — a second бизнес-заход whose real recovery envelope
(A's own attempt) kept lying elsewhere. The queue-level duplicate guard
only partially mitigates it (waiting/called), so it is not an exactly-once
barrier for every later state.

The round-11 oracle (``POST /queue/join/probe``) answers the ownership
question WITHOUT a single mutation: no claim, no patient resolution, no
талон allocation, no status/expiry write:

  pending session (unbound)  -> ``pending_unbound``   (nothing executed)
  joined + matching payload  -> ``joined_match``      (saved snapshot re-served)
  joined + foreign payload   -> ``joined_mismatch``
  legacy joined, no fingerprint -> ``joined_owner_unknown`` (fail-closed)
  claimed by a concurrent request -> ``processing``
  expired / unknown token    -> ``expired`` / ``not_found``

Pinned here: every probe outcome leaves the row AND the business state
exactly as it was (entry/patient counts unchanged), and only the ORIGINAL
``/join/complete`` still executes the join for a pending session.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import (
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueToken,
)
from app.models.patient import Patient
from app.services.queue_service import QueueBusinessService

COMPLETE_URL = "/api/v1/queue/join/complete"
PROBE_URL = "/api/v1/queue/join/probe"
START_URL = "/api/v1/queue/join/start"


def _clinic_day():
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _local_now():
    return datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)


def _make_token(db_session, test_doctor, token_value: str) -> None:
    db_session.add(
        DailyQueue(
            day=_clinic_day(),
            specialist_id=test_doctor.id,
            queue_tag="cardiology_common",
            active=True,
        )
    )
    db_session.add(
        QueueToken(
            token=token_value,
            day=_clinic_day(),
            specialist_id=test_doctor.id,
            department="cardiology",
            expires_at=_local_now() + timedelta(hours=2),
            active=True,
        )
    )
    db_session.commit()


def _row(db_session, session_token: str) -> QueueJoinSession:
    return (
        db_session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == session_token)
        .one()
    )


def _payload(session_token: str, name: str, phone: str) -> dict:
    return {
        "session_token": session_token,
        "patient_name": name,
        "phone": phone,
    }


@pytest.mark.queue
def test_round11_probe_of_pending_session_is_read_only(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R11-A (round-11 P1-2): the review's core repro. A pending
    (payload-unbound) session probed with patient A's typed data returns
    ``pending_unbound`` and performs NOTHING — no claim, no patient row,
    no талон. The mutating complete remains the ONLY execution path."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    _make_token(db_session, test_doctor, "round11-probe-pending-token")

    start_resp = client.post(START_URL, json={"token": "round11-probe-pending-token"})
    assert start_resp.status_code == 200, start_resp.json()
    session_token = start_resp.json()["session_token"]

    entries_before = db_session.query(OnlineQueueEntry).count()
    patients_before = db_session.query(Patient).count()

    # Patient A «checks» the outstanding candidate with THEIR OWN data —
    # the exact action the old code routed through /join/complete.
    probe = client.post(
        PROBE_URL, json=_payload(session_token, "Patient A", "+998900000401")
    )
    assert probe.status_code == 200, probe.json()
    body = probe.json()
    assert body["outcome"] == "pending_unbound"
    assert body["result"] is None

    # The business state is EXACTLY as before the probe.
    row = _row(db_session, session_token)
    assert row.status == "pending"
    assert row.payload_fingerprint is None
    assert row.queue_entry_id is None
    assert db_session.query(OnlineQueueEntry).count() == entries_before
    assert db_session.query(Patient).count() == patients_before

    # The ORIGINAL complete still works — the exactly-once execution path
    # is unchanged; the probe never consumed the one-shot claim.
    complete = client.post(
        COMPLETE_URL, json=_payload(session_token, "Patient A", "+998900000401")
    )
    assert complete.status_code == 200, complete.json()
    assert complete.json()["replayed"] is False


@pytest.mark.queue
def test_round11_probe_of_joined_session_classifies_and_never_writes(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R11-B (round-11 P1-2): a committed attempt probed with the
    payload that created it re-serves the SAVED snapshot (``joined_match``
    + ``replayed: true``) without any second талон; the same row probed
    with a foreign payload answers ``joined_mismatch`` and leaks nothing.
    Either way the row is untouched."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    _make_token(db_session, test_doctor, "round11-probe-joined-token")

    start_resp = client.post(START_URL, json={"token": "round11-probe-joined-token"})
    session_token = start_resp.json()["session_token"]

    payload_a = _payload(session_token, "Patient A", "+998900000402")
    first = client.post(COMPLETE_URL, json=payload_a)
    assert first.status_code == 200, first.json()
    talon_number = first.json()["queue_number"]

    entries_after_commit = db_session.query(OnlineQueueEntry).count()
    row_before = _row(db_session, session_token)
    fingerprint_before = row_before.payload_fingerprint
    expires_before = row_before.expires_at

    # Matching payload: the read-only re-serve.
    match = client.post(
        PROBE_URL,
        json=_payload(session_token, " patient a ", "+998900000402"),
    )
    assert match.status_code == 200, match.json()
    match_body = match.json()
    assert match_body["outcome"] == "joined_match"
    assert match_body["result"] is not None
    assert match_body["result"]["queue_number"] == talon_number
    assert match_body["result"]["replayed"] is True

    # Foreign payload: decisive mismatch, no data leaks.
    foreign = client.post(
        PROBE_URL, json=_payload(session_token, "Patient B", "+998900000403")
    )
    assert foreign.status_code == 200, foreign.json()
    foreign_body = foreign.json()
    assert foreign_body["outcome"] == "joined_mismatch"
    assert foreign_body["result"] is None
    assert foreign_body.get("queue_number") is None

    # Read-only proof: same entries, same row bytes.
    assert db_session.query(OnlineQueueEntry).count() == entries_after_commit
    row_after = _row(db_session, session_token)
    assert row_after.status == "joined_v2"
    assert row_after.payload_fingerprint == fingerprint_before
    assert row_after.expires_at == expires_before


@pytest.mark.queue
def test_round11_probe_refuses_to_execute_for_processing_and_dead_states(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R11-C (round-11 P1-2): ``joining`` (a claim in flight) is the
    UNKNOWN class; a past-TTL pending row is ``expired``; an unknown token
    is ``not_found``. None of them execute anything or leak a snapshot."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    _make_token(db_session, test_doctor, "round11-probe-states-token")

    start_resp = client.post(START_URL, json={"token": "round11-probe-states-token"})
    session_token = start_resp.json()["session_token"]

    row = _row(db_session, session_token)
    row.status = "joining"  # a concurrent complete holds the claim
    db_session.commit()
    probe = client.post(
        PROBE_URL, json=_payload(session_token, "Patient A", "+998900000404")
    )
    assert probe.status_code == 200, probe.json()
    assert probe.json()["outcome"] == "processing"
    assert probe.json()["result"] is None
    assert _row(db_session, session_token).status == "joining"

    # Expired pending: nothing was executed, the identity is dead.
    row.status = "pending"
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    probe_expired = client.post(
        PROBE_URL, json=_payload(session_token, "Patient A", "+998900000404")
    )
    assert probe_expired.status_code == 200, probe_expired.json()
    assert probe_expired.json()["outcome"] == "expired"
    assert probe_expired.json()["result"] is None

    # Unknown token: the honest dead-end class.
    probe_unknown = client.post(
        PROBE_URL, json=_payload("no-such-session-token", "Patient A", "+998900000404")
    )
    assert probe_unknown.status_code == 200, probe_unknown.json()
    assert probe_unknown.json()["outcome"] == "not_found"

    assert db_session.query(OnlineQueueEntry).count() == 0


@pytest.mark.queue
def test_round11_probe_fail_closed_for_legacy_joined_row(
    client, db_session, test_doctor, monkeypatch
):
    """PIN R11-D (round-11 P1-2): a legacy ``joined`` row without a
    payload fingerprint proves NOTHING about ownership — the oracle
    answers the fail-closed ``joined_owner_unknown`` (never a snapshot,
    never ``joined_mismatch``, which would unlock a fresh start on top of
    an unattributed COMMITTED талон)."""
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    _make_token(db_session, test_doctor, "round11-probe-legacy-token")

    start_resp = client.post(START_URL, json={"token": "round11-probe-legacy-token"})
    session_token = start_resp.json()["session_token"]

    row = _row(db_session, session_token)
    row.status = "joined"  # written by a pre-round-5 worker
    row.payload_fingerprint = None
    row.response_snapshot = None
    db_session.commit()

    probe = client.post(
        PROBE_URL, json=_payload(session_token, "Patient A", "+998900000405")
    )
    assert probe.status_code == 200, probe.json()
    assert probe.json()["outcome"] == "joined_owner_unknown"
    assert probe.json()["result"] is None
    # The row stays exactly as it was.
    row_after = _row(db_session, session_token)
    assert row_after.status == "joined"
    assert row_after.payload_fingerprint is None
    assert db_session.query(OnlineQueueEntry).count() == 0
