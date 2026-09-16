from __future__ import annotations

from datetime import date

import pytest

from app.crud import queue_resource_routing
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.services import queue_claim_service
from app.services.queue_claim_service import (
    QueueClaimConflictError,
    lock_and_resolve_active_tag_claim,
)


def _add_entry(
    db_session,
    *,
    daily_queue: DailyQueue,
    number: int,
    patient_id: int | None = None,
    phone: str | None = None,
    telegram_id: int | None = None,
    status: str = "waiting",
    patient_name: str = "SYNTHETIC-QUEUE-CLAIM",
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=number,
        patient_id=patient_id,
        patient_name=patient_name,
        phone=phone,
        telegram_id=telegram_id,
        source="desk",
        status=status,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.unit
@pytest.mark.queue
def test_claim_resolver_locks_before_read_and_owns_no_transaction(
    monkeypatch,
) -> None:
    events: list[str] = []

    class _EmptyQuery:
        def join(self, *args):
            return self

        def filter(self, *args):
            return self

        def order_by(self, *args):
            return self

        def all(self):
            return []

    class _RecordingDb:
        def query(self, *args):
            events.append("query")
            return _EmptyQuery()

    monkeypatch.setattr(
        queue_claim_service,
        "lock_queue_tag_claim_scope",
        lambda *args: events.append("lock"),
    )

    result = queue_claim_service.lock_and_resolve_active_tag_claim(
        _RecordingDb(),  # type: ignore[arg-type]
        day=date(2026, 9, 12),
        queue_tag="cardiology_common",
        patient_id=1,
    )

    assert result is None
    assert events == ["lock", "query"]


@pytest.mark.unit
@pytest.mark.queue
def test_claim_resolver_merges_normalized_identity_signals_by_entry_id(
    db_session,
    test_daily_queue,
    test_patient,
) -> None:
    entry = _add_entry(
        db_session,
        daily_queue=test_daily_queue,
        number=1,
        patient_id=test_patient.id,
        phone="90 000 00 00",
        telegram_id=123456789,
        status="in_progress",
    )

    claim = lock_and_resolve_active_tag_claim(
        db_session,
        day=test_daily_queue.day,
        queue_tag=test_daily_queue.queue_tag,
        patient_id=test_patient.id,
        phone="+998 (90) 000-00-00",
        telegram_id=" 123456789 ",
    )

    assert claim is not None
    assert claim.daily_queue.id == test_daily_queue.id
    assert claim.entry.id == entry.id


@pytest.mark.unit
@pytest.mark.queue
def test_claim_resolver_ignores_terminal_and_inactive_rows(
    db_session,
    test_daily_queue,
    test_patient,
) -> None:
    _add_entry(
        db_session,
        daily_queue=test_daily_queue,
        number=1,
        patient_id=test_patient.id,
        status="served",
    )
    test_daily_queue.active = False
    db_session.commit()

    claim = lock_and_resolve_active_tag_claim(
        db_session,
        day=test_daily_queue.day,
        queue_tag=test_daily_queue.queue_tag,
        patient_id=test_patient.id,
    )

    assert claim is None


@pytest.mark.unit
@pytest.mark.queue
def test_claim_resolver_rejects_distinct_entries_across_same_tag_queues(
    db_session,
    test_daily_queue,
) -> None:
    resource = QueueResource(
        code="claim-test-resource",
        queue_tag=test_daily_queue.queue_tag,
        display_name="SYNTHETIC QUEUE CLAIM RESOURCE",
        active=True,
    )
    db_session.add(resource)
    db_session.flush()
    resource_queue = DailyQueue(
        day=test_daily_queue.day,
        queue_resource_id=resource.id,
        queue_tag=test_daily_queue.queue_tag,
        active=True,
    )
    db_session.add(resource_queue)
    db_session.commit()
    db_session.refresh(resource_queue)

    _add_entry(
        db_session,
        daily_queue=test_daily_queue,
        number=1,
        phone="+998900000001",
    )
    _add_entry(
        db_session,
        daily_queue=resource_queue,
        number=2,
        telegram_id=987654321,
        status="diagnostics",
    )

    with pytest.raises(QueueClaimConflictError):
        lock_and_resolve_active_tag_claim(
            db_session,
            day=test_daily_queue.day,
            queue_tag=test_daily_queue.queue_tag,
            phone="90-000-00-01",
            telegram_id="987654321",
        )


@pytest.mark.unit
@pytest.mark.queue
def test_claim_resolver_patient_scoped_phone_identity(
    db_session,
    test_daily_queue,
    test_patient,
) -> None:
    """RQ-25.a.1 (S-22, the merged-main ruling reconciled onto the
    coordinator): the identity scope is the PATIENT, not the phone. A
    typed row of ANOTHER patient sharing the family phone is that
    patient's claim, never this one's — no claim, no conflict; the
    family member simply gets their own number. The legacy phone
    bridge (entries with no patient link) still resolves, and the
    cross-patient telegram match still fails closed."""
    # a TYPED entry of another patient with the shared family phone —
    # NOT this patient's claim (S-22), and not a conflict either
    _add_entry(
        db_session,
        daily_queue=test_daily_queue,
        number=1,
        patient_id=test_patient.id,
        phone="+998900000002",
        status="called",
    )

    claim = lock_and_resolve_active_tag_claim(
        db_session,
        day=test_daily_queue.day,
        queue_tag=test_daily_queue.queue_tag,
        patient_id=test_patient.id + 1,
        phone="998 90 000 00 02",
    )

    assert claim is None

    # the LEGACY bridge: an entry with no patient link and the same
    # phone still resolves as this caller's claim (name-narrowed when
    # the name is supplied, phone-only otherwise)
    legacy = _add_entry(
        db_session,
        daily_queue=test_daily_queue,
        number=2,
        patient_id=None,
        phone="+998900000002",
        status="waiting",
    )

    bridged = lock_and_resolve_active_tag_claim(
        db_session,
        day=test_daily_queue.day,
        queue_tag=test_daily_queue.queue_tag,
        phone="998 90 000 00 02",
    )
    assert bridged is not None
    assert bridged.entry.id == legacy.id

    # a typed entry of another patient matched by TELEGRAM is a contact
    # match pointing at a different non-null patient id — fail closed
    other = _add_entry(
        db_session,
        daily_queue=test_daily_queue,
        number=3,
        patient_id=test_patient.id,
        phone=None,
        telegram_id=555000111,
        status="waiting",
    )
    assert other is not None

    with pytest.raises(QueueClaimConflictError):
        lock_and_resolve_active_tag_claim(
            db_session,
            day=test_daily_queue.day,
            queue_tag=test_daily_queue.queue_tag,
            patient_id=test_patient.id + 1,
            telegram_id=555000111,
        )


@pytest.mark.unit
@pytest.mark.queue
def test_registry_creation_lock_delegates_to_neutral_claim_scope(
    db_session,
    monkeypatch,
) -> None:
    calls: list[tuple[object, str, date]] = []

    def _record_lock(db, queue_tag: str, day: date) -> None:
        calls.append((db, queue_tag, day))

    monkeypatch.setattr(
        queue_resource_routing,
        "lock_queue_tag_claim_scope",
        _record_lock,
    )
    target_day = date(2026, 9, 12)

    queue_resource_routing.lock_registry_tag_creation(
        db_session,
        "cardiology_common",
        target_day,
    )

    assert calls == [(db_session, "cardiology_common", target_day)]


@pytest.mark.unit
@pytest.mark.queue
def test_no_internal_transaction_boundary_in_coordinator_cart_and_allocator() -> None:
    """Source pin (QD-2E P1): the claim coordinator, the wizard cart
    helpers and the allocator facade never own the transaction
    boundary — no ``.commit()``/``.rollback()`` call may appear in their
    code (comments/docstrings are fine; the AST scan ignores them).

    The single commit of the cart belongs to the calling endpoint, and
    the morning batch owns its per-visit commits; a commit inside any
    of these helpers would release the (day, tag) advisory locks early
    and let a competing claim creator interleave.
    """
    import ast
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[2]
    targets = [
        "app/services/queue_claim_service.py",
        "app/services/registrar_wizard_queue_assignment_service.py",
        "app/services/queue_domain_service.py",
    ]
    for relative in targets:
        source = (backend_root / relative).read_text(encoding="utf-8")
        offenders: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"commit", "rollback"}
            ):
                offenders.append(f"L{node.lineno}:{node.func.attr}")
        assert offenders == [], (
            f"{relative} must not own the transaction boundary — found "
            f"{offenders}"
        )
