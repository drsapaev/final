"""
Интеграционные тесты для batch queue entries endpoint

Тестируем:
- POST /api/v1/registrar-integration/queue/entries/batch
- Source preservation
- Fair queue numbering (queue_time = current time)
- Duplicate detection
- Service grouping by specialist
- Auto-create DailyQueue
- Error handling
- Access control
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User


@pytest.fixture(scope="function")
def test_services(db_session):
    """Создает тестовые услуги"""
    services = []

    # Услуга 1: Консультация кардиолога
    service1 = Service(
        code="CARDIO_CONS",
        name="Консультация кардиолога",
        price=150000.00,
        duration_minutes=30,
        is_active=True,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=True
    )
    db_session.add(service1)
    services.append(service1)

    # Услуга 2: ЭКГ
    service2 = Service(
        code="ECG",
        name="ЭКГ",
        price=50000.00,
        duration_minutes=15,
        is_active=True,
        requires_doctor=False,
        queue_tag="cardiology_diagnostics",
        is_consultation=False
    )
    db_session.add(service2)
    services.append(service2)

    # Услуга 3: Общий анализ крови
    service3 = Service(
        code="LAB_CBC",
        name="Общий анализ крови",
        price=30000.00,
        duration_minutes=5,
        is_active=True,
        requires_doctor=False,
        queue_tag="laboratory_general",
        is_consultation=False
    )
    db_session.add(service3)
    services.append(service3)

    db_session.commit()
    for service in services:
        db_session.refresh(service)

    return services


@pytest.fixture(scope="function")
def test_specialists(db_session):
    """Создает тестовых специалистов"""
    specialists = []

    # Специалист 1: Кардиолог
    cardio = User(
        username="cardio_specialist",
        email="cardio@clinic.com",
        full_name="Кардиолог Иванов",
        hashed_password="hashed",
        role="cardio",
        is_active=True
    )
    db_session.add(cardio)
    specialists.append(cardio)

    # Специалист 2: Лаборант
    lab = User(
        username="lab_specialist",
        email="lab@clinic.com",
        full_name="Лаборант Петрова",
        hashed_password="hashed",
        role="Lab",
        is_active=True
    )
    db_session.add(lab)
    specialists.append(lab)

    db_session.commit()
    for specialist in specialists:
        db_session.refresh(specialist)

    return specialists


@pytest.mark.integration
@pytest.mark.queue
class TestQueueBatchAPI:
    """Тесты batch queue entries endpoint"""

    def test_create_single_queue_entry_success(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services
    ):
        """Тест: Успешное создание одной записи в очереди"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert len(data["entries"]) == 1
        assert data["entries"][0]["specialist_id"] == test_specialists[0].id
        assert "queue_id" in data["entries"][0]
        assert "number" in data["entries"][0]
        assert "queue_time" in data["entries"][0]
        assert "Создано" in data["message"]

    def test_create_multiple_queue_entries_different_specialists(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services
    ):
        """Тест: Создание записей к разным специалистам"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "online",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    },
                    {
                        "specialist_id": test_specialists[1].id,
                        "service_id": test_services[2].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert len(data["entries"]) == 2

        # Проверяем что созданы записи для обоих специалистов
        specialist_ids = [entry["specialist_id"] for entry in data["entries"]]
        assert test_specialists[0].id in specialist_ids
        assert test_specialists[1].id in specialist_ids

    def test_source_preservation(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services, db_session
    ):
        """Тест: Сохранение оригинального source"""
        # Создаем запись с source='online'
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "online",  # ⭐ Важно: source='online'
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Проверяем в базе данных
        queue_entry = db_session.query(OnlineQueueEntry).filter_by(
            patient_id=test_patient.id
        ).first()

        assert queue_entry is not None
        assert queue_entry.source == "online"  # ⭐ Source сохранен

    def test_duplicate_detection(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services, db_session
    ):
        """Тест: Обнаружение дубликатов (пациент уже в очереди к специалисту)"""
        # Создаем первую запись
        response1 = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response1.status_code == 200
        first_data = response1.json()
        first_queue_id = first_data["entries"][0]["queue_id"]
        first_number = first_data["entries"][0]["number"]

        # Пытаемся создать дубликат (тот же пациент, тот же специалист)
        response2 = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[1].id,  # Другая услуга, но тот же специалист
                        "quantity": 1
                    }
                ]
            }
        )

        assert response2.status_code == 200
        second_data = response2.json()

        # Должна вернуться существующая запись
        assert second_data["entries"][0]["queue_id"] == first_queue_id
        assert second_data["entries"][0]["number"] == first_number
        assert "существовала" in second_data["message"]

    def test_service_grouping_by_specialist(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services, db_session
    ):
        """Тест: Группировка услуг по специалистам (несколько услуг одного специалиста = одна запись)"""
        # Создаем несколько услуг для одного специалиста
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    },
                    {
                        "specialist_id": test_specialists[0].id,  # Тот же специалист
                        "service_id": test_services[1].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Должна быть создана ОДНА запись (группировка)
        assert len(data["entries"]) == 1
        assert data["entries"][0]["specialist_id"] == test_specialists[0].id

    def test_auto_create_daily_queue(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services, db_session
    ):
        """Тест: Автоматическое создание DailyQueue если не существует"""
        # Убедимся что очереди для специалиста сегодня нет
        today = date.today()
        existing_queue = db_session.query(DailyQueue).filter_by(
            day=today,
            specialist_id=test_specialists[0].id
        ).first()

        if existing_queue:
            db_session.delete(existing_queue)
            db_session.commit()

        # Создаем запись
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200

        # Проверяем что DailyQueue была создана автоматически
        new_queue = db_session.query(DailyQueue).filter_by(
            day=today,
            specialist_id=test_specialists[0].id
        ).first()

        assert new_queue is not None
        assert new_queue.is_clinic_wide is False  # Персональная очередь

    def test_patient_not_found_error(
        self, client, registrar_auth_headers, test_specialists, test_services
    ):
        """Тест: Ошибка - пациент не найден"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": 999999,  # Несуществующий ID
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]

    def test_service_not_found_error(
        self, client, registrar_auth_headers, test_patient, test_specialists
    ):
        """Тест: Ошибка - услуга не найдена"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": 999999,  # Несуществующий ID
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]

    def test_specialist_not_found_error(
        self, client, registrar_auth_headers, test_patient, test_services
    ):
        """Тест: Ошибка - специалист не найден"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": 999999,  # Несуществующий ID
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]

    def test_invalid_source_error(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services
    ):
        """Тест: Ошибка - неверный source"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "invalid_source",  # Неверный source
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 422  # Validation error

    def test_admin_access_allowed(
        self, client, auth_headers, test_patient, test_specialists, test_services
    ):
        """Тест: Admin имеет доступ"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=auth_headers,  # Admin auth
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200

    def test_registrar_access_allowed(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services
    ):
        """Тест: Registrar имеет доступ"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 200

    def test_doctor_access_denied(
        self, client, cardio_auth_headers, test_patient, test_specialists, test_services
    ):
        """Тест: Doctor НЕ имеет доступа"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=cardio_auth_headers,  # Cardio user auth
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 403  # Forbidden

    def test_unauthenticated_access_denied(
        self, client, test_patient, test_specialists, test_services
    ):
        """Тест: Неавторизованный доступ запрещен"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            # Без headers (нет авторизации)
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response.status_code == 401  # Unauthorized

    def test_empty_services_list_error(
        self, client, registrar_auth_headers, test_patient
    ):
        """Тест: Ошибка - пустой список услуг"""
        response = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "desk",
                "services": []  # Пустой список
            }
        )

        assert response.status_code == 422  # Validation error

    def test_fair_queue_numbering(
        self, client, registrar_auth_headers, test_patient, test_specialists, test_services, db_session
    ):
        """Тест: Справедливая нумерация (queue_time = current time)"""
        # Создаем первую запись
        response1 = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": test_patient.id,
                "source": "online",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[0].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response1.status_code == 200
        first_number = response1.json()["entries"][0]["number"]
        first_queue_time = response1.json()["entries"][0]["queue_time"]

        # Создаем второго пациента
        patient2 = Patient(
            first_name="Петр",
            last_name="Петров",
            middle_name="Петрович",
            phone="+998901234568",
            birth_date=date(1985, 5, 5)
        )
        db_session.add(patient2)
        db_session.commit()
        db_session.refresh(patient2)

        # Создаем вторую запись
        response2 = client.post(
            "/api/v1/registrar-integration/queue/entries/batch",
            headers=registrar_auth_headers,
            json={
                "patient_id": patient2.id,
                "source": "desk",
                "services": [
                    {
                        "specialist_id": test_specialists[0].id,
                        "service_id": test_services[1].id,
                        "quantity": 1
                    }
                ]
            }
        )

        assert response2.status_code == 200
        second_number = response2.json()["entries"][0]["number"]
        second_queue_time = response2.json()["entries"][0]["queue_time"]

        # Проверяем справедливую нумерацию
        assert second_number > first_number  # Больший номер
        assert second_queue_time >= first_queue_time  # Позднее время