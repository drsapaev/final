from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.telegram_config import (
    PatientOnboardingRequest,
    TelegramConfig,
    TelegramUser,
)


MINI_APP_BOT_TOKEN = "123456:test-mini-app-token"


def _signed_mini_app_init_data(
    telegram_id: int,
    *,
    bot_token: str = MINI_APP_BOT_TOKEN,
    auth_date: datetime | None = None,
) -> str:
    checked_at = auth_date or datetime.now(timezone.utc)
    params = {
        "auth_date": str(int(checked_at.timestamp())),
        "query_id": "AAEAAAE",
        "user": json.dumps({"id": telegram_id}, separators=(",", ":")),
    }
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    payload_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode({**params, "hash": payload_hash})


def _add_mini_app_telegram_config(db_session) -> None:
    db_session.add(TelegramConfig(bot_token=MINI_APP_BOT_TOKEN, active=True))
    db_session.commit()


def _create_unlinked_telegram_user(db_session, *, chat_id: int) -> TelegramUser:
    telegram_user = TelegramUser(
        chat_id=chat_id,
        username=f"onboarding_{chat_id}",
        first_name="Onboarding",
        language_code="ru",
        notifications_enabled=False,
        appointment_reminders=False,
        lab_notifications=False,
        active=True,
        blocked=False,
    )
    db_session.add(telegram_user)
    db_session.commit()
    db_session.refresh(telegram_user)
    return telegram_user


def _future_appointment_date() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def _create_onboarding_request(
    db_session,
    *,
    chat_id: int,
    status: str = "pending_review",
    review_message: str | None = None,
) -> PatientOnboardingRequest:
    telegram_user = _create_unlinked_telegram_user(db_session, chat_id=chat_id)
    request_row = PatientOnboardingRequest(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=telegram_user.chat_id,
        status=status,
        language_code="ru",
        contact_phone=f"+99890{chat_id}",
        contact_name="Review Patient",
        review_message=review_message,
    )
    db_session.add(request_row)
    db_session.commit()
    db_session.refresh(request_row)
    return request_row


