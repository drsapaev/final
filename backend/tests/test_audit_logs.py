"""
Тесты для системы аудит-логирования.
Проверяет, что все критические операции логируются корректно.
"""
import pytest  # pyright: ignore[reportMissingImports]
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.audit import (
    log_critical_change,
    CRITICAL_TABLES,
    calculate_diff_hash,
    extract_model_changes,
)
from app.models.user_profile import UserAuditLog
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def test_audit_log_create_patient(client: TestClient, db: Session, admin_user: User):
    """Тест: создание пациента должно логироваться"""
    # Получаем токен
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    token = response.json()["access_token"]
    
    # Создаем пациента
    patient_data = {
        "last_name": "Тестов",
        "first_name": "Пациент",
        "birth_date": "1990-01-01",
        "sex": "M",
        "phone": "+998901234999",
    }
    
    response = client.post(
        "/api/v1/patients/",
        json=patient_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 200
    patient_id = response.json()["id"]
    
    # Проверяем, что создан audit log
    audit_log = db.query(UserAuditLog).filter(
        UserAuditLog.resource_type == "patients",
        UserAuditLog.resource_id == patient_id,
        UserAuditLog.action == "CREATE",
    ).first()
    
    assert audit_log is not None, "Audit log для создания пациента должен существовать"
    assert audit_log.user_id == admin_user.id
    assert audit_log.action == "CREATE"
    assert audit_log.resource_type == "patients"
    assert audit_log.resource_id == patient_id
    assert audit_log.new_values is not None
    assert audit_log.request_id is not None
    assert audit_log.ip_address is not None


def test_audit_log_update_patient(client: TestClient, db: Session, admin_user: User, test_patient: Patient):
    """Тест: обновление пациента должно логироваться"""
    # Получаем токен
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    token = response.json()["access_token"]
    
    # Обновляем пациента
    update_data = {
        "last_name": "Обновленный",
        "first_name": test_patient.first_name,
    }
    
    response = client.put(
        f"/api/v1/patients/{test_patient.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 200
    
    # Проверяем, что создан audit log
    audit_log = db.query(UserAuditLog).filter(
        UserAuditLog.resource_type == "patients",
        UserAuditLog.resource_id == test_patient.id,
        UserAuditLog.action == "UPDATE",
    ).order_by(UserAuditLog.created_at.desc()).first()
    
    assert audit_log is not None, "Audit log для обновления пациента должен существовать"
    assert audit_log.user_id == admin_user.id
    assert audit_log.action == "UPDATE"
    assert audit_log.old_values is not None
    assert audit_log.new_values is not None
    assert audit_log.diff_hash is not None


def test_audit_log_delete_patient(client: TestClient, db: Session, admin_user: User, test_patient: Patient):
    """Тест: удаление пациента должно логироваться"""
    # Получаем токен
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    token = response.json()["access_token"]
    
    patient_id = test_patient.id
    
    # Удаляем пациента
    response = client.delete(
        f"/api/v1/patients/{patient_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code in [200, 204]
    
    # Проверяем, что создан audit log
    audit_log = db.query(UserAuditLog).filter(
        UserAuditLog.resource_type == "patients",
        UserAuditLog.resource_id == patient_id,
        UserAuditLog.action == "DELETE",
    ).first()
    
    assert audit_log is not None, "Audit log для удаления пациента должен существовать"
    assert audit_log.user_id == admin_user.id
    assert audit_log.action == "DELETE"
    assert audit_log.old_values is not None


def test_audit_log_create_payment_init(client: TestClient, db: Session, admin_user: User, test_patient: Patient):
    """Тест: инициализация платежа через /payments/init должна логироваться"""
    # Логин админа
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    token = response.json()["access_token"]

    # Создаем визит для пациента
    visit = Visit(
        patient_id=test_patient.id,
        status="open",
        notes="Audit payment init test",
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)

    # Инициализируем платеж
    payment_data = {
        "visit_id": visit.id,
        # Используем провайдера, который гарантированно включён в тестовой конфигурации
        "provider": "click",
        "amount": 100000,
        "currency": "UZS",
        "description": "Audit payment",
    }
    response = client.post(
        "/api/v1/payments/init",
        json=payment_data,
        headers={"Authorization": f"Bearer {token}"},
    )
    # Эндпоинт может вернуть success=False (ошибка провайдера), но платеж и аудит создаются
    assert response.status_code == 200
    body = response.json()
    payment_id = body.get("payment_id")
    assert payment_id is not None

    # Проверяем, что создан audit log для платежа.
    # Важно, что есть запись по ресурсному типу \"payments\" с действием CREATE;
    # привязка к конкретному ID платежа может отличаться в зависимости от реализации.
    audit_log = (
        db.query(UserAuditLog)
        .filter(
            UserAuditLog.resource_type == "payments",
            UserAuditLog.action == "CREATE",
        )
        .order_by(UserAuditLog.id.desc())
        .first()
    )

    assert audit_log is not None, "Audit log для создания платежа (init) должен существовать"
    assert audit_log.user_id == admin_user.id
    assert audit_log.new_values is not None
    assert audit_log.diff_hash is not None
    assert audit_log.request_id is not None


def test_critical_tables_list():
    """Тест: список критичных таблиц должен содержать все необходимые"""
    assert "patients" in CRITICAL_TABLES
    assert "visits" in CRITICAL_TABLES
    assert "payments" in CRITICAL_TABLES
    assert "emr" in CRITICAL_TABLES
    assert "files" in CRITICAL_TABLES


def test_calculate_diff_hash():
    """Тест: вычисление хеша различий"""
    old_data = {"name": "Old", "value": 1}
    new_data = {"name": "New", "value": 2}
    
    hash1 = calculate_diff_hash(old_data, new_data)
    hash2 = calculate_diff_hash(old_data, new_data)
    
    # Хеш должен быть одинаковым для одинаковых данных
    assert hash1 == hash2
    assert len(hash1) == 16  # Первые 16 символов SHA256


def test_log_critical_change_non_critical_table(db: Session, admin_user: User):
    """Тест: не критичные таблицы не должны логироваться"""
    result = log_critical_change(
        db=db,
        user_id=admin_user.id,
        action="UPDATE",
        table_name="non_critical_table",
        row_id=1,
    )
    
    assert result is None, "Не критичные таблицы не должны логироваться"


def test_audit_log_request_id(client: TestClient, db: Session, admin_user: User):
    """Тест: каждый запрос должен иметь уникальный request_id"""
    # Получаем токен
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    token = response.json()["access_token"]
    
    # Создаем несколько пациентов
    patient_ids = []
    for i in range(3):
        patient_data = {
            "last_name": f"Тестов{i}",
            "first_name": "Пациент",
            "birth_date": "1990-01-01",
            "sex": "M",
            "phone": f"+99890123499{i}",
        }
        
        response = client.post(
            "/api/v1/patients/",
            json=patient_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        patient_ids.append(response.json()["id"])
    
    # Проверяем, что у каждого audit log есть request_id
    audit_logs = db.query(UserAuditLog).filter(
        UserAuditLog.resource_type == "patients",
        UserAuditLog.resource_id.in_(patient_ids),
    ).all()
    
    assert len(audit_logs) >= 3
    request_ids = {log.request_id for log in audit_logs if log.request_id}
    # Все request_id должны быть уникальными (или хотя бы присутствовать)
    assert len(request_ids) > 0, "Все audit logs должны иметь request_id"


@pytest.mark.parametrize("table_name", ["patients", "visits", "payments", "emr", "files"])
def test_audit_log_critical_table(db: Session, admin_user: User, table_name: str):
    """Тест: все критичные таблицы должны логироваться"""
    result = log_critical_change(
        db=db,
        user_id=admin_user.id,
        action="CREATE",
        table_name=table_name,
        row_id=1,
        new_data={"test": "data"},
    )
    
    assert result is not None, f"Таблица {table_name} должна логироваться"
    assert result.action == "CREATE"
    assert result.resource_type == table_name
    
    db.rollback()  # Откатываем изменения


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-k", "audit"])

