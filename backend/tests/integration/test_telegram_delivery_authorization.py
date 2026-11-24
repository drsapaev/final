"""Real HTTP/DB security checks; all Telegram provider methods are mocked."""

import asyncio
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints import telegram_bot as bot_api
from app.api.v1.endpoints import telegram_integration as integration
from app.main import app
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.lab import LabOrder, LabReportInstance, LabResult
from app.models.online_queue import QueueToken
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.visit import Visit
from app.services import telegram_delivery_authorization
from tests.conftest import mint_access_token
from tests.integration.test_activation_concurrency_pg import pg_engine  # noqa: F401


@pytest.fixture
def telegram_case(db_session, test_doctor_user, monkeypatch):
    suffix = secrets.randbelow(10**7)
    patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone=f"+99890{suffix:07d}")
    other = Patient(first_name="SYNTHETIC", last_name="OTHER", phone=f"+99891{suffix:07d}")
    doctor = Doctor(user_id=test_doctor_user.id, specialty="cardiology", active=True)
    db_session.add_all([patient, other, doctor])
    db_session.flush()
    appt = Appointment(patient_id=patient.id, doctor_id=doctor.id,
                       appointment_date=date(2030, 1, 2), appointment_time="10:30")
    visit = Visit(patient_id=patient.id, doctor_id=doctor.id)
    link = TelegramUser(patient_id=patient.id, chat_id=800000000 + suffix,
                        active=True, blocked=False, notifications_enabled=True,
                        appointment_reminders=True, lab_notifications=True)
    other_link = TelegramUser(patient_id=other.id, chat_id=900000000 + suffix,
                              active=True, blocked=False, notifications_enabled=True,
                              appointment_reminders=True, lab_notifications=True)
    db_session.add_all([appt, visit, link, other_link])
    db_session.flush()
    order = LabOrder(patient_id=patient.id, visit_id=visit.id, status="done")
    db_session.add(order)
    db_session.flush()
    result = LabResult(order_id=order.id, test_name="SYNTHETIC LAB")
    db_session.add(result)
    db_session.commit()

    direct_appointment = AsyncMock(return_value=True)
    direct_lab = AsyncMock(return_value=True)
    direct_generic = AsyncMock(return_value=True)
    monkeypatch.setattr(bot_api.telegram_bot, "bot", object())
    monkeypatch.setattr(bot_api.telegram_bot, "send_appointment_reminder", direct_appointment)
    monkeypatch.setattr(bot_api.telegram_bot, "send_lab_results_ready", direct_lab)
    monkeypatch.setattr(bot_api.telegram_bot, "send_notification", direct_generic)
    token = secrets.token_urlsafe(20)
    service = SimpleNamespace(active=True, bot_token=token, initialize=AsyncMock(return_value=True),
                              send_plain_message=AsyncMock(return_value=True))
    monkeypatch.setattr(integration, "get_telegram_bot_service", AsyncMock(return_value=service))
    monkeypatch.setattr(integration, "resolve_patient_bot_token", lambda _db: token)
    monkeypatch.setattr(integration.crud_telegram, "get_telegram_config", lambda _db: None)
    return SimpleNamespace(patient=patient, other=other, doctor=doctor, appointment=appt,
                           visit=visit, result=result, link=link, other_link=other_link,
                           service=service, direct_appointment=direct_appointment,
                           direct_lab=direct_lab, direct_generic=direct_generic, user=test_doctor_user,
                           headers={"Authorization": f"Bearer {mint_access_token(test_doctor_user)}"})


def test_appointment_uses_database_identity_and_exact_link(client, telegram_case):
    c = telegram_case
    response = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=c.headers,
        json={"user_id": c.link.chat_id, "appointment": {"id": c.appointment.id,
              "doctor_name": "ATTACKER NAME", "date": "1900-01-01"}})
    assert response.status_code == 200, response.text
    args = c.direct_appointment.await_args.args
    assert args[0] == c.link.chat_id
    assert args[1]["id"] == c.appointment.id and args[1]["patient_id"] == c.patient.id
    assert args[1]["date"] == "2030-01-02" and "ATTACKER NAME" not in repr(args)


