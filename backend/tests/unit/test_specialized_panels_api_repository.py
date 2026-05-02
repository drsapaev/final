from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.repositories.specialized_panels_api_repository import (
    SpecializedPanelsApiRepository,
)


def _create_patient(db_session, *, first_name: str, last_name: str, phone: str) -> Patient:
    patient = Patient(first_name=first_name, last_name=last_name, phone=phone)
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_visit(db_session, *, patient_id: int, department: str) -> Visit:
    visit = Visit(
        patient_id=patient_id,
        status="open",
        discount_mode="none",
        department=department,
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _attach_service(
    db_session,
    *,
    visit_id: int,
    name: str,
    code: str,
    queue_tag: str,
    service_code: str,
    price: Decimal = Decimal("100000"),
) -> Service:
    service = Service(
        name=name,
        code=code,
        queue_tag=queue_tag,
        service_code=service_code,
        price=price,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    visit_service = VisitService(
        visit_id=visit_id,
        service_id=service.id,
        code=code,
        name=name,
        price=price,
        qty=1,
    )
    db_session.add(visit_service)
    db_session.commit()
    return service


@pytest.mark.unit
class TestSpecializedPanelsApiRepository:
    def test_list_cardiology_patients_handles_explicit_visit_service_join_and_search(
        self, db_session
    ):
        patient = _create_patient(
            db_session,
            first_name="Иван",
            last_name="Иванов",
            phone="+998900000001",
        )
        visit = _create_visit(db_session, patient_id=patient.id, department="Кардиология")
        _attach_service(
            db_session,
            visit_id=visit.id,
            name="ЭКГ",
            code="K10",
            queue_tag="ecg",
            service_code="K10",
        )
        repository = SpecializedPanelsApiRepository(db_session)

        patients, total = repository.list_cardiology_patients(
            skip=0,
            limit=10,
            search="Иванов Иван",
        )

        assert total == 1
        assert [row.id for row in patients] == [patient.id]

    def test_list_dentistry_patients_handles_explicit_visit_service_join(
        self, db_session
    ):
        patient = _create_patient(
            db_session,
            first_name="Саида",
            last_name="Алиева",
            phone="+998900000002",
        )
        visit = _create_visit(db_session, patient_id=patient.id, department="Стоматология")
        _attach_service(
            db_session,
            visit_id=visit.id,
            name="Рентгенография зуба",
            code="S10",
            queue_tag="stomatology",
            service_code="S10",
        )
        repository = SpecializedPanelsApiRepository(db_session)

        patients, total = repository.list_dentistry_patients(
            skip=0,
            limit=10,
            search=None,
        )

        assert total == 1
        assert [row.id for row in patients] == [patient.id]

    def test_get_cardiology_analytics_uses_visit_service_revenue(self, db_session):
        patient = _create_patient(
            db_session,
            first_name="Карим",
            last_name="Тестов",
            phone="+998900000003",
        )
        visit = _create_visit(db_session, patient_id=patient.id, department="cardiology")
        _attach_service(
            db_session,
            visit_id=visit.id,
            name="Консультация кардиолога",
            code="K01",
            queue_tag="cardio",
            service_code="K01",
            price=Decimal("150000"),
        )
        repository = SpecializedPanelsApiRepository(db_session)

        total_visits, total_revenue, status_stats, daily_stats = (
            repository.get_cardiology_analytics(start_date=None, end_date=None)
        )

        assert total_visits == 1
        assert float(total_revenue) == 150000.0
        assert status_stats[0].count == 1
        assert daily_stats[0].visits == 1

