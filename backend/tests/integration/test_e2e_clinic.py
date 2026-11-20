"""
End-to-End интеграционный тест для полного флоу клиники:
Login → Create Patient → Create Visit → Create EMR → Create Payment → PayMe Webhook → Verify
"""
import base64
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction
from app.models.user_profile import UserAuditLog
from app.models.visit import Visit, VisitService

# Используем фикстуру client из conftest.py
# Не создаем новую, чтобы избежать проблем с потоками SQLite


@pytest.fixture
def registrar_user(db_session):
    """Создает тестового регистратора"""
    from app.core.security import get_password_hash
    from app.models.user import User

    user = User(
        username="registrar",
        email="registrar@test.com",
        full_name="Test Registrar",
        hashed_password=get_password_hash("registrar123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_doctor_user(db_session, registrar_user):
    """Создает тестового врача"""
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.user import User

    doctor_user = User(
        username="doctor",
        email="doctor@test.com",
        full_name="Test Doctor",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(doctor_user)
    db_session.commit()
    db_session.refresh(doctor_user)

    from datetime import time

    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="Терапия",
        active=True,
        auto_close_time=time(9, 0),  # Преобразуем строку в time объект
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    return doctor_user


def _create_payme_auth_header(secret_key: str) -> str:
    """Создает Authorization header для PayMe webhook"""
    auth_string = f"Paycom:{secret_key}"
    encoded = base64.b64encode(auth_string.encode()).decode()
    return f"Basic {encoded}"


@pytest.fixture
def payme_secret_key(monkeypatch):
    """Возвращает PayMe secret key для тестов из настроек, чтобы совпадал с провайдером"""
    from app.services.payment_provider_manager_factory import (
        reset_payment_manager_for_tests,
    )

    test_secret_key = "test_secret"
    settings = get_settings()
    monkeypatch.setattr(settings, "PAYME_ENABLED", True)
    monkeypatch.setattr(settings, "PAYME_MERCHANT_ID", "test_merchant")
    monkeypatch.setattr(settings, "PAYME_SECRET_KEY", test_secret_key)
    reset_payment_manager_for_tests()
    yield test_secret_key
    reset_payment_manager_for_tests()


@pytest.mark.integration
def test_e2e_clinic_flow(
    client: TestClient,
    db_session: Session,
    registrar_user,
    test_doctor_user,
    test_service,
    payme_secret_key,
    monkeypatch,
):
    """
    Полный E2E тест флоу клиники:
    1. Login
    2. Create Patient
    3. Create Visit
    4. Create Appointment (из Visit)
    5. Create EMR
    6. Create Payment
    7. Simulate PayMe Webhook
    8. Verify Payment Status
    9. Verify Audit Logs
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.payment_webhooks._emit_payment_notification_from_webhook_result",
        AsyncMock(),
    )
    # ========== ШАГ 1: LOGIN ==========
    login_response = client.post(
        "/api/v1/authentication/login",
        json={
            "username": registrar_user.username,
            "password": "registrar123",
        },
    )
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    login_data = login_response.json()
    assert "access_token" in login_data, "Access token not in response"
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ========== ШАГ 2: CREATE PATIENT ==========
    patient_data = {
        "last_name": "CHECKOUT",
        "first_name": "SYNTHETIC",
        "middle_name": "E2E",
        "birth_date": "1990-01-01",
        "sex": "M",
        "phone": "+998900000121",
        # Не добавляем doc_type и doc_number, чтобы избежать валидации
    }
    patient_response = client.post(
        "/api/v1/patients/",
        json=patient_data,
        headers=headers,
    )
    assert patient_response.status_code == 200, f"Create patient failed: {patient_response.text}"
    patient = patient_response.json()
    patient_id = patient["id"]
    assert patient_id is not None, "Patient ID should not be None"

    # Проверяем audit log для создания пациента
    audit_log_patient = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.resource_type == "patients",
            UserAuditLog.resource_id == patient_id,
            UserAuditLog.action == "CREATE",
        )
        .first()
    )
    assert audit_log_patient is not None, "Audit log для создания пациента должен существовать"
    assert audit_log_patient.user_id == registrar_user.id
    assert audit_log_patient.request_id is not None

    # ========== ШАГ 3: CREATE VISIT ==========
    visit_data = {
        "patient_id": patient_id,
        "doctor_id": test_doctor_user.id,  # Используем user_id врача
        "notes": "E2E тестовый визит",
        "planned_date": date.today().isoformat(),
    }
    visit_response = client.post(
        "/api/v1/visits/visits",
        json=visit_data,
        headers=headers,
    )
    assert visit_response.status_code == 201, f"Create visit failed: {visit_response.text}"
    visit = visit_response.json()
    visit_id = visit["id"]
    assert visit_id is not None, "Visit ID should not be None"

    # Проверяем audit log для создания визита
    audit_log_visit = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.resource_type == "visits",
            UserAuditLog.resource_id == visit_id,
            UserAuditLog.action == "CREATE",
        )
        .first()
    )
    assert audit_log_visit is not None, "Audit log для создания визита должен существовать"

    # ========== ШАГ 4: CREATE APPOINTMENT (из Visit) ==========
    # Создаем Appointment из Visit для EMR
    visit_obj = db_session.query(Visit).filter(Visit.id == visit_id).first()
    assert visit_obj is not None, "Visit должен существовать в БД"

    # Создаем Appointment если его нет
    appointment = (
        db_session.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.appointment_date == visit_obj.visit_date,
            Appointment.doctor_id == visit_obj.doctor_id,
        )
        .first()
    )

    if not appointment:
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=visit_obj.doctor_id,
            appointment_date=visit_obj.visit_date or date.today(),
            appointment_time=None,
            status="in_visit",
            department=visit_obj.department,
            notes=visit_obj.notes,
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

    appointment_id = appointment.id

    # ========== ШАГ 5: CREATE EMR ==========
    # Используем doctor token для создания EMR
    doctor_login_response = client.post(
        "/api/v1/authentication/login",
        json={
            "username": test_doctor_user.username,
            "password": "doctor123",
        },
    )
    assert doctor_login_response.status_code == 200
    doctor_token = doctor_login_response.json()["access_token"]
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}

    emr_data = {
        "appointment_id": appointment_id,
        "chief_complaint": "Головная боль",
        "diagnosis": "Мигрень",
        "notes": "E2E тестовая запись EMR",
        "is_draft": False,
    }
    emr_response = client.post(
        f"/api/v1/appointments/{appointment_id}/emr",
        json=emr_data,
        headers=doctor_headers,
    )
    assert emr_response.status_code == 200, f"Create EMR failed: {emr_response.text}"
    emr = emr_response.json()
    emr_id = emr["id"]
    assert emr_id is not None, "EMR ID should not be None"

    # Проверяем audit log для создания EMR
    audit_log_emr = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.resource_type == "emr",
            UserAuditLog.resource_id == emr_id,
            UserAuditLog.action == "CREATE",
        )
        .first()
    )
    assert audit_log_emr is not None, "Audit log для создания EMR должен существовать"
    assert audit_log_emr.user_id == test_doctor_user.id

    # ========== ШАГ 6: CREATE PAYMENT ==========
    amount = Decimal(str(test_service.price))
    # The metadata-only test database omits the confirmation epoch trigger.
    visit_obj.confirmation_context_epoch = 1
    db_session.add(VisitService(
        visit_id=visit_id, service_id=test_service.id, name=test_service.name,
        qty=1, price=amount, currency="UZS",
    ))
    db_session.commit()
    payment_data = {
        "visit_id": visit_id,
        "amount": format(amount, "f"),
        "currency": "UZS",
        "method": "online",
        "provider": "payme",
    }
    payment_response = client.post(
        "/api/v1/payments/init",
        json=payment_data,
        headers=headers,
    )
    assert payment_response.status_code == 200, f"Create payment failed: {payment_response.text}"
    payment_init = payment_response.json()
    assert payment_init["success"] is True, payment_init
    payment_id = payment_init["payment_id"]
    assert payment_id is not None

    # Проверяем audit log для создания платежа
    audit_log_payment = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.resource_type == "payments",
            UserAuditLog.resource_id == payment_id,
            UserAuditLog.action == "CREATE",
        )
        .first()
    )
    assert audit_log_payment is not None, "Audit log для создания платежа должен существовать"

    # ========== ШАГ 7: SIMULATE PAYME WEBHOOK ==========
    payment_obj = db_session.get(Payment, payment_id)
    assert payment_obj.visit_id == visit_id
    assert payment_obj.amount == amount and payment_obj.currency == "UZS"
    assert payment_obj.status == "pending"
    order_id = payment_obj.provider_data["account"]["order_id"]
    assert order_id == payment_init["provider_payment_id"]
    auth_header = _create_payme_auth_header(payme_secret_key)
    provider_transaction_id = f"synthetic-payme-{payment_id}"
    timestamp = int(datetime.now(UTC).timestamp() * 1000)
    order = {"amount": int(amount * 100), "account": {"order_id": order_id}}

    def acknowledge(method: str, params: dict) -> dict:
        response = client.post(
            "/api/v1/payments/webhook/payme",
            json={"method": method, "params": params, "id": f"synthetic-{method}"},
            headers={"Authorization": auth_header},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "result" in body, body
        return body["result"]

    assert acknowledge("CheckPerformTransaction", order)["allow"] is True
    created = acknowledge("CreateTransaction", order | {"id": provider_transaction_id, "time": timestamp})
    assert created["state"] == 1
    performed = acknowledge("PerformTransaction", {"id": provider_transaction_id})
    assert performed["state"] == 2

    # ========== ШАГ 8: VERIFY PAYMENT STATUS ==========
    # Обновляем payment из БД
    db_session.refresh(payment_obj)

    assert payment_obj.status == "paid" and payment_obj.paid_at is not None
    paid_at = payment_obj.paid_at
    assert acknowledge("PerformTransaction", {"id": provider_transaction_id})["state"] == 2
    db_session.refresh(payment_obj)
    assert payment_obj.status == "paid" and payment_obj.paid_at == paid_at
    settlement = db_session.query(PaymentTransaction).filter_by(
        provider="payme", transaction_id=provider_transaction_id,
    ).one()
    assert settlement.payment_id == payment_id

    payment_status_response = client.get(
        f"/api/v1/payments/{payment_id}",
        headers=headers,
    )
    assert payment_status_response.status_code == 200, payment_status_response.text
    assert payment_status_response.json()["status"] == "paid"

    # ========== ШАГ 9: VERIFY AUDIT LOGS ==========
    # Проверяем, что все audit logs созданы
    all_audit_logs = (
        db_session.query(UserAuditLog)
        .filter(
            UserAuditLog.user_id.in_([registrar_user.id, test_doctor_user.id])
        )
        .order_by(UserAuditLog.created_at.desc())
        .all()
    )

    # Должны быть audit logs для: patient, visit, payment, emr
    audit_actions = {log.action for log in all_audit_logs}
    audit_resources = {log.resource_type for log in all_audit_logs}

    assert "CREATE" in audit_actions, "Должен быть хотя бы один CREATE audit log"
    assert "patients" in audit_resources, "Должен быть audit log для patients"
    assert "visits" in audit_resources, "Должен быть audit log для visits"
    assert "payments" in audit_resources, "Должен быть audit log для payments"
    assert "emr" in audit_resources, "Должен быть audit log для emr"

    # Проверяем, что все audit logs имеют request_id
    for log in all_audit_logs:
        assert log.request_id is not None, f"Audit log {log.id} должен иметь request_id"
        assert log.ip_address is not None, f"Audit log {log.id} должен иметь ip_address"

    print("✅ E2E тест успешно завершен!")
    print(f"   - Patient ID: {patient_id}")
    print(f"   - Visit ID: {visit_id}")
    print(f"   - Appointment ID: {appointment_id}")
    print(f"   - EMR ID: {emr_id}")
    print(f"   - Payment ID: {payment_id}")
    print(f"   - Audit logs: {len(all_audit_logs)}")

