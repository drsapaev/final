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
        assert not mock_audit.called
        # E-054 leftover 3: структурный detail {code, message} — код
        # машиночитаем, человекочитаемый текст сохранён (str(detail)-паттерн
        # прежних потребителей продолжает работать).
        assert exc_info.value.detail["code"] == "patient_phone_exists"
        assert exc_info.value.detail["message"] == "Пациент с таким номером телефона уже существует"

    @patch("app.services.patient_service.log_critical_change")
    def test_create_patient_rejects_duplicate_doc_number(
        self, mock_audit, db_session, admin_user, test_patient
    ):
        """E-054 leftover 3: дубликат документа несёт код patient_doc_exists."""
        service = PatientService(db_session)
        test_patient.doc_number = "AA1234567"
        db_session.commit()
        payload = PatientCreate(
            last_name="Новый",
            first_name="Пациент",
            doc_number="AA1234567",
        )

        with pytest.raises(HTTPException) as exc_info:
            service.create_patient(
                request=Mock(), patient_in=payload, current_user=admin_user
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "patient_doc_exists"
        assert "номером документа" in exc_info.value.detail["message"]

    @patch("app.services.patient_service.log_critical_change")
    def test_update_patient_rejects_duplicate_phone(
        self, mock_audit, db_session, admin_user, test_patient
    ):
        """E-054 leftover 3: дубликат телефона при update — тот же код."""
        from app.schemas.patient import PatientUpdate

        service = PatientService(db_session)
        other = PatientCreate(
            last_name="Другой",
            first_name="Пациент",
            phone="+998900000099",
        )
        created = service.create_patient(
            request=Mock(), patient_in=other, current_user=admin_user
        )

        payload = PatientUpdate(phone=test_patient.phone)
        with pytest.raises(HTTPException) as exc_info:
            service.update_patient(
                request=Mock(),
                patient_id=created.id,
                patient_in=payload,
                current_user=admin_user,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "patient_phone_exists"
