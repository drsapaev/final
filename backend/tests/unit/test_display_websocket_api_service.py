from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.display_websocket_api_service import (
    DisplayWebSocketApiDomainError,
    DisplayWebSocketApiService,
)


@pytest.mark.unit
class TestDisplayWebSocketApiService:
    @pytest.mark.asyncio
    async def test_call_patient_raises_when_entry_missing(self):
        repository = SimpleNamespace(
            get_queue_entry=lambda entry_id: None,
            save=lambda: None,
            list_active_entries_for_day=lambda day: [],
            get_active_doctor_by_specialty=lambda specialty: None,
            get_daily_queue_for_specialist=lambda day, specialist_id: None,
            get_next_waiting_entry=lambda queue_id: None,
        )
        service = DisplayWebSocketApiService(db=None, repository=repository)

        with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
            await service.call_patient(
                entry_id=1,
                board_ids=[],
                current_user=SimpleNamespace(id=1, role="Admin"),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_doctor_calls_patient_by_linked_doctor_id_not_user_id(self):
        entry = SimpleNamespace(
            id=10,
            number=4,
            patient_name="Patient",
            status="waiting",
            called_at=None,
            queue=SimpleNamespace(
                specialist_id=7,
                specialist=SimpleNamespace(
                    user=SimpleNamespace(full_name="Dr Linked"),
                    cabinet="12",
                ),
            ),
        )
        manager = SimpleNamespace(
            connections=[],
            broadcast_patient_call=AsyncMock(),
        )

        class Repository:
            def get_queue_entry(self, entry_id):
                return entry

            def get_active_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, user_id=100, specialty="cardio")

            def save(self):
                return None

        service = DisplayWebSocketApiService(
            db=None,
            repository=Repository(),
            manager_provider=lambda: manager,
        )

        result = await service.call_patient(
            entry_id=10,
            board_ids=[],
            current_user=SimpleNamespace(id=100, role="Doctor"),
        )

        assert result["success"] is True
        assert entry.status == "called"
        manager.broadcast_patient_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_doctor_cannot_call_patient_when_only_user_id_matches_queue(self):
        entry = SimpleNamespace(
            id=10,
            number=4,
            patient_name="Patient",
            status="waiting",
            called_at=None,
            queue=SimpleNamespace(specialist_id=100),
        )

        class Repository:
            def get_queue_entry(self, entry_id):
                return entry

            def get_active_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, user_id=100, specialty="cardio")

            def save(self):
                raise AssertionError("foreign queue must not be mutated")

        service = DisplayWebSocketApiService(db=None, repository=Repository())

        with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
            await service.call_patient(
                entry_id=10,
                board_ids=[],
                current_user=SimpleNamespace(id=100, role="Doctor"),
            )

        assert exc_info.value.status_code == 403
        assert entry.status == "waiting"

    def test_get_department_queue_state_payload_builds_counts(self):
        entry = SimpleNamespace(
            id=1,
            number=3,
            patient_name="P",
            status="waiting",
            source="online",
            created_at=datetime(2026, 2, 14, 10, 0, 0),
        )
        repository = SimpleNamespace(
            get_queue_entry=lambda entry_id: None,
            save=lambda: None,
            list_active_entries_for_day=lambda day: [entry],
            get_active_doctor_by_specialty=lambda specialty: None,
            get_daily_queue_for_specialist=lambda day, specialist_id: None,
            get_next_waiting_entry=lambda queue_id: None,
        )
        service = DisplayWebSocketApiService(db=None, repository=repository)

        payload = service.get_department_queue_state_payload(department="cardio")

        assert payload["department"] == "cardio"
        assert payload["total_waiting"] == 1
        assert payload["current_number"] == 3

    @pytest.mark.asyncio
    async def test_quick_call_next_raises_when_doctor_missing(self):
        repository = SimpleNamespace(
            get_queue_entry=lambda entry_id: None,
            save=lambda: None,
            list_active_entries_for_day=lambda day: [],
            get_active_doctor_by_specialty=lambda specialty: None,
            get_daily_queue_for_specialist=lambda day, specialist_id: None,
            get_next_waiting_entry=lambda queue_id: None,
        )
        service = DisplayWebSocketApiService(db=None, repository=repository)

        with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
            await service.quick_call_next(
                specialty="cardio",
                board_id=None,
                current_user=SimpleNamespace(id=1, role="Admin"),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_quick_call_next_uses_doctor_id_for_queue_lookup(self):
        specialist_ids = []

        def get_daily_queue_for_specialist(day, specialist_id):
            specialist_ids.append(specialist_id)
            return SimpleNamespace(id=20, specialist_id=specialist_id)

        repository = SimpleNamespace(
            get_queue_entry=lambda entry_id: None,
            save=lambda: None,
            list_active_entries_for_day=lambda day: [],
            get_active_doctor_by_specialty=lambda specialty: SimpleNamespace(
                id=4,
                user_id=9,
            ),
            get_daily_queue_for_specialist=get_daily_queue_for_specialist,
            get_next_waiting_entry=lambda queue_id: SimpleNamespace(id=33),
        )
        service = DisplayWebSocketApiService(db=None, repository=repository)
        service.call_patient = AsyncMock(return_value={"success": True})

        current_user = SimpleNamespace(id=1, role="Admin")
        result = await service.quick_call_next(
            specialty="cardio",
            board_id="b1",
            current_user=current_user,
        )

        assert result["success"] is True
        assert specialist_ids == [4]
        service.call_patient.assert_awaited_once_with(
            entry_id=33,
            board_ids=["b1"],
            current_user=current_user,
        )

    @pytest.mark.asyncio
    async def test_doctor_quick_call_uses_linked_doctor_id_not_user_id(self):
        specialist_ids = []

        def get_daily_queue_for_specialist(day, specialist_id):
            specialist_ids.append(specialist_id)
            return SimpleNamespace(id=20, specialist_id=specialist_id)

        class Repository:
            def get_active_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, user_id=100, specialty="cardio")

            def get_active_doctor_by_specialty(self, specialty):
                raise AssertionError("doctor users must use their linked profile")

            def get_daily_queue_for_specialist(self, day, specialist_id):
                return get_daily_queue_for_specialist(day, specialist_id)

            def get_next_waiting_entry(self, queue_id):
                return SimpleNamespace(id=33)

        service = DisplayWebSocketApiService(db=None, repository=Repository())
        service.call_patient = AsyncMock(return_value={"success": True})
        current_user = SimpleNamespace(id=100, role="Doctor")

        result = await service.quick_call_next(
            specialty="cardio",
            board_id="b1",
            current_user=current_user,
        )

        assert result["success"] is True
        assert specialist_ids == [7]
        service.call_patient.assert_awaited_once_with(
            entry_id=33,
            board_ids=["b1"],
            current_user=current_user,
        )

    @pytest.mark.asyncio
    async def test_doctor_cannot_quick_call_other_specialty(self):
        class Repository:
            def get_active_doctor_by_specialty(self, specialty):
                return SimpleNamespace(id=4, user_id=9, specialty=specialty)

            def get_active_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, user_id=100, specialty="derma")

            def get_daily_queue_for_specialist(self, day, specialist_id):
                raise AssertionError("foreign specialty must not be queried")

        service = DisplayWebSocketApiService(db=None, repository=Repository())

        with pytest.raises(DisplayWebSocketApiDomainError) as exc_info:
            await service.quick_call_next(
                specialty="cardio",
                board_id="b1",
                current_user=SimpleNamespace(id=100, role="Doctor"),
            )

        assert exc_info.value.status_code == 403
