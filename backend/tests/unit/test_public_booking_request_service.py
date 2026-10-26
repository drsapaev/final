from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

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
