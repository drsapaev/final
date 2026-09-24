"""Round-6 review pins (PR #3362) — canonical multi-tag lock order.

Round-5 owner finding (P1-2): ``complete_join_session_multiple`` moved
every allocation of a batch into ONE transaction (correct for atomicity),
but still processed ``specialist_ids`` in the USER's input order — so two
concurrent multi-joins with the same two directions in INVERTED order
acquired the transaction-scoped ``daily_queue:tag:<tag>:<day>`` advisory
scopes in opposite orders: the exact AB-BA deadlock the QD-2E canon
(``lock_queue_tag_claim_scope`` docstring) forbids. PostgreSQL aborted one
patient as the deadlock victim; the frontend classifies the unexpected 5xx
as UNKNOWN.

The round-6 fix pair (the same restore-of-order the registrar cart ships):

  - ``resolve_join_batch_tag_targets`` pre-resolves every selection's
    claim scope READ-ONLY;
  - ``prelock_join_batch_tag_scopes`` acquires EVERY distinct (day, tag)
    scope in SORTED order BEFORE the first write;
  - the allocations run in the same canonical order; the response and the
    payload fingerprint keep the USER's original selection order.

Pins:
  - R6-E (unit): allocations acquire scopes in sorted order; the response
    is reassembled in the USER's order; prelock covers the FULL scope set;
  - R6-G (unit): an all-failed, already-rolled-back batch raises the typed
    ``join_session_not_executed`` refusal (single and multi paths);
  - R6-F (real PostgreSQL): every batch prelocks its FULL sorted scope set
    BEFORE its first claim-coordinator lock, and two concurrent batches
    with INVERTED input orders both complete — the AB-BA inversion is
    unreachable by construction.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from unittest.mock import MagicMock, Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.clinic import ClinicSettings
from app.models.online_queue import (
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueResource,
    QueueToken,
)
from app.models.queue_profile import QueueProfile
from app.services.qr_queue import QRQueueService
from app.services.qr_queue._base import JoinSessionNotExecutedRefusal
from app.services.queue_service import QueueBusinessService, QueueValidationError


def _clinic_day():
    return datetime.now(ZoneInfo("Asia/Tashkent")).date()


def _local_now():
    return datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# DB stubs (the round-5 boundary test's proven shapes)
# ---------------------------------------------------------------------------
class _QueryStub:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _ClaimQueryStub:
    def __init__(self, model, session, qr_token):
        self._model = model
        self._session = session
        self._qr_token = qr_token

    def filter(self, *args, **kwargs):
        return self

    def update(self, values, synchronize_session=False):
        if self._model is not QueueJoinSession:
            return 0
        if (
            self._session.status == "pending"
            and self._session.expires_at > datetime.utcnow()
        ):
            self._session.status = next(iter(values.values()))
            return 1
        return 0

    def first(self):
        if self._model is QueueJoinSession:
            return self._session
        if self._model is QueueToken:
            return self._qr_token
        return None


class _ClaimDbStub:
    def __init__(self, session, qr_token):
        self._session = session
        self._qr_token = qr_token
        self.commit = Mock()
        self.flush = Mock()
        self.rollback = Mock()

    def query(self, model):
        return _ClaimQueryStub(model, self._session, self._qr_token)


def _pending_session() -> SimpleNamespace:
    return SimpleNamespace(
        qr_token="qr-token",
        status="pending",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        patient_name=None,
        phone=None,
        telegram_id=None,
        queue_entry_id=None,
        queue_number=None,
        joined_at=None,
    )


from types import SimpleNamespace  # noqa: E402  (after helpers for readability)


# ---------------------------------------------------------------------------
# R6-E — canonical allocation order + user-order restoration (unit)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_r6_e_multi_batch_allocates_in_sorted_tag_order_restores_user_order(
    monkeypatch,
):
    """PIN R6-E: the allocation loop runs in the CANONICAL (sorted tag)
    order while the response keeps the USER's original order — and the
    prelock covered the FULL scope set."""
    session = _pending_session()
    qr_token = SimpleNamespace(token="qr-token", department="common")
    db = _ClaimDbStub(session, qr_token)

    domain_service = MagicMock()
    # Allocations go through the FACADE method
    # queue_domain_service.allocate_ticket; the prelock helpers live on
    # queue_domain_service.allocator_service.
    allocator = domain_service.allocator_service
    calls: list[dict] = []

    def allocate_ticket(**kwargs):
        calls.append(kwargs)
        idx = kwargs["specialist_id_override"]
        return {
            "entry": SimpleNamespace(id=100 + idx, number=idx),
            "duplicate": False,
            "queue_length_before": 1,
            "estimated_wait_minutes": 5,
            "specialist_name": f"Dr. {idx}",
        }

    domain_service.allocate_ticket.side_effect = allocate_ticket
    prelocked: list[str] = []

    allocator.resolve_join_batch_tag_targets.side_effect = (
        lambda db, **kw: {0: "derma_tag", 1: "cardio_tag"}
    )

    def prelock(db, *, lock_targets, **kwargs):
        prelocked.extend(sorted(set(lock_targets.values())))

    allocator.prelock_join_batch_tag_scopes.side_effect = prelock

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=42),
    )
    monkeypatch.setattr(
        service,
        "_update_queue_statistics",
        lambda *a, **k: None,
        raising=False,
    )

    # USER order: [derma, cardio] — INVERTED relative to the canonical
    # (sorted) one.
    result = service.complete_join_session_multiple(
        session_token="session-token",
        specialist_ids=[11, 22],
        patient_name="Order Patient",
        phone="+998900000601",
        telegram_id=None,
        specialist_entity_types=["profile", "profile"],
    )

    # Pre-lock covered the full scope set in sorted order:
    assert prelocked == ["cardio_tag", "derma_tag"]
    # Allocations ran in the canonical sorted-tag order (cardio first):
    assert [c["specialist_id_override"] for c in calls] == [22, 11]
    # ...but the RESPONSE restored the USER's original order:
    assert [e["specialist_id"] for e in result["entries"]] == [11, 22]
    assert session.status == "joined_v2"  # round-6 P1-1 marker
    assert session.queue_entry_id == 111  # entries[0] == user's FIRST pick
    db.commit.assert_called_once()


@pytest.mark.unit
def test_r6_e_multi_batch_all_failed_is_typed_not_executed_refusal(monkeypatch):
    """PIN R6-G: a batch whose EVERY allocation failed and which was ALREADY
    rolled back raises the typed ``join_session_not_executed`` refusal with
    per-specialist details — never the masked generic ValueError the
    endpoint rendered as «Internal server error»."""
    session = _pending_session()
    qr_token = SimpleNamespace(token="qr-token", department="common")
    db = _ClaimDbStub(session, qr_token)

    domain_service = MagicMock()
    domain_service.allocate_ticket.side_effect = QueueValidationError(
        "Очередь заполнена"
    )
    allocator = domain_service.allocator_service
    allocator.resolve_join_batch_tag_targets.side_effect = lambda db, **kw: {}
    allocator.prelock_join_batch_tag_scopes.side_effect = lambda db, **kw: None

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=42),
    )

    with pytest.raises(JoinSessionNotExecutedRefusal) as exc_info:
        service.complete_join_session_multiple(
            session_token="session-token",
            specialist_ids=[11, 22],
            patient_name="Refused Patient",
            phone="+998900000602",
        )
    refusal = exc_info.value
    assert refusal.reason == "join_session_not_executed"
    assert len(refusal.details) == 2
    assert {d["specialist_id"] for d in refusal.details} == {11, 22}
    assert "заполнена" in refusal.details[0]["error"]
    # The rollback was CONFIRMED before the refusal was raised.
    db.rollback.assert_called()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_r6_e_single_path_domain_refusal_is_typed_not_executed(monkeypatch):
    """PIN R6-G2: the single path's proven-rollback domain refusal carries
    the same machine reason (the review's «queue full / window closed»
    class) instead of «Internal server error»."""
    session = _pending_session()
    qr_token = SimpleNamespace(token="qr-token", department="cardiology")
    db = _ClaimDbStub(session, qr_token)

    domain_service = MagicMock()
    domain_service.allocate_ticket.side_effect = QueueValidationError(
        "Очередь заполнена"
    )

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=42),
    )

    with pytest.raises(JoinSessionNotExecutedRefusal) as exc_info:
        service.complete_join_session(
            session_token="session-token",
            patient_name="Refused Patient",
            phone="+998900000603",
        )
    assert exc_info.value.reason == "join_session_not_executed"
    assert exc_info.value.details[0]["specialist_id"] is None
    db.rollback.assert_called()
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# R6-F — real PostgreSQL proof
# ---------------------------------------------------------------------------
@pytest.fixture
def r6_pg_engine():
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("multi-tag lock-order proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_r6_lock_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=20000 -clock_timeout=20000 "
                "-cdeadlock_timeout=500ms"
            )
        },
    )
    try:
        from app.db.base_class import Base

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.mark.integration
@pytest.mark.queue
def test_r6_f_inverted_batches_prelock_full_scope_before_first_claim(
    r6_pg_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PIN R6-F: EVERY batch acquires its complete sorted scope set through
    the prelock BEFORE its first claim-coordinator lock, and two concurrent
    batches with INVERTED input orders both complete."""
    session_factory = sessionmaker(
        bind=r6_pg_engine, autocommit=False, autoflush=False
    )
    suffix = uuid.uuid4().hex[:8]
    tag1 = f"cardio_{suffix}"
    tag2 = f"derma_{suffix}"

    with session_factory() as seed:
        seed.add_all(
            [
                ClinicSettings(key="timezone", value="UTC", category="queue"),
                ClinicSettings(key="queue_start_hour", value=0, category="queue"),
            ]
        )
        for i, tag in enumerate((tag1, tag2)):
            profile = QueueProfile(
                key=f"p{i}_{tag}",
                title=f"Profile {tag}",
                title_ru=f"Профиль {tag}",
                queue_tags=[tag],
                is_active=True,
                show_on_qr_page=True,
                display_order=i,
            )
            resource = QueueResource(
                code=f"res_{tag}",
                queue_tag=tag,
                display_name=f"Ресурс {tag}",
                active=True,
                start_number_online=1,
                max_online_per_day=30,
            )
            seed.add_all([profile, resource])
            seed.flush()
            seed.add(
                DailyQueue(
                    day=date.today(),
                    queue_resource_id=resource.id,
                    specialist_id=None,
                    queue_tag=tag,
                    active=True,
                )
            )
        token = QueueToken(
            token=f"r6-lock-{suffix}",
            day=date.today(),
            specialist_id=None,
            department="common",
            expires_at=_local_now() + timedelta(hours=4),
            active=True,
            is_clinic_wide=True,
        )
        seed.add(token)
        seed.commit()
        token_value = token.token

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", dt_time(0, 0))

    # ── observation: a global monotonic sequence over BOTH lock surfaces ──
    # kind 'prelock' = acquisitions made INSIDE the batch prelock helper
    #   (thread-local window flag); kind 'claim' = the claim coordinator.
    # Every other routing-lock call (e.g. the registry-creation lock inside
    # get_or_create) happens during allocations and is IGNORED — the pin is
    # about the prelock-before-first-claim order, not about the idempotent
    # re-acquisitions.
    thread_role = threading.local()
    in_prelock = threading.local()
    seq_lock = threading.Lock()
    seq = {"n": 0}
    lock_events: list[dict] = []

    import app.crud.queue_resource_routing as routing_module
    import app.services.queue_claim_service as claim_module

    real_routing_lock = routing_module.lock_queue_tag_claim_scope
    real_claim_lock = claim_module.lock_queue_tag_claim_scope

    def _record(queue_tag) -> None:
        role = getattr(thread_role, "value", None)
        if role is None:
            return
        if not getattr(in_prelock, "value", False):
            return  # allocation-time retake / registry lock — not the prelock
        with seq_lock:
            seq["n"] += 1
            lock_events.append(
                {"n": seq["n"], "role": role, "kind": "prelock", "tag": str(queue_tag)}
            )

    def observed_routing_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        _record(queue_tag)
        return real_routing_lock(db, queue_tag, day)

    def observed_claim_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        with seq_lock:
            seq["n"] += 1
            lock_events.append(
                {
                    "n": seq["n"],
                    "role": getattr(thread_role, "value", None),
                    "kind": "claim",
                    "tag": str(queue_tag),
                }
            )
        return real_claim_lock(db, queue_tag, day)

    monkeypatch.setattr(routing_module, "lock_queue_tag_claim_scope", observed_routing_lock)
    monkeypatch.setattr(claim_module, "lock_queue_tag_claim_scope", observed_claim_lock)
    # The batch prelock binds the name into _operations at import time —
    # patch THAT reference too so the prelock helper goes through the
    # observer.
    import app.services.queue_svc._operations as operations_module

    monkeypatch.setattr(
        operations_module, "lock_queue_tag_claim_scope", observed_routing_lock
    )

    # Mark the prelock WINDOW per thread so the observer can tell the
    # batch's own scope acquisitions from the allocation-time retakes.
    original_prelock = QueueBusinessService.prelock_join_batch_tag_scopes

    def observed_prelock(self, db, *, lock_targets, **kwargs):  # type: ignore[no-untyped-def]
        in_prelock.value = True
        try:
            return original_prelock(self, db, lock_targets=lock_targets, **kwargs)
        finally:
            in_prelock.value = False

    monkeypatch.setattr(
        QueueBusinessService, "prelock_join_batch_tag_scopes", observed_prelock
    )

    # Two pending join sessions (one per batch).
    sessions: dict[str, str] = {}
    for role in ("a", "b"):
        with session_factory() as s:
            start = QRQueueService(s).start_join_session(token=token_value)
            sessions[role] = start["session_token"]

    with session_factory() as s:
        pid1 = s.query(QueueProfile).filter(QueueProfile.key == f"p0_{tag1}").one().id
        pid2 = s.query(QueueProfile).filter(QueueProfile.key == f"p1_{tag2}").one().id

    results: dict[str, dict] = {}
    barrier = threading.Barrier(2, timeout=20)

    def _run_batch(role: str, specialist_ids: list[int]) -> None:
        thread_role.value = role
        s = session_factory()
        try:
            service = QRQueueService(s)
            result = service.complete_join_session_multiple(
                session_token=sessions[role],
                specialist_ids=specialist_ids,
                patient_name=f"Batch {role.upper()}",
                phone=f"+99893000000{'60' if role == 'a' else '70'}",
                specialist_entity_types=["profile", "profile"],
            )
            results[role] = {"ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001 — the assertions inspect it
            results[role] = {"ok": False, "error": repr(exc)}
            s.rollback()
        finally:
            s.close()

    def run_a():
        barrier.wait()
        # Worker A: user order [tag1, tag2] (already canonical).
        _run_batch("a", [pid1, pid2])

    def run_b():
        barrier.wait()
        # Worker B: INVERTED user order [tag2, tag1] — the deadlock input.
        _run_batch("b", [pid2, pid1])

    ta = threading.Thread(target=run_a)
    tb = threading.Thread(target=run_b)
    ta.start()
    tb.start()
    ta.join(timeout=30)
    tb.join(timeout=30)

    # Both inverted batches completed with BOTH tickets — no deadlock
    # abort, no 40P01 victim.
    assert results["a"]["ok"], results["a"]
    assert results["b"]["ok"], results["b"]
    assert [e["specialist_id"] for e in results["a"]["result"]["entries"]] == [pid1, pid2]
    assert [e["specialist_id"] for e in results["b"]["result"]["entries"]] == [pid2, pid1]

    # THE ORDERING INVARIANT: for each batch, its LAST prelock event
    # precedes its FIRST claim event in the global interleaving — a batch
    # takes its full sorted scope set before its first coordinator lock,
    # so the inverted-input AB-BA cycle is unreachable.
    for role in ("a", "b"):
        mine = [e for e in lock_events if e["role"] == role]
        prelocks = [e for e in mine if e["kind"] == "prelock"]
        claims = [e for e in mine if e["kind"] == "claim"]
        assert prelocks, f"batch {role} recorded no prelock events"
        assert claims, f"batch {role} recorded no claim events"
        assert max(e["n"] for e in prelocks) < min(e["n"] for e in claims), (
            f"batch {role}: prelock must precede the first claim: "
            f"{lock_events}"
        )
        # The prelocked set is the COMPLETE scope set, in sorted order.
        assert [e["tag"] for e in prelocks] == sorted([tag1, tag2])

    # Both batches joined BOTH tags: each resource queue holds exactly
    # one entry PER BATCH (two distinct patients), numbered without clash.
    with session_factory() as s:
        for tag in (tag1, tag2):
            q = s.query(DailyQueue).filter(DailyQueue.queue_tag == tag).one()
            entries = (
                s.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == q.id)
                .all()
            )
            assert len(entries) == 2, (tag, len(entries))
            assert len({e.patient_name for e in entries}) == 2


