from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import queue_batch_service as batch_module


def _service_with_repo(monkeypatch: pytest.MonkeyPatch, repo: Mock):
    monkeypatch.setattr(batch_module, "QueueBatchRepository", lambda db: repo)
    return batch_module.QueueBatchService(db=Mock())


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
    repo.find_existing_active_entry.return_value = SimpleNamespace(
        queue_id=22,
        number=5,
        queue_time=datetime(2026, 1, 1, 8, 0, 0),
    )

    create_queue_entry = Mock()
    monkeypatch.setattr(batch_module.queue_service, "create_queue_entry", create_queue_entry)

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
    create_queue_entry.assert_not_called()


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
    repo.find_existing_active_entry.return_value = None
    repo.get_or_create_daily_queue.return_value = SimpleNamespace(id=33)

    queue_entry = SimpleNamespace(
        queue_id=33,
        number=1,
        queue_time=datetime(2026, 1, 1, 9, 0, 0),
    )
    create_queue_entry = Mock(return_value=queue_entry)
    monkeypatch.setattr(batch_module.queue_service, "create_queue_entry", create_queue_entry)

    service = _service_with_repo(monkeypatch, repo)
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
    create_queue_entry.assert_called_once()
    assert create_queue_entry.call_args.kwargs["db"] is repo.db
    assert create_queue_entry.call_args.kwargs["commit"] is False


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
    repo.find_existing_active_entry.return_value = None
    repo.get_or_create_daily_queue.return_value = SimpleNamespace(id=44)

    monkeypatch.setattr(
        batch_module.queue_service,
        "create_queue_entry",
        Mock(side_effect=RuntimeError("boom")),
    )

    service = _service_with_repo(monkeypatch, repo)

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
