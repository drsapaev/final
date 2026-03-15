from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.queue_reorder_api_service import (
    QueueReorderApiDomainError,
    QueueReorderApiService,
)


@pytest.mark.unit
class TestQueueReorderApiService:
    def test_reorder_queue_raises_when_queue_missing(self):
        class Repository:
            def get_queue(self, queue_id):
                return None

        service = QueueReorderApiService(db=None, repository=Repository())

        with pytest.raises(QueueReorderApiDomainError) as exc_info:
            service.reorder_queue(
                queue_id=1,
                entry_orders=[{"entry_id": 1, "new_position": 1}],
                current_user=SimpleNamespace(id=1, role="Admin"),
            )

        assert exc_info.value.status_code == 404

    def test_move_queue_entry_returns_unchanged_message(self):
        queue = SimpleNamespace(
            id=1,
            day=SimpleNamespace(isoformat=lambda: "2026-01-01"),
            specialist=SimpleNamespace(user=SimpleNamespace(full_name="Doctor")),
            specialist_id=7,
            active=True,
            opened_at=None,
        )
        entry = SimpleNamespace(
            id=10,
            queue_id=1,
            number=1,
            patient_name="P",
            phone="1",
            status="waiting",
            source="online",
            created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
            called_at=None,
        )

        class Repository:
            def get_active_entry(self, entry_id):
                return entry

            def get_queue(self, queue_id):
                return queue

            def list_active_entries(self, *, queue_id):
                return [entry]

        service = QueueReorderApiService(db=None, repository=Repository())
        message, updated_count, _ = service.move_queue_entry(
            entry_id=10,
            new_position=1,
            current_user=SimpleNamespace(id=1, role="Admin"),
        )

        assert message == "Позиция не изменилась"
        assert updated_count == 0

    def test_get_queue_status_uses_domain_snapshot(self):
        queue = SimpleNamespace(
            id=1,
            day=SimpleNamespace(isoformat=lambda: "2026-01-01"),
            specialist=SimpleNamespace(user=SimpleNamespace(full_name="Doctor")),
            specialist_id=7,
            active=True,
            opened_at=None,
        )
        entry = SimpleNamespace(
            id=10,
            queue_id=1,
            number=1,
            patient_name="P",
            phone="1",
            status="waiting",
            source="online",
            created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
            called_at=None,
        )

        class DomainService:
            def get_queue_snapshot(self, *, queue_id):
                assert queue_id == 1
                return SimpleNamespace(queue=queue, entries=[entry])

        service = QueueReorderApiService(
            db=None,
            repository=SimpleNamespace(),
            domain_service=DomainService(),
        )

        result = service.get_queue_status(queue_id=1)

        assert result["queue_id"] == 1
        assert result["entries"][0]["id"] == 10

    def test_get_queue_status_by_specialist_uses_domain_snapshot(self):
        queue = SimpleNamespace(
            id=1,
            day=SimpleNamespace(isoformat=lambda: "2026-01-01"),
            specialist=SimpleNamespace(user=SimpleNamespace(full_name="Doctor")),
            specialist_id=7,
            active=True,
            opened_at=None,
        )

        class DomainService:
            def get_queue_snapshot_by_specialist_day(self, *, specialist_id, day):
                assert specialist_id == 7
                assert day == "2026-01-01"
                return SimpleNamespace(queue=queue, entries=[])

        service = QueueReorderApiService(
            db=None,
            repository=SimpleNamespace(),
            domain_service=DomainService(),
        )

        result = service.get_queue_status_by_specialist(
            specialist_id=7,
            day="2026-01-01",
        )

        assert result["queue_id"] == 1
        assert result["entries"] == []
