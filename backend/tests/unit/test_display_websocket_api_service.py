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
            await service.call_patient(entry_id=1, board_ids=[])

        assert exc_info.value.status_code == 404

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
            await service.quick_call_next(specialty="cardio", board_id=None)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_quick_call_next_delegates_to_call_patient(self):
        repository = SimpleNamespace(
            get_queue_entry=lambda entry_id: None,
            save=lambda: None,
            list_active_entries_for_day=lambda day: [],
            get_active_doctor_by_specialty=lambda specialty: SimpleNamespace(
                id=4,
                user_id=9,
            ),
            get_daily_queue_for_specialist=lambda day, specialist_id: SimpleNamespace(
                id=20,
            ),
            get_next_waiting_entry=lambda queue_id: SimpleNamespace(id=33),
        )
        service = DisplayWebSocketApiService(db=None, repository=repository)
        service.call_patient = AsyncMock(return_value={"success": True})

        result = await service.quick_call_next(specialty="cardio", board_id="b1")

        assert result["success"] is True
        service.call_patient.assert_awaited_once_with(entry_id=33, board_ids=["b1"])
