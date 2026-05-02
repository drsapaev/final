"""
Полные тесты для админ панели - все модули и функции
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.clinic import ClinicSettings, Doctor, Schedule, ServiceCategory
from app.models.ai_config import AIProvider
from app.core.auth import create_access_token

client = TestClient(app)


@pytest.fixture
def db_session():
    """Тестовая сессия БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_token(db_session):
    """Токен администратора для тестов"""
    # Создаем тестового админа
    admin_user = User(
        username="test_admin",
        email="admin@test.com",
        full_name="Test Admin",
        role="Admin",
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()
    
    # Создаем токен
    token = create_access_token(subject=admin_user.username)
    return token


def test_clinic_settings_crud(admin_token):
    """Тест CRUD операций настроек клиники"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Получение настроек
    response = client.get("/api/v1/admin/clinic/settings?category=clinic", headers=headers)
    assert response.status_code == 200
    
    # Обновление настроек
    settings_data = {
        "settings": {
            "clinic_name": "Test Clinic",
            "address": "Test Address",
            "timezone": "Asia/Tashkent"
        }
    }
    response = client.put("/api/v1/admin/clinic/settings", json=settings_data, headers=headers)
    assert response.status_code == 200


def test_queue_settings_crud(admin_token):
    """Тест настроек очередей"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Получение настроек очередей
    response = client.get("/api/v1/admin/queue/settings", headers=headers)
    assert response.status_code == 200
    
    # Обновление настроек очередей
    queue_settings = {
        "timezone": "Asia/Tashkent",
        "queue_start_hour": 7,
        "auto_close_time": "09:00",
        "start_numbers": {
            "cardiology": 1,
            "dermatology": 15,
            "stomatology": 3
        },
        "max_per_day": {
            "cardiology": 15,
            "dermatology": 20,
            "stomatology": 12
        }
    }
    response = client.put("/api/v1/admin/queue/settings", json=queue_settings, headers=headers)
    assert response.status_code == 200


def test_doctors_crud(admin_token):
    """Тест CRUD операций врачей"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Создание врача
    doctor_data = {
        "specialty": "cardiology",
        "cabinet": "101",
        "price_default": 100000,
        "start_number_online": 1,
        "max_online_per_day": 15,
        "active": True
    }
    response = client.post("/api/v1/admin/doctors", json=doctor_data, headers=headers)
    assert response.status_code == 200
    doctor_id = response.json()["id"]
    
    # Получение врача
    response = client.get(f"/api/v1/admin/doctors/{doctor_id}", headers=headers)
    assert response.status_code == 200
    
    # Обновление врача
    update_data = {"cabinet": "102"}
    response = client.put(f"/api/v1/admin/doctors/{doctor_id}", json=update_data, headers=headers)
    assert response.status_code == 200
    
    # Получение списка врачей
    response = client.get("/api/v1/admin/doctors", headers=headers)
    assert response.status_code == 200


def test_service_categories_crud(admin_token):
    """Тест CRUD операций категорий услуг"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Получение категорий
    response = client.get("/api/v1/admin/service-categories", headers=headers)
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) > 0
    
    # Проверяем базовые категории из документации
    category_codes = [cat["code"] for cat in categories]
    expected_codes = [
        "consultation.cardiology",
        "consultation.dermatology", 
        "consultation.stomatology",
        "procedure.cosmetology",
        "diagnostics.ecg",
        "diagnostics.echo"
    ]
    
    for code in expected_codes:
        assert code in category_codes, f"Категория {code} не найдена"


def test_ai_providers_crud(admin_token):
    """Тест CRUD операций AI провайдеров"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Получение провайдеров
    response = client.get("/api/v1/admin/ai/providers", headers=headers)
    assert response.status_code == 200
    providers = response.json()
    
    # Проверяем базовых провайдеров
    provider_names = [p["name"] for p in providers]
    expected_providers = ["openai", "gemini", "deepseek"]
    
    for provider in expected_providers:
        assert provider in provider_names, f"AI провайдер {provider} не найден"


def test_telegram_settings(admin_token):
    """Тест настроек Telegram"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Получение настроек Telegram
    response = client.get("/api/v1/admin/telegram/settings", headers=headers)
    assert response.status_code == 200
    
    # Обновление настроек
    telegram_settings = {
        "notifications_enabled": True,
        "appointment_reminders": True,
        "lab_results_notifications": True,
        "default_language": "ru"
    }
    response = client.put("/api/v1/admin/telegram/settings", json=telegram_settings, headers=headers)
    assert response.status_code == 200


