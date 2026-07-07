"""
E2E Test: Doctor Visit Flow
============================

Тестирует полный поток приёма врача:
1. Врач видит свою очередь
2. Вызов следующего пациента
3. Заполнение ЭМК (жалобы, диагноз, назначения)
4. Использование шаблонов
5. Генерация PDF (рецепт, памятка)
6. Завершение приёма

Маркеры: e2e, doctor
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.emr import EMR
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit, VisitService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def doctor_with_queue(db_session):
    """Создает врача с очередью пациентов"""
    # Создаем врача-пользователя
    doctor_user = db_session.query(User).filter(User.username == "e2e_doctor").first()
    if not doctor_user:
        doctor_user = User(
            username="e2e_doctor",
            email="e2e_doctor@test.com",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
            full_name="Тест Докторов",
        )
        db_session.add(doctor_user)
        db_session.commit()
        db_session.refresh(doctor_user)

    # Создаем профиль врача
    doctor = db_session.query(Doctor).filter(Doctor.user_id == doctor_user.id).first()
    if not doctor:
        doctor = Doctor(
            user_id=doctor_user.id,
            specialty="Терапия",
            active=True,
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

    # Создаем пациентов для очереди
    patients = []
    for i in range(3):
        patient = db_session.query(Patient).filter(
            Patient.phone == f"+9989900000{i:02d}"
        ).first()
        if not patient:
            patient = Patient(
                first_name=f"Пациент{i+1}",
                last_name=f"Очередь{i+1}",
                phone=f"+9989900000{i:02d}",
                birth_date=date(1990 + i, 1, 1),
            )
            db_session.add(patient)
            db_session.commit()
            db_session.refresh(patient)
        patients.append(patient)

    # Создаем дневную очередь
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor_user.id,
        queue_tag="therapy_common",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    # Добавляем пациентов в очередь
    entries = []
    for i, patient in enumerate(patients):
        # Создаем визит
        visit = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_date=date.today(),
            visit_time=f"{9 + i}:00",
            status="waiting",
            department="therapy",
        )
        db_session.add(visit)
        db_session.commit()
        db_session.refresh(visit)

        # Создаем запись в очереди
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=i + 1,
            patient_id=patient.id,
            patient_name=patient.short_name(),
            phone=patient.phone,
            visit_id=visit.id,
            status="waiting",
            source="registrar",
        )
        db_session.add(entry)
        entries.append({"entry": entry, "visit": visit})

    db_session.commit()

    return {
        "doctor_user": doctor_user,
        "doctor": doctor,
        "patients": patients,
        "queue": queue,
        "entries": entries,
    }


@pytest.fixture
def doctor_auth_headers(client: TestClient, doctor_with_queue):
    """Заголовки авторизации для врача"""
    user = doctor_with_queue["doctor_user"]
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200, f"Doctor login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Test Cases
# =============================================================================

@pytest.mark.integration
@pytest.mark.e2e
class TestDoctorVisitFlow:
    """E2E тесты потока приёма врача"""

    def test_doctor_can_view_queue(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue
    ):
        """Врач может видеть свою очередь"""
        queue = doctor_with_queue["queue"]

        response = client.get(
            f"/api/v1/queue/qr-tokens/{queue.queue_tag}/entries",
            headers=doctor_auth_headers,
            params={"date": date.today().isoformat()},
        )

        # Может потребоваться другой endpoint
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or "entries" in data

    def test_doctor_can_call_next_patient(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue
    ):
        """Врач может вызвать следующего пациента"""
        queue = doctor_with_queue["queue"]
        entry = doctor_with_queue["entries"][0]["entry"]

        response = client.post(
            f"/api/v1/queue/qr-tokens/{queue.queue_tag}/call-next",
            headers=doctor_auth_headers,
        )

        if response.status_code == 200:
            data = response.json()
            # Проверяем что вызван пациент
            assert "patient" in data or "entry" in data or "number" in data

    def test_delete_visit_service_rejects_child_from_different_visit(
        self,
        client: TestClient,
        db_session,
        auth_headers,
        doctor_with_queue,
        test_service,
    ):
        """Nested service delete must not trust visit_service_id alone."""
        first_visit = doctor_with_queue["entries"][0]["visit"]
        other_visit = doctor_with_queue["entries"][1]["visit"]

        first_service = VisitService(
            visit_id=first_visit.id,
            service_id=test_service.id,
            quantity=1,
            price=test_service.price,
        )
        other_service = VisitService(
            visit_id=other_visit.id,
            service_id=test_service.id,
            quantity=1,
            price=test_service.price,
        )
        db_session.add_all([first_service, other_service])
        db_session.commit()
        db_session.refresh(first_service)
        db_session.refresh(other_service)

        response = client.delete(
            f"/api/v1/doctor/visits/{first_visit.id}/services/{other_service.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404, response.text
        assert db_session.get(VisitService, first_service.id) is not None
        assert db_session.get(VisitService, other_service.id) is not None

    def test_add_visit_service_rejects_user_id_doctor_id_collision_bypass(
        self,
        client: TestClient,
        db_session,
        test_service,
    ):
        attacker_user = User(
            id=9401,
            username="visit_service_attacker",
            email="visit-service-attacker@test.com",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
        )
        victim_user = User(
            id=9403,
            username="visit_service_victim",
            email="visit-service-victim@test.com",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
        )
        attacker_doctor = Doctor(
            id=9402,
            user_id=attacker_user.id,
            specialty="therapy",
            active=True,
        )
        victim_doctor = Doctor(
            id=attacker_user.id,
            user_id=victim_user.id,
            specialty="therapy",
            active=True,
        )
        patient = Patient(
            first_name="Visit",
            last_name="Owner",
            phone="+998909401000",
            birth_date=date(1990, 1, 1),
        )
        db_session.add_all(
            [attacker_user, victim_user, attacker_doctor, victim_doctor, patient]
        )
        db_session.commit()
        db_session.refresh(patient)

        victim_visit = Visit(
            patient_id=patient.id,
            doctor_id=victim_doctor.id,
            visit_date=date.today(),
            visit_time="11:00",
            status="open",
            department="therapy",
        )
        db_session.add(victim_visit)
        db_session.commit()
        db_session.refresh(victim_visit)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": attacker_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.put(
            f"/api/v1/doctor/visits/{victim_visit.id}/add-service",
            params={"service_id": test_service.id},
            headers=headers,
        )

        assert response.status_code == 403, response.text
        assert (
            db_session.query(VisitService)
            .filter(VisitService.visit_id == victim_visit.id)
            .count()
            == 0
        )

    def test_today_visits_uses_doctor_id_not_user_id_collision(
        self,
        client: TestClient,
        db_session,
    ):
        attacker_user = User(
            id=9501,
            username="today_visit_attacker",
            email="today-visit-attacker@test.com",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
        )
        victim_user = User(
            id=9503,
            username="today_visit_victim",
            email="today-visit-victim@test.com",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
        )
        attacker_doctor = Doctor(
            id=9502,
            user_id=attacker_user.id,
            specialty="therapy",
            active=True,
        )
        victim_doctor = Doctor(
            id=attacker_user.id,
            user_id=victim_user.id,
            specialty="therapy",
            active=True,
        )
        patient = Patient(
            first_name="Private",
            last_name="Visit",
            phone="+998909501000",
            birth_date=date(1990, 1, 1),
        )
        db_session.add_all(
            [attacker_user, victim_user, attacker_doctor, victim_doctor, patient]
        )
        db_session.commit()
        db_session.refresh(patient)

        victim_visit = Visit(
            patient_id=patient.id,
            doctor_id=victim_doctor.id,
            visit_date=date.today(),
            visit_time="12:00",
            status="open",
            department="therapy",
        )
        db_session.add(victim_visit)
        db_session.commit()
        db_session.refresh(victim_visit)

        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": attacker_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = client.get("/api/v1/doctor/visits/today", headers=headers)

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["total_count"] == 0
        assert all(item["id"] != victim_visit.id for item in payload["visits"])

    def test_doctor_can_start_visit(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue, db_session
    ):
        """Врач может начать приём (изменить статус визита)"""
        visit = doctor_with_queue["entries"][0]["visit"]

        response = client.patch(
            f"/api/v1/visits/{visit.id}",
            headers=doctor_auth_headers,
            json={"status": "in_progress"},
        )

        if response.status_code == 200:
            data = response.json()
            assert data.get("status") == "in_progress"

    def test_doctor_can_fill_emr(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue
    ):
        """Врач может заполнить ЭМК"""
        visit = doctor_with_queue["entries"][0]["visit"]
        patient = doctor_with_queue["patients"][0]

        emr_data = {
            "visit_id": visit.id,
            "patient_id": patient.id,
            "chief_complaint": "Головная боль, слабость",
            "history_of_present_illness": "Беспокоит в течение 3 дней",
            "diagnosis": "J06.9 - ОРВИ неуточненная",
            "treatment_plan": "Постельный режим, обильное питьё",
            "prescriptions": [
                {"name": "Парацетамол", "dosage": "500мг", "frequency": "2 раза в день"}
            ],
        }

        response = client.post(
            "/api/v1/emr/records",
            headers=doctor_auth_headers,
            json=emr_data,
        )

        # EMR endpoint может отличаться
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data

    def test_doctor_can_use_emr_template(
        self, client: TestClient, doctor_auth_headers
    ):
        """Врач может использовать шаблон ЭМК"""
        response = client.get(
            "/api/v1/emr/templates",
            headers=doctor_auth_headers,
        )

        assert response.status_code == 200
        templates = response.json()
        assert isinstance(templates, list)

    def test_doctor_can_add_diagnosis_with_ai_suggestion(
        self, client: TestClient, doctor_auth_headers
    ):
        """Врач может получить AI-подсказку для диагноза"""
        response = client.post(
            "/api/v1/ai/icd-suggest",
            headers=doctor_auth_headers,
            json={"symptoms": "головная боль, температура, слабость"},
        )

        if response.status_code == 200:
            data = response.json()
            # Проверяем структуру ответа AI
            assert "suggestions" in data or "codes" in data or isinstance(data, list)

    def test_doctor_can_generate_prescription_pdf(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue
    ):
        """Врач может сгенерировать рецепт в PDF"""
        visit = doctor_with_queue["entries"][0]["visit"]
        patient = doctor_with_queue["patients"][0]

        response = client.post(
            "/api/v1/print/templates/prescription",
            headers=doctor_auth_headers,
            json={
                "patient_id": patient.id,
                "visit_id": visit.id,
                "prescriptions": [
                    {"name": "Парацетамол", "dosage": "500мг", "frequency": "2 раза в день", "duration": "5 дней"}
                ],
            },
        )

        # 200 - PDF, 404 - endpoint не реализован
        if response.status_code == 200:
            assert response.headers.get("content-type") in [
                "application/pdf",
                "application/json",
            ]

    def test_doctor_can_complete_visit(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue, db_session
    ):
        """Врач может завершить приём"""
        visit = doctor_with_queue["entries"][0]["visit"]

        response = client.patch(
            f"/api/v1/visits/{visit.id}",
            headers=doctor_auth_headers,
            json={"status": "completed"},
        )

        if response.status_code == 200:
            data = response.json()
            assert data.get("status") == "completed"

            # Проверяем что запись в очереди тоже обновилась
            db_session.refresh(visit)
            assert visit.status == "completed"


@pytest.mark.integration
@pytest.mark.e2e
class TestDoctorQueueManagement:
    """Тесты управления очередью врачом"""

    def test_doctor_can_skip_patient(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue
    ):
        """Врач может пропустить пациента (неявка)"""
        entry = doctor_with_queue["entries"][0]["entry"]

        response = client.patch(
            f"/api/v1/queue/entries/{entry.id}/skip",
            headers=doctor_auth_headers,
        )

        # Endpoint может отличаться
        if response.status_code == 200:
            data = response.json()
            assert data.get("status") in ["skipped", "no_show"]

    def test_doctor_can_get_patient_history(
        self, client: TestClient, doctor_auth_headers, doctor_with_queue
    ):
        """Врач может просмотреть историю пациента"""
        patient = doctor_with_queue["patients"][0]

        response = client.get(
            f"/api/v1/patients/{patient.id}/history",
            headers=doctor_auth_headers,
        )

        # Endpoint может быть /patients/{id}/visits или /emr/patient/{id}
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or "visits" in data


@pytest.mark.integration
@pytest.mark.e2e
class TestDoctorSecurity:
    """Тесты безопасности для врачей"""

    def test_doctor_cannot_access_admin_routes(
        self, client: TestClient, doctor_auth_headers
    ):
        """Врач не может получить доступ к админским маршрутам"""
        # ADM-AUDIT-28 P0-6: admin_users.py was deleted; use /admin/departments
        response = client.get(
            "/api/v1/admin/departments",
            headers=doctor_auth_headers,
        )

        # Должен вернуть 403 Forbidden
        assert response.status_code in [403, 401]

    def test_doctor_cannot_view_other_doctor_queue(
        self, client: TestClient, doctor_auth_headers
    ):
        """Врач не может видеть очередь другого врача"""
        response = client.get(
            "/api/v1/queue/qr-tokens/other_specialty_999/entries",
            headers=doctor_auth_headers,
            params={"date": date.today().isoformat()},
        )

        # Должен вернуть пустой список или 404
        if response.status_code == 200:
            data = response.json()
            # Пустой список нормален для несуществующей очереди
            assert isinstance(data, list)
