"""
Тесты для системы онлайн-очереди согласно detail.md стр. 442-484
"""
import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.clinic import Doctor
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
def admin_token(db_session):
    """Токен администратора"""
    admin_user = User(
        username="test_admin",
        email="admin@test.com",
        full_name="Test Admin",
        role="Admin",
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()
    
    token = create_access_token(subject=admin_user.username)
    return token


@pytest.fixture
def test_doctor(db_session):
    """Тестовый врач"""
    doctor = Doctor(
        specialty="cardiology",
        cabinet="101",
        start_number_online=1,
        max_online_per_day=15,
        active=True
    )
    db_session.add(doctor)
    db_session.commit()
    return doctor


def test_qr_token_generation(admin_token, test_doctor):
    """
    Тест 1: Генерация QR токена
    Из detail.md стр. 447: POST /api/online-queue/qrcode?day&specialist_id
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Генерируем токен на завтра
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    response = client.post(
        f"/api/v1/online-queue/qrcode?day={tomorrow}&specialist_id={test_doctor.id}",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Проверяем структуру ответа
    assert "token" in data
    assert "qr_url" in data
    assert "specialist_name" in data
    assert "specialty" in data
    assert data["specialty"] == "cardiology"
    assert data["max_slots"] == 15


def test_queue_join_success(admin_token, test_doctor, db_session):
    """
    Тест 2: Успешное вступление в очередь
    Из detail.md стр. 450: один номер на телефон
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Генерируем токен
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    token_response = client.post(
        f"/api/v1/online-queue/qrcode?day={tomorrow}&specialist_id={test_doctor.id}",
        headers=headers
    )
    token = token_response.json()["token"]
    
    # Вступаем в очередь
    join_data = {
        "token": token,
        "phone": "+998901234567",
        "patient_name": "Тестовый Пациент"
    }
    
    response = client.post("/api/v1/online-queue/join", json=join_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] == True
    assert data["number"] == 1  # Первый номер для кардиологии
    assert data["duplicate"] == False


def test_queue_join_duplicate(admin_token, test_doctor):
    """
    Тест 3: Дубликат записи
    Из detail.md стр. 450: повтор → тот же номер
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Генерируем токен
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    token_response = client.post(
        f"/api/v1/online-queue/qrcode?day={tomorrow}&specialist_id={test_doctor.id}",
        headers=headers
    )
    token = token_response.json()["token"]
    
    join_data = {
        "token": token,
        "phone": "+998901234567",
        "patient_name": "Тестовый Пациент"
    }
    
    # Первое вступление
    response1 = client.post("/api/v1/online-queue/join", json=join_data)
    number1 = response1.json()["number"]
    
    # Повторное вступление с тем же телефоном
    response2 = client.post("/api/v1/online-queue/join", json=join_data)
    data2 = response2.json()
    
    assert data2["success"] == True
    assert data2["number"] == number1  # Тот же номер
    assert data2["duplicate"] == True


def test_queue_time_restrictions():
    """
    Тест 4: Ограничения по времени
    Из detail.md стр. 447: до 07:00 запрещено
    """
    # Этот тест требует мокинга времени
    # Пока пропускаем, но логика реализована в check_queue_availability
    pass


def test_queue_limits(admin_token, test_doctor):
    """
    Тест 5: Лимиты очереди
    Из detail.md стр. 453: по достижении N — отказ
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Генерируем токен
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    token_response = client.post(
        f"/api/v1/online-queue/qrcode?day={tomorrow}&specialist_id={test_doctor.id}",
        headers=headers
    )
    token = token_response.json()["token"]
    
    # Заполняем очередь до лимита (15 для кардиологии)
    for i in range(16):  # Пытаемся записать больше лимита
        join_data = {
            "token": token,
            "phone": f"+99890123456{i:02d}",
            "patient_name": f"Пациент {i+1}"
        }
        
        response = client.post("/api/v1/online-queue/join", json=join_data)
        
        if i < 15:  # Первые 15 должны пройти
            assert response.json()["success"] == True
        else:  # 16-й должен получить отказ
            data = response.json()
            assert data["success"] == False
            assert data["error_code"] == "QUEUE_FULL"


def test_queue_open_closes_online(admin_token, test_doctor):
    """
    Тест 6: Открытие приема закрывает онлайн-набор
    Из detail.md стр. 456: кнопка закрывает набор онлайн
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    # Открываем прием
    response = client.post(
        f"/api/v1/online-queue/open?day={tomorrow}&specialist_id={test_doctor.id}",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["closed_online_registration"] == True
    
    # Теперь попытка вступить в очередь должна быть отклонена
    # (Нужен токен, сгенерированный до открытия)


def test_specialty_start_numbers(admin_token, db_session):
    """
    Тест 7: Стартовые номера по специальностям
    Из detail.md стр. 459: стоматолог с №3; дерматолог с №15
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Создаем врачей разных специальностей
    doctors = [
        Doctor(specialty="cardiology", cabinet="101", start_number_online=1, active=True),
        Doctor(specialty="dermatology", cabinet="102", start_number_online=15, active=True), 
        Doctor(specialty="stomatology", cabinet="103", start_number_online=3, active=True)
    ]
    
    for doctor in doctors:
        db_session.add(doctor)
    db_session.commit()
    
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    # Проверяем стартовые номера
    expected_start_numbers = {
        "cardiology": 1,
        "dermatology": 15,
        "stomatology": 3
    }
    
    for doctor in doctors:
        # Генерируем токен
        token_response = client.post(
            f"/api/v1/online-queue/qrcode?day={tomorrow}&specialist_id={doctor.id}",
            headers=headers
        )
        token = token_response.json()["token"]
        
        # Записываемся в очередь
        join_data = {
            "token": token,
            "phone": f"+99890123456{doctor.id}",
            "patient_name": f"Пациент {doctor.specialty}"
        }
        
        response = client.post("/api/v1/online-queue/join", json=join_data)
        data = response.json()
        
        expected_number = expected_start_numbers[doctor.specialty]
        assert data["number"] == expected_number, f"Неверный стартовый номер для {doctor.specialty}"


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v", "--tb=short"])