@pytest.mark.unit
def test_unknown_mini_app_user_gets_onboarding_manifest_and_no_patient_row(
    client,
    db_session,
):
    _add_mini_app_telegram_config(db_session)
    chat_id = 9101
    _create_unlinked_telegram_user(db_session, chat_id=chat_id)
    initial_patients = db_session.query(Patient).count()

    response = client.post(
        "/api/v1/telegram/mini-app/patient/manifest",
        json={
            "initData": _signed_mini_app_init_data(chat_id),
            "section": "appointments",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["type"] == "onboarding"
    assert payload["patient"]["linked"] is False
    assert payload["capabilities"]["appointments"]["onboarding_request_enabled"] is True
    assert db_session.query(Patient).count() == initial_patients


@pytest.mark.unit
def test_unknown_user_submits_onboarding_request_without_patient_or_appointment(
    client,
    db_session,
):
    _add_mini_app_telegram_config(db_session)
    chat_id = 9102
    _create_unlinked_telegram_user(db_session, chat_id=chat_id)
    initial_patients = db_session.query(Patient).count()
    initial_appointments = db_session.query(Appointment).count()

    response = client.post(
        "/api/v1/telegram/mini-app/onboarding/requests",
        json={
            "initData": _signed_mini_app_init_data(chat_id),
            "section": "appointments",
            "languageCode": "ru",
            "contactPhone": "+998901112233",
            "contactName": "New Patient",
            "desiredService": "Cardiology",
            "desiredBranch": "Main",
            "desiredDate": _future_appointment_date(),
            "desiredTime": "09:30",
            "note": "Prefer morning appointment",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request"]["status"] == "pending_review"
    assert payload["safeNextAction"] == "wait_for_registrar_review"
    assert db_session.query(Patient).count() == initial_patients
    assert db_session.query(Appointment).count() == initial_appointments
    row = db_session.query(PatientOnboardingRequest).one()
    assert row.status == "pending_review"
    assert row.contact_phone == "+998901112233"
    assert row.desired_service == "Cardiology"


@pytest.mark.unit
def test_onboarding_scope_cannot_access_protected_patient_mini_app_sections(
    client,
    db_session,
):
    _add_mini_app_telegram_config(db_session)
    chat_id = 9103
    _create_unlinked_telegram_user(db_session, chat_id=chat_id)
    init_data = _signed_mini_app_init_data(chat_id)

    protected_calls = [
        (
            "/api/v1/telegram/mini-app/cabinet/summary",
            {"initData": init_data, "section": "cabinet"},
        ),
        (
            "/api/v1/telegram/mini-app/forms/preview",
            {"initData": init_data, "section": "forms"},
        ),
        (
            "/api/v1/telegram/mini-app/reports/download",
            {"initData": init_data, "section": "results", "reportId": 1},
        ),
        (
            "/api/v1/telegram/mini-app/appointments/preview",
            {
                "initData": init_data,
                "section": "appointments",
                "appointmentDate": _future_appointment_date(),
            },
        ),
        (
            "/api/v1/telegram/mini-app/appointments",
            {
                "initData": init_data,
                "section": "appointments",
                "appointmentDate": _future_appointment_date(),
            },
        ),
    ]

    for path, body in protected_calls:
        response = client.post(path, json=body)
        assert response.status_code == 403
        payload_text = str(response.json())
        assert "patient_scope_required" in payload_text
        assert init_data not in payload_text
        assert "Traceback" not in payload_text


@pytest.mark.unit
def test_registrar_links_existing_patient_and_writes_audit(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    registrar_user,
):
    telegram_user = _create_unlinked_telegram_user(db_session, chat_id=9104)
    request_row = PatientOnboardingRequest(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=telegram_user.chat_id,
        status="pending_review",
        language_code="ru",
        contact_phone="+998901112244",
    )
    db_session.add(request_row)
    db_session.commit()
    db_session.refresh(request_row)

    response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/link-existing",
        headers=registrar_auth_headers,
        json={"patientId": test_patient.id, "reviewMessage": "Linked by registrar"},
    )

    assert response.status_code == 200
    db_session.refresh(request_row)
    db_session.refresh(telegram_user)
    assert request_row.status == "linked_existing"
    assert request_row.resolved_patient_id == test_patient.id
    assert telegram_user.patient_id == test_patient.id
    audit_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "patient_onboarding_linked_existing")
        .one()
    )
    assert audit_log.actor_user_id == registrar_user.id
    assert audit_log.payload["resolved_patient_id"] == test_patient.id
    assert "entryToken" not in str(audit_log.payload)


@pytest.mark.unit
def test_registrar_lists_pending_onboarding_requests_with_safe_payload(
    client,
    db_session,
    registrar_auth_headers,
):
    pending_request = _create_onboarding_request(db_session, chat_id=9110)
    _create_onboarding_request(db_session, chat_id=9111, status="rejected")

    response = client.get(
        "/api/v1/telegram/onboarding/requests",
        headers=registrar_auth_headers,
        params={"status_filter": "pending_review"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["id"] == pending_request.id
    assert item["status"] == "pending_review"
    assert item["telegramChatId"] == pending_request.telegram_chat_id
    assert item["contactPhone"] == pending_request.contact_phone
    payload_text = str(payload)
    assert "entryToken" not in payload_text
    assert "pmo_" not in payload_text
    assert "payment_id" not in payload_text
    assert "diagnosis" not in payload_text
    assert "lab_details" not in payload_text


@pytest.mark.unit
def test_registrar_onboarding_actions_require_staff_role(client, db_session):
    request_row = _create_onboarding_request(db_session, chat_id=9112)

    list_response = client.get("/api/v1/telegram/onboarding/requests")
    action_response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/request-more-info",
        json={"reviewMessage": "Please add contact details."},
    )

    assert list_response.status_code in {401, 403}
    assert action_response.status_code in {401, 403}


@pytest.mark.unit
@pytest.mark.parametrize(
    "action,review_message,expected_status,expected_next_action",
    [
        (
            "request-more-info",
            "Please add the preferred service.",
            "needs_more_info",
            "submit_more_info",
        ),
        (
            "reject",
            "Please contact the registrar.",
            "rejected",
            "contact_registrar_or_submit_new_request",
        ),
    ],
)
def test_review_statuses_are_visible_through_own_status_endpoint(
    client,
    db_session,
    registrar_auth_headers,
    action,
    review_message,
    expected_status,
    expected_next_action,
):
    _add_mini_app_telegram_config(db_session)
    chat_id = 9120 if action == "request-more-info" else 9121
    request_row = _create_onboarding_request(db_session, chat_id=chat_id)

    review_response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/{action}",
        headers=registrar_auth_headers,
        json={"reviewMessage": review_message},
    )

    assert review_response.status_code == 200
    status_response = client.post(
        "/api/v1/telegram/mini-app/onboarding/status",
        json={
            "initData": _signed_mini_app_init_data(chat_id),
            "section": "appointments",
        },
    )
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["request"]["status"] == expected_status
    assert payload["request"]["reviewMessage"] == review_message
    assert payload["messageKey"] == f"patient_onboarding_{expected_status}"
    assert payload["safeNextAction"] == expected_next_action
    payload_text = str(payload)
    assert "entryToken" not in payload_text
    assert "payment_id" not in payload_text
    assert "diagnosis" not in payload_text


@pytest.mark.unit
@pytest.mark.parametrize("token_case", ["missing", "wrong_section", "expired"])
def test_onboarding_token_errors_are_safe_for_patient(
    client,
    db_session,
    monkeypatch,
    token_case,
):
    chat_id = 9130
    _create_unlinked_telegram_user(db_session, chat_id=chat_id)
    body = {"section": "appointments"}

    if token_case == "wrong_section":
        body["entryToken"] = telegram_webhook._build_patient_onboarding_entry_token(
            chat_id,
            "queue",
        )
    elif token_case == "expired":
        monkeypatch.setattr(
            telegram_webhook,
            "PATIENT_MINI_APP_ENTRY_TOKEN_TTL_SECONDS",
            -1,
        )
        body["entryToken"] = telegram_webhook._build_patient_onboarding_entry_token(
            chat_id,
            "appointments",
        )

    response = client.post(
        "/api/v1/telegram/mini-app/onboarding/status",
        json=body,
    )

    assert response.status_code == 403
    payload_text = str(response.json())
    assert "reason" in payload_text
    assert "Traceback" not in payload_text
    assert "entryToken" not in payload_text
    assert "pmo_" not in payload_text
    assert "patient_id" not in payload_text
    assert "payment_id" not in payload_text
    assert "diagnosis" not in payload_text


@pytest.mark.unit
def test_registrar_creates_patient_only_by_staff_action_and_writes_audit(
    client,
    db_session,
    registrar_auth_headers,
    registrar_user,
):
    telegram_user = _create_unlinked_telegram_user(db_session, chat_id=9105)
    request_row = PatientOnboardingRequest(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=telegram_user.chat_id,
        status="pending_review",
        language_code="ru",
        contact_phone="+998901112255",
        contact_name="Created Patient",
    )
    db_session.add(request_row)
    db_session.commit()
    db_session.refresh(request_row)
    initial_patients = db_session.query(Patient).count()

    response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/create-patient",
        headers=registrar_auth_headers,
        json={
            "patient": {
                "last_name": "Created",
                "first_name": "Patient",
                "phone": "+998901112255",
            },
            "reviewMessage": "Created by registrar",
        },
    )

    assert response.status_code == 200
    db_session.refresh(request_row)
    db_session.refresh(telegram_user)
    assert db_session.query(Patient).count() == initial_patients + 1
    assert request_row.status == "created_patient"
    assert telegram_user.patient_id == request_row.resolved_patient_id
    audit_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "patient_onboarding_created_patient")
        .one()
    )
    assert audit_log.actor_user_id == registrar_user.id
    assert audit_log.payload["resolved_patient_id"] == request_row.resolved_patient_id
    assert "entryToken" not in str(audit_log.payload)
