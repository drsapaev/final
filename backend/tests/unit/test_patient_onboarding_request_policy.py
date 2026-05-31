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


def _search_candidate_id(
    client,
    *,
    request_id: int,
    headers: dict[str, str],
    phone: str | None = None,
    name: str | None = None,
) -> str:
    payload_body = {
        **({"phone": phone} if phone else {}),
        **({"name": name} if name else {}),
    }
    for candidate_search_body in (payload_body, {}):
        response = client.post(
            f"/api/v1/telegram/onboarding/requests/{request_id}/search-patients",
            headers=headers,
            json=candidate_search_body,
        )
        assert response.status_code == 200
        payload = response.json()
        assert "entryToken" not in str(payload)
        if payload["candidates"]:
            return payload["candidates"][0]["candidateId"]
    raise AssertionError(f"Expected duplicate candidates, got payload={payload!r}")


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
    registrar_user,
):
    patient_response = client.post(
        "/api/v1/patients/",
        headers=registrar_auth_headers,
        json={
            "last_name": "Linked",
            "first_name": "Patient",
            "middle_name": "Test",
            "phone": "+998901234567",
            "birth_date": "1990-01-01",
        },
    )
    assert patient_response.status_code == 200
    linked_patient = patient_response.json()

    telegram_user = _create_unlinked_telegram_user(db_session, chat_id=9104)
    request_row = PatientOnboardingRequest(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=telegram_user.chat_id,
        status="pending_review",
        language_code="ru",
        contact_phone=linked_patient["phone"],
        contact_name=f'{linked_patient["last_name"]} {linked_patient["first_name"]}',
    )
    db_session.add(request_row)
    db_session.commit()
    db_session.refresh(request_row)
    candidate_id = _search_candidate_id(
        client,
        request_id=request_row.id,
        headers=registrar_auth_headers,
        phone=linked_patient["phone"],
        name=f'{linked_patient["last_name"]} {linked_patient["first_name"]}',
    )

    response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/link-existing",
        headers=registrar_auth_headers,
        json={
            "candidateId": candidate_id,
            "safeNote": "Linked by registrar",
            "reasonCode": "duplicate_suspected",
        },
    )

    assert response.status_code == 200
    db_session.refresh(request_row)
    db_session.refresh(telegram_user)
    assert request_row.status == "linked_existing"
    assert request_row.resolved_patient_id == linked_patient["id"]
    assert telegram_user.patient_id == linked_patient["id"]
    audit_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "patient_onboarding_linked_existing")
        .one()
    )
    assert audit_log.actor_user_id == registrar_user.id
    assert "resolved_patient_ref" in audit_log.payload
    assert "resolved_patient_id" not in audit_log.payload
    assert "entryToken" not in str(audit_log.payload)


