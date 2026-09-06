"""
Fix B (wizard profile save): PatientUpdate принимает full_name.

Оригинальный дефект: мастер регистрации отправляет правки профиля единым
full_name, но PatientUpdate не объявлял это поле — Pydantic молча отбрасывал
его (extra=ignore), PUT возвращал 200, а ФИО не сохранялось. Нельзя судить
о сохранении только по 200 — нужно проверять перечитанные данные.

Эти тесты прогоняются на SQLite-харнессе conftest (изолированной файловой БД);
отдельной disposable PostgreSQL в среде выполнения нет.
"""
import pytest  # pyright: ignore[reportMissingImports]  # noqa: F401  (маркер pytest-харнесса)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.user import User


def _create_patient(client: TestClient, token: str, phone: str) -> dict:
    response = client.post(
        "/api/v1/patients/",
        json={
            "last_name": "Тестов",
            "first_name": "Пациент",
            "birth_date": "1990-01-01",
            "sex": "M",
            "phone": phone,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_update_patient_full_name_is_split_and_persisted(
    client: TestClient, db: Session, admin_user: User, admin_password: str
):
    """PUT с full_name нормализуется в last/first/middle и сохраняется в БД."""
    from tests.conftest import mint_access_token

    token = mint_access_token(admin_user)
    created = _create_patient(client, token, "+998900000901")

    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={
            "full_name": "Иванов Иван Иванович",
            "address": "ул. Навои, 1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Ответ содержит перечитанную с сервера карточку
    assert body["last_name"] == "Иванов"
    assert body["first_name"] == "Иван"
    assert body["middle_name"] == "Иванович"
    assert body["address"] == "ул. Навои, 1"

    # Проверяем фактическое сохранение в БД (не только 200)
    db_patient = db.query(Patient).filter(Patient.id == created["id"]).first()
    assert db_patient is not None
    assert db_patient.last_name == "Иванов"
    assert db_patient.first_name == "Иван"
    assert db_patient.middle_name == "Иванович"


def test_update_patient_without_full_name_keeps_names(
    client: TestClient, db: Session, admin_user: User, admin_password: str
):
    """PUT без full_name не трогает имя (обратная совместимость)."""
    from tests.conftest import mint_access_token

    token = mint_access_token(admin_user)
    created = _create_patient(client, token, "+998900000902")

    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={"address": "новый адрес"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    db_patient = db.query(Patient).filter(Patient.id == created["id"]).first()
    assert db_patient is not None
    assert db_patient.last_name == "Тестов"
    assert db_patient.first_name == "Пациент"
    assert db_patient.address == "новый адрес"


def test_update_patient_two_word_full_name_clears_middle_name(
    client: TestClient, db: Session, admin_user: User, admin_password: str
):
    """Полное переименование: 2 слова → middle_name очищается (семантика rename)."""
    from tests.conftest import mint_access_token

    token = mint_access_token(admin_user)
    created = _create_patient(client, token, "+998900000903")

    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={"full_name": "Петров Пётр"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    db_patient = db.query(Patient).filter(Patient.id == created["id"]).first()
    assert db_patient is not None
    assert db_patient.last_name == "Петров"
    assert db_patient.first_name == "Пётр"
    assert not db_patient.middle_name
