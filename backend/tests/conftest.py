"""
Конфигурация pytest для тестов системы клиники
"""

# ============================================================
# CRITICAL: Set env flags BEFORE any app imports.
# rate_limiter.py, config.py, and other modules read these
# at import-time. If they are set after import, the values
# are stale and rate limiting stays enabled → 429 failures.
# ============================================================
import os

os.environ["TESTING"] = "1"  # must override, not just setdefault
os.environ.setdefault("ENV", "dev")  # required by SEC-005 model_validator

import asyncio
import inspect
import secrets
import tempfile
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.core.security import get_password_hash

# ✅ КРИТИЧЕСКИ ВАЖНО: Импортируем app.db.base, который загружает ВСЕ модели
# Это гарантирует, что Base.metadata содержит все таблицы
from app.db import base  # noqa: F401 - импорт для регистрации моделей
from app.db.base_class import Base

TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD") or secrets.token_urlsafe(24)

from app.main import app
from app.models import (  # noqa: F401
    appointment,
    authentication,
    billing,  # ✅ FIX: Import billing models for tests
    clinic,
    department,
    emr,
    file_system,
    lab,
    online_queue,
    payment,
    payment_webhook,
    role_permission,
    schedule,
    user_profile,
)
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit


@pytest.fixture(scope="session")
def test_db():
    """Создает тестовую базу данных"""
    # Используем временную файловую БД вместо in-memory
    # In-memory SQLite не работает в разных потоках даже с check_same_thread=False
    import os

    # Создаем временный файл БД
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)  # Закрываем файловый дескриптор, SQLAlchemy откроет сам

    # check_same_thread=False позволяет использовать БД в разных потоках (для TestClient)
    engine = create_engine(f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False})

    # ✅ КРИТИЧЕСКИ ВАЖНО: Импортируем все модели перед созданием таблиц
    # app.db.base уже импортирует все модели через app.models.__init__
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)

    # Проверяем, что таблицы созданы (для отладки)
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "users" not in tables:
        raise RuntimeError(f"CRITICAL: Table 'users' not created! Available tables: {tables}")

    yield engine

    # Удаляем временный файл БД после тестов
    try:
        os.unlink(db_path)
    except Exception:
        pass  # Игнорируем ошибки удаления


