"""Registrar doctor-selection contract for consultations and named clinicians."""

from __future__ import annotations

from datetime import date

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, QueueResource
from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration


def _headers(admin_user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _consultation(
    db_session,
    *,
    code: str,
    queue_tag: str | None = None,
    department_key: str = "cardio",
) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name="Консультация кардиолога",
        department_key=department_key,
        queue_tag=queue_tag,
        price=50000,
        active=True,
        requires_doctor=False,
        is_consultation=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _doctor(db_session, *, username: str, name: str | None, specialty: str = "cardiology", active: bool = True) -> Doctor:
    user = User(
        username=username,
        full_name=name,
        hashed_password="unused-test-hash",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(user_id=user.id, specialty=specialty, active=active)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _cart(patient_id: int, service_id: int, doctor_id: int | None) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": [
            {
                "doctor_id": doctor_id,
                "visit_date": date.today().isoformat(),
                "department": "cardio",
                "services": [{"service_id": service_id, "quantity": 1}],
            }
        ],
    }


def _rows(client, headers: dict[str, str]) -> dict[int, dict]:
    response = client.get("/api/v1/registrar/services", headers=headers)
    assert response.status_code == 200, response.text
    return {
        row["id"]: row
        for group in response.json()["services_by_group"].values()
        for row in group
    }


def test_consultation_requires_doctor_selection_without_changing_queue_flag(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC01")
    row = _rows(client, _headers(admin_user))[service.id]
    assert row["requires_doctor"] is False
    assert row["is_consultation"] is True
    assert row["doctor_selection_required"] is True

    before_visits = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()
    before_invoices = db_session.query(PaymentInvoice).filter(PaymentInvoice.patient_id == test_patient.id).count()
    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, None),
    )
    assert response.status_code == 400, response.text
    assert "требует выбора врача" in response.json()["detail"]
    assert db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == before_visits
    assert db_session.query(PaymentInvoice).filter(PaymentInvoice.patient_id == test_patient.id).count() == before_invoices


def test_consultation_without_queue_flag_checks_specialty_and_accepts_real_doctor(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC02", queue_tag="cardio")
    wrong = _doctor(db_session, username="rdc_wrong", name="Тестовый Стоматолог", specialty="dentistry")
    correct = _doctor(db_session, username="rdc_correct", name="Тестовый Кардиолог")

    rejected = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, wrong.id),
    )
    assert rejected.status_code == 400, rejected.text
    assert "не подходит" in rejected.json()["detail"]

    accepted = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, correct.id),
    )
    assert accepted.status_code == 200, accepted.text
    visit = db_session.get(Visit, accepted.json()["visit_ids"][0])
    assert visit.doctor_id == correct.id


