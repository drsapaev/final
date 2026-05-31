"""
✅ CERTIFICATION: Тесты безопасности файловой системы.
Проверяет:
- SHA256 хеширование файлов
- Версионирование при замене содержимого
- Контроль доступа по ролям
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import date

from app.models.appointment import Appointment
from app.models.file_system import File, FileVersion
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


class TestFileSecurity:
    """Тесты безопасности файловой системы"""

    def test_file_hash_is_computed_on_upload(
        self, client: TestClient, db_session: Session
    ):
        """✅ CERTIFICATION: SHA256 хеш вычисляется при загрузке файла"""
        # Создаем пользователя с ролью, которая может загружать файлы (Doctor)
        from app.core.security import get_password_hash
        from app.models.user import User

        doctor_user = db_session.query(User).filter(User.username == "doctor_file_test").first()
        if not doctor_user:
            doctor_user = User(
                username="doctor_file_test",
                email="doctor_file@test.com",
                hashed_password=get_password_hash("doctor123"),
                role="Doctor",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(doctor_user)
            db_session.commit()
            db_session.refresh(doctor_user)

        # Получаем токен
        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Загружаем тестовый файл
        file_content = b"Test file content for hashing"
        file_obj = BytesIO(file_content)
        file_obj.name = "test.txt"

        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("test.txt", file_obj, "text/plain")},
            data={
                "file_type": "document",
                "permission": "private",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        file_data = response.json()
        assert "file_hash" in file_data
        assert file_data["file_hash"] is not None
        assert len(file_data["file_hash"]) == 64  # SHA256 hex = 64 символа

        # Проверяем в БД
        db_file = db_session.query(File).filter(File.id == file_data["id"]).first()
        assert db_file.file_hash is not None
        assert len(db_file.file_hash) == 64

    def test_file_versioning_on_content_replace(
        self, client: TestClient, db_session: Session
    ):
        """✅ CERTIFICATION: Версия создается при замене содержимого файла"""
        # Создаем пользователя с ролью Doctor
        from app.core.security import get_password_hash
        from app.models.user import User

        doctor_user = db_session.query(User).filter(User.username == "doctor_file_test2").first()
        if not doctor_user:
            doctor_user = User(
                username="doctor_file_test2",
                email="doctor_file2@test.com",
                hashed_password=get_password_hash("doctor123"),
                role="Doctor",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(doctor_user)
            db_session.commit()
            db_session.refresh(doctor_user)

        # Получаем токен
        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Шаг 1: Загружаем исходный файл
        file_content_1 = b"Original file content"
        file_obj_1 = BytesIO(file_content_1)
        file_obj_1.name = "original.txt"

        upload_response = client.post(
            "/api/v1/files/upload",
            files={"file": ("original.txt", file_obj_1, "text/plain")},
            data={
                "file_type": "document",
                "permission": "private",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]
        original_hash = upload_response.json()["file_hash"]

        # Шаг 2: Заменяем содержимое файла
        file_content_2 = b"Updated file content"
        file_obj_2 = BytesIO(file_content_2)
        file_obj_2.name = "updated.txt"

        replace_response = client.put(
            f"/api/v1/files/{file_id}/content",
            files={"file": ("updated.txt", file_obj_2, "text/plain")},
            data={"change_description": "Test versioning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert replace_response.status_code == 200
        updated_file = replace_response.json()
        new_hash = updated_file["file_hash"]

        # Проверяем, что хеш изменился
        assert new_hash != original_hash

        # Шаг 3: Проверяем, что версия создана
        versions = (
            db_session.query(FileVersion)
            .filter(FileVersion.file_id == file_id)
            .order_by(FileVersion.version_number)
            .all()
        )
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].file_hash == original_hash
        assert versions[0].file_path is not None

        # Проверяем, что текущий файл обновлен
        db_file = db_session.query(File).filter(File.id == file_id).first()
        assert db_file.file_hash == new_hash

    def test_file_access_control_by_role(
        self, client: TestClient, patient_token: str, db_session: Session
    ):
        """✅ CERTIFICATION: Patient не может загружать файлы"""
        file_content = b"Test file"
        file_obj = BytesIO(file_content)
        file_obj.name = "test.txt"

        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("test.txt", file_obj, "text/plain")},
            data={
                "file_type": "document",
                "permission": "private",
            },
            headers={"Authorization": f"Bearer {patient_token}"},
        )

        # Patient не должен иметь доступ к загрузке
        assert response.status_code == 403

    def test_file_upload_rejects_mismatched_patient_visit_context(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers: dict[str, str],
        test_patient,
        test_doctor,
    ):
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998901112233",
            birth_date=date(1985, 1, 1),
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=date.today(),
            visit_time="11:00",
            status="open",
        )
        db_session.add(other_visit)
        db_session.commit()
        db_session.refresh(other_visit)

        file_obj = BytesIO(b"wrong patient visit context")
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("context.txt", file_obj, "text/plain")},
            data={
                "file_type": "document",
                "permission": "private",
                "patient_id": str(test_patient.id),
                "visit_id": str(other_visit.id),
            },
            headers=auth_headers,
        )

        assert response.status_code == 409
        patient_files = db_session.query(File).filter(
            File.patient_id == test_patient.id
        )
        visit_files = db_session.query(File).filter(File.visit_id == other_visit.id)
        assert patient_files.count() == 0
        assert visit_files.count() == 0

    def test_file_upload_rejects_mismatched_patient_appointment_context(
        self,
        client: TestClient,
        db_session: Session,
        auth_headers: dict[str, str],
        test_patient,
        test_doctor,
    ):
        other_patient = Patient(
            first_name="Appointment",
            last_name="Other",
            phone="+998901112244",
            birth_date=date(1986, 1, 1),
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        other_appointment = Appointment(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today(),
            appointment_time="12:00",
            status="scheduled",
        )
        db_session.add(other_appointment)
        db_session.commit()
        db_session.refresh(other_appointment)

        file_obj = BytesIO(b"wrong appointment context")
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("appointment-context.txt", file_obj, "text/plain")},
            data={
                "file_type": "document",
                "permission": "private",
                "patient_id": str(test_patient.id),
                "appointment_id": str(other_appointment.id),
            },
            headers=auth_headers,
        )

        assert response.status_code == 409
        appointment_files = db_session.query(File).filter(
            File.appointment_id == other_appointment.id
        )
        assert appointment_files.count() == 0

    def test_file_hash_consistency(
        self, client: TestClient, db_session: Session
    ):
        """✅ CERTIFICATION: Одинаковые файлы имеют одинаковый хеш"""
        # Создаем пользователя с ролью Doctor
        from app.core.security import get_password_hash
        from app.models.user import User

        doctor_user = db_session.query(User).filter(User.username == "doctor_file_test3").first()
        if not doctor_user:
            doctor_user = User(
                username="doctor_file_test3",
                email="doctor_file3@test.com",
                hashed_password=get_password_hash("doctor123"),
                role="Doctor",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(doctor_user)
            db_session.commit()
            db_session.refresh(doctor_user)

        # Получаем токен
        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        file_content = b"Identical content"

        # Загружаем первый файл
        file_obj_1 = BytesIO(file_content)
        file_obj_1.name = "file1.txt"
        response_1 = client.post(
            "/api/v1/files/upload",
            files={"file": ("file1.txt", file_obj_1, "text/plain")},
            data={"file_type": "document", "permission": "private"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response_1.status_code == 200
        hash_1 = response_1.json()["file_hash"]

        # Загружаем второй файл с тем же содержимым
        file_obj_2 = BytesIO(file_content)
        file_obj_2.name = "file2.txt"
        response_2 = client.post(
            "/api/v1/files/upload",
            files={"file": ("file2.txt", file_obj_2, "text/plain")},
            data={"file_type": "document", "permission": "private"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response_2.status_code == 200
        hash_2 = response_2.json()["file_hash"]

        # Хеши должны совпадать
        assert hash_1 == hash_2

    def test_file_version_hash_required(
        self, client: TestClient, db_session: Session
    ):
        """✅ CERTIFICATION: Версия файла содержит file_hash"""
        # Создаем пользователя с ролью Doctor
        from app.core.security import get_password_hash
        from app.models.user import User

        doctor_user = db_session.query(User).filter(User.username == "doctor_file_test4").first()
        if not doctor_user:
            doctor_user = User(
                username="doctor_file_test4",
                email="doctor_file4@test.com",
                hashed_password=get_password_hash("doctor123"),
                role="Doctor",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(doctor_user)
            db_session.commit()
            db_session.refresh(doctor_user)

        # Получаем токен
        login_response = client.post(
            "/api/v1/authentication/login",
            json={"username": doctor_user.username, "password": "doctor123"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Загружаем файл
        file_content = b"Version test"
        file_obj = BytesIO(file_content)
        file_obj.name = "version_test.txt"

        upload_response = client.post(
            "/api/v1/files/upload",
            files={"file": ("version_test.txt", file_obj, "text/plain")},
            data={"file_type": "document", "permission": "private"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]
        original_hash = upload_response.json()["file_hash"]

        # Заменяем содержимое
        new_content = b"New version content"
        new_file_obj = BytesIO(new_content)
        new_file_obj.name = "new_version.txt"

        replace_response = client.put(
            f"/api/v1/files/{file_id}/content",
            files={"file": ("new_version.txt", new_file_obj, "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert replace_response.status_code == 200

        # Проверяем версию
        version = (
            db_session.query(FileVersion)
            .filter(FileVersion.file_id == file_id)
            .first()
        )
        assert version is not None
        assert version.file_hash is not None
        assert version.file_hash == original_hash