@pytest.fixture(scope="function")
def db_session(test_db):
    """Создает сессию БД для каждого теста"""
    connection = test_db.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    session = TestingSessionLocal()
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):  # type: ignore[no-untyped-def]
        nonlocal nested
        if trans.nested and not getattr(trans._parent, "nested", False):
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", restart_savepoint)
        session.close()
        if nested.is_active:
            nested.rollback()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def db(db_session):
    """Алиас для db_session для совместимости старых тестов."""
    return db_session

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
def admin_user(db_session, admin_password):
    """Создает тестового администратора"""
    # Переиспользуем пользователя, если он уже создан (из-за уникального username)
    user = db_session.query(User).filter(User.username == "test_admin").first()
    if user:
        return user

    user = User(
        username="test_admin",
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password=get_password_hash(admin_password),
        role="Admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="session")
def admin_password():
    return TEST_ADMIN_PASSWORD


@pytest.fixture(scope="function")
def cardio_user(db_session):
    """Создает тестового кардиолога"""
    # Проверяем, не существует ли уже пользователь с таким username
    existing = db_session.query(User).filter(User.username == "test_cardio").first()
    if existing:
        return existing

    user = User(
        username="test_cardio",
        email="cardio@test.com",
        full_name="Test Cardiologist",
        hashed_password=get_password_hash("cardio123"),
        role="cardio",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_doctor_user(db_session):
    """Создает тестового врача (User с ролью Doctor)"""
    # Проверяем, не существует ли уже пользователь с таким username
    existing = db_session.query(User).filter(User.username == "test_doctor").first()
    if existing:
        return existing

    user = User(
        username="test_doctor",
        email="doctor@test.com",
        full_name="Test Doctor",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def registrar_user(db_session):
    """Создает тестового регистратора"""
    # Проверяем, не существует ли уже пользователь с таким username
    existing = db_session.query(User).filter(User.username == "test_registrar").first()
    if existing:
        return existing

    user = User(
        username="test_registrar",
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


@pytest.fixture(scope="function")
def test_patient(db_session):
    """Создает тестового пациента"""
    patient = Patient(
        first_name="Иван",
        last_name="Иванов",
        middle_name="Иванович",
        phone="+998901234567",
        birth_date=date(1990, 1, 1),
        address="Тестовый адрес",
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
        active=True,
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
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=True,
        allow_doctor_price_override=False,
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
        confirmation_expires_at=datetime.utcnow().replace(hour=23, minute=59),
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
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


@pytest.fixture
def registrar_token(client: TestClient, registrar_user: User) -> str:
    """Токен регистратора"""
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": registrar_user.username, "password": "registrar123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def patient_token(client: TestClient, db_session: Session) -> str:
    """Токен пациента"""
    # Создаём пациента если нет
    patient_user = db_session.query(User).filter(User.username == "patient_test").first()
    if not patient_user:
        patient_user = User(
            username="patient_test",
            email="patient@test.com",
            hashed_password=get_password_hash("patient123"),
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(patient_user)
        db_session.commit()
        db_session.refresh(patient_user)

    response = client.post(
        "/api/v1/authentication/login",
        json={"username": patient_user.username, "password": "patient123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


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
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture(scope="function")
def auth_headers(client, admin_user, admin_password):
    """Создает заголовки авторизации для администратора"""
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": admin_password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def cardio_auth_headers(client, cardio_user):
    """Создает заголовки авторизации для кардиолога"""
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": cardio_user.username, "password": "cardio123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def registrar_auth_headers(client, registrar_user):
    """Создает заголовки авторизации для регистратора"""
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": registrar_user.username, "password": "registrar123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# Маркеры для pytest
def pytest_pyfunc_call(pyfuncitem):
    if "asyncio" not in pyfuncitem.keywords:
        return None
    test_function = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_function):
        return None
    fixture_args = {
        arg: pyfuncitem.funcargs[arg]
        for arg in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(test_function(**fixture_args))
    return True


def pytest_configure(config):
    """Конфигурация pytest"""
    os.environ.setdefault("DISABLE_2FA_REQUIREMENT", "true")  # Disable 2FA for most tests
    config.addinivalue_line("markers", "asyncio: asynchronous tests")
    config.addinivalue_line("markers", "unit: Юнит тесты")
    config.addinivalue_line("markers", "integration: Интеграционные тесты")
    config.addinivalue_line("markers", "e2e: Сквозные E2E тесты")
    config.addinivalue_line("markers", "slow: Медленные тесты")
    config.addinivalue_line("markers", "security: Тесты безопасности")
    config.addinivalue_line("markers", "migration: Тесты миграций")
    config.addinivalue_line("markers", "confirmation: Тесты подтверждения визитов")
    config.addinivalue_line("markers", "queue: Тесты очередей")


@pytest.fixture(scope="function")
def admin_auth_headers(client, admin_user, admin_password):
    """Alias for auth_headers — some tests use admin_auth_headers."""
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": admin_password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def prod_env(monkeypatch: pytest.MonkeyPatch):
    """Valid production environment baseline for prod-path tests.

    Provides all env vars required by ``get_settings()`` prod validators.
    Tests using this fixture should still ``delenv("TESTING")`` to exercise
    the real prod path, but every *other* fail-closed check is satisfied here.

    When a new prod validator is added to ``get_settings()``, update THIS
    fixture — not every individual test.
    """
    # ── Core identity ──────────────────────────────────────────
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "test-only-prod-secret-key-32chars!!")
    monkeypatch.delenv("TESTING", raising=False)               # SEC-005
    monkeypatch.delenv("DISABLE_2FA_REQUIREMENT", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ALL", raising=False)

    # ── DB ───────────────────────────────────────────────────
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://clinic:clinic@localhost:5432/clinicdb",
    )

    # ── SMS provider (at least one) ────────────────────────────
    monkeypatch.setenv("ESKIZ_EMAIL", "test@example.invalid")
    monkeypatch.setenv("ESKIZ_PASSWORD", "test-invalid-secret")

    # ── AI encryption key ──────────────────────────────────────
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdC1vbmx5LWZlcm5ldC1rZXktMzJjaGFycyEh")

    # ── AUTH_SECRET removed so tests can verify fallback ───────
    monkeypatch.delenv("AUTH_SECRET", raising=False)

    # ── ENABLE_FALLBACK_AUTH / ENABLE_TEST_PAYMENT_INIT ───────
    # Both default False, but be explicit
    monkeypatch.delenv("ENABLE_FALLBACK_AUTH", raising=False)
    monkeypatch.delenv("ENABLE_TEST_PAYMENT_INIT", raising=False)

    return monkeypatch


# M4-P0-2: Clear replay-protection cache before each test to prevent
# cross-test contamination from init_data replay protection.
@pytest.fixture(autouse=True)
def _clear_replay_cache():
    """Auto-fixture: clear cache_manager before each test."""
    try:
        from app.core.cache import cache_manager
        cache_manager.clear()
    except Exception:
        pass
    yield
    try:
        from app.core.cache import cache_manager
        cache_manager.clear()
    except Exception:
        pass
