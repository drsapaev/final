from __future__ import annotations

from datetime import date
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

    def test_list_queue_cabinet_info_builds_payloads(self) -> None:
        queue = SimpleNamespace(
            id=5,
            day=SimpleNamespace(isoformat=lambda: "2026-03-07"),
            specialist_id=7,
            queue_tag="lab",
            cabinet_number="201",
            cabinet_floor=2,
            cabinet_building="B",
            active=True,
        )
        doctor = SimpleNamespace(user=SimpleNamespace(full_name="Doctor Test"))

        class Repository:
            def list_daily_queues(self, *, day_obj, specialist_id, cabinet_number):
                assert specialist_id == 7
                return [queue]

            def get_doctor(self, doctor_id):
                assert doctor_id == 7
                return doctor

            def count_entries(self, *, queue_id):
                assert queue_id == 5
                return 3

        service = QueueDomainService(db=None, read_repository=Repository())
        result = service.list_queue_cabinet_info(
            day=None,
            specialist_id=7,
            cabinet_number=None,
        )

        assert result == [
            {
                "id": 5,
                "day": "2026-03-07",
                "specialist_id": 7,
                "specialist_name": "Doctor Test",
                "queue_tag": "lab",
                "cabinet_number": "201",
                "cabinet_floor": 2,
                "cabinet_building": "B",
                "entries_count": 3,
                "active": True,
            }
        ]

    def test_get_queue_cabinet_info_raises_when_queue_missing(self) -> None:
        class Repository:
            def get_queue(self, queue_id):
                return None

        service = QueueDomainService(db=None, read_repository=Repository())

        with pytest.raises(QueueDomainReadError) as exc_info:
            service.get_queue_cabinet_info(queue_id=5)

        assert exc_info.value.status_code == 404

    def test_get_queue_limits_status_preserves_runtime_user_id_lookup(self) -> None:
        doctor = SimpleNamespace(
            id=3,
            user_id=33,
            specialty="cardio",
            cabinet="101",
            user=SimpleNamespace(full_name="Doctor Test"),
        )
        queue = SimpleNamespace(id=9, opened_at=None)

        class Repository:
            def list_active_doctors(self, *, specialty):
                assert specialty == "cardio"
                return [doctor]

            def get_queue_by_specialist_day(self, *, specialist_id, day):
                assert specialist_id == 33
                assert day.isoformat() == "2026-03-07"
                return queue

            def count_entries(self, *, queue_id):
                assert queue_id == 9
                return 4

        service = QueueDomainService(
            db="db",
            read_repository=Repository(),
            get_settings=lambda db: {"max_per_day": {"cardio": 5}},
        )

        result = service.get_queue_limits_status(
            day=date(2026, 3, 7),
            specialty="cardio",
        )

        assert result == [
            {
                "doctor_id": 3,
                "doctor_name": "Doctor Test",
                "specialty": "cardio",
                "cabinet": "101",
                "day": date(2026, 3, 7),
                "current_entries": 4,
                "max_entries": 5,
                "limit_reached": False,
                "queue_opened": False,
                "online_available": True,
            }
        ]

    def test_get_queue_groups_payload_preserves_static_groups_and_db_enrichment(self) -> None:
        service_row = SimpleNamespace(service_code="K77")

        class Repository:
            def list_active_services(self):
                return [service_row]

        service = QueueDomainService(db=None, read_repository=Repository())

        payload = service.get_queue_groups_payload()

        assert payload["groups"]["cardiology"]["tab_key"] == "cardio"
        assert payload["code_to_group"]["K01"] == "cardiology"
        assert payload["code_to_group"]["K77"] == "cardiology"
        assert payload["tab_to_group"]["cardio"] == "cardiology"

    def test_get_service_code_mappings_payload_preserves_static_aliases_and_db_enrichment(
        self,
    ) -> None:
        service_row = SimpleNamespace(
            service_code="L77",
            name="Расширенный лабораторный профиль",
            queue_tag="laboratory",
        )

        class Repository:
            def list_active_services(self):
                return [service_row]

        service = QueueDomainService(db=None, read_repository=Repository())

        payload = service.get_service_code_mappings_payload()

        assert payload["specialty_to_code"]["laboratory"] == "L77"
        assert payload["code_to_name"]["L77"] == "Расширенный лабораторный профиль"
        assert payload["category_mapping"]["laboratory"] == "L"
        assert payload["specialty_aliases"]["derma"] == "dermatology"
