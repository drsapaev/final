"""
Тест полного цикла интеграции: запись → очередь → прием → завершение
Основа: detail.md стр. 444 (тест-чеклист для регистратуры)
"""
import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.patient import Patient
from app.models.clinic import Doctor, ServiceCategory, ClinicSettings
from app.models.service import Service
from app.models.online_queue import DailyQueue, OnlineOnlineQueueEntry, QueueToken
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
def setup_test_data(db_session):
    """Создание тестовых данных для полного цикла"""
    
    # 1. Создаем администратора
    admin_user = User(
        username="test_admin",
        email="admin@test.com",
        full_name="Test Admin",
        role="Admin",
        is_active=True
    )
    db_session.add(admin_user)
    
    # 2. Создаем регистратора
    registrar_user = User(
        username="test_registrar",
        email="registrar@test.com", 
        full_name="Test Registrar",
        role="Registrar",
        is_active=True
    )
    db_session.add(registrar_user)
    
    # 3. Создаем врача-кардиолога
    doctor_user = User(
        username="test_cardiologist",
        email="cardio@test.com",
        full_name="Dr. Кардиолог",
        role="Doctor",
        is_active=True
    )
    db_session.add(doctor_user)
    db_session.commit()
    
    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        cabinet="101",
        start_number_online=1,
        max_online_per_day=15,
        active=True
    )
    db_session.add(doctor)
    
    # 4. Создаем пациента
    patient = Patient(
        first_name="Тестовый",
        last_name="Пациент", 
        phone="+998901234567",
        birth_date=date(1985, 5, 15)
    )
    db_session.add(patient)
    
    # 5. Создаем категорию услуг
    category = ServiceCategory(
        code="consultation.cardiology",
        name_ru="Консультация кардиолога",
        specialty="cardiology",
        active=True
    )
    db_session.add(category)
    db_session.commit()
    
    # 6. Создаем услугу
    service = Service(
        name="Консультация кардиолога",
        code="CARDIO_CONS",
        price=100000,
        currency="UZS",
        duration_minutes=30,
        category_id=category.id,
        doctor_id=doctor.id,
        active=True
    )
    db_session.add(service)
    
    # 7. Создаем настройки очереди
    settings = [
        ClinicSettings(key="timezone", value="Asia/Tashkent", category="clinic"),
        ClinicSettings(key="queue_start_hour", value=7, category="queue"),
        ClinicSettings(key="start_number_cardiology", value=1, category="queue"),
        ClinicSettings(key="max_per_day_cardiology", value=15, category="queue")
    ]
    
    for setting in settings:
        db_session.add(setting)
    
    db_session.commit()
    
    return {
        "admin_user": admin_user,
        "registrar_user": registrar_user,
        "doctor_user": doctor_user,
        "doctor": doctor,
        "patient": patient,
        "service": service,
        "category": category
    }


