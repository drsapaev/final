from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from app.api.v1.endpoints import admin_telegram, telegram_webhook
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.schemas.notifications import SendMessageRequest
from app.services import telegram_bot
from app.services.telegram_templates import TelegramTemplatesService
from app.models.lab import LabReportInstance, LabReportTemplate, LabReportTemplateVersion
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.telegram_config import (
    TelegramConfig,
    TelegramMessage,
    TelegramPatientFormSubmission,
    TelegramStaffLinkToken,
    TelegramUser,
)


class FakeTelegramBotService:
    def __init__(self, active: bool = True):
        self.active = active
        self.initialize = AsyncMock(return_value=True)
        self.process_webhook_update = AsyncMock(return_value=None)
        self._send_message = AsyncMock(return_value=True)
        self._send_document = AsyncMock(return_value=(True, 77, None))
        self.bot_token = "bot-token"
        self.webhook_url = "https://example.com/webhook"


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


def _future_mini_app_appointment_date() -> date:
    return date.today() + timedelta(days=1)


def _link_patient_to_chat(
    db_session,
    *,
    chat_id: int,
    patient_id: int,
    language_code: str = "ru",
) -> TelegramUser:
    telegram_user = TelegramUser(
        chat_id=chat_id,
        patient_id=patient_id,
        username="patient_chat",
        first_name="Patient",
        language_code=language_code,
        notifications_enabled=True,
        appointment_reminders=True,
        lab_notifications=True,
        active=True,
        blocked=False,
    )
    db_session.add(telegram_user)
    db_session.commit()
    db_session.refresh(telegram_user)
    return telegram_user


def _reply_keyboard_texts(reply_markup):
    return [
        button["text"]
        for row in reply_markup.get("keyboard", [])
        for button in row
    ]


def _create_lab_report_instance(
    db_session,
    *,
    patient_id: int,
    template: LabReportTemplate,
    version: LabReportTemplateVersion,
    status_value: str,
    created_at: datetime,
) -> LabReportInstance:
    instance = LabReportInstance(
        patient_id=patient_id,
        template_id=template.id,
        template_version_id=version.id,
        status=status_value,
        patient_snapshot={},
        branding_snapshot={},
        signer_snapshot={},
        created_at=created_at,
        finalized_at=created_at if status_value == "FINALIZED" else None,
        printed_at=created_at if status_value == "PRINTED" else None,
    )
    db_session.add(instance)
    db_session.flush()
    return instance