@pytest.mark.unit
def test_onboarding_duplicate_search_keeps_exact_phone_match_beyond_page_limit(
    client,
    db_session,
    registrar_auth_headers,
):
    target_phone = "+998901234321"
    for index in range(45):
        db_session.add(
            Patient(
                last_name=f"Alpha{index:02d}",
                first_name="Filler",
                phone=f"+99890000{index:04d}",
            )
        )
    target = Patient(
        last_name="Zulu",
        first_name="Exact",
        phone=target_phone,
    )
    db_session.add(target)
    request_row = _create_onboarding_request(db_session, chat_id=9106)
    request_row.contact_phone = target_phone
    request_row.contact_name = "Unknown Caller"
    db_session.commit()

    response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/search-patients",
        headers=registrar_auth_headers,
        json={"phone": "901234321"},
    )

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert candidates
    assert candidates[0]["matchReasons"]["phone_match"] is True
    assert candidates[0]["maskedPhone"].endswith("21")
    assert len(candidates) <= 40


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
        json={"reasonCode": "other", "safeNote": "Please add contact details."},
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
        json={"reasonCode": "other", "safeNote": review_message},
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
    duplicate_review_response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/search-patients",
        headers=registrar_auth_headers,
        json={
            "phone": request_row.contact_phone,
            "name": request_row.contact_name,
        },
    )
    assert duplicate_review_response.status_code == 200

    response = client.post(
        f"/api/v1/telegram/onboarding/requests/{request_row.id}/create-patient",
        headers=registrar_auth_headers,
        json={
            "patient": {
                "last_name": "Created",
                "first_name": "Patient",
                "phone": "+998901112255",
            },
            "reasonCode": "other",
            "safeNote": "Created by registrar",
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
    assert "resolved_patient_ref" in audit_log.payload
    assert "resolved_patient_id" not in audit_log.payload
    assert "entryToken" not in str(audit_log.payload)


@pytest.mark.unit
def test_onboarding_analytics_summary_returns_safe_dashboard_metrics(
    client,
    db_session,
    registrar_auth_headers,
):
    now = datetime.now(timezone.utc)
    pending_request = _create_onboarding_request(db_session, chat_id=9201, status="pending_review")
    needs_info_request = _create_onboarding_request(
        db_session,
        chat_id=9202,
        status="needs_more_info",
        review_message="Please confirm contact details.",
    )
    linked_request = _create_onboarding_request(db_session, chat_id=9203, status="linked_existing")
    rejected_request = _create_onboarding_request(
        db_session,
        chat_id=9204,
        status="rejected",
        review_message="Please contact the clinic.",
    )

    pending_request.created_at = now - timedelta(hours=5)
    needs_info_request.created_at = now - timedelta(hours=3)
    needs_info_request.reviewed_at = now - timedelta(hours=1)
    linked_request.created_at = now - timedelta(hours=2)
    linked_request.reviewed_at = now - timedelta(minutes=30)
    rejected_request.created_at = now - timedelta(hours=1)
    rejected_request.reviewed_at = now - timedelta(minutes=10)
    db_session.add_all(
        [
            AuditLog(
                action="patient_onboarding_started",
                entity_type="telegram_onboarding_telemetry",
                payload={"role": "patient", "scope": "onboarding", "section": "appointments"},
            ),
            AuditLog(
                action="patient_onboarding_opened",
                entity_type="telegram_onboarding_telemetry",
                payload={"role": "patient", "scope": "onboarding", "section": "appointments"},
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/telegram/onboarding/analytics/summary",
        headers=registrar_auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["funnel"]["started"] == 1
    assert payload["funnel"]["opened"] == 1
    assert payload["funnel"]["submitted"] >= 4
    assert payload["dashboard"]["pendingRequests"] >= 1
    assert payload["dashboard"]["overdueRequests"] >= 1
    assert payload["dashboard"]["todaySubmitted"] >= 1
    assert payload["dashboard"]["averageReviewTimeMinutes"] > 0
    assert payload["dashboard"]["conversionRate"] >= 0
    payload_text = str(payload)
    assert "entryToken" not in payload_text
    assert "pma_" not in payload_text
    assert pending_request.contact_phone not in payload_text
    assert "diagnosis" not in payload_text


@pytest.mark.unit
def test_onboarding_csv_export_masks_sensitive_fields(
    client,
    db_session,
    registrar_auth_headers,
):
    request_row = _create_onboarding_request(db_session, chat_id=9205, status="needs_more_info")
    request_row.contact_phone = "+998901234567"
    request_row.contact_name = "Sensitive Patient"
    request_row.desired_service = "Cardiology"
    request_row.desired_branch = "Main"
    request_row.reviewed_at = datetime.now(timezone.utc)
    db_session.commit()

    response = client.get(
        "/api/v1/telegram/onboarding/requests/export",
        headers=registrar_auth_headers,
        params={"status_filter": "needs_more_info"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert "request_id,status,created_at,reviewed_at" in body
    assert "Cardiology" in body
    assert "Main" in body
    assert "Sensitive Patient" not in body
    assert "+998901234567" not in body
    assert "entryToken" not in body
    assert "payment_id" not in body
    assert "diagnosis" not in body
