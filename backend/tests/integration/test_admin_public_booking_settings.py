"""Admin-only clinic-wide public booking configuration contract."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings, Doctor
from app.models.online_queue import QueueResource
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


def _published_doctor(
    db_session: Session, *, username: str, full_name: str, specialty: str
) -> Doctor:
    owner = User(
        username=username,
        hashed_password="not-used-in-this-test",
        role="Doctor",
        is_active=True,
        full_name=full_name,
    )
    db_session.add(owner)
    db_session.flush()
    doctor = Doctor(
        user_id=owner.id,
        specialty=specialty,
        active=True,
        show_on_website=True,
        slug=f"{username.replace('_', '-')}-profile",
        bio_ru="Врач клиники.",
        bio_uz="Klinika shifokori.",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


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


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("role", "Registrar"),
        ("role", "Cashier"),
        ("role", "Lab"),
        ("specialty", "general"),
        ("specialty", "   "),
    ],
)
def test_doctor_options_require_doctor_role_and_completed_profile(
    client: TestClient,
    auth_headers,
    db_session: Session,
    field: str,
    value: str,
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

    owner = db_session.get(User, doctor.user_id)
    assert owner is not None
    if field == "role":
        owner.role = value
    else:
        doctor.specialty = value
    db_session.commit()

    response = client.get(BASE, headers=auth_headers)

    assert response.status_code == 200, response.text
    option = next(
        item for item in response.json()["doctors"] if item["id"] == doctor.id
    )
    assert option["eligible"] is False
    assert response.json()["is_ready"] is False


@pytest.mark.integration
@pytest.mark.parametrize(
    ("requires_doctor", "is_consultation", "queue_tag"),
    [
        (False, False, None),
        (False, True, None),
    ],
)
def test_service_must_follow_doctor_booking_contract(
    client: TestClient,
    auth_headers,
    db_session: Session,
    requires_doctor: bool,
    is_consultation: bool,
    queue_tag: str | None,
) -> None:
    service, _ = _published_catalog(db_session)
    service.requires_doctor = requires_doctor
    service.is_consultation = is_consultation
    service.queue_tag = queue_tag
    db_session.commit()

    response = client.get(BASE, headers=auth_headers)

    assert response.status_code == 200, response.text
    option = next(
        item for item in response.json()["services"] if item["id"] == service.id
    )
    assert option["eligible"] is False


@pytest.mark.integration
def test_resource_owned_service_is_not_bookable_as_doctor_appointment(
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

    service.queue_tag = "booking-test-ecg"
    db_session.add(
        QueueResource(
            code="booking_test_ecg",
            queue_tag="booking-test-ecg",
            display_name="Test ECG Resource",
            active=True,
        )
    )
    db_session.commit()

    response = client.get(BASE, headers=auth_headers)

    assert response.status_code == 200, response.text
    option = next(
        item for item in response.json()["services"] if item["id"] == service.id
    )
    assert option["eligible"] is False
    assert response.json()["is_ready"] is False


@pytest.mark.integration
def test_pinned_service_requires_its_selected_doctor(
    client: TestClient, auth_headers, db_session: Session
) -> None:
    service, doctor = _published_catalog(db_session)
    other_doctor = _published_doctor(
        db_session,
        username="booking_settings_other_doctor",
        full_name="Other Test Doctor",
        specialty="dermatology",
    )
    service.doctor_id = doctor.id
    db_session.commit()

    mismatched = client.put(
        BASE,
        headers=auth_headers,
        json={
            "expected_version": 0,
            "is_enabled": True,
            "mode": "confirmed_appointment",
            "booking_horizon_days": 14,
            "service_ids": [service.id],
            "doctor_ids": [other_doctor.id],
        },
    )
    assert mismatched.status_code == 422
    assert mismatched.json()["detail"]["code"] == "booking_settings_incomplete"

    matching = client.put(
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
    assert matching.status_code == 200, matching.text
    assert matching.json()["is_ready"] is True


@pytest.mark.integration
def test_department_service_requires_a_compatible_selected_specialty(
    client: TestClient, auth_headers, db_session: Session
) -> None:
    service, _ = _published_catalog(db_session)
    service.department_key = "cardiology"
    dermatologist = _published_doctor(
        db_session,
        username="booking_settings_dermatologist",
        full_name="Test Dermatologist",
        specialty="dermatology",
    )
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
            "doctor_ids": [dermatologist.id],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "booking_settings_incomplete"
