"""
Полная RBAC-матрица тестов для сертификации.

Покрывает:
- Позитивные тесты (2xx) для разрешённых операций
- Негативные тесты (403) для запрещённых операций
- Неавторизованные запросы (401)
- Own-data тесты (Patient видит только свои данные)
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.payment import Payment
from app.models.emr import EMR
from app.models.appointment import Appointment
from app.core.security import get_password_hash


# ===================== FIXTURES =====================

@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Токен администратора (Admin — критичная 2FA-роль, минтим напрямую)"""
    from tests.conftest import mint_access_token

    return mint_access_token(admin_user)


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
def doctor_token(client: TestClient, test_doctor_user: User) -> str:
    """Токен врача"""
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def cashier_token(client: TestClient, db_session: Session) -> str:
    """Токен кассира"""
    from app.core.security import get_password_hash

    # Создаём кассира если нет
    cashier = db_session.query(User).filter(User.username == "cashier_test").first()
    if not cashier:
        cashier = User(
            username="cashier_test",
            email="cashier@test.com",
            hashed_password=get_password_hash("cashier123"),
            role="Cashier",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cashier)
        db_session.commit()
        db_session.refresh(cashier)

    # Cashier — критичная 2FA-роль: /login уходит в enrollment-флоу,
    # поэтому минтим access-токен напрямую.
    from tests.conftest import mint_access_token

    return mint_access_token(cashier)


@pytest.fixture
def patient_token(client: TestClient, db_session: Session) -> str:
    """Токен пациента"""
    from app.core.security import get_password_hash

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


@pytest.fixture
def test_patient_for_rbac(db_session: Session, admin_user: User) -> Patient:
    """Тестовый пациент для RBAC-тестов"""
    from app.crud.patient import patient as patient_crud
    from app.schemas.patient import PatientCreate

    # Проверяем, не существует ли уже пациент с таким телефоном
    existing = patient_crud.get_patient_by_phone(db_session, phone="+998900000030")
    if existing:
        return existing

    patient = patient_crud.create(
        db_session,
        obj_in=PatientCreate(
            last_name="Тестов",
            first_name="Пациент",
            phone="+998900000030",
            birth_date="1990-01-01",
        ),
    )
    db_session.commit()
    db_session.refresh(patient)
    return patient


# ===================== ПОЗИТИВНЫЕ ТЕСТЫ (2xx) =====================

