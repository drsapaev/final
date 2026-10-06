from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service_execution import ServiceExecution
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.repositories.queue_cabinet_management_api_repository import (
    QueueCabinetManagementApiRepository,
)
from app.services.queue_cabinet_management_api_service import (
    QueueCabinetManagementApiService,
    QueueCabinetManagementDomainError,
)


@pytest.mark.unit
class TestQueueCabinetManagementApiService:
    def test_preview_repository_batches_owner_waiting_and_active_status_reads(
        self, db_session
    ):
        user = User(
            username="cabinet-preview-doctor",
            full_name="Preview Doctor",
            hashed_password="!disabled:test",
            role="Doctor",
        )
        db_session.add(user)
        db_session.flush()
        doctor = Doctor(
            user_id=user.id,
            specialty="cardiology",
            cabinet="999",
            active=True,
        )
        db_session.add(doctor)
        db_session.flush()
        queue = DailyQueue(
            day=date(2026, 10, 5),
            specialist_id=doctor.id,
            cabinet_number="101",
            active=True,
        )
        resource = QueueResource(
            code="cabinet_preview_resource",
            queue_tag="cabinet_preview",
            display_name="Preview room",
            default_cabinet="205",
            active=True,
        )
        db_session.add_all([queue, resource])
        db_session.flush()
        resource_queue = DailyQueue(
            day=date(2026, 10, 5),
            queue_resource_id=resource.id,
            queue_tag=resource.queue_tag,
            cabinet_number="204",
            active=True,
        )
        db_session.add(resource_queue)
        db_session.flush()
        waiting_entry = OnlineQueueEntry(queue_id=queue.id, number=1, status="waiting")
        db_session.add_all(
            [
                waiting_entry,
                OnlineQueueEntry(queue_id=queue.id, number=2, status="called"),
                OnlineQueueEntry(queue_id=queue.id, number=3, status="in_progress"),
            ]
        )
        db_session.flush()
        patient = Patient(
            last_name="SYNTHETIC-Preview",
            first_name="SYNTHETIC-Patient",
        )
        db_session.add(patient)
        db_session.flush()
        visit = Visit(patient_id=patient.id, status="open")
        db_session.add(visit)
        db_session.flush()
        visit_service = VisitService(
            visit_id=visit.id,
            service_id=999,
            name="SYNTHETIC Preview Procedure",
            qty=1,
        )
        db_session.add(visit_service)
        db_session.flush()
        db_session.add(
            ServiceExecution(
                visit_service_id=visit_service.id,
                queue_entry_id=waiting_entry.id,
                attempt_no=1,
                status="in_progress",
                started_by_user_id=user.id,
                started_at=datetime(2026, 10, 5, 12, 0, tzinfo=UTC),
            )
        )
        db_session.flush()

        repository = QueueCabinetManagementApiRepository(db_session)
        queues = repository.list_daily_queues_by_ids(
            queue_ids=[queue.id, resource_queue.id]
        )

        assert len(queues) == 2
        queues_by_id = {item.id: item for item in queues}
        assert queues_by_id[queue.id].specialist.user.full_name == "Preview Doctor"
        assert queues_by_id[resource_queue.id].queue_resource.display_name == (
            "Preview room"
        )
        assert repository.count_waiting_entries_by_queue_ids(
            queue_ids=[queue.id, resource_queue.id]
        ) == {queue.id: 1}
        assert repository.list_entry_statuses_by_queue_ids(
            queue_ids=[queue.id, resource_queue.id],
            statuses=("called", "in_progress", "in_service", "diagnostics"),
        ) == {queue.id: {"called", "in_progress"}}
        active_execution_queue_ids = (
            repository.list_queue_ids_with_active_service_execution(
                queue_ids=[queue.id, resource_queue.id]
            )
        )
        assert active_execution_queue_ids == {queue.id}

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

    def test_get_queues_cabinet_info_falls_back_to_username_when_full_name_missing(
        self,
    ):
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

    def test_preview_cabinet_reassignment_keeps_day_and_owner_defaults_distinct(
        self, monkeypatch
    ):
        clinic_day = date(2026, 10, 5)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        doctor_queue = SimpleNamespace(
            id=11,
            day=clinic_day,
            specialist_id=7,
            queue_resource_id=None,
            specialist=SimpleNamespace(
                cabinet="999",
                user=SimpleNamespace(full_name="Dr Example", username="doctor"),
            ),
            queue_resource=None,
            cabinet_number="101",
        )
        resource_queue = SimpleNamespace(
            id=12,
            day=clinic_day,
            specialist_id=None,
            queue_resource_id=21,
            specialist=None,
            queue_resource=SimpleNamespace(
                display_name="ECG room",
                default_cabinet="205",
            ),
            cabinet_number="204",
        )

        class Repository:
            def list_daily_queues_by_ids(self, *, queue_ids):
                assert queue_ids == [11, 12]
                return [doctor_queue, resource_queue]

            def count_waiting_entries_by_queue_ids(self, *, queue_ids):
                assert queue_ids == [11, 12]
                return {11: 3, 12: 1}

            def list_entry_statuses_by_queue_ids(self, *, queue_ids, statuses):
                assert queue_ids == [11, 12]
                assert "called" in statuses
                return {}

            def list_queue_ids_with_active_service_execution(self, *, queue_ids):
                assert queue_ids == [11, 12]
                return set()

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        result = service.preview_cabinet_reassignment(
            queue_ids=[11, 12], new_cabinet_number="301"
        )

        assert result["clinic_day"] == clinic_day
        assert result["can_apply"] is True
        assert result["items"] == [
            {
                "queue_id": 11,
                "queue_day": clinic_day,
                "owner_type": "doctor",
                "owner_id": 7,
                "owner_name": "Dr Example",
                "owner_default_cabinet": "999",
                "old_cabinet_number": "101",
                "new_cabinet_number": "301",
                "waiting_count": 3,
                "blocking_reasons": [],
                "can_apply": True,
            },
            {
                "queue_id": 12,
                "queue_day": clinic_day,
                "owner_type": "resource",
                "owner_id": 21,
                "owner_name": "ECG room",
                "owner_default_cabinet": "205",
                "old_cabinet_number": "204",
                "new_cabinet_number": "301",
                "waiting_count": 1,
                "blocking_reasons": [],
                "can_apply": True,
            },
        ]

    def test_preview_cabinet_reassignment_reports_active_blockers(self, monkeypatch):
        clinic_day = date(2026, 10, 5)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        queues = [
            SimpleNamespace(
                id=queue_id,
                day=clinic_day,
                specialist_id=queue_id,
                queue_resource_id=None,
                specialist=SimpleNamespace(
                    cabinet=None,
                    user=SimpleNamespace(full_name=f"Doctor {queue_id}", username=None),
                ),
                queue_resource=None,
                cabinet_number=None,
            )
            for queue_id in (1, 2, 3, 4)
        ]

        class Repository:
            def list_daily_queues_by_ids(self, *, queue_ids):
                return queues

            def count_waiting_entries_by_queue_ids(self, *, queue_ids):
                return {1: 2, 2: 1}

            def list_entry_statuses_by_queue_ids(self, *, queue_ids, statuses):
                assert "in_progress" in statuses
                return {
                    1: {"called"},
                    2: {"in_service"},
                    4: {"in_progress"},
                }

            def list_queue_ids_with_active_service_execution(self, *, queue_ids):
                return {3}

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        result = service.preview_cabinet_reassignment(
            queue_ids=[1, 2, 3, 4], new_cabinet_number="301"
        )

        assert result["can_apply"] is False
        assert result["items"][0]["blocking_reasons"] == ["patient_called"]
        assert result["items"][0]["waiting_count"] == 2
        assert result["items"][1]["blocking_reasons"] == ["clinical_work_in_progress"]
        assert result["items"][2]["blocking_reasons"] == ["active_service_execution"]
        assert result["items"][3]["blocking_reasons"] == ["clinical_work_in_progress"]
        assert all(not item["can_apply"] for item in result["items"])

    def test_preview_cabinet_reassignment_rejects_non_today_or_missing_queues(
        self, monkeypatch
    ):
        clinic_day = date(2026, 10, 5)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )

        class Repository:
            queues = []

            def list_daily_queues_by_ids(self, *, queue_ids):
                return self.queues

        repository = Repository()
        service = QueueCabinetManagementApiService(db=None, repository=repository)

        with pytest.raises(QueueCabinetManagementDomainError) as missing:
            service.preview_cabinet_reassignment(
                queue_ids=[1], new_cabinet_number="301"
            )
        assert missing.value.status_code == 404

        repository.queues = [
            SimpleNamespace(id=1, day=date(2026, 10, 4)),
        ]
        with pytest.raises(QueueCabinetManagementDomainError) as wrong_day:
            service.preview_cabinet_reassignment(
                queue_ids=[1], new_cabinet_number="301"
            )
        assert wrong_day.value.status_code == 409

    def test_preview_request_rejects_duplicate_ids_and_blank_cabinet(self):
        from pydantic import ValidationError

        from app.api.v1.endpoints.queue_cabinet_management import (
            CabinetReassignmentPreviewRequest,
        )

        with pytest.raises(ValidationError):
            CabinetReassignmentPreviewRequest(
                queue_ids=[5, 5], new_cabinet_number="301"
            )
        with pytest.raises(ValidationError):
            CabinetReassignmentPreviewRequest(
                queue_ids=[True], new_cabinet_number="301"
            )
        with pytest.raises(ValidationError):
            CabinetReassignmentPreviewRequest(queue_ids=[0], new_cabinet_number="301")
        with pytest.raises(ValidationError):
            CabinetReassignmentPreviewRequest(queue_ids=[5], new_cabinet_number="   ")

        request = CabinetReassignmentPreviewRequest(
            queue_ids=[5], new_cabinet_number=" 301 "
        )
        assert request.new_cabinet_number == "301"

    def test_preview_openapi_publishes_positive_nonempty_queue_ids(self):
        from app.main import app

        schema = app.openapi()["components"]["schemas"][
            "CabinetReassignmentPreviewRequest"
        ]["properties"]["queue_ids"]

        assert schema["minItems"] == 1
        assert schema["uniqueItems"] is True
        item_schema = schema["items"]
        assert (
            item_schema.get("minimum", 0) > 0
            or item_schema.get("exclusiveMinimum") == 0
        )

        responses = app.openapi()["paths"]["/api/v1/admin/queues/cabinet-info/preview"][
            "post"
        ]["responses"]
        assert {"200", "401", "403", "404", "409", "422"}.issubset(responses)
        for status_code in ("401", "403", "404", "409"):
            assert (
                responses[status_code]["content"]["application/json"]["schema"]["$ref"]
                == "#/components/schemas/CabinetReassignmentPreviewError"
            )
