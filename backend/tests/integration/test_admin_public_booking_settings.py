"""Admin-only clinic-wide public booking configuration contract."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings, Doctor
from app.models.service import Service
from app.models.user import User

BASE = "/api/v1/admin/public-booking-settings"


def _published_catalog(db_session: Session) -> tuple[Service, Doctor]:
    doctor_user = User(
        username="booking_settings_doctor",
        hashed_password="not-used-in-this-test",
        role="Doctor",
        is_active=True,
        full_name="Test Doctor",
    )
    db_session.add(doctor_user)
    db_session.flush()
    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        active=True,
        show_on_website=True,
        slug="test-doctor",
        bio_ru="Врач-кардиолог",
        bio_uz="Kardiolog shifokor",
    )
    service = Service(
        name="Cardiology consultation",
        name_uz="Kardiolog maslahati",
        description_ru="Приём врача-кардиолога.",
        description_uz="Kardiolog shifokor qabuli.",
        slug="cardiology-consultation",
        duration_minutes=30,
        active=True,
        show_on_website=True,
        requires_doctor=True,
    )
    db_session.add_all([doctor, service])
    db_session.commit()
    db_session.refresh(doctor)
    db_session.refresh(service)
    return service, doctor


@pytest.mark.integration
def test_settings_default_off_and_admin_can_save_ready_configuration(
    client: TestClient, auth_headers, db_session: Session
) -> None:
    service, doctor = _published_catalog(db_session)

    initial = client.get(BASE, headers=auth_headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["is_enabled"] is False
    assert initial.json()["is_ready"] is False
    assert initial.json()["version"] == 0
    assert {item["id"] for item in initial.json()["services"]} >= {service.id}
    assert {item["id"] for item in initial.json()["doctors"]} >= {doctor.id}
    assert next(
        item for item in initial.json()["services"] if item["id"] == service.id
    )["eligible"]
    assert next(item for item in initial.json()["doctors"] if item["id"] == doctor.id)[
        "eligible"
    ]

    saved = client.put(
        BASE,
        headers=auth_headers,
        json={
            "expected_version": 0,
            "is_enabled": True,
            "mode": "registrar_request",
            "booking_horizon_days": 30,
            "service_ids": [service.id],
            "doctor_ids": [doctor.id],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert saved.json()["is_enabled"] is True
    assert saved.json()["is_ready"] is True
    assert saved.json()["mode"] == "registrar_request"
    assert saved.json()["updated_by"] is not None

    stale = client.put(
        BASE,
        headers=auth_headers,
        json={
            "expected_version": 0,
            "is_enabled": False,
            "mode": "registrar_request",
            "booking_horizon_days": 30,
            "service_ids": [service.id],
            "doctor_ids": [doctor.id],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "booking_settings_version_conflict"


@pytest.mark.integration
def test_settings_fail_closed_when_selected_catalog_item_is_no_longer_eligible(
    client: TestClient, auth_headers, db_session: Session
) -> None:
    service, doctor = _published_catalog(db_session)
    saved = client.put(
        BASE,
        headers=auth_headers,
        json={
            "expected_version": 0,
            "is_enabled": True,
            "mode": "confirmed_appointment",
            "booking_horizon_days": 14,
            "service_ids": [service.id],
            "doctor_ids": [doctor.id],
        },
    )
    assert saved.status_code == 200, saved.text

    doctor.active = False
    db_session.commit()
    current = client.get(BASE, headers=auth_headers)
    assert current.status_code == 200, current.text
    assert current.json()["is_enabled"] is True
    assert current.json()["is_ready"] is False
    assert (
        next(item for item in current.json()["doctors"] if item["id"] == doctor.id)[
            "eligible"
        ]
        is False
    )


@pytest.mark.integration
def test_admin_role_is_required_and_generic_settings_cannot_bypass_contract(
    client: TestClient, auth_headers, patient_token: str, db_session: Session
) -> None:
    forbidden = client.get(BASE, headers={"Authorization": f"Bearer {patient_token}"})
    assert forbidden.status_code == 403

    create = client.post(
        "/api/v1/admin/clinic/settings",
        headers=auth_headers,
        json={
            "key": "public_booking_settings",
            "value": {"is_enabled": True},
            "category": "clinic",
        },
    )
    assert create.status_code == 409
    assert create.json()["detail"]["code"] == "use_public_booking_settings_endpoint"

    batch = client.put(
        "/api/v1/admin/clinic/settings",
        headers=auth_headers,
        json={"settings": {"public_booking_settings": {"is_enabled": True}}},
    )
    assert batch.status_code == 409

    db_session.add(
        ClinicSettings(
            key="public_booking_settings",
            value={"version": 1, "is_enabled": False},
            category="booking_settings",
        )
    )
    db_session.commit()
    hidden_list = client.get(
        "/api/v1/admin/clinic/settings?category=booking_settings",
        headers=auth_headers,
    )
    assert hidden_list.status_code == 200
    assert all(item["key"] != "public_booking_settings" for item in hidden_list.json())
    hidden_detail = client.get(
        "/api/v1/admin/clinic/settings/public_booking_settings", headers=auth_headers
    )
    assert hidden_detail.status_code == 404


@pytest.mark.integration
def test_ineligible_catalog_selection_cannot_enable_booking(
    client: TestClient, auth_headers, db_session: Session
) -> None:
    service, doctor = _published_catalog(db_session)
    service.duration_minutes = None
    db_session.commit()

    response = client.put(
        BASE,
        headers=auth_headers,
        json={
            "expected_version": 0,
            "is_enabled": True,
            "mode": "confirmed_appointment",
            "booking_horizon_days": 14,
            "service_ids": [service.id],
            "doctor_ids": [doctor.id],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "booking_settings_incomplete"