# ---------------------------------------------------------------------------
# R8 — single vs multi phone↔tag AB-BA (round-8 P2-3)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_r8_a_multi_phone_lock_precedes_batch_tag_prelock(monkeypatch):
    """PIN R8-A: in the multi path the patient phone advisory lock (inside
    ``_find_or_create_patient``) is acquired BEFORE the batch tag-scope
    prelock — the SAME phone → sorted-tags order the single path already
    follows. The round-6 prelock put the tag scopes on the wrong side of
    the phone lock: a single join (phone → tag) against a concurrent multi
    join of the same phone/day (tags → phone) closed a live AB-BA cycle."""
    session = _pending_session()
    qr_token = SimpleNamespace(token="qr-token", department="common")
    db = _ClaimDbStub(session, qr_token)

    domain_service = MagicMock()
    domain_service.allocate_ticket.side_effect = [
        {
            "entry": SimpleNamespace(id=101, number=1),
            "duplicate": False,
            "queue_length_before": 1,
            "estimated_wait_minutes": 5,
            "specialist_name": "Dr. 11",
        },
        {
            "entry": SimpleNamespace(id=102, number=2),
            "duplicate": False,
            "queue_length_before": 2,
            "estimated_wait_minutes": 10,
            "specialist_name": "Dr. 22",
        },
    ]
    allocator = domain_service.allocator_service
    allocator.resolve_join_batch_tag_targets.side_effect = (
        lambda db, **kw: {0: "derma_tag", 1: "cardio_tag"}
    )

    order: list[str] = []

    def prelock(db, *, lock_targets, **kwargs):
        order.append("prelock:sorted_tags")

    allocator.prelock_join_batch_tag_scopes.side_effect = prelock

    service = QRQueueService(db, queue_domain_service=domain_service)

    def observed_patient(*args, **kwargs):
        order.append("phone")
        return SimpleNamespace(id=42)

    monkeypatch.setattr(service, "_find_or_create_patient", observed_patient)
    monkeypatch.setattr(
        service,
        "_update_queue_statistics",
        lambda *a, **k: None,
        raising=False,
    )

    service.complete_join_session_multiple(
        session_token="session-token",
        specialist_ids=[11, 22],
        patient_name="Order Patient",
        phone="+998900000604",
        telegram_id=None,
        specialist_entity_types=["profile", "profile"],
    )

    assert order[0] == "phone", (
        f"the phone lock must precede the batch tag-scope prelock, got {order}"
    )
    assert order[1] == "prelock:sorted_tags"