def test_full_integration_cycle(setup_test_data):
    """
    Тест полного цикла интеграции
    Из detail.md стр. 444: CRUD запись: создать пациента → визит → печать талона
    """
    
    data = setup_test_data
    
    # Токены для разных ролей
    admin_token = create_access_token(subject=data["admin_user"].username)
    registrar_token = create_access_token(subject=data["registrar_user"].username)
    doctor_token = create_access_token(subject=data["doctor_user"].username)
    
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    registrar_headers = {"Authorization": f"Bearer {registrar_token}"}
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}
    
    print("🧪 Тестирование полного цикла интеграции...")
    
    # ===== ШАГ 1: РЕГИСТРАТУРА - Генерация QR кода =====
    print("1️⃣ Генерация QR кода в регистратуре...")
    
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    response = client.post(
        f"/api/v1/registrar/generate-qr?day={tomorrow}&specialist_id={data['doctor'].id}",
        headers=registrar_headers
    )
    
    assert response.status_code == 200
    qr_data = response.json()
    assert qr_data["success"] == True
    assert "token" in qr_data
    
    print(f"   ✅ QR токен создан: {qr_data['token'][:8]}...")
    
    # ===== ШАГ 2: ПАЦИЕНТ - Вступление в онлайн-очередь =====
    print("2️⃣ Пациент вступает в онлайн-очередь...")
    
    join_request = {
        "token": qr_data["token"],
        "phone": data["patient"].phone,
        "patient_name": f"{data['patient'].last_name} {data['patient'].first_name}"
    }
    
    response = client.post("/api/v1/online-queue/join", json=join_request)
    
    assert response.status_code == 200
    join_result = response.json()
    assert join_result["success"] == True
    assert join_result["number"] == 1  # Первый номер для кардиологии
    
    print(f"   ✅ Пациент получил номер: #{join_result['number']}")
    
    # ===== ШАГ 3: РЕГИСТРАТУРА - Открытие приема =====
    print("3️⃣ Регистратура открывает прием...")
    
    response = client.post(
        f"/api/v1/registrar/open-reception?day={tomorrow}&specialist_id={data['doctor'].id}",
        headers=registrar_headers
    )
    
    assert response.status_code == 200
    open_result = response.json()
    assert open_result["success"] == True
    
    print("   ✅ Прием открыт, онлайн-набор закрыт")
    
    # ===== ШАГ 4: ВРАЧ - Просмотр очереди =====
    print("4️⃣ Врач видит пациента в очереди...")
    
    response = client.get("/api/v1/doctor/cardiology/queue/today", headers=doctor_headers)
    
    assert response.status_code == 200
    queue_data = response.json()
    assert queue_data["queue_exists"] == True
    assert len(queue_data["entries"]) == 1
    assert queue_data["entries"][0]["number"] == 1
    
    print(f"   ✅ Врач видит пациента #{queue_data['entries'][0]['number']}")
    
    entry_id = queue_data["entries"][0]["id"]
    
    # ===== ШАГ 5: ВРАЧ - Вызов пациента =====
    print("5️⃣ Врач вызывает пациента...")
    
    response = client.post(f"/api/v1/doctor/queue/{entry_id}/call", headers=doctor_headers)
    
    assert response.status_code == 200
    call_result = response.json()
    assert call_result["success"] == True
    
    print("   ✅ Пациент вызван в кабинет")
    
    # ===== ШАГ 6: ВРАЧ - Начало приема =====
    print("6️⃣ Врач начинает прием...")
    
    response = client.post(f"/api/v1/doctor/queue/{entry_id}/start-visit", headers=doctor_headers)
    
    assert response.status_code == 200
    start_result = response.json()
    assert start_result["success"] == True
    
    print("   ✅ Прием начат")
    
    # ===== ШАГ 7: ВРАЧ - Завершение приема =====
    print("7️⃣ Врач завершает прием...")
    
    visit_data = {
        "complaint": "Боли в области сердца",
        "diagnosis": "Стенокардия напряжения",
        "icd10": "I20.8",
        "services": [data["service"].id],
        "notes": "Рекомендована консультация повторно через месяц"
    }
    
    response = client.post(
        f"/api/v1/doctor/queue/{entry_id}/complete",
        json=visit_data,
        headers=doctor_headers
    )
    
    assert response.status_code == 200
    complete_result = response.json()
    assert complete_result["success"] == True
    
    print("   ✅ Прием завершен")
    
    # ===== ШАГ 8: ПРОВЕРКА ИТОГОВОГО СОСТОЯНИЯ =====
    print("8️⃣ Проверка финального состояния...")
    
    response = client.get("/api/v1/doctor/cardiology/queue/today", headers=doctor_headers)
    final_queue = response.json()
    
    # Пациент должен быть в статусе "served"
    served_entry = final_queue["entries"][0]
    assert served_entry["status"] == "served"
    
    print("   ✅ Пациент в статусе 'принят'")
    
    print("\n🎉 ПОЛНЫЙ ЦИКЛ ИНТЕГРАЦИИ ПРОШЕЛ УСПЕШНО!")
    print("📋 Проверено:")
    print("   ✅ Генерация QR в регистратуре")
    print("   ✅ Вступление пациента в онлайн-очередь") 
    print("   ✅ Открытие приема регистратурой")
    print("   ✅ Просмотр очереди врачом")
    print("   ✅ Вызов и прием пациента")
    print("   ✅ Завершение визита")
    print("\n🚀 СИСТЕМА ГОТОВА К РАБОТЕ!")


def test_queue_settings_integration(setup_test_data):
    """
    Тест интеграции настроек очереди
    Из detail.md стр. 459: стартовые номера по специальностям
    """
    
    data = setup_test_data
    registrar_token = create_access_token(subject=data["registrar_user"].username)
    headers = {"Authorization": f"Bearer {registrar_token}"}
    
    # Получаем настройки очереди
    response = client.get("/api/v1/registrar/queue-settings", headers=headers)
    
    assert response.status_code == 200
    settings = response.json()
    
    # Проверяем что настройки из админ панели применились
    assert "specialties" in settings
    assert "cardiology" in settings["specialties"]
    assert settings["specialties"]["cardiology"]["start_number"] == 1
    assert settings["specialties"]["cardiology"]["max_per_day"] == 15
    
    print("✅ Настройки очереди корректно интегрированы")


def test_services_integration(setup_test_data):
    """
    Тест интеграции справочника услуг
    """
    
    data = setup_test_data
    doctor_token = create_access_token(subject=data["doctor_user"].username)
    headers = {"Authorization": f"Bearer {doctor_token}"}
    
    # Получаем услуги для кардиолога
    response = client.get("/api/v1/doctor/cardiology/services", headers=headers)
    
    assert response.status_code == 200
    services = response.json()
    
    # Проверяем что услуги из админ панели доступны
    assert "services_by_category" in services
    assert services["total_services"] > 0
    
    print("✅ Справочник услуг корректно интегрирован")


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
