from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.enums import AppointmentStatus
from app.services.appointment_flow_api_service import (
    AppointmentFlowApiDomainError,
    AppointmentFlowApiService,
)


@pytest.mark.unit
class TestAppointmentFlowApiService:
    def test_resolve_appointment_from_visit_sets_emr_appointment_id(self):
        visit = SimpleNamespace(id=10, patient_id=1, doctor_id=2, visit_date=None)
        existing_appointment = SimpleNamespace(id=77)
        emr_data = SimpleNamespace(appointment_id=0)

        class Repository:
            def get_visit(self, visit_id):
                return visit

            def get_existing_appointment_for_visit(self, visit_obj):
                return existing_appointment

            def create_appointment_from_visit(self, visit_obj):
                raise AssertionError("must not create appointment")

        service = AppointmentFlowApiService(db=None, repository=Repository())
        resolved, resolved_visit = service.resolve_appointment_from_visit(
            appointment_id=10,
            emr_data=emr_data,
        )

        assert resolved is existing_appointment
        assert resolved_visit is visit
        assert emr_data.appointment_id == 77

    def test_resolve_appointment_from_visit_raises_when_visit_missing(self):
        class Repository:
            def get_visit(self, visit_id):
                return None

        service = AppointmentFlowApiService(db=None, repository=Repository())

        with pytest.raises(AppointmentFlowApiDomainError):
            service.resolve_appointment_from_visit(
                appointment_id=123,
                emr_data=SimpleNamespace(appointment_id=0),
            )

    def test_promote_appointment_to_in_visit_commits_and_refreshes(self):
        state = {"committed": False, "refreshed": False}
        appointment = SimpleNamespace(status="called")

        class Repository:
            def commit(self):
                state["committed"] = True

            def refresh(self, instance):
                state["refreshed"] = True
                assert instance is appointment

        service = AppointmentFlowApiService(db=None, repository=Repository())
        service.promote_appointment_to_in_visit(appointment=appointment)

        assert appointment.status == AppointmentStatus.IN_VISIT
        assert state["committed"] is True
        assert state["refreshed"] is True
