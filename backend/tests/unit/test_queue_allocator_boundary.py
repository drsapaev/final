from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.context_facades.queue_facade import QueueContextFacade
from app.services.queue_domain_service import QueueDomainService


@pytest.mark.unit
def test_allocate_ticket_create_entry_delegates_to_legacy_allocator() -> None:
    allocator = Mock()
    expected_entry = SimpleNamespace(
        id=10,
        queue_id=20,
        number=3,
        status="waiting",
        source="desk",
        queue_time=datetime(2026, 3, 7, 9, 0, 0),
    )
    allocator.create_queue_entry.return_value = expected_entry

    service = QueueDomainService(
        db="db-session",
        read_repository=Mock(),
        allocator_service=allocator,
    )

    result = service.allocate_ticket(
        allocation_mode="create_entry",
        daily_queue=SimpleNamespace(id=20),
        patient_id=1,
        patient_name="Test Patient",
        source="desk",
        queue_time=expected_entry.queue_time,
        commit=False,
    )

    assert result is expected_entry
    allocator.create_queue_entry.assert_called_once()
    assert allocator.create_queue_entry.call_args.args[0] == "db-session"
    assert allocator.create_queue_entry.call_args.kwargs["patient_id"] == 1
    assert allocator.create_queue_entry.call_args.kwargs["source"] == "desk"
    assert allocator.create_queue_entry.call_args.kwargs["commit"] is False


@pytest.mark.unit
def test_allocate_ticket_join_with_token_preserves_legacy_duplicate_result() -> None:
    allocator = Mock()
    expected = {
        "entry": SimpleNamespace(id=11, number=7, status="waiting", source="online"),
        "duplicate": True,
        "duplicate_reason": "телефону +998900000000",
        "queue_length_before": 1,
        "estimated_wait_minutes": 15,
    }
    allocator.join_queue_with_token.return_value = expected

    service = QueueDomainService(
        db="db-session",
        read_repository=Mock(),
        allocator_service=allocator,
    )

    result = service.allocate_ticket(
        allocation_mode="join_with_token",
        token_str="qr-token",
        patient_name="Test Patient",
        phone="+998900000000",
        source="online",
    )

    assert result == expected
    allocator.join_queue_with_token.assert_called_once()
    assert allocator.join_queue_with_token.call_args.args[0] == "db-session"
    assert allocator.join_queue_with_token.call_args.kwargs["token_str"] == "qr-token"
    assert allocator.join_queue_with_token.call_args.kwargs["source"] == "online"


@pytest.mark.unit
def test_allocate_ticket_raises_for_unsupported_mode() -> None:
    service = QueueDomainService(
        db="db-session",
        read_repository=Mock(),
        allocator_service=Mock(),
    )

    with pytest.raises(ValueError) as exc_info:
        service.allocate_ticket(allocation_mode="unsupported")

    assert "Unsupported allocation_mode" in str(exc_info.value)


@pytest.mark.unit
def test_queue_context_facade_allocate_ticket_delegates_to_contract() -> None:
    contract = Mock()
    expected_entry = SimpleNamespace(id=12, number=5, queue_id=22)
    contract.allocate_ticket.return_value = expected_entry

    facade = QueueContextFacade(contract)

    result = facade.allocate_ticket(
        allocation_mode="create_entry",
        correlation_id="req-1",
        daily_queue=SimpleNamespace(id=22),
        patient_id=9,
        source="confirmation",
    )

    assert result is expected_entry
    contract.allocate_ticket.assert_called_once()
    assert contract.allocate_ticket.call_args.kwargs["allocation_mode"] == "create_entry"
    assert contract.allocate_ticket.call_args.kwargs["request_id"] == "req-1"
    assert contract.allocate_ticket.call_args.kwargs["patient_id"] == 9