@pytest.mark.parametrize("day,appointment_time,allowed", [
    (date(2030, 1, 2), "08:59", False),
    (date(2030, 1, 2), "09:00", False),
    (date(2030, 1, 2), "09:01", True),
    (date(2030, 1, 2), None, False),
    (date(2030, 1, 3), None, True),
    (date(2030, 1, 3), "30:70", False),
    (date(2030, 1, 3), "10:00+03:00", False),
])
def test_appointment_reminder_occurrence_matches_rsvp_policy(
    client, db_session, admin_auth_headers, telegram_case, monkeypatch, day, appointment_time, allowed
):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2030, 1, 2, 4, 0, tzinfo=UTC)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(telegram_delivery_authorization, "datetime", FrozenDatetime)
    monkeypatch.setattr("app.services.appointment_rsvp.settings.TIMEZONE", "Asia/Tashkent")
    case = telegram_case
    case.appointment.appointment_date = day
    case.appointment.appointment_time = appointment_time
    db_session.commit()
    requests = [
        ("/api/v1/telegram/bot/send-appointment-reminder", {"user_id": case.link.chat_id, "appointment": {"id": case.appointment.id}}),
        ("/api/v1/telegram/send-notification", {"chat_id": case.link.chat_id, "template_key": "appointment_reminder", "data": {"id": case.appointment.id}}),
        ("/api/v1/telegram/appointment-reminder", {"patient_phone": case.patient.phone, "appointment_data": {"id": case.appointment.id}}),
    ]
    for path, body in requests:
        response = client.post(path, headers=admin_auth_headers, json=body)
        assert response.status_code == (200 if allowed else 409), (path, response.text)
    quick = client.post("/api/v1/telegram/quick/appointment-reminder", headers=admin_auth_headers,
        params={"patient_phone": case.patient.phone, "doctor_name": "SYNTHETIC", "appointment_date": "ignored",
                "appointment_time": "ignored", "appointment_id": case.appointment.id})
    assert quick.status_code == (200 if allowed else 409), quick.text
    assert case.direct_appointment.await_count == (1 if allowed else 0)
    assert case.service.send_plain_message.await_count == (3 if allowed else 0)


def test_disabled_bot_does_not_deliver_from_direct_endpoints(
    client, db_session, admin_auth_headers, telegram_case
):
    from app.models.telegram_config import TelegramConfig

    case = telegram_case
    config = TelegramConfig(active=False)
    db_session.add(config)
    db_session.commit()
    for path, body in [
        ("/api/v1/telegram/bot/send-notification", {"user_id": case.link.chat_id, "message": "SYNTHETIC"}),
        ("/api/v1/telegram/bot/send-appointment-reminder", {"user_id": case.link.chat_id, "appointment": {"id": case.appointment.id}}),
        ("/api/v1/telegram/bot/send-lab-notification", {"user_id": case.link.chat_id, "results": {"id": case.result.id}}),
    ]:
        response = client.post(path, headers=admin_auth_headers, json=body)
        assert response.status_code == 503, (path, response.text)
    case.direct_generic.assert_not_awaited()
    case.direct_appointment.assert_not_awaited()
    case.direct_lab.assert_not_awaited()
    config.active = True
    db_session.commit()
    response = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=admin_auth_headers,
                           json={"user_id": case.link.chat_id, "appointment": {"id": case.appointment.id}})
    assert response.status_code == 200, response.text
    case.direct_appointment.assert_awaited_once()


def test_appointment_rejects_missing_id_and_another_chat(client, telegram_case):
    c = telegram_case
    missing = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=c.headers,
                          json={"user_id": c.link.chat_id, "appointment": {}})
    wrong = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=c.headers,
                        json={"user_id": c.other_link.chat_id, "appointment": {"id": c.appointment.id}})
    assert missing.status_code == 400
    assert wrong.status_code == 404
    c.direct_appointment.assert_not_awaited()


@pytest.mark.parametrize("state", ["cancelled", "completed", "no_show", "unknown"])
def test_terminal_appointment_never_sends_reminder(client, db_session, telegram_case, state):
    c = telegram_case
    c.appointment.status = state
    db_session.commit()
    response = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=c.headers,
                           json={"user_id": c.link.chat_id, "appointment": {"id": c.appointment.id}})
    assert response.status_code == 409
    c.direct_appointment.assert_not_awaited()


@pytest.mark.parametrize("flag,value", [("active", False), ("blocked", True),
                                        ("notifications_enabled", False), ("appointment_reminders", False)])
def test_appointment_rejects_ineligible_link(client, db_session, telegram_case, flag, value):
    c = telegram_case
    setattr(c.link, flag, value)
    db_session.commit()
    response = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=c.headers,
                           json={"user_id": c.link.chat_id, "appointment": {"id": c.appointment.id}})
    assert response.status_code == 404
    c.direct_appointment.assert_not_awaited()


