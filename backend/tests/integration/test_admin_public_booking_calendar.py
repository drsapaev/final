"""Admin-managed public-booking calendar contract and fail-closed behavior."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services.public_booking_calendar_settings import (
    PublicBookingCalendarSettingsService,
)

BASE = "/api/v1/admin/public-booking-calendar"


@pytest.mark.integration
def test_admin_can_edit_confirm_and_reopen_explicit_working_holiday(
    client: TestClient, auth_headers, db_session
) -> None:
    missing = client.get(f"{BASE}/2091", headers=auth_headers)
    assert missing.status_code == 200
    assert missing.json() == {
        "year": 2091,
        "version": 0,
        "is_confirmed": False,
        "holidays": [],
        "confirmed_at": None,
        "confirmed_by": None,
        "updated_at": None,
        "updated_by": None,
    }

    saved = client.put(
        f"{BASE}/2091",
        headers=auth_headers,
        json={
            "expected_version": 0,
            "holidays": [
                {"date": "2091-01-01", "is_working_day": False},
                {"date": "2091-03-08", "is_working_day": True},
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1
    assert saved.json()["is_confirmed"] is False
    assert saved.json()["updated_by"] is not None

    confirmed = client.post(
        f"{BASE}/2091/confirm",
        headers=auth_headers,
        json={"expected_version": 1},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["version"] == 2
    assert confirmed.json()["is_confirmed"] is True
    assert confirmed.json()["confirmed_at"] is not None
    assert confirmed.json()["confirmed_by"] == confirmed.json()["updated_by"]

    calendar_service = PublicBookingCalendarSettingsService(db_session)
    calendar = calendar_service.load_policy_calendar()
    assert 2091 in calendar.confirmed_years
    assert not calendar.permits_date(date(2091, 1, 1))
    assert calendar.permits_date(date(2091, 3, 8))

    changed = client.put(
        f"{BASE}/2091",
        headers=auth_headers,
        json={
            "expected_version": 2,
            "holidays": [{"date": "2091-01-01", "is_working_day": True}],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 3
    assert changed.json()["is_confirmed"] is False
    assert changed.json()["confirmed_at"] is None
    assert 2091 not in calendar_service.load_policy_calendar().confirmed_years


@pytest.mark.integration
def test_calendar_rejects_stale_versions_and_dates_outside_the_year(
    client: TestClient, auth_headers
) -> None:
    first = client.put(
        f"{BASE}/2092",
        headers=auth_headers,
        json={"expected_version": 0, "holidays": []},
    )
    assert first.status_code == 200, first.text

    stale = client.put(
        f"{BASE}/2092",
        headers=auth_headers,
        json={"expected_version": 0, "holidays": []},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "booking_calendar_version_conflict"

    outside_year = client.put(
        f"{BASE}/2092",
        headers=auth_headers,
        json={
            "expected_version": 1,
            "holidays": [{"date": "2093-01-01", "is_working_day": False}],
        },
    )
    assert outside_year.status_code == 422
    assert outside_year.json()["detail"]["code"] == "booking_calendar_date_outside_year"


@pytest.mark.integration
def test_generic_clinic_settings_endpoints_cannot_mutate_reserved_calendar_keys(
    client: TestClient, auth_headers
) -> None:
    key = "public_booking_calendar_year_2094"

    create = client.post(
        "/api/v1/admin/clinic/settings",
        headers=auth_headers,
        json={"key": key, "value": {"is_confirmed": True}, "category": "clinic"},
    )
    assert create.status_code == 409

    batch = client.put(
        "/api/v1/admin/clinic/settings",
        headers=auth_headers,
        json={"settings": {key: {"is_confirmed": True}}},
    )
    assert batch.status_code == 409

    client.put(
        f"{BASE}/2094",
        headers=auth_headers,
        json={"expected_version": 0, "holidays": []},
    )
    update = client.put(
        f"/api/v1/admin/clinic/settings/{key}",
        headers=auth_headers,
        json={"value": {"is_confirmed": True}},
    )
    assert update.status_code == 409


@pytest.mark.integration
def test_calendar_management_is_admin_only(
    client: TestClient, registrar_auth_headers
) -> None:
    response = client.get(f"{BASE}/2095", headers=registrar_auth_headers)
    assert response.status_code == 403
