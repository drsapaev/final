from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.patient_portal_service import (
    PatientPortalDomainError,
    PatientPortalService,
)


@pytest.mark.unit
class TestPatientPortalService:
    def test_get_my_appointment_details_raises_if_not_found(self):
        repository = SimpleNamespace(
            get_patient_appointment=lambda appointment_id, patient_id: None,
        )
        service = PatientPortalService(db=None, repository=repository)

        with pytest.raises(PatientPortalDomainError) as exc_info:
            service.get_my_appointment_details(appointment_id=123, patient_id=456)

        assert exc_info.value.status_code == 404

    def test_get_my_results_returns_repository_rows(self):
        expected = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        repository = SimpleNamespace(
            list_patient_lab_orders=lambda patient_id: expected,
        )
        service = PatientPortalService(db=None, repository=repository)

        result = service.get_my_results(patient_id=7)

        assert result == expected

