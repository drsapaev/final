"""Validation tests for the Admin public-booking settings contract."""

import pytest
from pydantic import ValidationError

from app.schemas.public_booking_settings import PublicBookingSettingsUpdate


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("service_ids", [1, 1]),
        ("doctor_ids", [2, 2]),
        ("service_ids", [0]),
        ("doctor_ids", [-1]),
    ],
)
def test_settings_reject_duplicate_or_non_positive_ids(field, values) -> None:
    payload = {
        "expected_version": 0,
        "is_enabled": False,
        "mode": None,
        "booking_horizon_days": None,
        "service_ids": [1],
        "doctor_ids": [2],
    }
    payload[field] = values
    with pytest.raises(ValidationError):
        PublicBookingSettingsUpdate.model_validate(payload)


def test_settings_reject_unknown_fields_and_out_of_range_horizon() -> None:
    payload = {
        "expected_version": 0,
        "is_enabled": False,
        "mode": None,
        "booking_horizon_days": 366,
        "service_ids": [],
        "doctor_ids": [],
    }
    with pytest.raises(ValidationError):
        PublicBookingSettingsUpdate.model_validate(payload)

    payload["booking_horizon_days"] = 30
    payload["internal_note"] = "must not be accepted"
    with pytest.raises(ValidationError):
        PublicBookingSettingsUpdate.model_validate(payload)
