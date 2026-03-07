from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.queue_domain_service import (
    QueueDomainReadError,
    QueueDomainService,
)


@pytest.mark.unit
class TestQueueDomainService:
    def test_get_queue_snapshot_returns_queue_and_entries(self) -> None:
        queue = SimpleNamespace(id=5)
        entries = [SimpleNamespace(id=10), SimpleNamespace(id=11)]

        class Repository:
            def get_queue(self, queue_id):
                assert queue_id == 5
                return queue

            def list_snapshot_entries(self, *, queue_id, statuses):
                assert queue_id == 5
                assert tuple(statuses) == ("waiting", "called")
                return entries

        service = QueueDomainService(db=None, read_repository=Repository())
        snapshot = service.get_queue_snapshot(queue_id=5)

        assert snapshot.queue is queue
        assert snapshot.entries == entries

    def test_get_queue_snapshot_by_specialist_day_raises_when_missing(self) -> None:
        class Repository:
            def get_queue_by_specialist_day(self, *, specialist_id, day):
                return None

        service = QueueDomainService(db=None, read_repository=Repository())

        with pytest.raises(QueueDomainReadError) as exc_info:
            service.get_queue_snapshot_by_specialist_day(
                specialist_id=7,
                day=SimpleNamespace(),
            )

        assert exc_info.value.status_code == 404
