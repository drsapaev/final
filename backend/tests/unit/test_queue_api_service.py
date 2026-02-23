from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.queue_api_service import QueueApiService


@pytest.mark.unit
class TestQueueApiService:
    def test_get_or_create_daily_queue_creates_when_missing(self):
        created = SimpleNamespace(id=1)

        class Repository:
            def get_daily_queue(self, *, day, specialist_id):
                return None

            def create_daily_queue(self, *, day, specialist_id):
                return created

        service = QueueApiService(db=None, repository=Repository())
        queue = service.get_or_create_daily_queue(day="2026-01-01", specialist_id=7)
        assert queue is created

    def test_mark_entry_called_delegates_to_repository(self):
        state = {"called": False}
        entry = SimpleNamespace(id=1)

        class Repository:
            def mark_entry_called(self, entry_obj):
                state["called"] = True
                assert entry_obj is entry

        service = QueueApiService(db=None, repository=Repository())
        service.mark_entry_called(entry)
        assert state["called"] is True
