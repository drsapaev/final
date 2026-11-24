"""The legacy endpoints require a proven subject before queuing a notification."""

from datetime import date
from unittest.mock import AsyncMock

from app.models.visit import Visit


def test_ambiguous_legacy_requests_do_not_enqueue(
    client, db_session, admin_auth_headers, test_patient, monkeypatch
):
    import app.api.v1.endpoints.notifications as endpoint

    dispatch = AsyncMock()
    monkeypatch.setattr(endpoint, "dispatch_patient_notification_intent", dispatch)
    visit = Visit(
        patient_id=test_patient.id,
        visit_date=date(2026, 4, 1),
        status="open",
        confirmation_context_epoch=123,
    )
    db_session.add(visit)
    db_session.commit()
    reminder = client.post(
        "/api/v1/notifications/send-appointment-reminder",
        headers=admin_auth_headers,
        params={
            "patient_id": test_patient.id,
            "appointment_date": "2026-04-01T10:00:00",
            "doctor_name": "Synthetic",
            "department": "Synthetic",
        },
    )
    payment = client.post(
        "/api/v1/notifications/send-payment-notification",
        headers=admin_auth_headers,
        params={"visit_id": visit.id, "amount": 123, "currency": "UZS"},
    )
    assert reminder.status_code == 409
    assert payment.status_code == 409
    dispatch.assert_not_awaited()