def test_display_board_settings(admin_token):
    """Тест настроек табло"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Получение табло
    response = client.get("/api/v1/admin/display/boards", headers=headers)
    assert response.status_code == 200
    
    # Получение тем
    response = client.get("/api/v1/admin/display/themes", headers=headers)
    assert response.status_code == 200
    themes = response.json()
    assert len(themes) >= 3  # light, dark, medical


def test_system_info(admin_token):
    """Тест получения информации о системе"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    response = client.get("/api/v1/admin/system/info", headers=headers)
    assert response.status_code == 200
    
    system_info = response.json()
    assert "system" in system_info
    assert "application" in system_info


def test_admin_stats(admin_token):
    """Тест статистики админ панели"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Общая статистика
    response = client.get("/api/v1/admin/stats", headers=headers)
    assert response.status_code == 200
    
    stats = response.json()
    required_fields = [
        "totalUsers", "totalDoctors", "totalPatients", 
        "totalRevenue", "appointmentsToday", "roleStats"
    ]
    
    for field in required_fields:
        assert field in stats, f"Поле {field} отсутствует в статистике"
    
    # Быстрая статистика
    response = client.get("/api/v1/admin/quick-stats", headers=headers)
    assert response.status_code == 200


def test_queue_generation(admin_token, db_session):
    """Тест генерации QR токенов очереди"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Создаем тестового врача
    doctor = Doctor(
        specialty="cardiology",
        cabinet="101",
        start_number_online=1,
        max_online_per_day=15,
        active=True
    )
    db_session.add(doctor)
    db_session.commit()
    
    # Тестируем генерацию QR
    test_data = {
        "doctor_id": doctor.id,
        "date": "2025-01-27"
    }
    response = client.post("/api/v1/admin/queue/test", json=test_data, headers=headers)
    assert response.status_code == 200
    
    result = response.json()
    assert result["success"] == True
    assert "test_data" in result
    assert "token" in result["test_data"]


def test_unauthorized_access():
    """Тест защиты от неавторизованного доступа"""
    
    # Попытка доступа без токена
    response = client.get("/api/v1/admin/clinic/settings")
    assert response.status_code == 401
    
    # Попытка доступа с неверным токеном
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/api/v1/admin/clinic/settings", headers=headers)
    assert response.status_code == 401


def test_role_based_access(db_session):
    """Тест ролевого доступа"""
    
    # Создаем пользователя с ролью "Doctor"
    doctor_user = User(
        username="test_doctor",
        email="doctor@test.com", 
        full_name="Test Doctor",
        role="Doctor",
        is_active=True
    )
    db_session.add(doctor_user)
    db_session.commit()
    
    # Создаем токен врача
    doctor_token = create_access_token(subject=doctor_user.username)
    headers = {"Authorization": f"Bearer {doctor_token}"}
    
    # Врач не должен иметь доступ к админ функциям
    response = client.get("/api/v1/admin/clinic/settings", headers=headers)
    assert response.status_code == 403


def test_data_validation():
    """Тест валидации данных"""
    # Тесты будут добавлены по мере необходимости
    pass


def test_performance_endpoints(admin_token):
    """Тест производительности критических endpoints"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    import time
    
    # Тестируем время ответа критических endpoints
    endpoints = [
        "/api/v1/admin/stats",
        "/api/v1/admin/quick-stats",
        "/api/v1/admin/doctors",
        "/api/v1/admin/service-categories"
    ]
    
    for endpoint in endpoints:
        start_time = time.time()
        response = client.get(endpoint, headers=headers)
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 2.0, f"Endpoint {endpoint} слишком медленный"


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
