from __future__ import annotations

from datetime import date, datetime

import pytest

from app.models.appointment import Appointment
from app.models.lab import LabOrder
from app.repositories.patient_portal_repository import PatientPortalRepository


@pytest.mark.unit
class TestPatientPortalRepository:
    def test_get_patient_appointment_returns_only_patient_owned_row(
        self,
        db_session,
        test_patient,
    ):
        other_patient_id = test_patient.id + 999
        appointment = Appointment(
            patient_id=test_patient.id,
            appointment_date=date.today(),
            appointment_time="09:00",
            status="scheduled",
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)
        repository = PatientPortalRepository(db_session)

        own = repository.get_patient_appointment(
            appointment_id=appointment.id,
            patient_id=test_patient.id,
        )
        other = repository.get_patient_appointment(
            appointment_id=appointment.id,
            patient_id=other_patient_id,
        )

        assert own is not None
        assert own.id == appointment.id
        assert other is None

    def test_list_patient_lab_orders_filters_by_patient(self, db_session, test_patient):
        db_session.add_all(
            [
                LabOrder(
                    patient_id=test_patient.id,
                    status="ordered",
                    notes="one",
                    created_at=datetime.utcnow(),
                ),
                LabOrder(
                    patient_id=test_patient.id + 1,
                    status="ordered",
                    notes="other",
                    created_at=datetime.utcnow(),
                ),
            ]
        )
        db_session.commit()
        repository = PatientPortalRepository(db_session)

        rows = repository.list_patient_lab_orders(patient_id=test_patient.id)

        assert len(rows) == 1
        assert rows[0].notes == "one"
