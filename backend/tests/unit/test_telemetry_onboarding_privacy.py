import logging

import pytest

from app.api.v1.endpoints.telemetry import ALLOWED_EVENTS, TelemetryEvent, store_events, validate_event
from app.models.audit import AuditLog


ONBOARDING_EVENTS = {
    "patient_onboarding_started",
    "patient_onboarding_opened",
    "patient_onboarding_submitted",
    "patient_onboarding_pending_review",
    "patient_onboarding_needs_more_info",
    "registrar_onboarding_reviewed",
    "patient_onboarding_linked_existing",
    "patient_onboarding_created_patient",
    "patient_onboarding_rejected",
    "patient_onboarding_expired",
}


@pytest.mark.unit
def test_patient_onboarding_telemetry_events_are_whitelisted():
    assert ONBOARDING_EVENTS <= ALLOWED_EVENTS

    for event in ONBOARDING_EVENTS:
        assert validate_event(
            TelemetryEvent(
                event=event,
                entity="telegram_mini_app",
                meta={
                    "role": "patient",
                    "scope": "onboarding",
                    "section": "appointments",
                    "language": "ru",
                    "success": True,
                    "reason_code": None,
                },
            )
        ) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "blocked_key",
    [
        "entryToken",
        "entry_token",
        "raw_token",
        "diagnosis",
        "lab_details",
        "full_phone",
        "full_name",
        "payment_id",
        "invoice_id",
        "provider_payload",
        "emr",
    ],
)
def test_patient_onboarding_telemetry_rejects_sensitive_payload_keys(blocked_key):
    assert validate_event(
        TelemetryEvent(
            event="patient_onboarding_submitted",
            entity="telegram_mini_app",
            meta={blocked_key: "not-safe"},
        )
    ) is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_patient_onboarding_telemetry_events_do_not_write_anonymous_audit_logs(
    caplog,
    db_session,
):
    event = TelemetryEvent(
        event="patient_onboarding_opened",
        entity="telegram_mini_app",
        meta={
            "role": "patient",
            "scope": "onboarding",
            "section": "appointments",
            "language": "ru",
            "success": True,
            "reason_code": None,
        },
    )

    with caplog.at_level(logging.INFO, logger="app.api.v1.endpoints.telemetry"):
        await store_events([event])

    audit_rows = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == "telegram_onboarding_telemetry")
        .all()
    )
    assert audit_rows == []
    assert "patient_onboarding_opened" in caplog.text
    assert "entryToken" not in caplog.text
    assert "full_phone" not in caplog.text


@pytest.mark.unit
def test_anonymous_telemetry_endpoint_cannot_populate_audit_log(client, db_session):
    response = client.post(
        "/api/v1/telemetry",
        json={
            "events": [
                {
                    "event": "patient_onboarding_opened",
                    "entity": "telegram_mini_app",
                    "meta": {
                        "role": "patient",
                        "scope": "onboarding",
                        "section": "appointments",
                        "language": "ru",
                        "success": True,
                        "reason_code": None,
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "rejected": 0}
    assert (
        db_session.query(AuditLog)
        .filter(AuditLog.entity_type == "telegram_onboarding_telemetry")
        .count()
        == 0
    )