def test_doctor_cannot_notify_unassigned_appointment_or_lab(client, db_session, telegram_case):
    c = telegram_case
    c.appointment.doctor_id = None
    c.visit.doctor_id = None
    db_session.commit()
    appt = client.post("/api/v1/telegram/bot/send-appointment-reminder", headers=c.headers,
                       json={"user_id": c.link.chat_id, "appointment": {"id": c.appointment.id}})
    lab = client.post("/api/v1/telegram/bot/send-lab-notification", headers=c.headers,
                      json={"user_id": c.link.chat_id, "results": {"id": c.result.id}})
    assert (appt.status_code, lab.status_code) == (404, 404)
    c.direct_appointment.assert_not_awaited()
    c.direct_lab.assert_not_awaited()


def test_lab_delivery_false_is_not_reported_as_success(client, telegram_case):
    c = telegram_case
    c.direct_lab.return_value = False
    response = client.post("/api/v1/telegram/bot/send-lab-notification", headers=c.headers,
                           json={"user_id": c.link.chat_id, "results": {"id": c.result.id,
                                 "test_name": "FORGED LAB"}})
    assert response.status_code == 502
    assert c.direct_lab.await_args.args[1]["test_name"] == "SYNTHETIC LAB"


def test_lab_rejects_unready_or_opted_out_result(client, db_session, telegram_case):
    c = telegram_case
    order = db_session.get(LabOrder, c.result.order_id)
    order.status = "ordered"
    db_session.commit()
    unready = client.post("/api/v1/telegram/bot/send-lab-notification", headers=c.headers,
                          json={"user_id": c.link.chat_id, "results": {"id": c.result.id}})
    assert unready.status_code == 409
    order.status = "done"
    c.link.lab_notifications = False
    db_session.commit()
    opted_out = client.post("/api/v1/telegram/bot/send-lab-notification", headers=c.headers,
                            json={"user_id": c.link.chat_id, "results": {"id": c.result.id}})
    assert opted_out.status_code == 404
    c.direct_lab.assert_not_awaited()


def test_finalized_report_can_provide_missing_order_patient_and_visit(
    client, db_session, telegram_case
):
    c = telegram_case
    order = db_session.get(LabOrder, c.result.order_id)
    order.patient_id = None
    order.visit_id = None
    order.status = "ordered"
    source = LabReportInstance(order_id=order.id, patient_id=c.patient.id, visit_id=c.visit.id,
                               template_id=1, template_version_id=1, status="FINALIZED")
    db_session.add(source)
    db_session.flush()
    c.result.source_instance_id = source.id
    db_session.commit()
    response = client.post("/api/v1/telegram/bot/send-lab-notification", headers=c.headers,
                           json={"user_id": c.link.chat_id, "results": {"id": c.result.id}})
    assert response.status_code == 200, response.text
    c.direct_lab.assert_awaited_once()


def test_integration_lab_is_patient_bound_and_uses_protected_message(client, telegram_case):
    c = telegram_case
    response = client.post("/api/v1/telegram/lab-results-notification", headers=c.headers,
        json={"patient_phone": c.patient.phone, "lab_data": {"id": c.result.id,
              "patient_name": "FORGED", "test_type": "FORGED LAB"}})
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "message": "Уведомление о результатах отправлено"}
    sent_chat, sent_text = c.service.send_plain_message.await_args.args
    assert sent_chat == c.link.chat_id and "FORGED" not in sent_text
    assert "SYNTHETIC LAB" not in sent_text


def test_integration_rejects_foreign_phone_and_missing_id(client, telegram_case):
    c = telegram_case
    foreign = client.post("/api/v1/telegram/lab-results-notification", headers=c.headers,
                          json={"patient_phone": c.other.phone, "lab_data": {"id": c.result.id}})
    missing = client.post("/api/v1/telegram/lab-results-notification", headers=c.headers,
                          json={"patient_phone": c.patient.phone, "lab_data": {}})
    assert (foreign.status_code, missing.status_code) == (404, 400)
    c.service.send_plain_message.assert_not_awaited()


