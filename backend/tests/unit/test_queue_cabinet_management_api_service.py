from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.models.audit import AuditLog
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
    def _seed_reassignment_targets(self, db_session, day: date):
        user = User(
            username="cabinet-apply-doctor",
            full_name="Synthetic Cabinet Doctor",
            hashed_password="!disabled:test",
            role="Doctor",
        )
        db_session.add(user)
        db_session.flush()
        doctor = Doctor(user_id=user.id, specialty="cardiology", cabinet="900")
        resource = QueueResource(
            code="cabinet_apply_resource",
            queue_tag="cabinet_apply",
            display_name="Synthetic Cabinet Room",
            default_cabinet="901",
            active=True,
        )
        db_session.add_all([doctor, resource])
        db_session.flush()
        doctor_queue = DailyQueue(
            day=day,
            specialist_id=doctor.id,
            cabinet_number="101",
            active=True,
        )
        resource_queue = DailyQueue(
            day=day,
            queue_resource_id=resource.id,
            queue_tag=resource.queue_tag,
            cabinet_number="201",
            active=True,
        )
        yesterday_queue = DailyQueue(
            day=day.fromordinal(day.toordinal() - 1),
            specialist_id=doctor.id,
            cabinet_number="old-day",
            active=True,
        )
        db_session.add_all([doctor_queue, resource_queue, yesterday_queue])
        db_session.flush()
        return doctor, resource, doctor_queue, resource_queue, yesterday_queue

    def test_apply_cabinet_reassignment_updates_only_explicit_today_targets_and_audits(
        self, db_session, admin_user, monkeypatch
    ):
        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        doctor, resource, doctor_queue, resource_queue, yesterday_queue = (
            self._seed_reassignment_targets(db_session, clinic_day)
        )

        result = QueueCabinetManagementApiService(
            db_session
        ).apply_cabinet_reassignment(
            targets=[
                {
                    "queue_id": doctor_queue.id,
                    "expected_owner_type": "doctor",
                    "expected_owner_id": doctor.id,
                    "expected_cabinet_number": "101",
                },
                {
                    "queue_id": resource_queue.id,
                    "expected_owner_type": "resource",
                    "expected_owner_id": resource.id,
                    "expected_cabinet_number": "201",
                },
            ],
            new_cabinet_number="301",
            reason_code="room_unavailable",
            actor_user_id=admin_user.id,
            actor_role="Admin",
            request_id="synthetic-request-apply-1",
        )

        assert result["clinic_day"] == clinic_day
        assert result["changed_queue_ids"] == [doctor_queue.id, resource_queue.id]
        assert result["unchanged_queue_ids"] == []
        assert doctor_queue.cabinet_number == "301"
        assert resource_queue.cabinet_number == "301"
        assert doctor.cabinet == "900"
        assert resource.default_cabinet == "901"
        assert yesterday_queue.cabinet_number == "old-day"
        audit_rows = (
            db_session.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .order_by(AuditLog.entity_id)
            .all()
        )
        assert [row.entity_id for row in audit_rows] == [
            doctor_queue.id,
            resource_queue.id,
        ]
        assert audit_rows[0].actor_user_id == admin_user.id
        assert audit_rows[0].actor_role == "Admin"
        assert audit_rows[0].payload == {
            "queue_day": clinic_day.isoformat(),
            "owner_type": "doctor",
            "owner_id": doctor.id,
            "old_cabinet_number": "101",
            "new_cabinet_number": "301",
            "reason_code": "room_unavailable",
            "request_id": "synthetic-request-apply-1",
        }

    def test_apply_cabinet_reassignment_stale_target_changes_nothing(self, monkeypatch):
        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        doctor_queue = SimpleNamespace(
            id=1,
            day=clinic_day,
            specialist_id=9,
            queue_resource_id=None,
            specialist=SimpleNamespace(
                cabinet="900",
                user=SimpleNamespace(full_name="Synthetic Doctor", username="doctor"),
            ),
            queue_resource=None,
            cabinet_number="101",
        )
        resource_queue = SimpleNamespace(
            id=2,
            day=clinic_day,
            specialist_id=None,
            queue_resource_id=19,
            specialist=None,
            queue_resource=SimpleNamespace(
                display_name="Synthetic Room", default_cabinet="901"
            ),
            cabinet_number="201",
        )
        state = {"committed": False, "rolled_back": False, "audits": []}

        class Repository:
            def lock_daily_queues_for_cabinet_reassignment(self, *, queue_ids):
                assert queue_ids == [1, 2]
                return [doctor_queue, resource_queue]

            def lock_queue_entries_for_cabinet_reassignment(self, *, queue_ids):
                assert queue_ids == [1, 2]
                return []

            def list_entry_statuses_by_queue_ids(self, **_kwargs):
                return {}

            def list_queue_ids_with_active_service_execution(self, **_kwargs):
                return set()

            def add_cabinet_reassignment_audit(self, **kwargs):
                state["audits"].append(kwargs)

            def commit(self):
                state["committed"] = True

            def rollback(self):
                state["rolled_back"] = True

        service = QueueCabinetManagementApiService(db=None, repository=Repository())

        with pytest.raises(QueueCabinetManagementDomainError) as stale:
            service.apply_cabinet_reassignment(
                targets=[
                    {
                        "queue_id": 1,
                        "expected_owner_type": "doctor",
                        "expected_owner_id": 9,
                        "expected_cabinet_number": "101",
                    },
                    {
                        "queue_id": 2,
                        "expected_owner_type": "resource",
                        "expected_owner_id": 19,
                        "expected_cabinet_number": "stale",
                    },
                ],
                new_cabinet_number="301",
                reason_code="room_unavailable",
                actor_user_id=1,
                actor_role="Admin",
                request_id="synthetic-request-apply-stale",
            )

        assert stale.value.status_code == 409
        assert doctor_queue.cabinet_number == "101"
        assert resource_queue.cabinet_number == "201"
        assert state == {"committed": False, "rolled_back": True, "audits": []}

    @pytest.mark.asyncio
    async def test_applied_doctor_daily_cabinet_is_announced_on_display_call(
        self, db_session, admin_user, monkeypatch
    ):
        from unittest.mock import AsyncMock

        from app.api.v1.endpoints.queue_cabinet_management import (
            CabinetReassignmentApplyRequest,
        )
        from app.services.display_websocket_api_service import (
            DisplayWebSocketApiService,
        )

        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        doctor, _resource, doctor_queue, _resource_queue, _yesterday_queue = (
            self._seed_reassignment_targets(db_session, clinic_day)
        )
        entry = OnlineQueueEntry(
            queue_id=doctor_queue.id,
            number=17,
            status="waiting",
            patient_name="SYNTHETIC-display-target",
        )
        db_session.add(entry)
        db_session.flush()

        cabinet_service = QueueCabinetManagementApiService(db_session)
        preview = cabinet_service.preview_cabinet_reassignment(
            queue_ids=[doctor_queue.id], new_cabinet_number="305"
        )
        apply_request = CabinetReassignmentApplyRequest(
            targets=[
                {
                    "queue_id": item["queue_id"],
                    "expected_owner_type": item["owner_type"],
                    "expected_owner_id": item["owner_id"],
                    "expected_cabinet_number": item["old_cabinet_number"],
                }
                for item in preview["items"]
            ],
            new_cabinet_number="305",
            reason_code="room_unavailable",
        )
        cabinet_service.apply_cabinet_reassignment(
            targets=[target.model_dump() for target in apply_request.targets],
            new_cabinet_number=apply_request.new_cabinet_number,
            reason_code=apply_request.reason_code,
            actor_user_id=admin_user.id,
            actor_role="Admin",
            request_id="synthetic-review-display-cabinet",
        )

        manager = SimpleNamespace(connections=[], broadcast_patient_call=AsyncMock())
        display_service = DisplayWebSocketApiService(
            db=None,
            repository=SimpleNamespace(
                get_queue_entry=lambda _entry_id: SimpleNamespace(
                    id=entry.id,
                    number=entry.number,
                    patient_name=entry.patient_name,
                    status="waiting",
                    called_at=None,
                    queue=doctor_queue,
                ),
                save=lambda: None,
            ),
            manager_provider=lambda: manager,
        )
        result = await display_service.call_patient(
            entry_id=entry.id,
            board_ids=[],
            current_user=SimpleNamespace(id=admin_user.id, role="Admin"),
        )

        assert result["call_data"]["cabinet"] == "305"
        assert manager.broadcast_patient_call.await_args.kwargs["cabinet"] == "305"
        assert doctor.cabinet == "900"

    def test_apply_accepts_exact_whitespace_bearing_preview_cabinet(
        self, db_session, admin_user, monkeypatch
    ):
        from app.api.v1.endpoints.queue_cabinet_management import (
            CabinetReassignmentApplyRequest,
        )

        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        _doctor, _resource, doctor_queue, _resource_queue, _yesterday_queue = (
            self._seed_reassignment_targets(db_session, clinic_day)
        )
        doctor_queue.cabinet_number = " 101 "
        db_session.flush()

        cabinet_service = QueueCabinetManagementApiService(db_session)
        preview = cabinet_service.preview_cabinet_reassignment(
            queue_ids=[doctor_queue.id], new_cabinet_number="301"
        )
        old_snapshot = preview["items"][0]["old_cabinet_number"]
        assert old_snapshot == " 101 "

        apply_request = CabinetReassignmentApplyRequest(
            targets=[
                {
                    "queue_id": doctor_queue.id,
                    "expected_owner_type": "doctor",
                    "expected_owner_id": preview["items"][0]["owner_id"],
                    "expected_cabinet_number": old_snapshot,
                }
            ],
            new_cabinet_number=" 301 ",
            reason_code="room_unavailable",
        )
        assert apply_request.targets[0].expected_cabinet_number == old_snapshot
        assert apply_request.new_cabinet_number == "301"
        result = cabinet_service.apply_cabinet_reassignment(
            targets=[target.model_dump() for target in apply_request.targets],
            new_cabinet_number=apply_request.new_cabinet_number,
            reason_code=apply_request.reason_code,
            actor_user_id=admin_user.id,
            actor_role="Admin",
            request_id="synthetic-review-whitespace-snapshot",
        )

        assert result["changed_queue_ids"] == [doctor_queue.id]
        assert doctor_queue.cabinet_number == "301"

    def test_apply_cabinet_reassignment_rolls_back_if_strict_audit_insert_fails(
        self, monkeypatch
    ):
        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        doctor_queue = SimpleNamespace(
            id=1,
            day=clinic_day,
            specialist_id=9,
            queue_resource_id=None,
            specialist=SimpleNamespace(
                cabinet="900",
                user=SimpleNamespace(full_name="Synthetic Doctor", username="doctor"),
            ),
            queue_resource=None,
            cabinet_number="101",
        )
        state = {"committed": False, "rolled_back": False}

        class Repository:
            def lock_daily_queues_for_cabinet_reassignment(self, *, queue_ids):
                assert queue_ids == [1]
                return [doctor_queue]

            def lock_queue_entries_for_cabinet_reassignment(self, *, queue_ids):
                assert queue_ids == [1]
                return []

            def list_entry_statuses_by_queue_ids(self, **_kwargs):
                return {}

            def list_queue_ids_with_active_service_execution(self, **_kwargs):
                return set()

            def add_cabinet_reassignment_audit(self, **_kwargs):
                raise RuntimeError("synthetic audit insert failure")

            def commit(self):
                state["committed"] = True

            def rollback(self):
                state["rolled_back"] = True
                doctor_queue.cabinet_number = "101"

        service = QueueCabinetManagementApiService(db=None, repository=Repository())

        with pytest.raises(QueueCabinetManagementDomainError) as failed:
            service.apply_cabinet_reassignment(
                targets=[
                    {
                        "queue_id": 1,
                        "expected_owner_type": "doctor",
                        "expected_owner_id": 9,
                        "expected_cabinet_number": "101",
                    }
                ],
                new_cabinet_number="301",
                reason_code="room_unavailable",
                actor_user_id=1,
                actor_role="Admin",
                request_id="synthetic-request-apply-audit-failure",
            )

        assert failed.value.status_code == 500
        assert doctor_queue.cabinet_number == "101"
        assert state == {"committed": False, "rolled_back": True}

    def test_apply_request_requires_explicit_unique_expected_state(self):
        from pydantic import ValidationError

        from app.api.v1.endpoints.queue_cabinet_management import (
            CabinetReassignmentApplyRequest,
        )

        target = {
            "queue_id": 5,
            "expected_owner_type": "doctor",
            "expected_owner_id": 9,
            "expected_cabinet_number": None,
        }
        with pytest.raises(ValidationError):
            CabinetReassignmentApplyRequest(
                targets=[target, target],
                new_cabinet_number="301",
                reason_code="room_unavailable",
            )
        with pytest.raises(ValidationError):
            CabinetReassignmentApplyRequest(
                targets=[
                    {
                        key: value
                        for key, value in target.items()
                        if key != "expected_cabinet_number"
                    }
                ],
                new_cabinet_number="301",
                reason_code="room_unavailable",
            )
        request = CabinetReassignmentApplyRequest(
            targets=[target | {"expected_cabinet_number": " 101 "}],
            new_cabinet_number=" 301 ",
            reason_code="room_unavailable",
        )
        assert request.targets[0].expected_cabinet_number == " 101 "
        assert request.new_cabinet_number == "301"

    def test_apply_endpoint_requires_key_and_admin_role(
        self, client, admin_auth_headers, registrar_auth_headers
    ):
        from app.main import app

        path = "/api/v1/admin/queues/cabinet-info/apply"
        body = {
            "targets": [
                {
                    "queue_id": 5,
                    "expected_owner_type": "doctor",
                    "expected_owner_id": 9,
                    "expected_cabinet_number": None,
                }
            ],
            "new_cabinet_number": "301",
            "reason_code": "room_unavailable",
        }
        missing_key = client.post(
            path,
            json=body,
            headers=admin_auth_headers,
        )
        anonymous = client.post(
            path,
            json=body,
            headers={"Idempotency-Key": "synthetic-cabinet-apply-anonymous"},
        )
        registrar = client.post(
            path,
            json=body,
            headers=registrar_auth_headers
            | {"Idempotency-Key": "synthetic-cabinet-apply-non-admin"},
        )
        oversized_key = client.post(
            path,
            json=body,
            headers=admin_auth_headers | {"Idempotency-Key": "x" * 129},
        )

        assert missing_key.status_code == 422
        assert anonymous.status_code == 401
        assert registrar.status_code == 403
        assert oversized_key.status_code == 400
        assert oversized_key.json()["code"] == "idempotency_key_invalid"
        operation = app.openapi()["paths"][path]["post"]
        key_header = next(
            item
            for item in operation["parameters"]
            if item["in"] == "header" and item["name"] == "Idempotency-Key"
        )
        assert key_header["required"] is True
        assert key_header["schema"]["minLength"] == 1
        assert key_header["schema"]["maxLength"] == 128
        assert {"400", "401", "403", "404", "409", "422", "503"}.issubset(
            operation["responses"]
        )
        invalid_key_schema = operation["responses"]["400"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        idempotency_error = app.openapi()["components"]["schemas"][
            invalid_key_schema.rsplit("/", 1)[-1]
        ]
        assert idempotency_error["properties"]["code"]["enum"] == [
            "idempotency_key_invalid",
            "idempotency_unavailable",
        ]

    def test_apply_endpoint_same_key_replays_without_duplicate_audit(
        self, client, db_session, admin_auth_headers, monkeypatch
    ):
        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        doctor, _resource, doctor_queue, _resource_queue, _yesterday = (
            self._seed_reassignment_targets(db_session, clinic_day)
        )
        headers = admin_auth_headers | {
            "Idempotency-Key": "synthetic-cabinet-apply-replay-1"
        }
        body = {
            "targets": [
                {
                    "queue_id": doctor_queue.id,
                    "expected_owner_type": "doctor",
                    "expected_owner_id": doctor.id,
                    "expected_cabinet_number": "101",
                }
            ],
            "new_cabinet_number": "302",
            "reason_code": "administrative_correction",
        }

        first = client.post(
            "/api/v1/admin/queues/cabinet-info/apply",
            json=body,
            headers=headers,
        )
        second = client.post(
            "/api/v1/admin/queues/cabinet-info/apply",
            json=body,
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == first.json()
        assert doctor_queue.cabinet_number == "302"
        assert (
            db_session.query(AuditLog)
            .filter(AuditLog.event_type == "QUEUE_CABINET_REASSIGNMENT")
            .count()
            == 1
        )

    def test_legacy_single_and_sync_endpoints_reject_snapshot_writes(
        self, client, db_session, admin_auth_headers, monkeypatch
    ):
        clinic_day = date(2026, 10, 6)
        monkeypatch.setattr(
            "app.services.queue_cabinet_management_api_service.clinic_today",
            lambda _db: clinic_day,
        )
        _doctor, _resource, doctor_queue, _resource_queue, _yesterday = (
            self._seed_reassignment_targets(db_session, clinic_day)
        )

        single = client.put(
            f"/api/v1/admin/queues/{doctor_queue.id}/cabinet-info",
            json={"cabinet_number": "306"},
            headers=admin_auth_headers,
        )
        sync = client.post(
            "/api/v1/admin/queues/sync-cabinet-info",
            headers=admin_auth_headers,
        )

        assert single.status_code == 409
        assert sync.status_code == 409
        db_session.refresh(doctor_queue)
        assert doctor_queue.cabinet_number == "101"

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

    def test_update_queue_cabinet_info_updates_metadata_and_commits(self):
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
            cabinet_info={"cabinet_floor": 2},
            updated_by="admin",
        )

        assert result["success"] is True
        assert queue.cabinet_number is None
        assert queue.cabinet_floor == 2
        assert state["committed"] is True
        assert state["refreshed"] is True

    def test_legacy_single_writer_rejects_cabinet_change_atomically(self):
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
        with pytest.raises(QueueCabinetManagementDomainError) as exc_info:
            service.update_queue_cabinet_info(
                queue_id=10,
                cabinet_info={
                    "cabinet_number": None,
                    "cabinet_floor": None,
                    "cabinet_building": None,
                },
                updated_by="admin",
            )

        assert exc_info.value.status_code == 409
        assert queue.cabinet_number == "101"
        assert queue.cabinet_floor == 3
        assert queue.cabinet_building == "A"
        assert state == {"committed": False, "refreshed": False}

    def test_legacy_bulk_writer_reports_snapshot_rejection_without_partial_row(self):
        queue = SimpleNamespace(
            id=8,
            cabinet_number="101",
            cabinet_floor=3,
            cabinet_building="A",
        )
        state = {"committed": False}

        class Repository:
            def get_daily_queue(self, queue_id):
                return queue if queue_id == queue.id else None

            def commit(self):
                state["committed"] = True

        result = QueueCabinetManagementApiService(
            db=None, repository=Repository()
        ).bulk_update_cabinet_info(
            updates=[
                {
                    "queue_id": 8,
                    "cabinet_info": {
                        "cabinet_number": "202",
                        "cabinet_floor": 4,
                    },
                }
            ],
            updated_by="admin",
        )

        assert result["success"] is True
        assert result["updated_queues"] == []
        assert result["errors"][0]["queue_id"] == 8
        assert queue.cabinet_number == "101"
        assert queue.cabinet_floor == 3
        assert state["committed"] is False

    def test_legacy_sync_is_rejected_without_reading_or_mutating_queues(self):
        class Repository:
            def list_queues_for_day(self, **_kwargs):
                raise AssertionError("disabled sync must not read daily queues")

        service = QueueCabinetManagementApiService(db=None, repository=Repository())
        with pytest.raises(QueueCabinetManagementDomainError) as exc_info:
            service.sync_cabinet_info_from_doctors(
                day=None, specialist_id=None, synced_by="admin"
            )

        assert exc_info.value.status_code == 409

    def test_cabinet_mutation_openapi_documents_legacy_conflicts(self):
        from app.main import app

        paths = app.openapi()["paths"]
        single = paths["/api/v1/admin/queues/{queue_id}/cabinet-info"]["put"]
        sync = paths["/api/v1/admin/queues/sync-cabinet-info"]["post"]
        for operation in (single, sync):
            conflict = operation["responses"]["409"]["content"]["application/json"][
                "schema"
            ]
            assert conflict["$ref"] == (
                "#/components/schemas/QueueCabinetMutationError"
            )
        error_contract = app.openapi()["components"]["schemas"][
            "QueueCabinetMutationError"
        ]
        assert error_contract["required"] == ["detail"]
        assert error_contract["properties"]["detail"]["type"] == "string"

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