@pytest.mark.integration
@pytest.mark.queue
def test_r8_b_real_pg_phone_advisory_lock_precedes_every_prelock_scope(
    r6_pg_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PIN R8-B (real PostgreSQL): inside one live multi join the
    ``qr_patient:<phone>`` advisory-lock statement executes BEFORE the first
    batch tag-scope prelock acquisition — the single-path order, observed
    on the actual connection (the unit pin R8-A proves the call order, this
    pin proves it survives the real execution path)."""
    session_factory = sessionmaker(
        bind=r6_pg_engine, autocommit=False, autoflush=False
    )
    suffix = uuid.uuid4().hex[:8]
    tag = f"cardio_{suffix}"

    with session_factory() as seed:
        seed.add_all(
            [
                ClinicSettings(key="timezone", value="UTC", category="queue"),
                ClinicSettings(key="queue_start_hour", value=0, category="queue"),
            ]
        )
        profile = QueueProfile(
            key=f"p0_{tag}",
            title=f"Profile {tag}",
            title_ru=f"Профиль {tag}",
            queue_tags=[tag],
            is_active=True,
            show_on_qr_page=True,
            display_order=0,
        )
        resource = QueueResource(
            code=f"res_{tag}",
            queue_tag=tag,
            display_name=f"Ресурс {tag}",
            active=True,
            start_number_online=1,
            max_online_per_day=30,
        )
        seed.add_all([profile, resource])
        seed.flush()
        seed.add(
            DailyQueue(
                day=date.today(),
                queue_resource_id=resource.id,
                specialist_id=None,
                queue_tag=tag,
                active=True,
            )
        )
        token = QueueToken(
            token=f"r8-lock-{suffix}",
            day=date.today(),
            specialist_id=None,
            department="common",
            expires_at=_local_now() + timedelta(hours=4),
            active=True,
            is_clinic_wide=True,
        )
        seed.add(token)
        seed.commit()
        token_value = token.token

    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", dt_time(0, 0))

    seq_lock = threading.Lock()
    seq = {"n": 0}
    events: list[dict] = []

    import app.crud.queue_resource_routing as routing_module
    import app.services.queue_claim_service as claim_module
    import app.services.queue_svc._operations as operations_module
    import app.services.qr_queue._patients as patients_module

    real_routing_lock = routing_module.lock_queue_tag_claim_scope
    real_claim_lock = claim_module.lock_queue_tag_claim_scope

    def _record(kind: str, tag_value) -> None:
        with seq_lock:
            seq["n"] += 1
            events.append({"n": seq["n"], "kind": kind, "tag": str(tag_value)})

    def observed_routing_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        _record("prelock-or-claim", queue_tag)
        return real_routing_lock(db, queue_tag, day)

    def observed_claim_lock(db, queue_tag, day):  # type: ignore[no-untyped-def]
        _record("prelock-or-claim", queue_tag)
        return real_claim_lock(db, queue_tag, day)

    monkeypatch.setattr(routing_module, "lock_queue_tag_claim_scope", observed_routing_lock)
    monkeypatch.setattr(claim_module, "lock_queue_tag_claim_scope", observed_claim_lock)
    monkeypatch.setattr(
        operations_module, "lock_queue_tag_claim_scope", observed_routing_lock
    )

    # The phone lock goes through _patients.text(...): observe the
    # constructed advisory-lock statements.
    real_text = patients_module.text

    def observed_text(statement, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "pg_advisory_xact_lock" in statement:
            _record("phone", "qr_patient")
        return real_text(statement, *args, **kwargs)

    monkeypatch.setattr(patients_module, "text", observed_text)

    with session_factory() as s:
        start = QRQueueService(s).start_join_session(token=token_value)
        session_token = start["session_token"]
        pid = s.query(QueueProfile).filter(QueueProfile.key == f"p0_{tag}").one().id

    with session_factory() as s:
        service = QRQueueService(s)
        result = service.complete_join_session_multiple(
            session_token=session_token,
            specialist_ids=[pid],
            patient_name="R8 Single Phone",
            phone="+9989300000099",
            specialist_entity_types=["profile"],
        )
        assert [e["specialist_id"] for e in result["entries"]] == [pid]

    phones = [e for e in events if e["kind"] == "phone"]
    scopes = [e for e in events if e["kind"] == "prelock-or-claim"]
    assert phones, "the phone advisory lock never executed on PostgreSQL"
    assert scopes, "no tag-scope lock was observed"
    assert max(e["n"] for e in phones) < min(e["n"] for e in scopes), (
        f"the phone lock must precede EVERY tag-scope acquisition: {events}"
    )
