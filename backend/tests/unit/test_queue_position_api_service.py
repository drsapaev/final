from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.queue_position_api_service import (
    QueuePositionApiDomainError,
    QueuePositionApiService,
)


@pytest.mark.unit
class TestQueuePositionApiService:
    def test_get_position_entry_raises_when_missing(self):
        repository = SimpleNamespace(get_entry=lambda entry_id: None)
        service = QueuePositionApiService(db=None, repository=repository)

        with pytest.raises(QueuePositionApiDomainError) as exc_info:
            service.get_position_entry(entry_id=10)

        assert exc_info.value.status_code == 404

    def test_get_position_entry_by_number_requires_queue_and_entry(self):
        repository = SimpleNamespace(
            get_today_queue_by_specialist=lambda specialist_id, day: SimpleNamespace(id=1),
            get_queue_entry_by_number=lambda queue_id, queue_number: SimpleNamespace(id=5),
        )
        service = QueuePositionApiService(db=None, repository=repository)

        entry = service.get_position_entry_by_number(queue_number=12, specialist_id=7)

        assert entry.id == 5

