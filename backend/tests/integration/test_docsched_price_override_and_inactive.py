"""DOCSCHED-BE-006/007 catalogue authorization for the doctor visit writers."""

from __future__ import annotations

import math
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.notification_service import NotificationService


def _clinic_today(db_session) -> date:
    from app.crud.clinic import clinic_today

    return clinic_today(db_session)


def _unique_suffix() -> str:
    return uuid4().hex[:10]


def _make_service(
    db_session,
    *,
    price: float = 200000.0,
    allow_override: bool = False,
    active: bool = True,
    is_consultation: bool = False,
) -> Service:
    suffix = _unique_suffix()
    service = Service(
        code=f"DSO{suffix[:6].upper()}",
        name=f"Услуга override {suffix}",
        price=price,
        duration_minutes=30,
        active=active,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=is_consultation,
        allow_doctor_price_override=allow_override,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _make_patient(db_session) -> Patient:
    suffix = _unique_suffix()
    patient = Patient(
        first_name="SYNTHETIC",
        last_name=f"Catalogue{suffix[:4].upper()}",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _prior_context_visit(db_session, *, patient: Patient, doctor: Doctor) -> Visit:
    """Doctor-owned pre-existing visit создаёт patient↔doctor context."""
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=_clinic_today(db_session),
        visit_time="09:00",
        status="open",
        discount_mode="none",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    return visit


def _schedule_payload(patient: Patient, service: Service, *, visit_date, **overrides):
    payload = {
        "patient_id": patient.id,
        "services": [{"service_id": service.id, "quantity": 1}],
        "visit_date": visit_date.isoformat(),
        "visit_time": "10:00",
        "discount_mode": "none",
        "all_free": False,
        "confirmation_channel": "phone",
    }
    payload.update(overrides)
    return payload


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE006ScheduleNextPriceOverrideAuthorization:
    """Schedule-next: произвольная цена — финансовая привилегия сервиса."""

    @pytest.fixture(autouse=True)
    def _spy_invitation(self, monkeypatch):
        async def _spy(self, db, visit_id, channel="auto", *, expected_context=None):
            return {"success": True, "channel": channel}

        monkeypatch.setattr(
            NotificationService, "send_visit_confirmation_invitation", _spy
        )

    @pytest.mark.parametrize("requested_price", [100000, 0])
    def test_different_custom_price_requires_the_flag(
        self, client, db_session, cardio_auth_headers, test_doctor, requested_price
    ):
        service = _make_service(db_session, price=200000.0, allow_override=False)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient,
                service,
                visit_date=visit_date,
                services=[
                    {"service_id": service.id, "quantity": 1, "custom_price": requested_price}
                ],
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code in (400, 422), (
            f"произвольная цена прошла без override-флага: {response.status_code} "
            f"{response.text[:200]}"
        )
        assert not (
            db_session.query(VisitService)
            .join(Visit, Visit.id == VisitService.visit_id)
            .filter(VisitService.service_id == service.id)
            .all()
        ), "отклонённая строка цены не должна персиститься"

    def test_custom_price_on_flagged_service_accepted(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        """Positive control: флаг разрешает произвольную цену (как derma)."""
        service = _make_service(db_session, price=200000.0, allow_override=True)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient,
                service,
                visit_date=visit_date,
                services=[
                    {"service_id": service.id, "quantity": 1, "custom_price": 1}
                ],
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text
        line = (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == response.json()["visit_id"])
            .one()
        )
        assert math.isclose(line.price, 1.0), (
            f"цена флаг-разрешённого override искажена: {line.price}"
        )

    def test_zero_catalogue_price_allowed_without_flag(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, price=0.0, allow_override=False)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient,
                service,
                visit_date=visit_date,
                services=[
                    {"service_id": service.id, "quantity": 1, "custom_price": 0}
                ],
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text
        line = (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == response.json()["visit_id"])
            .one()
        )
        assert line.price == 0, (
            f"осознанный ноль заменён каталогом/отклонён: {line.price}"
        )

    def test_catalogue_equal_custom_price_allowed_without_flag(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        """custom_price == цене каталога — no-op, привилегии не требует."""
        service = _make_service(db_session, price=200000.0, allow_override=False)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(
                patient,
                service,
                visit_date=visit_date,
                services=[
                    {
                        "service_id": service.id,
                        "quantity": 1,
                        "custom_price": 200000.0,
                    }
                ],
            ),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text
        line = (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == response.json()["visit_id"])
            .one()
        )
        assert math.isclose(line.price, 200000.0)


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE007InactiveServiceNotBookable:
    """Schedule-next: выведенная из каталога услуга не бронируется."""

    @pytest.fixture(autouse=True)
    def _spy_invitation(self, monkeypatch):
        async def _spy(self, db, visit_id, channel="auto", *, expected_context=None):
            return {"success": True, "channel": channel}

        monkeypatch.setattr(
            NotificationService, "send_visit_confirmation_invitation", _spy
        )

    def test_inactive_service_rejected_no_visit_rows(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, price=200000.0, active=False)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(patient, service, visit_date=visit_date),
            headers=cardio_auth_headers,
        )
        assert response.status_code in (400, 404, 422), (
            f"неактивная услуга забронирована: {response.status_code} "
            f"{response.text[:200]}"
        )
        assert (
            db_session.query(Visit)
            .filter(
                Visit.patient_id == patient.id,
                Visit.status == "pending_confirmation",
            )
            .all()
            == []
        ), "визит с неактивной услугой не должен создаваться"

    def test_active_service_accepted_positive_control(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, price=200000.0, active=True)
        patient = _make_patient(db_session)
        _prior_context_visit(db_session, patient=patient, doctor=test_doctor)
        visit_date = _clinic_today(db_session) + timedelta(days=1)

        response = client.post(
            "/api/v1/doctor/visits/schedule-next",
            json=_schedule_payload(patient, service, visit_date=visit_date),
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text


@pytest.mark.integration
@pytest.mark.confirmation
class TestDOCSCHEDBE006AddServicePriceOverrideAuthorization:
    """Add-service: тот же байпас на втором входе (audit group 21)."""

    def _visit_for_doctor(self, db_session, test_doctor) -> Visit:
        patient = _make_patient(db_session)
        return _prior_context_visit(db_session, patient=patient, doctor=test_doctor)

    def test_add_service_arbitrary_custom_price_rejected_without_flag(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, price=200000.0, allow_override=False)
        visit = self._visit_for_doctor(db_session, test_doctor)

        response = client.put(
            f"/api/v1/doctor/visits/{visit.id}/add-service",
            params={
                "service_id": service.id,
                "quantity": 1,
                "custom_price": 1,
            },
            headers=cardio_auth_headers,
        )
        assert response.status_code in (400, 422), (
            f"add-service принял произвольную цену без флага: "
            f"{response.status_code} {response.text[:200]}"
        )
        assert (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == visit.id)
            .all()
            == []
        ), "отклонённая строка не должна персиститься"

    def test_add_service_custom_price_on_flagged_service_accepted(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, price=200000.0, allow_override=True)
        visit = self._visit_for_doctor(db_session, test_doctor)

        response = client.put(
            f"/api/v1/doctor/visits/{visit.id}/add-service",
            params={
                "service_id": service.id,
                "quantity": 1,
                "custom_price": 1,
            },
            headers=cardio_auth_headers,
        )
        assert response.status_code == 200, response.text
        line = (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == visit.id)
            .one()
        )
        assert math.isclose(line.price, 1.0)

    def test_inactive_service_cannot_be_added_to_an_existing_visit(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, active=False)
        visit = self._visit_for_doctor(db_session, test_doctor)

        response = client.put(
            f"/api/v1/doctor/visits/{visit.id}/add-service",
            params={"service_id": service.id},
            headers=cardio_auth_headers,
        )

        assert response.status_code == 400, response.text
        assert not db_session.query(VisitService).filter_by(visit_id=visit.id).count()

    def test_flagged_service_price_must_match_the_stored_money_scale(
        self, client, db_session, cardio_auth_headers, test_doctor
    ):
        service = _make_service(db_session, allow_override=True)
        visit = self._visit_for_doctor(db_session, test_doctor)

        response = client.put(
            f"/api/v1/doctor/visits/{visit.id}/add-service",
            params={"service_id": service.id, "custom_price": "1200.125"},
            headers=cardio_auth_headers,
        )

        assert response.status_code == 422, response.text
        assert not db_session.query(VisitService).filter_by(visit_id=visit.id).count()
