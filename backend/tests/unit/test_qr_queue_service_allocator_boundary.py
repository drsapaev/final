from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models.online_queue import QueueJoinSession, QueueToken
from app.services.qr_queue_service import QRQueueService


class _QueryStub:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _DbStub:
    def __init__(self, results):
        self._results = list(results)
        self.commit = Mock()

    def query(self, model):
        return _QueryStub(self._results.pop(0))


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


@pytest.mark.unit
def test_complete_join_session_uses_queue_domain_boundary(monkeypatch):
    session = SimpleNamespace(
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
    qr_token = SimpleNamespace(
        token="qr-token",
        specialist_id=11,
        department="cardiology",
    )
    db = _DbStub([session, qr_token])
    domain_service = Mock()
    domain_service.allocate_ticket.return_value = {
        "entry": SimpleNamespace(id=88, number=5),
        "duplicate": True,
        "queue_length_before": 2,
        "estimated_wait_minutes": 15,
        "specialist_name": "Dr. Boundary",
    }

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=123),
    )

    result = service.complete_join_session(
        session_token="session-token",
        patient_name="Boundary Patient",
        phone="+998900000137",
        telegram_id=77,
    )

    assert result["success"] is True
    assert result["queue_number"] == 5
    assert result["queue_length"] == 2
    assert session.status == "joined"
    assert session.queue_entry_id == 88
    assert session.queue_number == 5
    db.commit.assert_called_once()
    domain_service.allocate_ticket.assert_called_once_with(
        allocation_mode="join_with_token",
        token_str="qr-token",
        patient_name="Boundary Patient",
        phone="+998900000137",
        telegram_id=77,
        patient_id=123,
        source="online",
        # Round-5 (PR #3362 review, P1-2): the allocation runs WITHOUT its
        # own commit — the claim, the талон and the joined outcome share
        # ONE transaction boundary owned by the complete flow.
        commit=False,
    )


@pytest.mark.unit
def test_complete_join_session_multiple_uses_queue_domain_boundary(monkeypatch):
    session = SimpleNamespace(
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
    qr_token = SimpleNamespace(
        token="qr-token",
        department="cardiology",
    )
    db = _DbStub([session, qr_token])
    domain_service = Mock()
    domain_service.allocate_ticket.side_effect = [
        {
            "entry": SimpleNamespace(id=101, number=4),
            "duplicate": True,
            "queue_length_before": 1,
            "estimated_wait_minutes": 10,
            "specialist_name": "Dr. First",
        },
        {
            "entry": SimpleNamespace(id=102, number=9),
            "duplicate": True,
            "queue_length_before": 3,
            "estimated_wait_minutes": 25,
            "specialist_name": "Dr. Second",
        },
    ]

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=456),
    )

    result = service.complete_join_session_multiple(
        session_token="session-token",
        specialist_ids=[11, 22],
        patient_name="Boundary Patient",
        phone="+998900000139",
        telegram_id=99,
    )

    assert result["success"] is True
    assert len(result["entries"]) == 2
    assert result["entries"][0]["queue_number"] == 4
    assert result["entries"][1]["queue_number"] == 9
    assert session.status == "joined"
    assert session.queue_entry_id == 101
    assert session.queue_number == 4
    db.commit.assert_called_once()
    assert domain_service.allocate_ticket.call_count == 2
    first_call = domain_service.allocate_ticket.call_args_list[0]
    second_call = domain_service.allocate_ticket.call_args_list[1]
    assert first_call.kwargs["allocation_mode"] == "join_with_token"
    assert first_call.kwargs["specialist_id_override"] == 11
    assert second_call.kwargs["specialist_id_override"] == 22


@pytest.mark.unit
def test_complete_join_session_claim_replays_joined_before_allocator(monkeypatch):
    """Round-4 (PR #3362, P1-2) + Round-5 (P1-3): the retry after a lost
    complete response re-uses the ORIGINAL attempt identity AND the
    ORIGINAL payload. A joined session REPLAYS its saved result only to
    the payload that created it — the replay is served BEFORE the
    allocator, and a different payload can never reach the business
    operation under someone else's attempt identity."""
    session = SimpleNamespace(
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
    qr_token = SimpleNamespace(
        token="qr-token",
        specialist_id=11,
        department="cardiology",
    )
    db = _ClaimDbStub(session, qr_token)
    domain_service = Mock()

    def allocate_ticket(**kwargs):
        assert session.status == "joining"
        return {
            "entry": SimpleNamespace(id=88, number=5),
            "duplicate": True,
            "queue_length_before": 2,
            "estimated_wait_minutes": 15,
            "specialist_name": "Dr. Boundary",
        }

    domain_service.allocate_ticket.side_effect = allocate_ticket

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=123),
    )

    original_body = {
        "session_token": "session-token",
        "patient_name": "Boundary Patient",
        "phone": "+998900000137",
        "telegram_id": 77,
    }
    service.complete_join_session(**original_body)

    # Round-5: the retry with the SAME session token AND the SAME payload
    # REPLAYS the saved result — a decisive answer, the allocator ran once.
    replay = service.complete_join_session(**original_body)

    assert replay["success"] is True
    assert replay["replayed"] is True
    assert replay["queue_number"] == 5
    assert session.status == "joined"
    assert domain_service.allocate_ticket.call_count == 1


@pytest.mark.unit
def test_complete_join_session_replay_refuses_foreign_payload(monkeypatch):
    """Round-5 (PR #3362 review, P1-3): ONE session token = ONE immutable
    payload. The old semantics let «Replay Patient / ...138» re-use a
    session joined by «Boundary Patient / ...137» — the exact wrong-patient
    hole. The replay with a different identity is now refused decisively
    (join_session_payload_mismatch) and never reaches the allocator."""
    session = SimpleNamespace(
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
    qr_token = SimpleNamespace(
        token="qr-token",
        specialist_id=11,
        department="cardiology",
    )
    db = _ClaimDbStub(session, qr_token)
    domain_service = Mock()
    domain_service.allocate_ticket.return_value = {
        "entry": SimpleNamespace(id=88, number=5),
        "duplicate": True,
        "queue_length_before": 2,
        "estimated_wait_minutes": 15,
        "specialist_name": "Dr. Boundary",
    }

    service = QRQueueService(db, queue_domain_service=domain_service)
    monkeypatch.setattr(
        service,
        "_find_or_create_patient",
        lambda patient_name, phone: SimpleNamespace(id=123),
    )

    service.complete_join_session(
        session_token="session-token",
        patient_name="Boundary Patient",
        phone="+998900000137",
        telegram_id=77,
    )
    assert domain_service.allocate_ticket.call_count == 1

    from app.services.qr_queue._base import JoinSessionStateRefusal

    with pytest.raises(JoinSessionStateRefusal) as refusal:
        service.complete_join_session(
            session_token="session-token",
            # the review's dangerous replay: ANOTHER person's identity
            patient_name="Replay Patient",
            phone="+998900000138",
            telegram_id=78,
        )
    assert refusal.value.reason == "join_session_payload_mismatch"
    # the business operation still ran exactly ONCE for this session
    assert domain_service.allocate_ticket.call_count == 1