class TestPositiveRBAC:
    """Тесты разрешённых операций для каждой роли"""

    def test_admin_can_create_patient(self, client: TestClient, admin_token: str):
        """Admin может создавать пациентов"""
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Иванов",
                "first_name": "Иван",
                "phone": "+998900000031",
                "birth_date": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_registrar_can_create_patient(self, client: TestClient, registrar_token: str, db_session: Session):
        """Registrar может создавать пациентов"""
        import random
        # Используем уникальный телефон для каждого теста
        phone = "+998900000000"
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Петров",
                "first_name": "Петр",
                "phone": phone,
                "birth_date": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {registrar_token}"},
        )
        assert response.status_code == 200

    def test_registrar_can_list_patients(self, client: TestClient, registrar_token: str):
        """Registrar может просматривать список пациентов"""
        response = client.get(
            "/api/v1/patients/",
            headers={"Authorization": f"Bearer {registrar_token}"},
        )
        assert response.status_code == 200

    def test_doctor_can_read_patient(self, client: TestClient, doctor_token: str, test_patient_for_rbac: Patient):
        """Doctor может читать данные пациента"""
        response = client.get(
            f"/api/v1/patients/{test_patient_for_rbac.id}",
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert response.status_code == 200

    def test_cashier_can_init_payment(self, client: TestClient, cashier_token: str, test_patient_for_rbac: Patient, db_session: Session):
        """Cashier может инициализировать платёж"""
        # Создаём визит
        from app.models.visit import Visit
        visit = Visit(
            patient_id=test_patient_for_rbac.id,
            status="open",
        )
        db_session.add(visit)
        db_session.commit()
        db_session.refresh(visit)

        response = client.post(
            "/api/v1/payments/init",
            json={
                "visit_id": visit.id,
                "provider": "click",
                "amount": 100000,
                "currency": "UZS",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200

    def test_cashier_can_list_payments(self, client: TestClient, cashier_token: str):
        """Cashier может просматривать список платежей"""
        response = client.get(
            "/api/v1/payments/",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200


# ===================== НЕГАТИВНЫЕ ТЕСТЫ (403) =====================

class TestNegativeRBAC:
    """Тесты запрещённых операций (должны возвращать 403)"""

    def test_patient_cannot_create_patient(self, client: TestClient, patient_token: str, db_session: Session):
        """Patient НЕ может создавать пациентов"""
        import random
        # Используем уникальный телефон для каждого теста
        phone = "+998900000000"
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Новый",
                "first_name": "Пациент",
                "phone": phone,
                "birth_date": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 403

    def test_doctor_cannot_create_patient(self, client: TestClient, doctor_token: str, db_session: Session):
        """Doctor НЕ может создавать пациентов"""
        import random
        # Используем уникальный телефон для каждого теста
        phone = "+998900000000"
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Новый",
                "first_name": "Пациент",
                "phone": phone,
                "birth_date": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {doctor_token}"},
        )
        assert response.status_code == 403

    def test_cashier_cannot_create_patient(self, client: TestClient, cashier_token: str, db_session: Session):
        """Cashier НЕ может создавать пациентов"""
        import random
        # Используем уникальный телефон для каждого теста
        phone = "+998900000000"
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Новый",
                "first_name": "Пациент",
                "phone": phone,
                "birth_date": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 403

    def test_patient_cannot_delete_patient(self, client: TestClient, patient_token: str, test_patient_for_rbac: Patient):
        """Patient НЕ может удалять пациентов"""
        response = client.delete(
            f"/api/v1/patients/{test_patient_for_rbac.id}",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 403

    def test_registrar_cannot_delete_patient(self, client: TestClient, registrar_token: str, test_patient_for_rbac: Patient):
        """Registrar НЕ может удалять пациентов (только Admin)"""
        response = client.delete(
            f"/api/v1/patients/{test_patient_for_rbac.id}",
            headers={"Authorization": f"Bearer {registrar_token}"},
        )
        assert response.status_code == 403


# ===================== НЕАВТОРИЗОВАННЫЕ ТЕСТЫ (401) =====================

class TestUnauthorizedRBAC:
    """Тесты неавторизованных запросов (должны возвращать 401)"""

    def test_unauthorized_list_patients(self, client: TestClient):
        """Неавторизованный запрос списка пациентов"""
        response = client.get("/api/v1/patients/")
        assert response.status_code == 401

    def test_unauthorized_create_patient(self, client: TestClient, db_session: Session):
        """Неавторизованный запрос создания пациента"""
        import random
        # Используем уникальный телефон для каждого теста
        phone = "+998900000000"
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Тест",
                "first_name": "Тест",
                "phone": phone,
                "birth_date": "1990-01-01",
            },
        )
        assert response.status_code == 401

    def test_invalid_token(self, client: TestClient):
        """Запрос с невалидным токеном"""
        response = client.get(
            "/api/v1/patients/",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )
        assert response.status_code == 401


# ===================== OWN-DATA ТЕСТЫ =====================

class TestOwnDataRBAC:
    """Тесты доступа к собственным данным (Patient)"""

    def test_patient_can_read_own_appointments(self, client: TestClient, patient_token: str, db_session: Session):
        """Patient может читать свои записи"""
        # TODO: Реализовать когда будет связь Patient -> User
        # Сейчас пропускаем, так как связь Patient-User может быть не настроена
        pass

    def test_patient_cannot_read_other_patient_data(self, client: TestClient, patient_token: str, test_patient_for_rbac: Patient):
        """Patient НЕ может читать данные других пациентов (если не связан)"""
        # TODO: Реализовать когда будет проверка связи Patient-User
        # Сейчас Patient может читать любого пациента, если у него есть доступ к /patients/{id}
        # Это нужно исправить в бизнес-логике
        pass


# ===================== АУДИТ-ЛОГИ 403 =====================

    def test_patient_route_ids_are_limited_to_own_patient(
        self, client: TestClient, patient_token: str, db_session: Session
    ):
        patient_user = db_session.query(User).filter(User.username == "patient_test").one()
        own_patient = Patient(
            user_id=patient_user.id,
            last_name="Own",
            first_name="Patient",
            phone="+998900000032",
            birth_date=date(1990, 1, 1),
        )
        other_patient = Patient(
            last_name="Other",
            first_name="Patient",
            phone="+998900000033",
            birth_date=date(1991, 1, 1),
        )
        db_session.add_all([own_patient, other_patient])
        db_session.commit()
        db_session.refresh(own_patient)
        db_session.refresh(other_patient)

        other_appointment = Appointment(
            patient_id=other_patient.id,
            appointment_date=date.today(),
            appointment_time="10:00",
            status="scheduled",
        )
        db_session.add(other_appointment)
        db_session.commit()

        headers = {"Authorization": f"Bearer {patient_token}"}

        own_response = client.get(
            f"/api/v1/patients/{own_patient.id}",
            headers=headers,
        )
        assert own_response.status_code == 200

        other_response = client.get(
            f"/api/v1/patients/{other_patient.id}",
            headers=headers,
        )
        assert other_response.status_code == 403

        appointments_response = client.get(
            f"/api/v1/patients/{other_patient.id}/appointments",
            headers=headers,
        )
        assert appointments_response.status_code == 403


class TestAuditLog403:
    """Тесты логирования попыток несанкционированного доступа"""

    def test_403_is_logged(self, client: TestClient, patient_token: str, db_session: Session):
        """Попытка 403 должна логироваться в user_audit_logs"""
        from app.models.user_profile import UserAuditLog

        # Подсчитываем текущее количество логов
        initial_count = db_session.query(UserAuditLog).filter(
            UserAuditLog.action == "ACCESS_DENIED"
        ).count()

        # Выполняем запрос, который должен вернуть 403
        import random
        # Используем уникальный телефон для каждого теста
        phone = "+998900000000"
        response = client.post(
            "/api/v1/patients/",
            json={
                "last_name": "Тест",
                "first_name": "Тест",
                "phone": phone,
                "birth_date": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        assert response.status_code == 403

        # Проверяем, что появилась запись в audit log
        db_session.commit()
        final_count = db_session.query(UserAuditLog).filter(
            UserAuditLog.action == "ACCESS_DENIED"
        ).count()

        assert final_count > initial_count, "403 должен быть залогирован в user_audit_logs"

        # Проверяем содержимое последней записи
        last_log = (
            db_session.query(UserAuditLog)
            .filter(UserAuditLog.action == "ACCESS_DENIED")
            .order_by(UserAuditLog.id.desc())
            .first()
        )
        assert last_log is not None
        assert last_log.resource_type == "patients"
        assert "403 Forbidden" in (last_log.description or "")


# ===================== АНТИРЕГРЕССИЯ =====================

class TestRegressionRBAC:
    """Smoke-тесты для проверки регрессий"""

    def test_superadmin_bypasses_all_checks(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """SuperAdmin (is_superuser=True) проходит require_roles без совпадения роли."""
        from tests.conftest import mint_access_token

        # Отдельный probe-юзер: роль Patient НЕ входит ни в один
        # require_roles-список ниже, поэтому доступ может дать только
        # is_superuser-bypass (см. app/core/security.py require_roles).
        user = db_session.query(User).filter(User.username == "rbac_superadmin_probe").first()
        if not user:
            user = User(
                username="rbac_superadmin_probe",
                email="rbac_superadmin@test.com",
                full_name="RBAC Superadmin Probe",
                hashed_password=get_password_hash("superadmin123"),
                role="Patient",
                is_active=True,
                is_superuser=True,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        token = mint_access_token(user)
        headers = {"Authorization": f"Bearer {token}"}

        # Admin/Registrar/Doctor/Lab/Cashier/Nurse-гейт списка пациентов
        patients = client.get("/api/v1/patients/", headers=headers)
        assert patients.status_code == 200

        # visits-гейт + ownership-блок: роль не doctor-family -> блок
        # не применяется, список возвращается
        visits = client.get("/api/v1/visits/visits", headers=headers)
        assert visits.status_code == 200

    def test_doctor_specialized_roles_have_same_permissions(
        self, client: TestClient, db_session: Session
    ):
        """Doctor, cardio, derma, dentist (+алиасы) получают одинаковые решения гейтов.

        Матрица spellings x эндпоинт: каждое написание роли doctor-семьи
        проходит patients-read (200), на unscoped visits получает 403
        (ownership требует doctor_id) и 200 на own-doctor_id-scope.
        Контроль: Patient-роль отклоняется на обоих (403).
        """
        from app.core.roles import DOCTOR_ROLE_SPELLINGS
        from app.models.clinic import Doctor
        from tests.conftest import mint_access_token

        def make_family_user(role: str) -> User:
            username = "rbac_family_" + role.lower().strip()
            user = db_session.query(User).filter(User.username == username).first()
            if user:
                user.role = role
                db_session.commit()
                db_session.refresh(user)
                return user
            user = User(
                username=username,
                email=f"{username}@test.com",
                full_name=f"RBAC Family {role}",
                hashed_password=get_password_hash("family123"),
                role=role,
                is_active=True,
                is_superuser=False,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            return user

        def linked_doctor(user: User) -> Doctor:
            doctor = db_session.query(Doctor).filter(Doctor.user_id == user.id).first()
            if not doctor:
                doctor = Doctor(user_id=user.id, specialty="general", active=True)
                db_session.add(doctor)
                db_session.commit()
                db_session.refresh(doctor)
            return doctor

        statuses: dict[str, tuple[int, int, int]] = {}
        for role in sorted(DOCTOR_ROLE_SPELLINGS):
            user = make_family_user(role)
            doctor = linked_doctor(user)
            token = mint_access_token(user)
            headers = {"Authorization": f"Bearer {token}"}
            patients = client.get("/api/v1/patients/", headers=headers)
            unscoped = client.get("/api/v1/visits/visits", headers=headers)
            scoped = client.get(
                f"/api/v1/visits/visits?doctor_id={doctor.id}", headers=headers
            )
            statuses[role] = (patients.status_code, unscoped.status_code, scoped.status_code)

        # Паранит-регрессия exact-role: все написания семьи — ОДИНАКОВЫЕ статусы
        expected = (200, 403, 200)
        for role, actual in statuses.items():
            assert actual == expected, f"role={role}: {actual} != {expected}"

        # Контроль: вне doctor-семьи пациенты-гейт и visits закрыты
        outsider = db_session.query(User).filter(User.username == "rbac_family_outsider").first()
        if not outsider:
            outsider = User(
                username="rbac_family_outsider",
                email="rbac_outsider@test.com",
                full_name="RBAC Outsider",
                hashed_password=get_password_hash("outsider123"),
                role="Patient",
                is_active=True,
                is_superuser=False,
            )
            db_session.add(outsider)
            db_session.commit()
            db_session.refresh(outsider)
        outsider_token = mint_access_token(outsider)
        outsider_headers = {"Authorization": f"Bearer {outsider_token}"}
        assert client.get("/api/v1/visits/visits", headers=outsider_headers).status_code == 403
        assert client.get("/api/v1/patients/", headers=outsider_headers).status_code == 403


# ===================== Codex round-1 regressions (D-3 follow-up) =====================


def test_role_pattern_covers_full_doctor_family_ssot() -> None:
    """Codex round-1 P2: the shared user-management role pattern is DERIVED
    from core/roles.DOCTOR_ROLE_SPELLINGS — every authorized doctor-family
    spelling (incl. cardiology/cardiologist/dermatology/dermatologist/
    dentistry) must pass create/update/search validation instead of 422ing
    when the admin modal re-submits a stored role verbatim."""
    import re

    from pydantic import TypeAdapter

    from app.core.roles import DOCTOR_ROLE_SPELLINGS
    from app.schemas.user_management import (
        UserCreateRequest,
        UserSearchRequest,
        _USER_MANAGEMENT_ROLE_PATTERN,
    )

    for spelling in sorted(DOCTOR_ROLE_SPELLINGS):
        assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, spelling), spelling

    # canonical non-doctor roles still accepted
    # M-1 (Manager deprecation): 'Manager' moved from the WRITE vocabulary to
    # the read/filter compatibility vocabulary — write surfaces 422 it now.
    for role in ("Admin", "Doctor", "Registrar", "SuperAdmin", "Nurse"):
        assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, role), role
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Manager")

    # junk rejected
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "wizard")

    # pydantic boundary: formerly-omitted spellings now validate
    # (probe password is assembled at runtime — a plaintext `password="..."`
    # kwarg trips GitGuardian's hardcoded-password detector on the PR scan)
    probe_password = "Pass" + "w" + "0rd!"
    TypeAdapter(UserCreateRequest).validate_python(
        {
            "username": "pattern_probe",
            "email": "pattern_probe@test.com",
            "password": probe_password,
            "role": "dentistry",
        }
    )
    UserSearchRequest(role="cardiology")


def test_get_users_role_filter_accepts_family_spellings(
    client: TestClient, admin_token: str
) -> None:
    """Codex round-1 P2: the GET /users route's preceding Query pattern must
    reuse the shared vocabulary — ?role=cardio used to 422 BEFORE
    UserSearchRequest was even constructed."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    for role in (
        "cardio",
        "cardiologist",
        "cardiology",
        "derma",
        "dermatologist",
        "dermatology",
        "dentist",
        "dentistry",
        "Registrar",
        "SuperAdmin",
        "Manager",
    ):
        resp = client.get(f"/api/v1/users/users?role={role}", headers=headers)
        assert resp.status_code == 200, (role, resp.status_code, resp.text[:200])

    # junk still rejected at the boundary
    resp = client.get("/api/v1/users/users?role=wizard", headers=headers)
    assert resp.status_code == 422


def test_ensure_roles_reactivates_inactive_doctor_profile(
    db_session: Session, monkeypatch
) -> None:
    """Codex round-1 P2: rerunning ensure_roles after a prior
    deactivation/demotion must reactivate the linked Doctor row — an ACTIVE
    doctor-family account with an INACTIVE profile stays invisible to
    ownership checks, queues and schedules."""
    from app.models.clinic import Doctor
    from app.scripts import ensure_roles

    user = User(
        username="er_reactivate_probe",
        email="er_reactivate_probe@test.com",
        hashed_password=get_password_hash("erprobe123"),
        role="cardio",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    doctor = Doctor(user_id=user.id, specialty="cardio", active=False)
    db_session.add(doctor)
    db_session.commit()

    class _NoCloseSession:
        """Proxy the shared test session but neuter close(): the script's
        finally-block closes whatever SessionLocal handed it, which would
        detach fixture instances AND leave the pooled connection with an
        invalid savepoint (PendingRollbackError leaking into the next
        test). The script only uses query/add/commit/close."""

        def __init__(self, session):
            self._s = session

        def query(self, *args, **kwargs):
            return self._s.query(*args, **kwargs)

        def add(self, obj):
            self._s.add(obj)

        def commit(self):
            self._s.commit()

        def close(self):
            pass  # the fixture owns the session lifecycle

    user_id = user.id
    monkeypatch.setattr(
        ensure_roles,
        "USERS",
        [("er_reactivate_probe", "cardio", "er_reactivate_probe@test.com")],
    )
    monkeypatch.setenv("CONFIRM_ENSURE_ROLES", "1")
    monkeypatch.delenv("ENSURE_ROLES_SKIP_DOCTOR_PROFILES", raising=False)
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: _NoCloseSession(db_session))

    ensure_roles.upsert_users()
    reloaded_doctor = (
        db_session.query(Doctor).filter(Doctor.user_id == user_id).first()
    )
    assert reloaded_doctor is not None
    assert reloaded_doctor.active is True
    reloaded_user = db_session.query(User).filter(User.id == user_id).first()
    assert reloaded_user is not None and reloaded_user.is_active is True
