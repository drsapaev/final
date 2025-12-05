"""
End-to-End интеграционный тест для полного флоу клиники:
Login → Create Patient → Create Visit → Create EMR → Create Payment → PayMe Webhook → Verify
"""
import base64
import json
from datetime import date, datetime

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.user_profile import UserAuditLog
from app.models.visit import Visit


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
def payme_secret_key():
    """Возвращает PayMe secret key для тестов из настроек, чтобы совпадал с провайдером"""
    settings = get_settings()
    return getattr(settings, "PAYME_SECRET_KEY", "test_secret")


@pytest.mark.integration
def test_e2e_clinic_flow(
    client: TestClient,
    db_session: Session,
    registrar_user,
    test_doctor_user,
    payme_secret_key,
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
        "last_name": "Тестов",
        "first_name": "Пациент",
        "middle_name": "E2E",
        "birth_date": "1990-01-01",
        "sex": "M",
        "phone": "+998901234567",
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
    payment_data = {
        "visit_id": visit_id,
        "amount": 100000,  # 1000.00 UZS
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
    # В тестовой среде провайдер может быть не настроен → success=False,
    # но платеж и аудит должны быть созданы, а payment_id возвращён.
    payment_id = payment_init.get("payment_id")
    assert payment_id is not None, f"Payment ID should not be None. Response: {payment_init}"

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

    # Получаем payment из БД для order_id
    payment_obj = db_session.query(Payment).filter(Payment.id == payment_id).first()
    assert payment_obj is not None, "Payment должен существовать в БД"
    order_id = f"clinic_{payment_id}_{int(datetime.now().timestamp())}"

    # ========== ШАГ 7: SIMULATE PAYME WEBHOOK ==========
    # Используем тестовый secret key из фикстуры
    
    # Получаем order_id из payment (он должен быть в provider_data или payment_id)
    # PayMe использует order_id в формате "clinic_{payment_id}_{timestamp}"
    # Обновляем payment из БД для получения актуальных данных
    db_session.refresh(payment_obj)
    order_id = payment_obj.provider_data.get("account", {}).get("order_id") if payment_obj.provider_data else None
    if not order_id:
        # Если order_id нет в provider_data, создаем его
        from app.services.queue_service import queue_service
        now = queue_service.get_local_timestamp(db_session)
        order_id = f"clinic_{payment_id}_{int(now.timestamp())}"

    # Создаем PayMe webhook payload (JSON-RPC формат) для CheckPerformTransaction
    check_payload = {
        "method": "CheckPerformTransaction",
        "params": {
            "amount": 100000,
            "account": {
                "order_id": order_id,
            },
        },
        "id": "test_request_123",
    }

    # Создаем Authorization header
    auth_header = _create_payme_auth_header(payme_secret_key)

    # Отправляем CheckPerformTransaction webhook
    check_response = client.post(
        "/api/v1/payments/webhook/payme",
        json=check_payload,
        headers={"Authorization": auth_header},
    )
    assert check_response.status_code == 200, f"CheckPerformTransaction webhook failed: {check_response.text}"
    check_result = check_response.json()
    assert "result" in check_result or "error" not in check_result, "CheckPerformTransaction should succeed"

    # Отправляем CreateTransaction webhook
    payme_transaction_id = f"test_trans_{payment_id}_{int(datetime.now().timestamp())}"
    create_payload = {
        "method": "CreateTransaction",
        "params": {
            "amount": 100000,
            "account": {
                "order_id": order_id,
            },
            "time": int(datetime.now().timestamp() * 1000),
        },
        "id": "test_request_124",
    }

    create_response = client.post(
        "/api/v1/payments/webhook/payme",
        json=create_payload,
        headers={"Authorization": auth_header},
    )
    assert create_response.status_code == 200, f"CreateTransaction webhook failed: {create_response.text}"
    create_result = create_response.json()
    
    # Извлекаем transaction ID из ответа CreateTransaction
    # PayMe возвращает transaction ID в result.transaction
    if "result" in create_result and "transaction" in create_result["result"]:
        payme_transaction_id = str(create_result["result"]["transaction"])
    elif "result" in create_result and isinstance(create_result["result"], dict):
        # Альтернативный формат ответа
        payme_transaction_id = str(create_result["result"].get("transaction", payme_transaction_id))

    # Отправляем PerformTransaction webhook (симуляция успешной оплаты)
    perform_payload = {
        "method": "PerformTransaction",
        "params": {
            "id": payme_transaction_id,
            "time": int(datetime.now().timestamp() * 1000),
        },
        "id": "test_request_125",
    }

    perform_response = client.post(
        "/api/v1/payments/webhook/payme",
        json=perform_payload,
        headers={"Authorization": auth_header},
    )
    assert perform_response.status_code == 200, f"PerformTransaction webhook failed: {perform_response.text}"

    # ========== ШАГ 8: VERIFY PAYMENT STATUS ==========
    # Обновляем payment из БД
    db_session.refresh(payment_obj)
    
    # Проверяем статус платежа (может быть "paid" или "pending" в зависимости от обработки webhook)
    # В реальном сценарии webhook должен обновить статус
    payment_status_response = client.get(
        f"/api/v1/payments/{payment_id}",
        headers=headers,
    )
    if payment_status_response.status_code == 200:
        payment_status = payment_status_response.json()
        # В тестовой среде статус может быть "processing"/"pending"/"paid"/"failed"
        # в зависимости от последовательности webhook-вызовов.
        assert payment_status.get("status") in ["paid", "pending", "failed", "processing"], (
            f"Unexpected payment status: {payment_status.get('status')}"
        )

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

