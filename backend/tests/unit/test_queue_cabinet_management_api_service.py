from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.queue_cabinet_management_api_service import (
    QueueCabinetManagementApiService,
    QueueCabinetManagementDomainError,
)


@pytest.mark.unit
class TestQueueCabinetManagementApiService:
    def test_get_queues_cabinet_info_raises_on_invalid_date(self):
        class Repository:
            def list_daily_queues(self, **kwargs):
                return []

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        with pytest.raises(QueueCabinetManagementDomainError) as exc_info:
            service.get_queues_cabinet_info(
                day="bad-date",
                specialist_id=None,
                cabinet_number=None,
            )
        assert exc_info.value.status_code == 400

    def test_update_queue_cabinet_info_updates_fields_and_commits(self):
        queue = SimpleNamespace(
            cabinet_number=None,
            cabinet_floor=None,
            cabinet_building=None,
        )
        state = {"committed": False, "refreshed": False}

        class Repository:
            def get_daily_queue(self, queue_id):
                return queue

            def commit(self):
                state["committed"] = True

            def refresh(self, obj):
                state["refreshed"] = True

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        result = service.update_queue_cabinet_info(
            queue_id=10,
            cabinet_info={"cabinet_number": "201", "cabinet_floor": 2},
            updated_by="admin",
        )

        assert result["success"] is True
        assert queue.cabinet_number == "201"
        assert queue.cabinet_floor == 2
        assert state["committed"] is True
        assert state["refreshed"] is True

    def test_update_queue_cabinet_info_can_clear_fields_with_explicit_nulls(self):
        queue = SimpleNamespace(
            cabinet_number="101",
            cabinet_floor=3,
            cabinet_building="A",
        )
        state = {"committed": False, "refreshed": False}

        class Repository:
            def get_daily_queue(self, queue_id):
                return queue

            def commit(self):
                state["committed"] = True

            def refresh(self, obj):
                state["refreshed"] = True

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        result = service.update_queue_cabinet_info(
            queue_id=10,
            cabinet_info={
                "cabinet_number": None,
                "cabinet_floor": None,
                "cabinet_building": None,
            },
            updated_by="admin",
        )

        assert result["success"] is True
        assert queue.cabinet_number is None
        assert queue.cabinet_floor is None
        assert queue.cabinet_building is None
        assert state["committed"] is True
        assert state["refreshed"] is True

    def test_get_cabinet_statistics_counts_queues_and_entries(self):
        queue = SimpleNamespace(
            id=1,
            day=date(2026, 1, 2),
            specialist_id=5,
            cabinet_number="101",
            cabinet_floor=1,
            cabinet_building="A",
        )

        class Repository:
            def list_queues_for_period(self, *, date_from, date_to):
                return [queue]

            def count_entries(self, *, queue_id):
                return 3

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        result = service.get_cabinet_statistics(date_from=None, date_to=None)

        assert result["statistics"]["total_queues"] == 1
        assert result["statistics"]["queues_with_cabinet"] == 1
        assert result["statistics"]["cabinets"][0]["total_entries"] == 3

    def test_get_queues_cabinet_info_falls_back_to_username_when_full_name_missing(self):
        queue = SimpleNamespace(
            id=11,
            day=date(2026, 1, 2),
            specialist_id=77,
            queue_tag="lab",
            cabinet_number="201",
            cabinet_floor=2,
            cabinet_building="A",
            active=True,
        )

        class Repository:
            def get_daily_queue(self, queue_id):
                return queue

            def get_doctor(self, doctor_id):
                return SimpleNamespace(
                    user=SimpleNamespace(full_name=None, username="cabinet-user")
                )

            def count_entries(self, *, queue_id):
                return 5

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        result = service.get_queue_cabinet_info(queue_id=11)

        assert result["specialist_name"] == "cabinet-user"
        assert result["entries_count"] == 5
