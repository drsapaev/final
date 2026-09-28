"""Round-12 review pins (PR #3362) — the probe is a CONCURRENCY oracle.

Round-11 review (P1): the round-11 recovery oracle answered ownership from
a PLAIN SELECT. Between the complete's claim (``UPDATE pending ->
joining``) and its single COMMIT the row lock is HELD while the last
COMMITTED version of the row is still ``pending`` — under MVCC the plain
SELECT reads that stale version and classifies an IN-FLIGHT business join
as ``pending_unbound`` (or ``expired`` near TTL). The ambiguity panel
would then offer the discard of an attempt that is about to commit, and a
fresh start could ride on top of the first attempt's талон.

The round-12 probe reads the row ``FOR UPDATE NOWAIT``: a concurrent
complete surfaces as PostgreSQL ``55P03 lock_not_available`` and the probe
answers ``processing`` — the honest UNKNOWN that keeps every envelope
intact. After the writer finishes, a retry probe classifies DECISIVELY:
``joined_match`` after a commit, truthful ``pending_unbound`` after a
rollback.

These pins can only be proven with TWO INDEPENDENT connections against
real PostgreSQL row locking (SQLite ignores ``FOR UPDATE`` and has a
single writer — the pre-round-12 committed-state classes are covered by
``test_qr_join_round11_recovery_oracle.py`` on SQLite). The module is
self-contained: it sets its own environment defaults BEFORE importing app
modules (same pattern as ``test_reminder_pipeline_pg.py``), builds its own
engine, and never touches the repo conftest. It is marked ``gate_d`` —
excluded from the default suite by pytest.ini addopts and executed in CI
by a dedicated backend-tests step whose DATABASE_URL points at the job's
postgres service (schema provisioned by ``alembic upgrade head`` there).

Run locally:
    cd backend && DATABASE_URL=postgresql+psycopg://clinic:pw@localhost:5432/clinicdb \
        pytest tests/integration/test_qr_join_probe_concurrency_pg.py -m gate_d --noconftest
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # backend/

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://clinic:clinic_ci_only_password@localhost:5432/clinicdb",
)
# Environment contract for the isolated (--noconftest) CI step: ENV=dev keeps
# the production-only config gates (ENCRYPTION_KEY / SMS provider) from
# firing, and TESTING=1 is deliberately NOT set — the config validator
# forbids it outside explicit dev values.
os.environ.setdefault("ENV", "dev")
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-probe-pg-concurrency-32-chars"
)
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "0")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.db.base  # noqa: F401,E402 - registers every model on Base

pytestmark = pytest.mark.gate_d

PROBE_TTL_GRACE = 1.6  # seconds the in-flight claim waits past the TTL


@pytest.fixture(scope="module")
def pg_engine():
    """Real PostgreSQL engine — the fixture ASSERTS the expected schema and
    never creates it (same schema-drift guardrail as
    ``test_reminder_pipeline_pg.py``): the gate_d database MUST be
    provisioned by ``alembic upgrade head`` first."""
    url = os.environ["DATABASE_URL"]
    if "postgres" not in url:
        pytest.skip("probe PG-concurrency proof requires PostgreSQL")
    from sqlalchemy import inspect

    engine = create_engine(url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "queue_join_sessions" not in tables:
        pytest.fail(
            "table queue_join_sessions does not exist — run "
            "`alembic upgrade head` against the gate_d database first; "
            "this fixture must not create schema outside Alembic "
            "(schema-drift guardrail)"
        )
    columns = {c["name"] for c in inspector.get_columns("queue_join_sessions")}
    missing = {
        "session_token",
        "status",
        "expires_at",
        "payload_fingerprint",
        "response_snapshot",
    } - columns
    if missing:
        pytest.fail(
            f"queue_join_sessions is missing probe columns {sorted(missing)} "
            "— the gate_d database is behind alembic head; upgrade it instead "
            "of letting the fixture mutate the schema"
        )
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(pg_engine):
    """Factory of INDEPENDENT sessions — the whole point of this proof:
    the writer (complete) and the prober must sit on separate connections
    so PostgreSQL row locks and MVCC visibility rules actually apply."""
    return sessionmaker(bind=pg_engine)


@pytest.fixture
def open_writers():
    """Sessions that may still HOLD the claim row lock when a test aborts
    on an assert. Teardown force-releases them BEFORE the cleanup deletes
    run — otherwise a failed pin would deadlock the whole suite (the
    delete blocks behind a lock owned by an abandoned transaction)."""
    writers: list = []
    yield writers
    for w in writers:
        try:
            w.rollback()
        except Exception:
            pass
        w.close()


@pytest.fixture
def cleanup_sessions(pg_engine, open_writers):
    """Session tokens created by a test; deleted on teardown so the shared
    CI postgres service stays clean across runs."""
    tokens: list[str] = []
    yield tokens
    from app.models.online_queue import QueueJoinSession

    s = sessionmaker(bind=pg_engine)()
    try:
        for token in tokens:
            s.query(QueueJoinSession).filter(
                QueueJoinSession.session_token == token
            ).delete()
        s.commit()
    finally:
        s.close()


def _seed_pending_session(session_factory, tokens, ttl_seconds=7200.0):
    """A committed ``pending`` attempt envelope, exactly as /join/start
    leaves it behind (unbound: no fingerprint, no snapshot)."""
    from app.models.online_queue import QueueJoinSession

    token = f"round12-probe-race-{uuid.uuid4().hex[:16]}"
    s = session_factory()
    try:
        s.add(
            QueueJoinSession(
                session_token=token,
                patient_name="Patient A",
                phone="+998900000412",
                status="pending",
                expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            )
        )
        s.commit()
    finally:
        s.close()
    tokens.append(token)
    return token


def _claim_in_flight(session_factory, token, open_writers=None):
    """Session A: run the REAL claim (``UPDATE pending -> joining``), keep
    the transaction OPEN (flushed, uncommitted) — the exact window between
    ``_claim_pending_join_session`` and the single complete COMMIT."""
    from app.services.qr_queue import QRQueueService

    s = session_factory()
    if open_writers is not None:
        open_writers.append(s)
    service = QRQueueService(s)
    claimed = service._claim_pending_join_session(token)
    assert claimed is not None, "claim must succeed for a fresh pending row"
    assert claimed.status == "joining"
    # flushed but NOT committed — the row lock is held from here on
    return s


def _finish_like_complete(session, token, ttl_seconds=3600.0):
    """Session A finishes the business operation the way
    ``complete_join_session`` does: joined_v2 + fingerprint + snapshot +
    horizon, one commit. (The талон itself is irrelevant to the probe —
    the oracle only reads the session row.)"""
    from app.models.online_queue import QueueJoinSession
    from app.services.qr_queue._sessions import (
        canonical_join_payload_fingerprint,  # noqa: F401 - defined there
    )

    row = (
        session.query(QueueJoinSession)
        .filter(QueueJoinSession.session_token == token)
        .with_for_update()
        .first()
    )
    row.status = "joined_v2"
    row.payload_fingerprint = canonical_join_payload_fingerprint(
        "Patient A", "+998900000412", None
    )
    row.response_snapshot = json.dumps(
        {
            "success": True,
            "queue_number": 42,
            "queue_length": 1,
            "estimated_wait_time": 10,
            "specialist_name": "Врач ID 1",
            "department": "cardiology",
        },
        ensure_ascii=False,
    )
    row.queue_number = 42
    row.joined_at = datetime.now(UTC)
    row.expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    session.commit()


def _probe(session_factory, token):
    """Session B: the recovery oracle under test (its own connection)."""
    from app.services.qr_queue import QRQueueService

    s = session_factory()
    try:
        service = QRQueueService(s)
        return service.probe_join_session(
            session_token=token,
            patient_name="Patient A",
            phone="+998900000412",
        )
    finally:
        s.rollback()
        s.close()


def test_probe_during_in_flight_complete_is_processing_then_joined_match(
    session_factory, cleanup_sessions, open_writers
):
    """PIN R12-A: while the complete transaction holds the claim, the probe
    must answer ``processing`` — NEVER ``pending_unbound``/``expired`` (the
    MVCC stale-read verdict of the pre-round-12 plain SELECT). After the
    complete commits, a retry probe classifies decisively and re-serves the
    saved snapshot."""
    token = _seed_pending_session(session_factory, cleanup_sessions)

    writer = _claim_in_flight(session_factory, token, open_writers)
    try:
        outcome = _probe(session_factory, token)
        assert outcome == {"outcome": "processing", "result": None}
    finally:
        # The prober's NOWAIT failure must NOT block the writer — the
        # business operation commits through as if the probe never ran.
        _finish_like_complete(writer, token)
        writer.close()

    outcome_after = _probe(session_factory, token)
    assert outcome_after["outcome"] == "joined_match"
    assert outcome_after["result"]["queue_number"] == 42
    assert outcome_after["result"]["replayed"] is True


def test_probe_after_rolled_back_complete_is_truthful_pending_unbound(
    session_factory, cleanup_sessions, open_writers
):
    """PIN R12-B: if the in-flight complete ROLLS BACK, the row lock is
    released and the probe finally classifies the REAL state — still
    ``pending``, nothing was ever executed — so ``pending_unbound`` becomes
    TRUE and the discard it unlocks duplicates nothing."""
    token = _seed_pending_session(session_factory, cleanup_sessions)

    writer = _claim_in_flight(session_factory, token, open_writers)
    try:
        outcome_in_flight = _probe(session_factory, token)
        assert outcome_in_flight["outcome"] == "processing"
    finally:
        writer.rollback()
        writer.close()

    outcome_after = _probe(session_factory, token)
    assert outcome_after == {"outcome": "pending_unbound", "result": None}

    # The row is untouched: the envelope still guards a live attempt.
    from app.models.online_queue import QueueJoinSession

    s = session_factory()
    try:
        row = (
            s.query(QueueJoinSession)
            .filter(QueueJoinSession.session_token == token)
            .one()
        )
        assert row.status == "pending"
        assert row.payload_fingerprint is None
        assert row.queue_entry_id is None
    finally:
        s.close()


def test_probe_near_ttl_during_in_flight_complete_never_declares_dead(
    session_factory, cleanup_sessions, open_writers
):
    """PIN R12-C (the expiry-adjacent race from the review): the claim
    happens BEFORE ``expires_at`` but the wall clock crosses it while the
    transaction is still in flight. The probe must NOT read the stale
    committed TTL and declare the attempt ``expired`` (discardable) — the
    row lock turns the read into ``processing`` until the writer's true
    outcome exists."""
    token = _seed_pending_session(
        session_factory, cleanup_sessions, ttl_seconds=1.0
    )

    writer = _claim_in_flight(session_factory, token, open_writers)
    try:
        # In-flight AND past the committed TTL now.
        import time

        time.sleep(PROBE_TTL_GRACE)
        outcome = _probe(session_factory, token)
        assert outcome["outcome"] == "processing"
    finally:
        _finish_like_complete(writer, token)
        writer.close()

    outcome_after = _probe(session_factory, token)
    assert outcome_after["outcome"] == "joined_match"
    assert outcome_after["result"]["replayed"] is True
