import pytest
from pydantic import ValidationError

from app.crud import clinic as crud_clinic
from app.models.clinic import ClinicSettings
from app.schemas.clinic import TicketPrintSettingsUpdate


from tests.auth_test_credentials import (
    REGISTRAR_PASSWORD,
)

def test_ticket_print_settings_defaults_when_missing(db_session):
    settings = crud_clinic.get_ticket_print_settings(db_session)

    assert settings == crud_clinic.TICKET_PRINT_SETTINGS_DEFAULTS


def test_ticket_print_settings_update_merges_partial_values(db_session, admin_user):
    settings = crud_clinic.update_ticket_print_settings(
        db_session,
        {
            "show_logo": True,
            "show_patient_name": True,
            "show_qr_code": True,
        },
        admin_user.id,
    )

    assert settings["show_logo"] is True
    assert settings["show_patient_name"] is True
    assert settings["show_qr_code"] is True
    assert settings["show_clinic_name"] is True
    assert settings["show_price"] is False

    stored_settings = {
        setting.key: setting.value
        for setting in db_session.query(ClinicSettings)
        .filter(ClinicSettings.category == crud_clinic.TICKET_PRINT_SETTINGS_CATEGORY)
        .all()
    }

    assert stored_settings["ticket_print_show_logo"] is True
    assert stored_settings["ticket_print_show_patient_name"] is True
    assert stored_settings["ticket_print_show_qr_code"] is True
    assert "bogus" not in stored_settings


def test_ticket_print_settings_schema_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        TicketPrintSettingsUpdate(show_logo=True, unexpected=True)


def test_ticket_print_settings_get_is_available_to_active_staff(client, registrar_user):
    login_response = client.post(
        "/api/v1/auth/minimal-login",
        json={"username": registrar_user.username, "password": REGISTRAR_PASSWORD},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/admin/clinic/ticket-print-settings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["show_clinic_name"] is True
    assert body["show_queue_number"] is True


def test_ticket_print_settings_put_remains_admin_only(client, registrar_user):
    login_response = client.post(
        "/api/v1/auth/minimal-login",
        json={"username": registrar_user.username, "password": REGISTRAR_PASSWORD},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.put(
        "/api/v1/admin/clinic/ticket-print-settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"show_logo": True},
    )

    assert response.status_code == 403


def test_clinic_settings_list_is_available_to_active_staff(client, registrar_user):
    login_response = client.post(
        "/api/v1/auth/minimal-login",
        json={"username": registrar_user.username, "password": REGISTRAR_PASSWORD},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/admin/clinic/settings",
        params={"category": "clinic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
