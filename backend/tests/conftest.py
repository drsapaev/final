"""
Конфигурация pytest для тестов системы клиники
"""
import pytest
import tempfile
import os
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db.base_class import Base
from app.api.deps import get_db
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.clinic import Doctor
from app.core.security import get_password_hash


@pytest.fixture(scope="session")
def test_db():
    """Создает тестовую базу данных"""
    # Используем in-memory БД для тестов
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Для in-memory БД очистка не нужна


@pytest.fixture(scope="function")
def db_session(test_db):
    """Создает сессию БД для каждого теста"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Создает тестовый клиент FastAPI"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_user(db_session):
    """Создает тестового администратора"""
    user = User(
        username="test_admin",
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password=get_password_hash("admin123"),
        role="Admin",
        is_active=True,
        is_superuser=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def cardio_user(db_session):
    """Создает тестового кардиолога"""
    user = User(
        username="test_cardio",
        email="cardio@test.com",
        full_name="Test Cardiologist",
        hashed_password=get_password_hash("cardio123"),
        role="cardio",
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def registrar_user(db_session):
    """Создает тестового регистратора"""
    user = User(
        username="test_registrar",
        email="registrar@test.com",
        full_name="Test Registrar",
        hashed_password=get_password_hash("registrar123"),
        role="Registrar",
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_patient(db_session):
    """Создает тестового пациента"""
    patient = Patient(
        first_name="Иван",
        last_name="Иванов",
        middle_name="Иванович",
        phone="+998901234567",
        birth_date=date(1990, 1, 1),
        address="Тестовый адрес"
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture(scope="function")
def test_doctor(db_session, cardio_user):
    """Создает тестового врача"""
    doctor = Doctor(
        user_id=cardio_user.id,
        specialty="Кардиология",
        license_number="TEST123",
        experience_years=10,
        bio="Тестовый кардиолог",
        is_active=True
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture(scope="function")
def test_service(db_session):
    """Создает тестовую услугу"""
    service = Service(
        code="TEST_CONS",
        name="Тестовая консультация",
        description="Тестовая консультация кардиолога",
        price=100000.00,
        duration_minutes=30,
        is_active=True,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=True,
        allow_doctor_price_override=False
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


@pytest.fixture(scope="function")
def test_visit(db_session, test_patient, test_doctor):
    """Создает тестовый визит"""
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="10:00",
        status="pending_confirmation",
        discount_mode="none",
        department="cardiology",
        confirmation_token="test-token-123",
        confirmation_channel="telegram",
        confirmation_expires_at=datetime.utcnow().replace(hour=23, minute=59)
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


@pytest.fixture(scope="function")
def test_daily_queue(db_session, cardio_user):
    """Создает тестовую дневную очередь"""
    queue = DailyQueue(
        day=date.today(),
        specialist_id=cardio_user.id,
        queue_tag="cardiology_common",
        active=True
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


@pytest.fixture(scope="function")
def test_queue_entry(db_session, test_daily_queue, test_patient, test_visit):
    """Создает тестовую запись в очереди"""
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        telegram_id=123456789,  # Фиксированное значение для тестов
        visit_id=test_visit.id,
        source="confirmation",
        status="waiting"
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture(scope="function")
def auth_headers(client, admin_user):
    """Создает заголовки авторизации для администратора"""
    response = client.post("/api/v1/authentication/login", json={
        "username": admin_user.username,
        "password": "admin123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def cardio_auth_headers(client, cardio_user):
    """Создает заголовки авторизации для кардиолога"""
    response = client.post("/api/v1/authentication/login", json={
        "username": cardio_user.username,
        "password": "cardio123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def registrar_auth_headers(client, registrar_user):
    """Создает заголовки авторизации для регистратора"""
    response = client.post("/api/v1/authentication/login", json={
        "username": registrar_user.username,
        "password": "registrar123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# Маркеры для pytest
def pytest_configure(config):
    """Конфигурация pytest"""
    config.addinivalue_line("markers", "unit: Юнит тесты")
    config.addinivalue_line("markers", "integration: Интеграционные тесты")
    config.addinivalue_line("markers", "slow: Медленные тесты")
    config.addinivalue_line("markers", "security: Тесты безопасности")
    config.addinivalue_line("markers", "migration: Тесты миграций")
    config.addinivalue_line("markers", "confirmation: Тесты подтверждения визитов")
    config.addinivalue_line("markers", "queue: Тесты очередей")
