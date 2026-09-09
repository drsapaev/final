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
            "last_name": "SYNTHETIC-Тестов",
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
    created = _create_patient(client, token, "+998000000901")

    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={
            "full_name": "SYNTHETIC-Иванов Иван Иванович",
            "address": "ул. Навои, 1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Ответ содержит перечитанную с сервера карточку
    assert body["last_name"] == "SYNTHETIC-Иванов"
    assert body["first_name"] == "Иван"
    assert body["middle_name"] == "Иванович"
    assert body["address"] == "ул. Навои, 1"

    # Проверяем фактическое сохранение в БД (не только 200)
    db_patient = db.query(Patient).filter(Patient.id == created["id"]).first()
    assert db_patient is not None
    assert db_patient.last_name == "SYNTHETIC-Иванов"
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
    assert db_patient.last_name == "SYNTHETIC-Тестов"
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
        json={"full_name": "SYNTHETIC-Петров Пётр"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    db_patient = db.query(Patient).filter(Patient.id == created["id"]).first()
    assert db_patient is not None
    assert db_patient.last_name == "SYNTHETIC-Петров"
    assert db_patient.first_name == "Пётр"
    assert not db_patient.middle_name


def test_update_patient_overlong_name_part_returns_422_not_500(
    client: TestClient, db: Session, admin_user: User, admin_password: str
):
    """Codex R2 #3090 (P2): компонент ФИО длиннее varchar(128) отвергается
    сервисом как 422, а не доходит до БД и падает 500."""
    from tests.conftest import mint_access_token

    token = mint_access_token(admin_user)
    created = _create_patient(client, token, "+998000000902")

    long_surname = "SYNTHETIC-" + "Д" * 129  # 129+ символов (> 128)
    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={"full_name": long_surname + " Иван"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
    assert "128" in response.json()["detail"]


def test_update_patient_full_name_accepts_create_contract_limit_384(
    client: TestClient, db: Session, admin_user: User, admin_password: str
):
    """Codex R3 #3090 (P2): лимит full_name в PatientUpdate совпадает с
    PatientCreate (3 x 128 = 384). Пациент, легитимно созданный с ФИО
    256-384 символа (компоненты в пределах varchar(128)), обязан проходить
    и через PUT — раньше схема возвращала 422 на 255 до компонентной
    валидации, блокируя повторное сохранение того же имени."""
    from tests.conftest import mint_access_token

    token = mint_access_token(admin_user)
    created = _create_patient(client, token, "+998000000904")

    # 384 символа суммарно: фамилия 128 + пробел + имя 128 + пробел + отчество 126
    long_full_name = "Д" * 128 + " " + "И" * 128 + " " + "О" * 126
    assert len(long_full_name) == 384

    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={"full_name": long_full_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Не 422 «less than 384» и не 500 — компоненты в пределах varchar(128)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["last_name"] == "Д" * 128
    assert body["first_name"] == "И" * 128
    assert body["middle_name"] == "О" * 126

    db_patient = db.query(Patient).filter(Patient.id == created["id"]).first()
    assert db_patient is not None
    assert db_patient.last_name == "Д" * 128
    assert db_patient.first_name == "И" * 128
    assert db_patient.middle_name == "О" * 126


def test_update_patient_full_name_over_384_rejected_by_schema(
    client: TestClient, db: Session, admin_user: User, admin_password: str
):
    """Codex R3 #3090 (P2): 385+ символов отвергается схемой (422) так же,
    как и в PatientCreate — контракт создания и обновления симметричен."""
    from tests.conftest import mint_access_token

    token = mint_access_token(admin_user)
    created = _create_patient(client, token, "+998000000905")

    # 385 символов суммарно: 129 + пробел + 128 + пробел + 126
    too_long = "Д" * 129 + " " + "И" * 128 + " " + "О" * 126
    assert len(too_long) == 385
    response = client.put(
        f"/api/v1/patients/{created['id']}",
        json={"full_name": too_long},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, response.text