def test_integration_rejects_other_patients_appointment_and_lab(
    client, db_session, registrar_user, telegram_case
):
    c = telegram_case
    other_appointment = Appointment(
        patient_id=c.other.id, doctor_id=c.doctor.id,
        appointment_date=date(2030, 1, 2), appointment_time="12:00",
    )
    other_order = LabOrder(patient_id=c.other.id, status="done")
    db_session.add_all([other_appointment, other_order])
    db_session.flush()
    other_result = LabResult(order_id=other_order.id, test_name="SYNTHETIC OTHER LAB")
    db_session.add(other_result)
    db_session.commit()
    registrar_headers = {"Authorization": f"Bearer {mint_access_token(registrar_user)}"}
    appt = client.post("/api/v1/telegram/appointment-reminder", headers=registrar_headers,
                       json={"patient_phone": c.patient.phone,
                             "appointment_data": {"id": other_appointment.id}})
    lab = client.post("/api/v1/telegram/lab-results-notification", headers=c.headers,
                      json={"patient_phone": c.patient.phone, "lab_data": {"id": other_result.id}})
    assert (appt.status_code, lab.status_code) == (404, 404)
    c.service.send_plain_message.assert_not_awaited()


def test_generic_requires_scoped_resource_and_target_link(client, telegram_case):
    c = telegram_case
    raw = client.post("/api/v1/telegram/send-notification", headers=c.headers,
                      json={"chat_id": c.link.chat_id, "template_key": "arbitrary", "data": {"text": "x"}})
    foreign = client.post("/api/v1/telegram/send-notification", headers=c.headers,
                          json={"chat_id": c.other_link.chat_id, "template_key": "appointment_reminder",
                                "data": {"id": c.appointment.id}})
    assert (raw.status_code, foreign.status_code) == (400, 404)
    c.service.send_plain_message.assert_not_awaited()


def test_admin_arbitrary_message_requires_both_category_opt_ins(
    client, db_session, admin_auth_headers, telegram_case
):
    c = telegram_case
    c.link.lab_notifications = False
    db_session.commit()
    denied = client.post("/api/v1/telegram/bot/send-notification", headers=admin_auth_headers,
                         json={"user_id": c.link.chat_id, "message": "SYNTHETIC"})
    assert denied.status_code == 404
    c.direct_generic.assert_not_awaited()
    c.link.lab_notifications = True
    db_session.commit()
    allowed = client.post("/api/v1/telegram/bot/send-notification", headers=admin_auth_headers,
                          json={"user_id": c.link.chat_id, "message": "SYNTHETIC"})
    assert allowed.status_code == 200, allowed.text
    c.direct_generic.assert_awaited_once_with(c.link.chat_id, "SYNTHETIC")


def test_integration_false_transport_is_502_and_no_recipient_metadata(client, telegram_case):
    c = telegram_case
    c.service.send_plain_message.return_value = False
    response = client.post("/api/v1/telegram/lab-results-notification", headers=c.headers,
                           json={"patient_phone": c.patient.phone, "lab_data": {"id": c.result.id}})
    assert response.status_code == 502
    assert c.patient.phone not in response.text and str(c.link.chat_id) not in response.text


def test_integration_rechecks_consent_after_awaited_initialization(client, db_session, telegram_case):
    c = telegram_case
    c.service.active = False

    async def revoke_during_initialize(_db):
        c.link.lab_notifications = False
        db_session.commit()
        c.service.active = True
        return True

    c.service.initialize.side_effect = revoke_during_initialize
    response = client.post("/api/v1/telegram/lab-results-notification", headers=c.headers,
                           json={"patient_phone": c.patient.phone, "lab_data": {"id": c.result.id}})
    assert response.status_code == 404
    c.service.send_plain_message.assert_not_awaited()


def test_integration_rechecks_appointment_after_awaited_initialization(
    client, db_session, registrar_user, telegram_case
):
    c = telegram_case
    c.service.active = False

    async def move_during_initialize(_db):
        c.appointment.patient_id = c.other.id
        db_session.commit()
        c.service.active = True
        return True

    c.service.initialize.side_effect = move_during_initialize
    headers = {"Authorization": f"Bearer {mint_access_token(registrar_user)}"}
    response = client.post("/api/v1/telegram/appointment-reminder", headers=headers,
                           json={"patient_phone": c.patient.phone,
                                 "appointment_data": {"id": c.appointment.id}})
    assert response.status_code == 404
    c.service.send_plain_message.assert_not_awaited()


