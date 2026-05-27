import pytest

from app.api.v1.endpoints.telemetry import ALLOWED_EVENTS, TelemetryEvent, validate_event


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
