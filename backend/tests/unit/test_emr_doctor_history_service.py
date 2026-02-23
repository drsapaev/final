from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.emr_doctor_history_service import (
    EMRDoctorHistoryDomainError,
    EMRDoctorHistoryService,
)


@pytest.mark.unit
class TestEMRDoctorHistoryService:
    def test_invalid_field_raises_domain_error(self):
        service = EMRDoctorHistoryService(db=None, repository=SimpleNamespace())

        with pytest.raises(EMRDoctorHistoryDomainError) as exc_info:
            service.get_history_entries(
                doctor_id=1,
                field_name="bad_field",
                search_text=None,
                limit=10,
            )

        assert exc_info.value.status_code == 400

    def test_get_history_entries_formats_payload(self):
        record = SimpleNamespace(
            complaints="Pain in chest",
            diagnosis="I20.0",
            created_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        repository = SimpleNamespace(
            list_records=lambda **kwargs: [record],
        )
        service = EMRDoctorHistoryService(db=None, repository=repository)

        entries = service.get_history_entries(
            doctor_id=1,
            field_name="complaints",
            search_text=None,
            limit=10,
        )

        assert len(entries) == 1
        assert entries[0]["content"] == "Pain in chest"
        assert entries[0]["diagnosis"] == "I20.0"