def test_qr_requires_unambiguous_patient_link_and_live_token(client, db_session, admin_auth_headers, telegram_case):
    c = telegram_case
    raw = secrets.token_urlsafe(24)
    db_session.add(QueueToken(token=raw, day=date(2030, 1, 2), active=True,
                              expires_at=datetime.now(UTC) + timedelta(hours=1)))
    db_session.commit()
    response = client.post("/api/v1/telegram/send-qr-code", headers=admin_auth_headers,
                           json={"patient_phone": c.patient.phone, "qr_data": {"token": raw}})
    assert response.status_code == 200, response.text
    assert raw not in response.text and c.patient.phone not in response.text
    assert c.service.send_plain_message.await_args.args[0] == c.link.chat_id
    assert raw in c.service.send_plain_message.await_args.args[1]


def test_qr_rejects_duplicate_patient_phone_and_expired_token(client, db_session, admin_auth_headers, telegram_case):
    c = telegram_case
    active = secrets.token_urlsafe(24)
    expired = secrets.token_urlsafe(24)
    c.other.phone = c.patient.phone
    db_session.add_all([
        QueueToken(token=active, day=date(2030, 1, 2), active=True,
                   expires_at=datetime.now(UTC) + timedelta(hours=1)),
        QueueToken(token=expired, day=date(2030, 1, 2), active=True,
                   expires_at=datetime.now(UTC) - timedelta(seconds=1)),
    ])
    db_session.commit()
    for token in (active, expired):
        response = client.post("/api/v1/telegram/send-qr-code", headers=admin_auth_headers,
                               json={"patient_phone": c.patient.phone, "qr_data": {"token": token}})
        assert response.status_code == 404
    c.service.send_plain_message.assert_not_awaited()


def test_postgres_revocation_during_transport_initialization_is_rechecked(pg_engine, monkeypatch):
    """A separate committed DB revocation before dispatch must stop delivery."""
    suffix = secrets.token_hex(5)
    with Session(pg_engine, expire_on_commit=False) as db:
        actor = User(username=f"SYNTHETIC-{suffix}", hashed_password=secrets.token_urlsafe(24),
                     role="Doctor", is_active=True, is_superuser=False)
        patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", phone="+998901234567")
        db.add_all([actor, patient])
        db.flush()
        doctor = Doctor(user_id=actor.id, specialty="cardiology", active=True)
        db.add(doctor)
        db.flush()
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id)
        link = TelegramUser(patient_id=patient.id, chat_id=123456789,
                            active=True, blocked=False, notifications_enabled=True,
                            appointment_reminders=True, lab_notifications=True)
        db.add_all([visit, link])
        db.flush()
        order = LabOrder(patient_id=patient.id, visit_id=visit.id, status="done")
        db.add(order)
        db.flush()
        result = LabResult(order_id=order.id, test_name="SYNTHETIC")
        db.add(result)
        db.commit()
        link_id, result_id, phone = link.id, result.id, patient.phone
        headers = {"Authorization": f"Bearer {mint_access_token(actor)}"}

    entered, resume = threading.Event(), threading.Event()
    token = secrets.token_urlsafe(20)
    service = SimpleNamespace(active=True, bot_token=token, send_plain_message=AsyncMock(return_value=True))

    async def initialize(_db):
        entered.set()
        if not await asyncio.to_thread(resume.wait, 10):
            raise TimeoutError("synthetic transport initialization timed out")
        service.active = True
        return True

    service.initialize = initialize
    monkeypatch.setattr(integration, "get_telegram_bot_service", AsyncMock(return_value=service))
    monkeypatch.setattr(integration, "resolve_patient_bot_token", lambda _db: token)
    monkeypatch.setattr(integration.crud_telegram, "get_telegram_config", lambda _db: None)

    def override_db():
        with Session(pg_engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as executor:
            allowed = client.post("/api/v1/telegram/lab-results-notification",
                                  headers=headers, json={"patient_phone": phone, "lab_data": {"id": result_id}})
            assert allowed.status_code == 200, allowed.text
            service.send_plain_message.assert_awaited_once()
            service.send_plain_message.reset_mock()
            service.active = False
            future = executor.submit(client.post, "/api/v1/telegram/lab-results-notification",
                                     headers=headers, json={"patient_phone": phone, "lab_data": {"id": result_id}})
            assert entered.wait(10)
            with Session(pg_engine) as revoker:
                revoker.get(TelegramUser, link_id).lab_notifications = False
                revoker.commit()
            resume.set()
            response = future.result(timeout=15)
        assert response.status_code == 404
        service.send_plain_message.assert_not_awaited()
    finally:
        resume.set()
        app.dependency_overrides.pop(get_db, None)