def test_consultation_without_queue_tag_is_not_saved_without_queue(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC04")
    doctor = _doctor(db_session, username="rdc_no_tag_doc", name="Тестовый Кардиолог")
    before = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert response.status_code == 409, response.text
    assert "тег очереди" in response.json()["detail"]
    assert db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == before


def test_resource_owned_consultation_fails_closed_before_cart_write(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC03", queue_tag="rdc_resource")
    db_session.add(
        QueueResource(
            code="rdc_resource",
            queue_tag="rdc_resource",
            display_name="Тестовый ресурс",
            active=True,
        )
    )
    db_session.commit()
    doctor = _doctor(db_session, username="rdc_resource_doc", name="Тестовый Кардиолог")
    before = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert response.status_code == 409, response.text
    assert "ресурсная" in response.json()["detail"]
    assert db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == before


def test_deactivated_resource_keeps_existing_day_surface_out_of_doctor_cart(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC08", queue_tag="rdc_day_resource")
    resource = QueueResource(
        code="rdc_day_resource",
        queue_tag="rdc_day_resource",
        display_name="Тестовый ресурс",
        active=False,
    )
    db_session.add(resource)
    db_session.flush()
    db_session.add(
        DailyQueue(
            day=date.today(),
            queue_tag=service.queue_tag,
            queue_resource_id=resource.id,
            active=True,
        )
    )
    db_session.commit()
    doctor = _doctor(db_session, username="rdc_day_resource_doc", name="Тестовый Кардиолог")
    before = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert response.status_code == 409, response.text
    assert "ресурсная" in response.json()["detail"]
    assert db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == before


def test_catalog_marks_consultations_without_doctor_queue_unavailable(
    client, db_session, admin_user
):
    missing_tag = _consultation(db_session, code="RDC08")
    doctor_queue = _consultation(db_session, code="RDC09", queue_tag="cardio")
    resource_queue = _consultation(db_session, code="RDC10", queue_tag="rdc_book_resource")
    inactive_resource = _consultation(db_session, code="RDC11", queue_tag="rdc_book_inactive")
    ordinary_service = Service(
        code="RDC12",
        service_code="RDC12",
        name="Анализ",
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add_all(
        [
            QueueResource(
                code="rdc_book_resource",
                queue_tag="rdc_book_resource",
                display_name="Активный ресурс",
                active=True,
            ),
            QueueResource(
                code="rdc_book_inactive",
                queue_tag="rdc_book_inactive",
                display_name="Неактивный ресурс",
                active=False,
            ),
            ordinary_service,
        ]
    )
    db_session.commit()

    rows = _rows(client, _headers(admin_user))
    assert rows[missing_tag.id]["doctor_booking_available"] is False
    assert rows[doctor_queue.id]["doctor_booking_available"] is True
    assert rows[resource_queue.id]["doctor_booking_available"] is False
    assert rows[inactive_resource.id]["doctor_booking_available"] is True
    assert rows[ordinary_service.id]["doctor_booking_available"] is True


def test_registrar_doctors_returns_all_named_eligible_doctors_after_first_page(
    client, db_session, admin_user
):
    doctors = [
        _doctor(db_session, username=f"rdc_page_{index}", name=f"Фамилия{index} Имя{index}")
        for index in range(101)
    ]
    unnamed = _doctor(db_session, username="rdc_unnamed", name=" ")
    inactive = _doctor(db_session, username="rdc_inactive", name="Фамилия Имя", active=False)

    response = client.get(
        "/api/v1/registrar/doctors",
        params={"with_schedule": False},
        headers=_headers(admin_user),
    )
    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()["doctors"]}
    assert all(doctor.id in rows for doctor in doctors)
    assert rows[doctors[-1].id]["full_name"] == "Фамилия100 Имя100"
    assert rows[doctors[-1].id]["user"]["full_name"] == "Фамилия100 Имя100"
    assert unnamed.id not in rows
    assert inactive.id not in rows


def test_inactive_owner_is_hidden_and_cannot_be_selected_by_id(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC05", queue_tag="cardio")
    doctor = _doctor(db_session, username="rdc_inactive_owner", name="Тестовый Кардиолог")
    doctor.user.is_active = False
    db_session.commit()

    response = client.get(
        "/api/v1/registrar/doctors",
        params={"with_schedule": False},
        headers=_headers(admin_user),
    )
    assert response.status_code == 200, response.text
    assert doctor.id not in {row["id"] for row in response.json()["doctors"]}

    rejected = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert rejected.status_code == 409, rejected.text
    assert "Профиль врача" in rejected.json()["detail"]


def test_internal_resource_owner_is_hidden_and_cannot_be_selected_by_id(
    client, db_session, admin_user, test_patient
):
    service = _consultation(db_session, code="RDC07", queue_tag="cardio")
    doctor = _doctor(db_session, username="rdc_resource_owner", name="Тестовый Кардиолог")
    doctor.user.role = "Resource"
    db_session.commit()

    response = client.get(
        "/api/v1/registrar/doctors",
        params={"with_schedule": False},
        headers=_headers(admin_user),
    )
    assert response.status_code == 200, response.text
    assert doctor.id not in {row["id"] for row in response.json()["doctors"]}

    rejected = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert rejected.status_code == 409, rejected.text


def test_legacy_cardiology_common_matches_russian_doctor_specialty(
    client, db_session, admin_user, test_patient
):
    service = _consultation(
        db_session,
        code="RDC06",
        queue_tag="cardiology_common",
        department_key="cardiology_common",
    )
    doctor = _doctor(
        db_session,
        username="rdc_legacy_cardio",
        name="Тестовый Кардиолог",
        specialty="Кардиология",
    )

    doctors = client.get(
        "/api/v1/registrar/doctors",
        params={"specialty": "cardiology_common", "with_schedule": False},
        headers=_headers(admin_user),
    )
    assert doctors.status_code == 200, doctors.text
    assert doctor.id in {row["id"] for row in doctors.json()["doctors"]}

    saved = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json=_cart(test_patient.id, service.id, doctor.id),
    )
    assert saved.status_code == 200, saved.text
