from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.schemas.patient import PatientCreate
from app.services.patient_service import PatientService


@pytest.mark.unit
class TestPatientService:
    @patch("app.services.patient_service.log_critical_change")
    def test_create_patient_with_full_name(self, mock_audit, db_session, admin_user):
        service = PatientService(db_session)
        payload = PatientCreate(
            full_name="Петров Петр",
            last_name="",
            first_name="",
            phone="+998900000040",
        )

        patient = service.create_patient(
            request=Mock(), patient_in=payload, current_user=admin_user
        )

        assert patient.id is not None
        assert patient.last_name == "Петров"
        assert patient.first_name == "Петр"
        assert patient.phone == "+998900000040"
        assert mock_audit.called

    @patch("app.services.patient_service.log_critical_change")
    def test_create_patient_rejects_duplicate_phone(
        self, mock_audit, db_session, admin_user, test_patient
    ):
        service = PatientService(db_session)
        payload = PatientCreate(
            last_name="Новый",
            first_name="Пациент",
            phone=test_patient.phone,
        )

        with pytest.raises(HTTPException) as exc_info:
            service.create_patient(
                request=Mock(), patient_in=payload, current_user=admin_user
            )

        assert exc_info.value.status_code == 400
        assert "номером телефона" in str(exc_info.value.detail)
        # Fix A: machine-readable code for the registrar wizard contract.
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert detail["code"] == "patient_phone_exists"
        assert "номером телефона" in detail["message"]
        assert not mock_audit.called
