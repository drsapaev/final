from __future__ import annotations

import pytest

from app.services.specialized_panels_api_service import (
    SpecializedPanelsApiDomainError,
    SpecializedPanelsApiService,
)


@pytest.mark.unit
class TestSpecializedPanelsApiService:
    def test_get_specialized_patient_history_raises_when_patient_missing(self):
        class Repository:
            def get_patient(self, patient_id):
                return None

        service = SpecializedPanelsApiService(db=None, repository=Repository())

        with pytest.raises(SpecializedPanelsApiDomainError) as exc_info:
            service.get_specialized_patient_history(patient_id=1, department="cardiology")

        assert exc_info.value.status_code == 404

    def test_get_specialized_statistics_calculates_averages(self):
        class Repository:
            def get_specialized_statistics(self, *, start_date, end_date):
                return 2, 200, 4, 100

        service = SpecializedPanelsApiService(db=None, repository=Repository())
        payload = service.get_specialized_statistics(start_date=None, end_date=None)

        assert payload["cardiology"]["average_visit_value"] == 100
        assert payload["dentistry"]["average_visit_value"] == 25
        assert payload["total"]["visits"] == 6
