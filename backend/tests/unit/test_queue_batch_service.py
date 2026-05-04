from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import queue_batch_service as batch_module
from app.repositories.queue_batch_repository import (
    REGISTRAR_BATCH_ACTIVE_DUPLICATE_STATUSES,
)


def _service_with_repo(monkeypatch: pytest.MonkeyPatch, repo: Mock):
    monkeypatch.setattr(batch_module, "QueueBatchRepository", lambda db: repo)
    service = batch_module.QueueBatchService(db=Mock())
    service.queue_domain_service = Mock()
    return service


def test_create_entries_fails_when_patient_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = None
    service = _service_with_repo(monkeypatch, repo)

    with pytest.raises(batch_module.QueueBatchDomainError) as exc:
        service.create_entries(
            patient_id=999,
            source="desk",
            services=[batch_module.QueueBatchServiceItem(specialist_id=1, service_id=1)],
        )

    assert exc.value.status_code == 404
    assert "не найден" in exc.value.detail
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()


def test_create_entries_fails_when_service_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = SimpleNamespace(
        first_name="Test",
        last_name="Patient",
        phone=None,
        short_name=lambda: "Test Patient",
    )
    repo.get_active_service.return_value = None
    service = _service_with_repo(monkeypatch, repo)

    with pytest.raises(batch_module.QueueBatchDomainError) as exc:
        service.create_entries(
            patient_id=1,
            source="desk",
            services=[batch_module.QueueBatchServiceItem(specialist_id=1, service_id=101)],
        )

    assert exc.value.status_code == 404
    assert "Услуга" in exc.value.detail
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()


def test_create_entries_fails_when_specialist_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = SimpleNamespace(
        first_name="Test",
        last_name="Patient",
        phone=None,
        short_name=lambda: "Test Patient",
    )
    repo.get_active_service.return_value = SimpleNamespace(id=10)
    repo.resolve_specialist_user_id.return_value = (None, False)
    service = _service_with_repo(monkeypatch, repo)

    with pytest.raises(batch_module.QueueBatchDomainError) as exc:
        service.create_entries(
            patient_id=1,
            source="desk",
            services=[batch_module.QueueBatchServiceItem(specialist_id=555, service_id=10)],
        )

    assert exc.value.status_code == 404
    assert "Специалист" in exc.value.detail
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()


def test_create_entries_reuses_existing_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = SimpleNamespace(
        first_name="Test",
        last_name="Patient",
        phone="+998901234567",
        short_name=lambda: "Test Patient",
    )
    repo.get_active_service.return_value = SimpleNamespace(id=11)
    repo.resolve_specialist_user_id.return_value = (101, False)
    repo.find_existing_active_entries.return_value = [
        SimpleNamespace(
        queue_id=22,
        number=5,
        queue_time=datetime(2026, 1, 1, 8, 0, 0),
        )
    ]

    service = _service_with_repo(monkeypatch, repo)
    result = service.create_entries(
        patient_id=1,
        source="desk",
        services=[batch_module.QueueBatchServiceItem(specialist_id=101, service_id=11)],
    )

    assert result.success is True
    assert len(result.entries) == 1
    assert result.entries[0].number == 5
    assert "уже существовала" in result.message
    repo.commit.assert_called_once()
    repo.rollback.assert_not_called()
    service.queue_domain_service.allocate_ticket.assert_not_called()


def test_create_entries_creates_new_queue_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = SimpleNamespace(
        first_name="Test",
        last_name="Patient",
        phone="+998901234567",
        short_name=lambda: "Test Patient",
    )
    repo.get_active_service.return_value = SimpleNamespace(id=12)
    repo.resolve_specialist_user_id.return_value = (202, False)
    repo.find_existing_active_entries.return_value = []
    repo.get_or_create_daily_queue.return_value = SimpleNamespace(id=33)

    queue_entry = SimpleNamespace(
        queue_id=33,
        number=1,
        queue_time=datetime(2026, 1, 1, 9, 0, 0),
    )
    service = _service_with_repo(monkeypatch, repo)
    service.queue_domain_service.allocate_ticket.return_value = queue_entry
    result = service.create_entries(
        patient_id=1,
        source="online",
        services=[batch_module.QueueBatchServiceItem(specialist_id=202, service_id=12)],
    )

    assert result.success is True
    assert len(result.entries) == 1
    assert result.entries[0].queue_id == 33
    assert "Создано 1 запись" in result.message
    repo.commit.assert_called_once()
    repo.rollback.assert_not_called()
    service.queue_domain_service.allocate_ticket.assert_called_once()
    assert service.queue_domain_service.allocate_ticket.call_args.kwargs[
        "allocation_mode"
    ] == "create_entry"
    assert service.queue_domain_service.allocate_ticket.call_args.kwargs[
        "daily_queue"
    ] is repo.get_or_create_daily_queue.return_value
    assert service.queue_domain_service.allocate_ticket.call_args.kwargs[
        "patient_id"
    ] == 1
    assert service.queue_domain_service.allocate_ticket.call_args.kwargs[
        "auto_number"
    ] is True
    assert service.queue_domain_service.allocate_ticket.call_args.kwargs[
        "commit"
    ] is False


def test_create_entries_wraps_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = SimpleNamespace(
        first_name="Test",
        last_name="Patient",
        phone=None,
        short_name=lambda: "Test Patient",
    )
    repo.get_active_service.return_value = SimpleNamespace(id=13)
    repo.resolve_specialist_user_id.return_value = (303, False)
    repo.find_existing_active_entries.return_value = []
    repo.get_or_create_daily_queue.return_value = SimpleNamespace(id=44)

    service = _service_with_repo(monkeypatch, repo)
    service.queue_domain_service.allocate_ticket.side_effect = RuntimeError("boom")

    with pytest.raises(batch_module.QueueBatchDomainError) as exc:
        service.create_entries(
            patient_id=1,
            source="desk",
            services=[batch_module.QueueBatchServiceItem(specialist_id=303, service_id=13)],
        )

    assert exc.value.status_code == 500
    assert "массового создания" in exc.value.detail
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()


def test_create_entries_rejects_ambiguous_active_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_patient.return_value = SimpleNamespace(
        first_name="Test",
        last_name="Patient",
        phone="+998901234567",
        short_name=lambda: "Test Patient",
    )
    repo.get_active_service.return_value = SimpleNamespace(id=14)
    repo.resolve_specialist_user_id.return_value = (404, False)
    repo.find_existing_active_entries.return_value = [
        SimpleNamespace(queue_id=55, number=1, queue_time=datetime(2026, 1, 1, 8, 0, 0)),
        SimpleNamespace(queue_id=55, number=2, queue_time=datetime(2026, 1, 1, 8, 5, 0)),
    ]

    service = _service_with_repo(monkeypatch, repo)

    with pytest.raises(batch_module.QueueBatchDomainError) as exc:
        service.create_entries(
            patient_id=1,
            source="desk",
            services=[batch_module.QueueBatchServiceItem(specialist_id=404, service_id=14)],
        )

    assert exc.value.status_code == 409
    assert "Неоднозначная активная запись очереди" in exc.value.detail
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()
    service.queue_domain_service.allocate_ticket.assert_not_called()


def test_registrar_batch_active_duplicate_statuses_include_live_claims() -> None:
    assert REGISTRAR_BATCH_ACTIVE_DUPLICATE_STATUSES == (
        "waiting",
        "called",
        "in_service",
        "diagnostics",
    )
