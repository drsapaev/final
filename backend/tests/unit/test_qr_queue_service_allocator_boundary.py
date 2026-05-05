from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

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
        phone="+998904040404",
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
        phone="+998904040404",
        telegram_id=77,
        patient_id=123,
        source="online",
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
        phone="+998905050505",
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
