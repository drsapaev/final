from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.registrar_notifications_api_service import (
    RegistrarNotificationsApiDomainError,
    RegistrarNotificationsApiService,
)


@pytest.mark.unit
class TestRegistrarNotificationsApiService:
    def test_get_appointment_context_raises_when_appointment_missing(self):
        class Repository:
            def get_visit(self, visit_id):
                return None

            def get_appointment(self, appointment_id):
                return None

        service = RegistrarNotificationsApiService(db=None, repository=Repository())

        with pytest.raises(RegistrarNotificationsApiDomainError) as exc_info:
            service.get_appointment_context(appointment_id=1, appointment_type="visit")

        assert exc_info.value.status_code == 404

    def test_get_queue_entry_raises_when_missing(self):
        class Repository:
            def get_queue_entry(self, queue_entry_id):
                return None

        service = RegistrarNotificationsApiService(db=None, repository=Repository())

        with pytest.raises(RegistrarNotificationsApiDomainError):
            service.get_queue_entry(queue_entry_id=99)

    def test_get_price_change_context_returns_entities(self):
        price_override = SimpleNamespace(id=1, doctor_id=2, service_id=3, visit_id=4)
        doctor = SimpleNamespace(id=2)
        service_obj = SimpleNamespace(id=3)
        visit = SimpleNamespace(id=4, patient_id=7)
        patient = SimpleNamespace(id=7)

        class Repository:
            def get_price_override(self, price_override_id):
                return price_override

            def get_doctor(self, doctor_id):
                return doctor

            def get_service(self, service_id):
                return service_obj

            def get_visit(self, visit_id):
                return visit

            def get_patient(self, patient_id):
                return patient

        service = RegistrarNotificationsApiService(db=None, repository=Repository())
        result = service.get_price_change_context(price_override_id=1)

        assert result == (price_override, doctor, service_obj, visit, patient)
