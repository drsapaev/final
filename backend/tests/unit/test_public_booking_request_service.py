from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.public_booking_settings import (
    PublicBookingOptionOut,
    PublicBookingSettingsOut,
)
from app.services.public_booking_request_service import (
    PublicBookingRequestError,
    PublicBookingRequestService,
)


def test_idempotency_hash_is_stable_patient_scoped_and_does_not_retain_key():
    service = object.__new__(PublicBookingRequestService)
    payload = {"operation": "create", "time": "09:00"}
    create_scope = "POST:/api/v1/patients/booking-requests"

    key_hash, payload_hash = service._idempotency_hashes(
        patient_id=12,
        idempotency_key="opaque-client-key",
        operation_scope=create_scope,
        payload=payload,
    )
    repeated_key_hash, repeated_payload_hash = service._idempotency_hashes(
        patient_id=12,
        idempotency_key="opaque-client-key",
        operation_scope=create_scope,
        payload={"time": "09:00", "operation": "create"},
    )
    other_patient_key_hash, _ = service._idempotency_hashes(
        patient_id=13,
        idempotency_key="opaque-client-key",
        operation_scope=create_scope,
        payload=payload,
    )
    other_operation_key_hash, _ = service._idempotency_hashes(
        patient_id=12,
        idempotency_key="opaque-client-key",
        operation_scope=(
            "POST:/api/v1/patients/booking-requests/"
            "00000000-0000-0000-0000-000000000001/resubmit"
        ),
        payload=payload,
    )

    assert len(key_hash) == 64
    assert "opaque-client-key" not in key_hash
    assert key_hash == repeated_key_hash
    assert payload_hash == repeated_payload_hash
    assert key_hash != other_patient_key_hash
    assert key_hash != other_operation_key_hash


def test_existing_request_confirmation_ignores_new_intake_mode_and_toggle():
    settings = PublicBookingSettingsOut(
        version=2,
        is_enabled=False,
        is_ready=False,
        mode=None,
        booking_horizon_days=None,
        service_ids=[11],
        doctor_ids=[22],
        services=[PublicBookingOptionOut(id=11, label="service", eligible=True)],
        doctors=[PublicBookingOptionOut(id=22, label="doctor", eligible=True)],
    )

    confirmation_settings = PublicBookingRequestService._settings_for_existing_request(
        settings=settings,
        service_id=11,
        doctor_id=22,
    )

    assert confirmation_settings.is_enabled is True
    assert confirmation_settings.is_ready is True
    assert confirmation_settings.booking_horizon_days == 365
    assert confirmation_settings.mode is None
    assert confirmation_settings.version == 2


@pytest.mark.parametrize(
    ("service_ids", "doctor_ids", "service_eligible", "doctor_eligible"),
    [
        ([11], [22], False, True),
        ([12], [22], True, True),
        ([11], [23], True, True),
        ([11], [22], True, False),
    ],
)
def test_existing_request_confirmation_requires_current_allowlist_eligibility(
    service_ids, doctor_ids, service_eligible, doctor_eligible
):
    settings = PublicBookingSettingsOut(
        version=3,
        is_enabled=False,
        is_ready=False,
        mode=None,
        booking_horizon_days=None,
        service_ids=service_ids,
        doctor_ids=doctor_ids,
        services=[
            PublicBookingOptionOut(id=11, label="service", eligible=service_eligible)
        ],
        doctors=[
            PublicBookingOptionOut(id=22, label="doctor", eligible=doctor_eligible)
        ],
    )

    with pytest.raises(PublicBookingRequestError) as exc_info:
        PublicBookingRequestService._settings_for_existing_request(
            settings=settings,
            service_id=11,
            doctor_id=22,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "booking_request_unavailable"


def test_idempotent_request_returns_same_patient_request():
    request = SimpleNamespace(id=uuid4(), patient_id=12)
    event = SimpleNamespace(request=request, payload_hash="payload-hash")
    service = object.__new__(PublicBookingRequestService)
    service.repository = SimpleNamespace(
        get_event_by_idempotency_key_hash=lambda _key: event
    )

    assert (
        service._idempotent_request(
            key_hash="key-hash",
            payload_hash="payload-hash",
            patient_id=12,
        )
        is request
    )


@pytest.mark.parametrize(
    ("patient_id", "request_id", "payload_hash"),
    [
        (13, None, "payload-hash"),
        (12, uuid4(), "payload-hash"),
        (12, None, "different-payload"),
    ],
)
def test_idempotent_request_rejects_key_reuse_with_different_scope_or_payload(
    patient_id: int, request_id, payload_hash: str
):
    request = SimpleNamespace(id=uuid4(), patient_id=12)
    event = SimpleNamespace(request=request, payload_hash="payload-hash")
    service = object.__new__(PublicBookingRequestService)
    service.repository = SimpleNamespace(
        get_event_by_idempotency_key_hash=lambda _key: event
    )

    with pytest.raises(PublicBookingRequestError) as exc_info:
        service._idempotent_request(
            key_hash="key-hash",
            payload_hash=payload_hash,
            patient_id=patient_id,
            request_id=request_id,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "booking_request_idempotency_conflict"