@pytest.mark.unit
class TestTelegramWebhookSecurity:
    def test_admin_webhook_info_response_hides_raw_telegram_payload(
        self, db_session, monkeypatch
    ):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "ok": True,
                    "result": {
                        "url": "https://clinic.example/api/v1/telegram/webhook",
                        "pending_update_count": 3,
                        "last_error_message": "provider-secret-detail",
                        "ip_address": "203.0.113.10",
                        "allowed_updates": ["message"],
                        "unexpected_secret": "raw-provider-secret",
                    },
                }

        monkeypatch.setattr(
            admin_telegram.requests,
            "get",
            lambda *_args, **_kwargs: FakeResponse(),
        )

        response = admin_telegram.get_telegram_webhook_info(
            db_session,
            SimpleNamespace(id=1),
        )

        assert response == {
            "webhook_set": True,
            "webhook_info": {
                "url": "https://clinic.example/api/v1/telegram/webhook",
                "pending_update_count": 3,
            },
        }
        assert "last_error_message" not in str(response)
        assert "ip_address" not in str(response)
        assert "allowed_updates" not in str(response)
        assert "raw-provider-secret" not in str(response)

    def test_webhook_rejects_missing_secret_configuration(
        self, client, monkeypatch
    ):
        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 10},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Telegram webhook secret is not configured"
        assert fake_service.process_webhook_update.await_count == 0

    def test_webhook_rejects_invalid_secret(self, client, db_session, monkeypatch):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 1},
            headers={"x-telegram-bot-api-secret-token": "wrong-secret"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid Telegram webhook secret"
        assert fake_service.process_webhook_update.await_count == 0

    def test_webhook_accepts_valid_secret(self, client, db_session, monkeypatch):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        update_payload = {"update_id": 2, "message": {"message_id": 11}}

        response = client.post(
            "/api/v1/telegram/webhook",
            json=update_payload,
            headers={"x-telegram-bot-api-secret-token": "topsecret"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        fake_service.process_webhook_update.assert_awaited_once()

    def test_webhook_does_not_log_full_payload(
        self, client, db_session, monkeypatch, caplog
    ):
        db_session.add(
            TelegramConfig(
                bot_token="bot-token",
                webhook_secret="topsecret",
                active=True,
            )
        )
        db_session.commit()

        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        caplog.set_level("INFO", logger="app.api.v1.endpoints.telegram_webhook")
        response = client.post(
            "/api/v1/telegram/webhook",
            json={
                "update_id": 3,
                "message": {
                    "message_id": 12,
                    "text": "Sensitive Patient Diagnosis",
                },
            },
            headers={"x-telegram-bot-api-secret-token": "topsecret"},
        )

        assert response.status_code == 200
        assert "Telegram webhook update accepted" in caplog.text
        assert "Sensitive Patient Diagnosis" not in caplog.text

    def test_mini_app_booking_preview_endpoint_returns_non_mutating_payload(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880201
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        initial_appointments = db_session.query(Appointment).count()
        appointment_date = _future_mini_app_appointment_date()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments/preview",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "doctorId": 12,
                "appointmentDate": appointment_date.isoformat(),
                "appointmentTime": "09:30",
                "department": "Cardiology",
                "notes": "Mini App request",
                "services": ["Consultation"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        appointment = payload["appointment"]
        assert payload["preview_only"] is True
        assert payload["mutation_allowed"] is False
        assert payload["scope"] == {"type": "patient", "patient_id": test_patient.id}
        assert "appointment_id" not in appointment
        assert appointment["patient_id"] == test_patient.id
        assert appointment["appointment_date"] == appointment_date.isoformat()
        assert appointment["appointment_time"] == "09:30"
        assert appointment["status"] == "scheduled"
        assert appointment["payment_type"] == "cash"
        assert appointment["payment_currency"] == "UZS"
        assert appointment["payment_provider"] is None
        assert appointment["payment_transaction_id"] is None
        assert appointment["payment_webhook_id"] is None
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_booking_preview_endpoint_rejects_forged_init_data(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880202
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        initial_appointments = db_session.query(Appointment).count()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments/preview",
            json={
                "initData": _signed_mini_app_init_data(chat_id).replace(
                    "hash=",
                    "hash=forged",
                    1,
                ),
                "patientId": test_patient.id,
                "appointmentDate": "2026-05-20",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == {"reason": "hash_mismatch"}
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_booking_preview_endpoint_rejects_staff_scope(
        self,
        client,
        db_session,
        admin_user,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880203
        db_session.add(
            TelegramUser(
                chat_id=chat_id,
                user_id=admin_user.id,
                language_code="ru",
                active=True,
                blocked=False,
            )
        )
        db_session.commit()
        initial_appointments = db_session.query(Appointment).count()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments/preview",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "appointmentDate": "2026-05-20",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == {"reason": "patient_scope_required"}
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_booking_preview_endpoint_requires_configured_bot_token(
        self,
        client,
        db_session,
    ):
        initial_appointments = db_session.query(Appointment).count()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments/preview",
            json={
                "initData": _signed_mini_app_init_data(880204),
                "appointmentDate": "2026-05-20",
            },
        )

        assert response.status_code == 503
        assert response.json()["detail"] == {"reason": "bot_token_required"}
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_booking_preview_endpoint_maps_invalid_booking_field_to_400(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880205
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        initial_appointments = db_session.query(Appointment).count()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments/preview",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "appointmentDate": "2000-01-01",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == {"reason": "appointment_date_in_past"}
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_patient_forms_preview_endpoint_returns_safe_schema(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880211
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        initial_appointments = db_session.query(Appointment).count()

        response = client.post(
            "/api/v1/telegram/mini-app/forms/preview",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["preview_only"] is True
        assert payload["mutation_allowed"] is False
        assert payload["message_key"] == "telegram_mini_app_patient_forms_preview_ready"
        assert payload["scope"] == {"type": "patient", "patient_id": test_patient.id}
        assert payload["policy"] == {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "storage_enabled": True,
        }
        assert payload["forms"][0]["id"] == "patient_intake"
        assert {field["key"] for field in payload["forms"][0]["fields"]} == {
            "chief_complaint",
            "allergies",
            "current_medications",
            "medical_history",
            "consent_to_contact",
        }
        assert "patient_id" not in payload["forms"][0]
        assert "submission" not in payload["forms"][0]
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_patient_forms_preview_endpoint_rejects_untrusted_scope(
        self,
        client,
        db_session,
        test_patient,
        admin_user,
    ):
        _add_mini_app_telegram_config(db_session)
        patient_chat_id = 880212
        staff_chat_id = 880213
        _link_patient_to_chat(db_session, chat_id=patient_chat_id, patient_id=test_patient.id)
        db_session.add(
            TelegramUser(
                chat_id=staff_chat_id,
                user_id=admin_user.id,
                language_code="ru",
                active=True,
                blocked=False,
            )
        )
        db_session.commit()
        initial_appointments = db_session.query(Appointment).count()

        forged_response = client.post(
            "/api/v1/telegram/mini-app/forms/preview",
            json={
                "initData": _signed_mini_app_init_data(patient_chat_id).replace(
                    "hash=",
                    "hash=forged",
                    1,
                ),
                "patientId": test_patient.id,
            },
        )
        staff_response = client.post(
            "/api/v1/telegram/mini-app/forms/preview",
            json={"initData": _signed_mini_app_init_data(staff_chat_id)},
        )
        wrong_patient_response = client.post(
            "/api/v1/telegram/mini-app/forms/preview",
            json={
                "initData": _signed_mini_app_init_data(patient_chat_id),
                "patientId": test_patient.id + 1,
            },
        )

        assert forged_response.status_code == 403
        assert forged_response.json()["detail"] == {"reason": "hash_mismatch"}
        assert staff_response.status_code == 403
        assert staff_response.json()["detail"] == {"reason": "patient_scope_required"}
        assert wrong_patient_response.status_code == 403
        assert wrong_patient_response.json()["detail"] == {"reason": "patient_scope_mismatch"}
        assert db_session.query(Appointment).count() == initial_appointments

    def test_mini_app_patient_form_submission_endpoint_creates_and_updates_submission(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880214
        telegram_user = _link_patient_to_chat(
            db_session,
            chat_id=chat_id,
            patient_id=test_patient.id,
        )

        create_response = client.post(
            "/api/v1/telegram/mini-app/forms/submissions",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "formId": "patient_intake",
                "status": "draft",
                "answers": {
                    "chief_complaint": "  Headache  ",
                    "allergies": "None",
                    "consent_to_contact": True,
                },
            },
        )

        assert create_response.status_code == 200
        created_payload = create_response.json()
        assert created_payload["stored"] is True
        assert created_payload["created"] is True
        assert created_payload["scope"] == {"type": "patient", "patient_id": test_patient.id}
        assert created_payload["submission"]["form_id"] == "patient_intake"
        assert created_payload["submission"]["status"] == "draft"
        assert created_payload["submission"]["answers"] == {
            "chief_complaint": "Headache",
            "allergies": "None",
            "consent_to_contact": True,
        }
        assert "telegram_chat_id" not in created_payload["submission"]
        assert "telegram_user_id" not in created_payload["submission"]

        submission = db_session.query(TelegramPatientFormSubmission).one()
        assert submission.patient_id == test_patient.id
        assert submission.telegram_user_id == telegram_user.id
        assert submission.telegram_chat_id == chat_id
        assert submission.status == "draft"
        assert submission.submitted_at is None

        update_response = client.post(
            "/api/v1/telegram/mini-app/forms/submissions",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "formId": "patient_intake",
                "status": "submitted",
                "answers": {
                    "chief_complaint": "Headache improved",
                    "allergies": "",
                    "current_medications": "Ibuprofen",
                    "medical_history": "No chronic conditions",
                    "consent_to_contact": False,
                },
            },
        )

        assert update_response.status_code == 200
        updated_payload = update_response.json()
        assert updated_payload["created"] is False
        assert updated_payload["submission"]["id"] == created_payload["submission"]["id"]
        assert updated_payload["submission"]["status"] == "submitted"
        assert updated_payload["submission"]["answers"]["chief_complaint"] == "Headache improved"
        assert updated_payload["submission"]["submitted_at"] is not None
        assert db_session.query(TelegramPatientFormSubmission).count() == 1

        preview_response = client.post(
            "/api/v1/telegram/mini-app/forms/preview",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
            },
        )

        assert preview_response.status_code == 200
        hydrated_form = preview_response.json()["forms"][0]
        assert hydrated_form["id"] == "patient_intake"
        assert hydrated_form["submission"]["id"] == created_payload["submission"]["id"]
        assert hydrated_form["submission"]["form_id"] == "patient_intake"
        assert hydrated_form["submission"]["status"] == "submitted"
        assert hydrated_form["submission"]["answers"]["chief_complaint"] == "Headache improved"
        assert hydrated_form["submission"]["submitted_at"] is not None
        assert "telegram_chat_id" not in hydrated_form["submission"]
        assert "telegram_user_id" not in hydrated_form["submission"]

    def test_mini_app_patient_form_submission_endpoint_rejects_invalid_answers(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880215
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)

        unknown_field_response = client.post(
            "/api/v1/telegram/mini-app/forms/submissions",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "formId": "patient_intake",
                "answers": {"diagnosis": "do not accept"},
            },
        )
        bool_type_response = client.post(
            "/api/v1/telegram/mini-app/forms/submissions",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "formId": "patient_intake",
                "answers": {"consent_to_contact": "yes"},
            },
        )
        wrong_patient_response = client.post(
            "/api/v1/telegram/mini-app/forms/submissions",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id + 1,
                "formId": "patient_intake",
                "answers": {"chief_complaint": "Headache"},
            },
        )

        assert unknown_field_response.status_code == 400
        assert unknown_field_response.json()["detail"] == {
            "reason": "patient_form_answer_unknown_field"
        }
        assert bool_type_response.status_code == 400
        assert bool_type_response.json()["detail"] == {
            "reason": "patient_form_answer_type_invalid"
        }
        assert wrong_patient_response.status_code == 403
        assert wrong_patient_response.json()["detail"] == {
            "reason": "patient_scope_mismatch"
        }
        assert db_session.query(TelegramPatientFormSubmission).count() == 0

    def test_mini_app_patient_cabinet_summary_endpoint_returns_safe_summary(
        self,
        client,
        db_session,
        test_patient,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880216
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        db_session.add(
            Appointment(
                patient_id=test_patient.id,
                appointment_date=date(2026, 5, 20),
                appointment_time="10:00",
                status="scheduled",
                visit_type="paid",
                payment_type="cash",
                payment_currency="UZS",
            )
        )
        db_session.commit()

        response = client.post(
            "/api/v1/telegram/mini-app/cabinet/summary",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
            },
        )
        wrong_patient_response = client.post(
            "/api/v1/telegram/mini-app/cabinet/summary",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id + 1,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["scope"] == {"type": "patient", "patient_id": test_patient.id}
        assert payload["patient"]["name"] == test_patient.short_name()
        assert payload["appointments"][0] == {
            "id": payload["appointments"][0]["id"],
            "date": "2026-05-20",
            "time": "10:00",
            "status": "scheduled",
            "department": None,
        }
        assert payload["payments"]["debt"] == "0"
        assert payload["policy"] == {
            "plain_telegram_chat_allowed": False,
            "medical_details_in_chat": False,
            "pdf_included": False,
        }
        assert "telegram_chat_id" not in str(payload)
        assert "telegram_user_id" not in str(payload)
        assert wrong_patient_response.status_code == 403
        assert wrong_patient_response.json()["detail"] == {
            "reason": "patient_scope_mismatch"
        }

    def test_mini_app_patient_report_download_endpoint_returns_safe_pdf(
        self,
        client,
        db_session,
        test_patient,
        monkeypatch,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880217
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        other_patient = Patient(first_name="Other", last_name="Report")
        template = LabReportTemplate(
            code="TG_MINI_APP_REPORT",
            name="Mini App Report",
            family="test",
        )
        db_session.add_all([other_patient, template])
        db_session.flush()
        version = LabReportTemplateVersion(
            template_id=template.id,
            version_no=1,
            status="PUBLISHED",
            layout_preset="default",
            page_settings={},
            branding_overrides={},
            signer_defaults={},
        )
        db_session.add(version)
        db_session.flush()
        ready_report = _create_lab_report_instance(
            db_session,
            patient_id=test_patient.id,
            template=template,
            version=version,
            status_value="FINALIZED",
            created_at=datetime.utcnow(),
        )
        other_report = _create_lab_report_instance(
            db_session,
            patient_id=other_patient.id,
            template=template,
            version=version,
            status_value="FINALIZED",
            created_at=datetime.utcnow(),
        )
        db_session.commit()
        monkeypatch.setattr(
            telegram_webhook,
            "_build_lab_report_pdf",
            lambda db, instance: (
                f"report-{instance.id}.pdf",
                b"%PDF-1.4 mini app",
                "Ready report",
            ),
        )

        response = client.post(
            "/api/v1/telegram/mini-app/reports/download",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "reportId": ready_report.id,
            },
        )
        other_patient_response = client.post(
            "/api/v1/telegram/mini-app/reports/download",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "reportId": other_report.id,
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == b"%PDF-1.4 mini app"
        assert f"report-{ready_report.id}.pdf" in response.headers["content-disposition"]
        assert other_patient_response.status_code == 404
        assert other_patient_response.json()["detail"] == {
            "reason": "report_not_ready_or_not_found"
        }

    def test_mini_app_booking_create_endpoint_creates_safe_appointment(
        self,
        client,
        db_session,
        test_patient,
        test_doctor,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880206
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        initial_appointments = db_session.query(Appointment).count()
        appointment_date = _future_mini_app_appointment_date()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "doctorId": test_doctor.id,
                "appointmentDate": appointment_date.isoformat(),
                "appointmentTime": "09:30",
                "department": "Cardiology",
                "notes": "Mini App create request",
                "services": ["Consultation"],
            },
        )

        assert response.status_code == 201
        payload = response.json()
        created = db_session.get(Appointment, payload["appointment_id"])
        assert payload["created"] is True
        assert payload["preview"]["preview_only"] is True
        assert payload["preview"]["mutation_allowed"] is False
        assert payload["preview"]["appointment"]["payment_provider"] is None
        assert created is not None
        assert created.patient_id == test_patient.id
        assert created.doctor_id == test_doctor.id
        assert created.appointment_date == appointment_date
        assert created.appointment_time == "09:30"
        assert created.status == "scheduled"
        assert created.visit_type == "paid"
        assert created.payment_type == "cash"
        assert created.payment_currency == "UZS"
        assert created.payment_provider is None
        assert created.payment_transaction_id is None
        assert created.payment_webhook_id is None
        assert db_session.query(Appointment).count() == initial_appointments + 1

    def test_mini_app_booking_create_endpoint_rejects_occupied_slot(
        self,
        client,
        db_session,
        test_patient,
        test_doctor,
    ):
        _add_mini_app_telegram_config(db_session)
        chat_id = 880207
        _link_patient_to_chat(db_session, chat_id=chat_id, patient_id=test_patient.id)
        appointment_date = _future_mini_app_appointment_date()
        db_session.add(
            Appointment(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                appointment_date=appointment_date,
                appointment_time="09:30",
                status="scheduled",
                visit_type="paid",
                payment_type="cash",
                payment_currency="UZS",
            )
        )
        db_session.commit()
        initial_appointments = db_session.query(Appointment).count()

        response = client.post(
            "/api/v1/telegram/mini-app/appointments",
            json={
                "initData": _signed_mini_app_init_data(chat_id),
                "patientId": test_patient.id,
                "doctorId": test_doctor.id,
                "appointmentDate": appointment_date.isoformat(),
                "appointmentTime": "09:30",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == {"reason": "appointment_time_slot_occupied"}
        assert db_session.query(Appointment).count() == initial_appointments

    def test_send_message_requires_admin_auth(self, client):
        response = client.post(
            "/api/v1/telegram/send-message",
            params={"chat_id": 123456, "message": "Привет"},
        )

        assert response.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_send_message_response_hides_chat_id(self, monkeypatch):
        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "get_telegram_bot_service",
            AsyncMock(return_value=fake_service),
        )

        response = await telegram_webhook.send_message_to_user(
            chat_id=123456,
            message="Private follow-up",
            parse_mode="HTML",
            body=SendMessageRequest(),
            db=object(),
            current_user=SimpleNamespace(role="Admin"),
        )

        assert response == {"status": "sent"}
        assert "chat_id" not in response
        assert "123456" not in str(response)
        fake_service._send_message.assert_awaited_once_with(
            chat_id=123456,
            text="Private follow-up",
            reply_markup=None,
        )

    @pytest.mark.asyncio
    async def test_contact_spoof_is_rejected(self, db_session):
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 101,
            "message": {
                "message_id": 1,
                "chat": {"id": 7001},
                "from": {"id": 111},
                "contact": {
                    "user_id": 222,
                    "phone_number": "+998901234567",
                },
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        assert (
            fake_service._send_message.await_args.args[1]
            == telegram_webhook.TELEGRAM_CONTACT_REJECTED_MESSAGE
        )
        assert (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7001)
            .first()
            is None
        )

    def test_patient_language_normalization_uses_canonical_uz_latn(self):
        assert telegram_webhook._normalize_patient_language("uz") == "uz-Latn"
        assert telegram_webhook._normalize_patient_language("uz_Latn") == "uz-Latn"
        assert telegram_webhook._normalize_patient_language("uzbek") == "uz-Latn"
        assert telegram_webhook._normalize_patient_language("ru") == "ru"

    def test_legacy_templates_accept_canonical_uz_latn(self):
        templates = TelegramTemplatesService()

        template = templates.get_template(
            "welcome",
            "uz-Latn",
            {"first_name": "Ali"},
        )

        assert "Programma Clinic-ga" in template["text"]
        assert "Ali" in template["text"]
        assert "Dobro" not in template["text"]

    @pytest.mark.parametrize(
        "language_code,main_expected,services_expected",
        [
            (
                "ru",
                [
                    "📲 Онлайн-сервисы",
                    "📋 Анкеты пациента",
                    "🧾 Документы и чеки",
                    "🧑‍⚕️ Врачи и расписание",
                    "📲 Кабинет пациента",
                    "👥 Режим сотрудника",
                ],
                [
                    "📋 Анкеты пациента",
                    "🧾 Документы и чеки",
                    "🧑‍⚕️ Врачи и расписание",
                    "📲 Кабинет пациента",
                    "👥 Режим сотрудника",
                    "⬅️ Главное меню",
                ],
            ),
            (
                "uz-Latn",
                [
                    "📲 Onlayn xizmatlar",
                    "📋 Bemor anketalari",
                    "🧾 Hujjatlar va cheklar",
                    "🧑‍⚕️ Shifokorlar jadvali",
                    "📲 Bemor kabineti",
                    "👥 Xodim rejimi",
                ],
                [
                    "📋 Bemor anketalari",
                    "🧾 Hujjatlar va cheklar",
                    "🧑‍⚕️ Shifokorlar jadvali",
                    "📲 Bemor kabineti",
                    "👥 Xodim rejimi",
                    "⬅️ Asosiy menyu",
                ],
            ),
        ],
    )
    def test_patient_visible_reply_menus_expose_service_buttons(
        self, language_code, main_expected, services_expected
    ):
        main_texts = _reply_keyboard_texts(
            telegram_webhook._localized_main_menu(language_code)
        )
        service_texts = _reply_keyboard_texts(
            telegram_webhook._localized_services_menu(language_code)
        )

        for expected in main_expected:
            assert expected in main_texts
        for expected in services_expected:
            assert expected in service_texts

    @pytest.mark.asyncio
    async def test_uzbek_language_choice_stores_canonical_uz_latn(self, db_session):
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 102,
            "message": {
                "message_id": 1,
                "chat": {"id": 7006},
                "from": {"id": 111, "language_code": "uz"},
                "text": "🇺🇿 O'zbekcha",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7006)
            .one()
        )
        assert telegram_user.language_code == "uz-Latn"
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False
        assert "O'zbekchaga" in fake_service._send_message.await_args.args[1]
        reply_markup = fake_service._send_message.await_args.args[2]
        assert reply_markup["keyboard"][0][0]["text"].startswith("📱")
        assert reply_markup["keyboard"][1][0]["text"].startswith("🏥")
        assert reply_markup["keyboard"][2][0]["text"].startswith("🎫")
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7006)
            .one()
        )
        assert log.template_key == "telegram_patient_language_selected_needs_contact"
        assert log.message_type == "patient_bot_reply"
        assert log.status == "sent"

    @pytest.mark.asyncio
    async def test_unknown_start_creates_only_telegram_user_not_patient(
        self, db_session
    ):
        initial_patients = db_session.query(Patient).count()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 119,
            "message": {
                "message_id": 1,
                "chat": {"id": 7018},
                "from": {"id": 7018, "username": "first_start"},
                "text": "/start",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7018)
            .one()
        )
        assert telegram_user.patient_id is None
        assert telegram_user.notifications_enabled is False
        assert db_session.query(Patient).count() == initial_patients
        fake_service._send_message.assert_awaited_once_with(
            7018,
            telegram_webhook._localized_text("language_prompt", "ru"),
            telegram_webhook.TELEGRAM_LANGUAGE_MENU,
        )
        reply_text = fake_service._send_message.await_args.args[1]
        assert "entryToken" not in reply_text
        assert "patient_id" not in reply_text
        assert "payment_id" not in reply_text
        assert "diagnosis" not in reply_text
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7018)
            .one()
        )
        assert log.template_key == "telegram_patient_language_prompt"

    @pytest.mark.asyncio
    async def test_plain_uzbek_button_switches_next_visible_menu(self, db_session):
        fake_service = FakeTelegramBotService(active=True)
        language_update = {
            "update_id": 120,
            "message": {
                "message_id": 1,
                "chat": {"id": 7020},
                "from": {"id": 111, "language_code": "ru"},
                "text": "O'zbekcha",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            language_update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7020)
            .one()
        )
        assert telegram_user.language_code == "uz-Latn"
        reply_text = fake_service._send_message.await_args.args[1]
        assert (
            telegram_webhook._localized_text("language_selected", "uz-Latn")
            in reply_text
        )
        assert (
            telegram_webhook._localized_text("share_contact", "uz-Latn")
            in reply_text
        )
        assert fake_service._send_message.await_args.args[2] == (
            telegram_webhook._localized_main_menu("uz-Latn")
        )

        fake_service._send_message.reset_mock()
        help_update = {
            "update_id": 121,
            "message": {
                "message_id": 2,
                "chat": {"id": 7020},
                "from": {"id": 111, "language_code": "ru"},
                "text": "Yordam",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            help_update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7020,
            telegram_webhook._localized_text("help", "uz-Latn"),
            telegram_webhook._localized_main_menu("uz-Latn"),
        )

    @pytest.mark.asyncio
    async def test_menu_command_refreshes_patient_main_menu_without_staff_intercept(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7026,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 126,
            "message": {
                "message_id": 1,
                "chat": {"id": 7026},
                "from": {"id": 111, "language_code": "uz"},
                "text": "/menu",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7026,
            telegram_webhook._localized_text("main_menu_refreshed", "uz-Latn"),
            telegram_webhook._localized_main_menu("uz-Latn"),
        )
        latest_log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7026)
            .order_by(TelegramMessage.id.desc())
            .first()
        )
        assert latest_log.template_key == "telegram_patient_main_menu_refreshed"

    @pytest.mark.asyncio
    async def test_settings_language_choice_keeps_localized_settings_menu(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7021,
            username="patient_chat",
            first_name="Patient",
            language_code="ru",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.add(
            TelegramMessage(
                chat_id=7021,
                message_type="patient_bot_reply",
                template_key="telegram_patient_settings",
                message_text="settings",
                status="sent",
                sent_at=datetime.utcnow(),
            )
        )
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        language_update = {
            "update_id": 122,
            "message": {
                "message_id": 3,
                "chat": {"id": 7021},
                "from": {"id": 111, "language_code": "ru"},
                "text": "O'zbekcha",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            language_update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.language_code == "uz-Latn"
        reply_text = fake_service._send_message.await_args.args[1]
        assert (
            telegram_webhook._localized_text("language_selected", "uz-Latn")
            in reply_text
        )
        assert "Joriy til: O'zbekcha" in reply_text
        assert fake_service._send_message.await_args.args[2] == (
            telegram_webhook._localized_settings_menu("uz-Latn")
        )
        latest_log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7021)
            .order_by(TelegramMessage.id.desc())
            .first()
        )
        assert latest_log.template_key == "telegram_patient_settings_language_selected"

    @pytest.mark.asyncio
    async def test_language_choice_preserves_existing_notification_consent(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7015,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 109,
            "message": {
                "message_id": 1,
                "chat": {"id": 7015},
                "from": {"id": 111, "language_code": "uz"},
                "text": "🇷🇺 Русский",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.language_code == "ru"
        assert telegram_user.notifications_enabled is True
        assert telegram_user.appointment_reminders is True
        assert telegram_user.lab_notifications is True
        assert "русский" in fake_service._send_message.await_args.args[1]

    @pytest.mark.asyncio
    async def test_notification_consent_accept_enables_patient_notifications(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7007,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=False,
            appointment_reminders=False,
            lab_notifications=False,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 103,
            "message": {
                "message_id": 1,
                "chat": {"id": 7007},
                "from": {"id": 111},
                "text": "🔔 Xabarnomalarga roziman",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.notifications_enabled is True
        assert telegram_user.appointment_reminders is True
        assert telegram_user.lab_notifications is True
        assert fake_service._send_message.await_args.args[1] == "Xabarnomalar yoqildi."

    @pytest.mark.asyncio
    async def test_notification_consent_decline_disables_patient_notifications(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7008,
            username="patient_chat",
            first_name="Patient",
            language_code="ru",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 104,
            "message": {
                "message_id": 1,
                "chat": {"id": 7008},
                "from": {"id": 111},
                "text": "Без уведомлений",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False

    @pytest.mark.asyncio
    async def test_settings_notification_choice_keeps_localized_settings_menu(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7022,
            username="patient_chat",
            first_name="Patient",
            language_code="ru",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.add(
            TelegramMessage(
                chat_id=7022,
                message_type="patient_bot_reply",
                template_key="telegram_patient_settings",
                message_text="settings",
                status="sent",
                sent_at=datetime.utcnow(),
            )
        )
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 123,
            "message": {
                "message_id": 4,
                "chat": {"id": 7022},
                "from": {"id": 111},
                "text": "Без уведомлений",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False
        reply_text = fake_service._send_message.await_args.args[1]
        assert (
            telegram_webhook._localized_text("notifications_disabled", "ru")
            in reply_text
        )
        assert (
            telegram_webhook._telegram_settings_message(db_session, 7022)
            in reply_text
        )
        assert fake_service._send_message.await_args.args[2] == (
            telegram_webhook._localized_settings_menu("ru")
        )
        latest_log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7022)
            .order_by(TelegramMessage.id.desc())
            .first()
        )
        assert (
            latest_log.template_key
            == "telegram_patient_settings_notifications_disabled"
        )

    @pytest.mark.asyncio
    async def test_settings_command_returns_localized_settings_menu(self, db_session):
        telegram_user = TelegramUser(
            chat_id=7009,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 105,
            "message": {
                "message_id": 1,
                "chat": {"id": 7009},
                "from": {"id": 111},
                "text": "/settings",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7009,
            telegram_webhook._telegram_settings_message(db_session, 7009),
            telegram_webhook._localized_settings_menu("uz-Latn"),
        )
        settings_message = fake_service._send_message.await_args.args[1]
        assert "Joriy til: O'zbekcha" in settings_message
        assert "Xabarnomalar: yoqilgan" in settings_message

    @pytest.mark.asyncio
    async def test_support_command_returns_localized_safe_contact_guidance(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7019,
            username="patient_chat",
            first_name="Patient",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 125,
            "message": {
                "message_id": 1,
                "chat": {"id": 7019},
                "from": {"id": 111},
                "text": "/support",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7019,
            telegram_webhook._localized_text("support", "uz-Latn"),
            telegram_webhook._localized_main_menu("uz-Latn"),
        )
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7019)
            .one()
        )
        assert log.template_key == "telegram_patient_support"

    @pytest.mark.asyncio
    async def test_book_command_returns_localized_safe_booking_entrypoint(
        self, db_session, test_patient, monkeypatch
    ):
        _link_patient_to_chat(
            db_session,
            chat_id=7022,
            patient_id=test_patient.id,
            language_code="uz-Latn",
        )
        monkeypatch.setattr(
            telegram_webhook.settings,
            "FRONTEND_URL",
            "https://clinic.example",
            raising=False,
        )
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 126,
            "message": {
                "message_id": 1,
                "chat": {"id": 7022},
                "from": {"id": 111},
                "text": "/book",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        chat_id, message, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7022
        assert message == telegram_webhook._localized_text("book", "uz-Latn")
        assert reply_markup == {
            "inline_keyboard": [
                [
                    {
                        "text": telegram_webhook._localized_text("booking_entry_button", "uz-Latn"),
                        "web_app": {
                            "url": "https://clinic.example" + admin_telegram.PATIENT_BOOKING_ENTRY_ROUTE,
                        },
                    }
                ]
            ]
        }
        assert str(test_patient.id) not in str(reply_markup)
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7022)
            .one()
        )
        assert log.template_key == "telegram_patient_book"

    @pytest.mark.parametrize(
        "command,text_key,button_key,template_key,section,chat_id,update_id",
        [
            (
                "/forms",
                "patient_forms",
                "patient_forms_entry_button",
                "telegram_patient_forms_placeholder",
                "forms",
                7050,
                1270,
            ),
            (
                "/documents",
                "patient_documents",
                "patient_documents_entry_button",
                "telegram_patient_documents_placeholder",
                "documents",
                7051,
                1271,
            ),
            (
                "/doctors",
                "doctor_schedule",
                "patient_doctors_entry_button",
                "telegram_patient_doctor_schedule_placeholder",
                "doctors",
                7052,
                1272,
            ),
            (
                "/cabinet",
                "patient_cabinet",
                "patient_cabinet_entry_button",
                "telegram_patient_cabinet_placeholder",
                "cabinet",
                7053,
                1273,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_patient_service_commands_return_protected_section_entry_button(
        self,
        db_session,
        test_patient,
        monkeypatch,
        command,
        text_key,
        button_key,
        template_key,
        section,
        chat_id,
        update_id,
    ):
        _link_patient_to_chat(
            db_session,
            chat_id=chat_id,
            patient_id=test_patient.id,
            language_code="uz-Latn",
        )
        monkeypatch.setattr(
            telegram_webhook.settings,
            "FRONTEND_URL",
            "https://clinic.example",
            raising=False,
        )
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": update_id,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id},
                "from": {"id": 111},
                "text": command,
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        reply_chat_id, message, reply_markup = fake_service._send_message.await_args.args
        assert reply_chat_id == chat_id
        assert message == telegram_webhook._localized_text(text_key, "uz-Latn")
        assert reply_markup == {
            "inline_keyboard": [
                [
                    {
                        "text": telegram_webhook._localized_text(button_key, "uz-Latn"),
                        "web_app": {
                            "url": (
                                "https://clinic.example"
                                f"{admin_telegram.PATIENT_MINI_APP_ENTRY_ROUTE}?section={section}"
                            ),
                        },
                    }
                ]
            ]
        }
        assert str(test_patient.id) not in str(reply_markup)
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == chat_id)
            .one()
        )
        assert log.template_key == template_key

    @pytest.mark.parametrize(
        "command,text_key,template_key,chat_id,update_id",
        [
            ("/forms", "patient_forms", "telegram_patient_forms_placeholder", 7054, 1274),
            (
                "/documents",
                "patient_documents",
                "telegram_patient_documents_placeholder",
                7055,
                1275,
            ),
            (
                "/doctors",
                "doctor_schedule",
                "telegram_patient_doctor_schedule_placeholder",
                7056,
                1276,
            ),
            (
                "/cabinet",
                "patient_cabinet",
                "telegram_patient_cabinet_placeholder",
                7057,
                1277,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_patient_service_commands_without_frontend_falls_back_to_services_menu(
        self,
        db_session,
        test_patient,
        monkeypatch,
        command,
        text_key,
        template_key,
        chat_id,
        update_id,
    ):
        _link_patient_to_chat(
            db_session,
            chat_id=chat_id,
            patient_id=test_patient.id,
            language_code="uz-Latn",
        )
        monkeypatch.setattr(
            telegram_webhook.settings,
            "FRONTEND_URL",
            "",
            raising=False,
        )
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": update_id,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id},
                "from": {"id": 111},
                "text": command,
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            chat_id,
            telegram_webhook._localized_text(text_key, "uz-Latn"),
            telegram_webhook._localized_services_menu("uz-Latn"),
        )
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == chat_id)
            .one()
        )
        assert log.template_key == template_key

    @pytest.mark.asyncio
    async def test_book_command_without_link_uses_request_review_onboarding_cta(
        self, db_session
    ):
        telegram_user = TelegramUser(
            chat_id=7030,
            username="unlinked_patient",
            first_name="NoLink",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 127,
            "message": {
                "message_id": 1,
                "chat": {"id": 7030},
                "from": {"id": 111},
                "text": "/book",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        chat_id, message, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7030
        assert message == telegram_webhook._localized_text("book", "uz-Latn")
        button = reply_markup["inline_keyboard"][0][0]
        assert button["text"] == telegram_webhook._localized_text(
            "onboarding_entry_button",
            "uz-Latn",
        )
        entry_url = button.get("url") or button.get("web_app", {}).get("url")
        assert entry_url
        assert "entryToken=pmo_" in entry_url
        assert "pma_" not in entry_url
        entry_token = parse_qs(urlsplit(entry_url).query)["entryToken"][0]
        parsed_onboarding = telegram_webhook._parse_patient_onboarding_entry_token(
            entry_token,
            expected_section="appointments",
        )
        assert parsed_onboarding["chat_id"] == 7030
        assert telegram_webhook._parse_patient_mini_app_entry_token(
            entry_token,
            expected_section="appointments",
        ) is None
        db_session.refresh(telegram_user)
        assert telegram_user.patient_id is None
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7030)
            .one()
        )
        assert log.template_key == "telegram_patient_book"

    @pytest.mark.parametrize(
        "command,template_key,chat_id,update_id",
        [
            ("/queue", "telegram_patient_queue", 7031, 1281),
            ("/payments", "telegram_patient_payments", 7032, 1282),
            (
                "/documents",
                "telegram_patient_documents_placeholder",
                7033,
                1283,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_unlinked_protected_commands_use_request_review_onboarding_cta(
        self,
        db_session,
        monkeypatch,
        command,
        template_key,
        chat_id,
        update_id,
    ):
        telegram_user = TelegramUser(
            chat_id=chat_id,
            username=f"unlinked_{chat_id}",
            first_name="NoLink",
            language_code="uz-Latn",
            notifications_enabled=True,
            appointment_reminders=True,
            lab_notifications=True,
            active=True,
            blocked=False,
        )
        db_session.add(telegram_user)
        db_session.commit()
        monkeypatch.setattr(
            telegram_webhook.settings,
            "FRONTEND_URL",
            "http://localhost:5173",
            raising=False,
        )
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": update_id,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id},
                "from": {"id": 111},
                "text": command,
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        reply_chat_id, message, reply_markup = fake_service._send_message.await_args.args
        assert reply_chat_id == chat_id
        assert message == telegram_webhook._localized_text(
            "unlinked_protected_action",
            "uz-Latn",
        )
        assert "payment_id" not in message
        assert "patient_id" not in message
        assert "diagnosis" not in message
        assert "Traceback" not in message
        button = reply_markup["inline_keyboard"][0][0]
        assert button["text"] == telegram_webhook._localized_text(
            "onboarding_entry_button",
            "uz-Latn",
        )
        entry_url = button.get("url") or button.get("web_app", {}).get("url")
        assert entry_url
        assert "entryToken=pmo_" in entry_url
        assert "pma_" not in entry_url
        entry_token = parse_qs(urlsplit(entry_url).query)["entryToken"][0]
        parsed_onboarding = telegram_webhook._parse_patient_onboarding_entry_token(
            entry_token,
            expected_section="appointments",
        )
        assert parsed_onboarding["chat_id"] == chat_id
        assert telegram_webhook._parse_patient_mini_app_entry_token(
            entry_token,
            expected_section="appointments",
        ) is None
        db_session.refresh(telegram_user)
        assert telegram_user.patient_id is None
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == chat_id)
            .one()
        )
        assert log.template_key == template_key

    @pytest.mark.asyncio
    async def test_staff_start_token_links_user_and_writes_audit(
        self, db_session, admin_user
    ):
        token = admin_telegram.issue_staff_link_start_token(
            db_session,
            user_id=admin_user.id,
            chat_id=7010,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            issued_by_user_id=admin_user.id,
            request_id="staff-link-webhook-test",
            nonce="staffwebhook",
        )
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 106,
            "message": {
                "message_id": 1,
                "chat": {"id": 7010},
                "from": {
                    "id": 7010,
                    "username": "staff_chat",
                    "first_name": "Staff",
                    "language_code": "ru",
                },
                "text": f"/start {token}",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7010)
            .one()
        )
        assert telegram_user.user_id == admin_user.id
        assert telegram_user.patient_id is None
        assert telegram_user.notifications_enabled is False

        token_record = (
            db_session.query(TelegramStaffLinkToken)
            .filter(
                TelegramStaffLinkToken.staff_user_id == admin_user.id,
                TelegramStaffLinkToken.telegram_chat_id == 7010,
            )
            .one()
        )
        assert token_record.consumed_at is not None

        audit_log = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "staff_link_created",
                AuditLog.actor_user_id == admin_user.id,
                AuditLog.entity_id == telegram_user.id,
            )
            .one()
        )
        payload_text = str(audit_log.payload)
        assert audit_log.payload["result"] == "success"
        assert audit_log.payload["actor_role"] == "admin"
        assert "telegram_chat:" in audit_log.payload["telegram_user_id_hash"]
        assert "7010" not in payload_text
        assert token not in payload_text
        fake_service._send_message.assert_awaited_once()
        assert (
            fake_service._send_message.await_args.args[1]
            == f"{telegram_webhook.TELEGRAM_STAFF_LINKED_MESSAGE}\nРоль: admin"
        )
        reply_markup = fake_service._send_message.await_args.args[2]
        assert "keyboard" in reply_markup
        assert reply_markup["resize_keyboard"] is True
        assert reply_markup["keyboard"][-1] == [{"text": "/staff"}, {"text": "/help"}]

    @pytest.mark.asyncio
    async def test_staff_start_token_replay_is_rejected_before_patient_onboarding(
        self, db_session, admin_user
    ):
        token = admin_telegram.issue_staff_link_start_token(
            db_session,
            user_id=admin_user.id,
            chat_id=7011,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            issued_by_user_id=admin_user.id,
            nonce="staffreplay",
        )
        update = {
            "update_id": 107,
            "message": {
                "message_id": 1,
                "chat": {"id": 7011},
                "from": {"id": 7011, "first_name": "Staff"},
                "text": f"/start {token}",
            },
        }

        first_service = FakeTelegramBotService(active=True)
        second_service = FakeTelegramBotService(active=True)
        first = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, first_service
        )
        replay = await telegram_webhook._handle_clinic_bot_update(
            {**update, "update_id": 108}, db_session, second_service
        )

        assert first is True
        assert replay is True
        second_service._send_message.assert_awaited_once_with(
            7011,
            telegram_webhook.TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
            telegram_webhook.TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        assert second_service._send_message.await_args.args[1] != (
            telegram_webhook._localized_text("language_prompt", "ru")
        )
        rejection_audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_link_token_rejected")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert rejection_audit is not None
        assert rejection_audit.payload["reason"] == "already_used"
        assert "7011" not in str(rejection_audit.payload)

    @pytest.mark.asyncio
    async def test_invalid_staff_start_token_does_not_create_telegram_user(
        self, db_session
    ):
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 109,
            "message": {
                "message_id": 1,
                "chat": {"id": 7013},
                "from": {"id": 7013, "first_name": "Staff"},
                "text": "/start stl_invalid",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        assert (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7013)
            .first()
            is None
        )
        fake_service._send_message.assert_awaited_once_with(
            7013,
            telegram_webhook.TELEGRAM_STAFF_LINK_REJECTED_MESSAGE,
            telegram_webhook.TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        rejection_audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_link_token_rejected")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert rejection_audit is not None
        assert rejection_audit.payload["reason"] == "signature_invalid"
        assert "7013" not in str(rejection_audit.payload)

    @pytest.mark.asyncio
    async def test_patient_dispatch_routes_staff_start_before_generic_start(
        self, db_session
    ):
        service = telegram_bot.TelegramBotService()
        calls = []
        update = {
            "update_id": 110,
            "message": {
                "message_id": 1,
                "chat": {"id": 7012},
                "from": {"id": 7012},
                "text": "/start stl_test",
            },
        }

        async def staff_start_handler(update_arg, db_arg, bot_arg):
            assert update_arg is update
            assert db_arg is db_session
            assert bot_arg is service
            calls.append("staff")
            return True

        async def ticket_start_handler(_update, _db, _bot):
            calls.append("ticket")
            return False

        async def contact_handler(_message, _db, _bot):
            calls.append("contact")
            return False

        async def start_handler(_chat_id, _message):
            calls.append("start")

        handled = await service.process_patient_bot_update(
            update,
            db_session,
            staff_start_handler=staff_start_handler,
            ticket_start_handler=ticket_start_handler,
            contact_handler=contact_handler,
            start_handler=start_handler,
            command_handlers={},
            text_handlers={},
        )

        assert handled is True
        assert calls == ["staff"]

    @pytest.mark.asyncio
    async def test_contact_link_new_user_prompts_notification_consent(
        self, db_session, test_patient
    ):
        fake_service = FakeTelegramBotService(active=True)
        message = {
            "message_id": 1,
            "chat": {"id": 7024},
            "from": {"id": 7024, "language_code": "ru"},
            "contact": {
                "user_id": 7024,
                "phone_number": test_patient.phone,
            },
        }

        handled = await telegram_webhook._handle_contact_link(
            message, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7024)
            .one()
        )
        assert telegram_user.patient_id == test_patient.id
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False
        chat_id, text, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7024
        assert telegram_webhook._localized_text("contact_linked", "ru") in text
        assert telegram_webhook._localized_text("notification_consent", "ru") in text
        assert reply_markup == telegram_webhook._localized_notification_consent_menu(
            "ru"
        )

    @pytest.mark.asyncio
    async def test_ticket_qr_link_new_user_prompts_notification_consent(
        self, db_session, test_patient, monkeypatch
    ):
        fake_service = FakeTelegramBotService(active=True)
        monkeypatch.setattr(
            telegram_webhook,
            "consume_telegram_ticket_start_token",
            lambda _db, _token: SimpleNamespace(patient_id=test_patient.id),
        )
        update = {
            "update_id": 128,
            "message": {
                "message_id": 1,
                "chat": {"id": 7025},
                "from": {"id": 7025, "language_code": "uz"},
                "text": f"/start {telegram_webhook.TELEGRAM_TICKET_QR_PREFIX}_abc",
            },
        }

        handled = await telegram_webhook._handle_ticket_qr_start(
            update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7025)
            .one()
        )
        assert telegram_user.patient_id == test_patient.id
        assert telegram_user.notifications_enabled is False
        assert telegram_user.appointment_reminders is False
        assert telegram_user.lab_notifications is False
        chat_id, text, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7025
        assert (
            telegram_webhook._localized_text("ticket_qr_linked", "uz-Latn")
            in text
        )
        assert (
            telegram_webhook._localized_text("notification_consent", "uz-Latn")
            in text
        )
        assert reply_markup == telegram_webhook._localized_notification_consent_menu(
            "uz-Latn"
        )

    @pytest.mark.asyncio
    async def test_patient_onboarding_contact_consent_reaches_localized_menu(
        self, db_session, test_patient
    ):
        chat_id = 7026
        fake_service = FakeTelegramBotService(active=True)
        start_update = {
            "update_id": 129,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id},
                "from": {"id": chat_id, "language_code": "ru"},
                "text": "/start",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            start_update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            chat_id,
            telegram_webhook._localized_text("language_prompt", "ru"),
            telegram_webhook.TELEGRAM_LANGUAGE_MENU,
        )
        fake_service._send_message.reset_mock()

        language_update = {
            "update_id": 130,
            "message": {
                "message_id": 2,
                "chat": {"id": chat_id},
                "from": {"id": chat_id, "language_code": "ru"},
                "text": "O'zbekcha",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            language_update, db_session, fake_service
        )

        assert handled is True
        telegram_user = (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == chat_id)
            .one()
        )
        assert telegram_user.language_code == "uz-Latn"
        assert telegram_user.patient_id is None
        assert telegram_user.notifications_enabled is False
        chat_arg, text_arg, reply_markup = fake_service._send_message.await_args.args
        assert chat_arg == chat_id
        assert (
            telegram_webhook._localized_text("language_selected", "uz-Latn")
            in text_arg
        )
        assert (
            telegram_webhook._localized_text("share_contact", "uz-Latn")
            in text_arg
        )
        assert reply_markup == telegram_webhook._localized_main_menu("uz-Latn")
        fake_service._send_message.reset_mock()

        contact_update = {
            "update_id": 131,
            "message": {
                "message_id": 3,
                "chat": {"id": chat_id},
                "from": {"id": chat_id, "language_code": "uz"},
                "contact": {
                    "user_id": chat_id,
                    "phone_number": test_patient.phone,
                },
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            contact_update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.patient_id == test_patient.id
        assert telegram_user.notifications_enabled is False
        chat_arg, text_arg, reply_markup = fake_service._send_message.await_args.args
        assert chat_arg == chat_id
        assert telegram_webhook._localized_text("contact_linked", "uz-Latn") in text_arg
        assert (
            telegram_webhook._localized_text("notification_consent", "uz-Latn")
            in text_arg
        )
        assert reply_markup == telegram_webhook._localized_notification_consent_menu(
            "uz-Latn"
        )
        fake_service._send_message.reset_mock()

        consent_update = {
            "update_id": 132,
            "message": {
                "message_id": 4,
                "chat": {"id": chat_id},
                "from": {"id": chat_id, "language_code": "uz"},
                "text": "Xabarnomalarga roziman",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            consent_update, db_session, fake_service
        )

        assert handled is True
        db_session.refresh(telegram_user)
        assert telegram_user.notifications_enabled is True
        assert telegram_user.appointment_reminders is True
        assert telegram_user.lab_notifications is True
        fake_service._send_message.assert_awaited_once_with(
            chat_id,
            telegram_webhook._localized_text("notifications_enabled", "uz-Latn"),
            telegram_webhook._localized_main_menu("uz-Latn"),
        )
        template_keys = [
            row.template_key
            for row in (
                db_session.query(TelegramMessage)
                .filter(TelegramMessage.chat_id == chat_id)
                .order_by(TelegramMessage.id.asc())
                .all()
            )
        ]
        assert template_keys == [
            "telegram_patient_language_prompt",
            "telegram_patient_language_selected_needs_contact",
            "telegram_patient_contact_linked",
            "telegram_patient_notifications_enabled",
        ]

    def test_queue_message_reports_linked_patient_position_and_cabinet(
        self, db_session, test_patient, test_daily_queue, test_queue_entry
    ):
        _link_patient_to_chat(db_session, chat_id=7002, patient_id=test_patient.id)
        now = datetime.utcnow()
        test_daily_queue.cabinet_number = "205"
        test_queue_entry.number = 2
        test_queue_entry.status = "waiting"
        test_queue_entry.queue_time = now
        earlier_entry = OnlineQueueEntry(
            queue_id=test_daily_queue.id,
            number=1,
            patient_id=None,
            patient_name="Earlier Patient",
            source="desk",
            status="waiting",
            queue_time=now - timedelta(minutes=5),
        )
        db_session.add(earlier_entry)
        db_session.commit()

        message = telegram_webhook._clinic_queue_message(db_session, 7002)

        assert "№2" in message
        assert "позиция: 2" in message
        assert "Кабинет 205" in message
        assert "Кардиология" in message

    def test_queue_status_refresh_preserves_ordering_and_queue_time(
        self, db_session, test_patient, test_daily_queue, test_queue_entry
    ):
        _link_patient_to_chat(db_session, chat_id=7003, patient_id=test_patient.id)
        test_daily_queue.day = date.today()
        first_time = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=20)
        linked_time = first_time + timedelta(minutes=10)
        later_time = linked_time + timedelta(minutes=10)
        test_queue_entry.number = 2
        test_queue_entry.status = "waiting"
        test_queue_entry.queue_time = linked_time
        test_queue_entry.patient_id = test_patient.id
        first_entry = OnlineQueueEntry(
            queue_id=test_daily_queue.id,
            number=1,
            patient_id=None,
            patient_name="First Patient",
            source="desk",
            status="waiting",
            queue_time=first_time,
        )
        later_entry = OnlineQueueEntry(
            queue_id=test_daily_queue.id,
            number=3,
            patient_id=None,
            patient_name="Later Patient",
            source="desk",
            status="waiting",
            queue_time=later_time,
        )
        db_session.add_all([later_entry, first_entry])
        db_session.commit()
        db_session.refresh(test_queue_entry)
        db_session.refresh(first_entry)
        db_session.refresh(later_entry)
        original_snapshot = [
            (entry.id, entry.number, entry.status, entry.queue_time)
            for entry in [first_entry, test_queue_entry, later_entry]
        ]

        first_message = telegram_webhook._clinic_queue_message(db_session, 7003)
        second_message = telegram_webhook._clinic_queue_message(db_session, 7003)

        assert first_message == second_message
        assert str(test_queue_entry.number) in second_message
        assert telegram_webhook._queue_entry_position(db_session, test_queue_entry) == 2
        db_session.refresh(first_entry)
        db_session.refresh(test_queue_entry)
        db_session.refresh(later_entry)
        assert [
            (entry.id, entry.number, entry.status, entry.queue_time)
            for entry in [first_entry, test_queue_entry, later_entry]
        ] == original_snapshot
        assert (
            db_session.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == test_daily_queue.id)
            .order_by(
                OnlineQueueEntry.priority.desc(),
                OnlineQueueEntry.queue_time.asc(),
                OnlineQueueEntry.id.asc(),
            )
            .all()
        ) == [first_entry, test_queue_entry, later_entry]

    def test_visits_message_lists_linked_patient_visits_without_medical_details(
        self, db_session, test_patient, test_visit
    ):
        _link_patient_to_chat(db_session, chat_id=7005, patient_id=test_patient.id)
        test_visit.status = "open"
        test_visit.notes = "diagnosis: private clinical note"
        db_session.commit()

        message = telegram_webhook._clinic_visits_message(db_session, 7005)

        assert f"#{test_visit.id}" in message
        assert test_visit.visit_date.isoformat() in message
        assert "open" in message
        assert "diagnosis" not in message
        assert "private clinical note" not in message
        if test_patient.phone:
            assert test_patient.phone not in message

    @pytest.mark.asyncio
    async def test_profile_command_returns_linked_patient_status_without_medical_details(
        self, db_session, test_patient, test_visit
    ):
        _link_patient_to_chat(db_session, chat_id=7022, patient_id=test_patient.id)
        test_visit.status = "open"
        test_visit.notes = "diagnosis: private clinical note"
        db_session.commit()
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 122,
            "message": {
                "message_id": 1,
                "chat": {"id": 7022},
                "from": {"id": 111},
                "text": "/profile",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        chat_id, message, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7022
        assert test_patient.first_name in message
        assert f"#{test_visit.id}" in message
        assert "open" in message
        assert reply_markup == telegram_webhook._localized_main_menu("ru")
        assert "diagnosis" not in message
        assert "private clinical note" not in message
        if test_patient.phone:
            assert test_patient.phone not in message

    def test_payments_message_calculates_debt_from_queue_total_and_payments(
        self, db_session, test_patient, test_visit, test_queue_entry
    ):
        _link_patient_to_chat(db_session, chat_id=7003, patient_id=test_patient.id)
        test_queue_entry.visit_id = test_visit.id
        test_queue_entry.total_amount = 120000
        db_session.add_all(
            [
                Payment(
                    visit_id=test_visit.id,
                    amount=Decimal("50000"),
                    status="paid",
                    method="cash",
                ),
                Payment(
                    visit_id=test_visit.id,
                    amount=Decimal("10000"),
                    status="pending",
                    method="cash",
                ),
            ]
        )
        db_session.commit()

        message = telegram_webhook._clinic_payments_message(db_session, 7003)

        assert "Начислено: 120 000 сум" in message
        assert "Оплачено: 50 000 сум" in message
        assert "Долг: 70 000 сум" in message
        assert "Ожидает подтверждения: 10 000 сум" in message

    def test_payments_message_uses_protected_entry_without_visit_ids(
        self, db_session, test_patient, test_visit, test_queue_entry, monkeypatch
    ):
        monkeypatch.setattr(
            telegram_webhook.settings,
            "FRONTEND_URL",
            "https://clinic.example",
            raising=False,
        )
        _link_patient_to_chat(db_session, chat_id=7023, patient_id=test_patient.id)
        test_queue_entry.visit_id = test_visit.id
        test_queue_entry.total_amount = 120000
        db_session.commit()

        message = telegram_webhook._clinic_payments_message(db_session, 7023)

        assert (
            telegram_webhook._localized_text("payments_visits", "ru").format(count=1)
            in message
        )
        assert (
            telegram_webhook._localized_text("payments_protected_entry", "ru")
            in message
        )
        assert (
            telegram_webhook._localized_text("payments_online_unavailable", "ru")
            not in message
        )
        assert f"#{test_visit.id}" not in message

    @pytest.mark.asyncio
    async def test_payments_command_sends_protected_entry_button_without_internal_ids(
        self, db_session, test_patient, test_visit, test_queue_entry, monkeypatch
    ):
        monkeypatch.setattr(
            telegram_webhook.settings,
            "FRONTEND_URL",
            "https://clinic.example/",
            raising=False,
        )
        _link_patient_to_chat(db_session, chat_id=7024, patient_id=test_patient.id)
        test_queue_entry.visit_id = test_visit.id
        test_queue_entry.total_amount = 120000
        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("10000"),
            status="pending",
            method="cash",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)
        fake_service = FakeTelegramBotService(active=True)
        update = {
            "update_id": 124,
            "message": {
                "message_id": 1,
                "chat": {"id": 7024},
                "from": {"id": 111},
                "text": "/payments",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        chat_id, _message, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7024
        assert reply_markup == {
            "inline_keyboard": [
                [
                    {
                        "text": telegram_webhook._localized_text(
                            "payments_entry_button", "ru"
                        ),
                        "web_app": {
                            "url": "https://clinic.example"
                            + admin_telegram.PATIENT_PAYMENT_ENTRY_ROUTE,
                        },
                    }
                ]
            ]
        }
        assert str(test_patient.id) not in str(reply_markup)
        assert str(test_visit.id) not in str(reply_markup)
        assert str(payment.id) not in str(reply_markup)
        telegram_payload = f"{_message} {reply_markup}"
        assert f"#{test_visit.id}" not in telegram_payload
        assert "patient_id" not in telegram_payload
        assert "visit_id" not in telegram_payload
        assert "payment_id" not in telegram_payload
        assert "invoice_id" not in telegram_payload
        assert "/payment/success" not in telegram_payload
        assert "/payment/cancel" not in telegram_payload
        assert "/internal-demo/payment-test" not in telegram_payload

    def test_ready_lab_reports_are_filtered_by_patient_status_and_limited(
        self, db_session, test_patient
    ):
        other_patient = Patient(first_name="Other", last_name="Patient")
        template = LabReportTemplate(
            code="TG_TEST_REPORT",
            name="Telegram Test Report",
            family="test",
        )
        db_session.add_all([other_patient, template])
        db_session.flush()
        version = LabReportTemplateVersion(
            template_id=template.id,
            version_no=1,
            status="PUBLISHED",
            layout_preset="default",
            page_settings={},
            branding_overrides={},
            signer_defaults={},
        )
        db_session.add(version)
        db_session.flush()
        base_time = datetime.utcnow()
        ready_instances = [
            _create_lab_report_instance(
                db_session,
                patient_id=test_patient.id,
                template=template,
                version=version,
                status_value=status_value,
                created_at=base_time + timedelta(minutes=index),
            )
            for index, status_value in enumerate(
                ["FINALIZED", "PRINTED", "FINALIZED", "PRINTED"], start=1
            )
        ]
        _create_lab_report_instance(
            db_session,
            patient_id=test_patient.id,
            template=template,
            version=version,
            status_value="DRAFT",
            created_at=base_time + timedelta(minutes=99),
        )
        _create_lab_report_instance(
            db_session,
            patient_id=other_patient.id,
            template=template,
            version=version,
            status_value="FINALIZED",
            created_at=base_time + timedelta(minutes=100),
        )
        db_session.commit()

        result = telegram_webhook._latest_ready_lab_report_instances(
            db_session, test_patient.id
        )

        assert len(result) == 3
        assert {item.patient_id for item in result} == {test_patient.id}
        assert {item.status for item in result} <= {"FINALIZED", "PRINTED"}
        assert [item.id for item in result] == [
            ready_instances[3].id,
            ready_instances[2].id,
            ready_instances[1].id,
        ]

    @pytest.mark.asyncio
    async def test_lab_results_flow_sends_pdf_through_bot_service(
        self, db_session, test_patient, monkeypatch
    ):
        _link_patient_to_chat(db_session, chat_id=7004, patient_id=test_patient.id)
        fake_service = FakeTelegramBotService(active=True)
        fake_instance = SimpleNamespace(id=456)
        monkeypatch.setattr(
            telegram_webhook,
            "_latest_ready_lab_report_instances",
            lambda db, patient_id: [fake_instance],
        )
        monkeypatch.setattr(
            telegram_webhook,
            "_build_lab_report_pdf",
            lambda db, instance: (
                "result.pdf",
                b"%PDF-1.4",
                "Ready result",
            ),
        )

        await telegram_webhook._send_clinic_lab_results(db_session, fake_service, 7004)

        fake_service._send_document.assert_awaited_once_with(
            7004,
            "result.pdf",
            b"%PDF-1.4",
            "Ready result",
        )
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.related_entity_id == 456)
            .one()
        )
        assert log.message_type == "lab_result_pdf"
        assert log.related_entity_type == "lab_report_instance"
        assert log.status == "sent"
        assert log.message_id == 77

    @pytest.mark.asyncio
    async def test_telegram_bot_service_send_document_posts_pdf_bytes(self, monkeypatch):
        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"ok": True, "result": {"message_id": 88}}

        def fake_post(url, data, files, timeout):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            captured["timeout"] = timeout
            return FakeResponse()

        monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
        service = telegram_bot.TelegramBotService()
        service.bot_token = "bot-token"

        ok, message_id, error = await service._send_document(
            7005,
            "service-result.pdf",
            b"%PDF-1.4 service",
            "Service result",
        )

        assert ok is True
        assert message_id == 88
        assert error is None
        assert captured["url"].endswith("/sendDocument")
        assert captured["data"] == {
            "chat_id": 7005,
            "caption": "Service result",
            "parse_mode": "HTML",
        }
        assert captured["files"]["document"] == (
            "service-result.pdf",
            b"%PDF-1.4 service",
            "application/pdf",
        )
        assert captured["timeout"] == 20

    @pytest.mark.asyncio
    async def test_telegram_bot_service_blocks_corrupted_send_message(self, monkeypatch):
        captured = []

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"ok": True}

        def fake_post(url, json, timeout):
            captured.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse()

        monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
        service = telegram_bot.TelegramBotService()
        service.bot_token = "bot-token"

        assert await service._send_message(7006, "???? Mini App") is False
        assert captured == []

        valid_ru_text = "\u041a\u0430\u0431\u0438\u043d\u0435\u0442 \u043f\u0430\u0446\u0438\u0435\u043d\u0442\u0430"
        assert telegram_bot.telegram_text_corruption_reason(valid_ru_text) is None
        assert await service._send_message(7006, valid_ru_text) is True
        assert len(captured) == 1
        assert captured[0]["json"]["text"] == valid_ru_text

    @pytest.mark.asyncio
    async def test_patient_bot_reply_blocks_corrupted_log_text(self, db_session):
        fake_service = FakeTelegramBotService(active=True)

        sent = await telegram_webhook._send_patient_bot_reply(
            db_session,
            fake_service,
            7007,
            "???? Mini App",
            telegram_webhook._localized_main_menu("ru"),
            "telegram_patient_help",
        )

        assert sent is False
        fake_service._send_message.assert_not_awaited()
        log = (
            db_session.query(TelegramMessage)
            .filter(TelegramMessage.chat_id == 7007)
            .one()
        )
        assert log.status == "failed"
        assert log.message_text == "[blocked_corrupted_text]"
        assert log.error_message == "blocked_corrupted_text:question_mark_run"

    def test_patient_facing_localized_templates_have_no_corruption_markers(self):
        for key, values in telegram_webhook.TELEGRAM_LOCALIZED_TEXTS.items():
            for language, text in values.items():
                assert telegram_bot.telegram_text_corruption_reason(text) is None, (
                    key,
                    language,
                    telegram_bot.telegram_text_corruption_reason(text),
                )

    @pytest.mark.asyncio
    async def test_telegram_bot_service_registers_patient_commands(self, monkeypatch):
        captured = []

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"ok": True, "result": True}

        def fake_post(url, json, timeout):
            captured.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse()

        monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
        service = telegram_bot.TelegramBotService()
        service.bot_token = "bot-token"

        ok, error = await service.set_patient_bot_commands()

        assert ok is True
        assert error is None
        assert len(captured) == 3 + len(telegram_bot.PATIENT_BOT_PROFILE_TEXTS)
        assert [item["json"].get("language_code") for item in captured[:2]] == [
            None,
            "uz",
        ]
        assert captured[0]["url"].endswith("/setMyCommands")
        assert captured[1]["url"].endswith("/setMyCommands")
        assert captured[2]["url"].endswith("/setChatMenuButton")
        assert captured[0]["json"]["commands"] == telegram_bot.PATIENT_BOT_COMMANDS_RU
        assert captured[1]["json"]["commands"] == telegram_bot.PATIENT_BOT_COMMANDS_UZ
        assert captured[2]["json"] == {
            "menu_button": telegram_bot.PATIENT_BOT_MENU_BUTTON
        }
        profile_calls = captured[3:]
        assert [item["url"].rsplit("/", 1)[-1] for item in profile_calls] == [
            item["method"] for item in telegram_bot.PATIENT_BOT_PROFILE_TEXTS
        ]
        assert [item["json"] for item in profile_calls] == [
            item["payload"] for item in telegram_bot.PATIENT_BOT_PROFILE_TEXTS
        ]
        ru_command_names = [
            command["command"] for command in captured[0]["json"]["commands"]
        ]
        uz_command_names = [
            command["command"] for command in captured[1]["json"]["commands"]
        ]
        assert len(ru_command_names) == len(set(ru_command_names))
        assert len(uz_command_names) == len(set(uz_command_names))
        assert {command["command"] for command in captured[0]["json"]["commands"]} == {
            "start",
            "menu",
            "book",
            "queue",
            "visits",
            "payments",
            "results",
            "services",
            "forms",
            "documents",
            "doctors",
            "cabinet",
            "profile",
            "settings",
            "support",
            "help",
        }
        assert {command["command"] for command in captured[1]["json"]["commands"]} == {
            "start",
            "menu",
            "book",
            "queue",
            "visits",
            "payments",
            "results",
            "services",
            "forms",
            "documents",
            "doctors",
            "cabinet",
            "profile",
            "settings",
            "support",
            "help",
        }
