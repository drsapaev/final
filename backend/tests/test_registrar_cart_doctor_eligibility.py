"""
RQ-05.a: серверная валидация допустимости врача при сохранении корзины.

E-023 трассировка: флаг requires_doctor на booking-пути не проверялся НИГДЕ —
POST /registrar/cart сохранял визит с requires_doctor=true услугой:
  - вообще без doctor_id (DTO делает врача опциональным «для лабораторных»);
  - с неактивным врачом;
  - с врачом чужой специальности (_department_key услуги игнорировался).

Гейт (_assert_cart_doctor_eligibility) стоит ДО первой записи и до prelock
advisory-замков: отклонённая корзина не оставляет частичного состояния.
Семантика «свой/чужой» зеркалирует фронтовый filterDoctorsForService
(W2-PR2): SSOT-таблица DOCTOR_QUEUE_SPECIALTY_VARIANTS, реверсивный поиск
канона (department_key "dental" → канон "dentistry"), неизвестные пары —
точное совпадение, незавершённый профиль врача отклоняется.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from tests.conftest import mint_access_token

pytestmark = [pytest.mark.integration]


def _cart_payload(*, patient_id: int, visits: list[dict]) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": visits,
    }


def _visit(service_id: int, *, doctor_id: int | None = None) -> dict:
    return {
        "doctor_id": doctor_id,
        "visit_date": date.today().isoformat(),
        "department": "general",
        "services": [{"service_id": service_id, "quantity": 1}],
    }


def _auth_headers(admin_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _counts(db: Session, patient_id: int) -> tuple[int, int, int]:
    visits = db.query(Visit).filter(Visit.patient_id == patient_id).count()
    invoices = (
        db.query(PaymentInvoice).filter(PaymentInvoice.patient_id == patient_id).count()
    )
    invoice_visits = (
        db.query(PaymentInvoiceVisit)
        .join(PaymentInvoice, PaymentInvoice.id == PaymentInvoiceVisit.invoice_id)
        .filter(PaymentInvoice.patient_id == patient_id)
        .count()
    )
    return visits, invoices, invoice_visits


def _make_service(
    db_session: Session,
    *,
    code: str,
    name: str,
    requires_doctor: bool = True,
    department_key: str | None = None,
) -> Service:
    service = Service(
        code=code,
        name=name,
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=requires_doctor,
        department_key=department_key,
        queue_tag=(department_key or code.lower()) if requires_doctor else None,
        is_consultation=requires_doctor,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _make_doctor(db_session: Session, *, specialty: str, active: bool = True) -> Doctor:
    user = User(
        username=f"rq05_doctor_{uuid4().hex[:12]}",
        full_name="Тестовый Врач",
        hashed_password="unused-test-hash",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=active,
        cabinet="101",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


# ── отклонения ────────────────────────────────────────────────────────────


def test_requires_doctor_service_without_doctor_rejected(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """requires_doctor=true без doctor_id → 400, состояние не меняется."""
    service = _make_service(
        db_session, code="RQ05A-NODOC", name="Консультация без врача"
    )
    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=None)],
        ),
    )

    assert response.status_code == 400, response.text
    assert "требует выбора врача" in response.json()["detail"]
    assert _counts(db_session, test_patient.id) == before


def test_requires_doctor_service_with_inactive_doctor_rejected(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """requires_doctor=true + неактивный врач → 400, состояние не меняется."""
    service = _make_service(db_session, code="RQ05A-INACT", name="Неактивный врач")
    doctor = _make_doctor(db_session, specialty="cardiology", active=False)
    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=doctor.id)],
        ),
    )

    assert response.status_code == 400, response.text
    assert "неактивен" in response.json()["detail"]
    assert _counts(db_session, test_patient.id) == before


def test_requires_doctor_service_with_missing_doctor_rejected(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """requires_doctor=true + несуществующий врач → 404 (а не 500 FK)."""
    service = _make_service(db_session, code="RQ05A-NOEXIST", name="Нет врача")
    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=999999)],
        ),
    )

    assert response.status_code == 404, response.text
    assert "не найден" in response.json()["detail"]
    assert _counts(db_session, test_patient.id) == before


def test_requires_doctor_service_specialty_mismatch_rejected(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Известный department_key + врач чужой специальности → 400."""
    service = _make_service(
        db_session,
        code="RQ05A-MISMATCH",
        name="Кардио-консультация",
        department_key="cardio",
    )
    dentist = _make_doctor(db_session, specialty="dentistry")
    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=dentist.id)],
        ),
    )

    assert response.status_code == 400, response.text
    assert "не подходит" in response.json()["detail"]
    assert _counts(db_session, test_patient.id) == before


def test_rejection_is_atomic_no_partial_visits(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Корзина из двух визитов: отказ второго не оставляет первый (rollback)."""
    lab = _make_service(
        db_session,
        code="RQ05A-LAB",
        name="Лаборатория",
        requires_doctor=False,
    )
    consult = _make_service(db_session, code="RQ05A-CONS", name="Консультация")
    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(lab.id, doctor_id=None),
                _visit(consult.id, doctor_id=None),
            ],
        ),
    )

    assert response.status_code == 400, response.text
    assert _counts(db_session, test_patient.id) == before


# ── допустимые пути (контролы) ────────────────────────────────────────────


def test_requires_doctor_service_with_matching_specialty_ok(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Контрол: requires_doctor=true + активный врач своей специальности → 200."""
    service = _make_service(
        db_session,
        code="RQ05A-OK",
        name="Кардио-консультация ок",
        department_key="cardio",
    )
    cardiologist = _make_doctor(db_session, specialty="Cardiology")

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=cardiologist.id)],
        ),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["visit_ids"]) == 1
    visit = db_session.query(Visit).get(payload["visit_ids"][0])
    assert visit.doctor_id == cardiologist.id


def test_department_key_alias_dental_dentistry_ok(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Реверсивный алиас W2-PR2: department_key "dental" ↔ specialty "dentistry"."""
    service = _make_service(
        db_session,
        code="RQ05A-ALIAS",
        name="Стоматология",
        department_key="dental",
    )
    dentist = _make_doctor(db_session, specialty="dentistry")

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=dentist.id)],
        ),
    )

    assert response.status_code == 200, response.text


def test_unknown_department_key_exact_match_semantics(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Пара вне таблицы: точное совпадение проходит, несовпадение отклоняется."""
    neuro_service = _make_service(
        db_session,
        code="RQ05A-NEURO",
        name="Неврология",
        department_key="neurology",
    )
    neurologist = _make_doctor(db_session, specialty="neurology")
    cardiologist = _make_doctor(db_session, specialty="cardiology")

    ok = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(neuro_service.id, doctor_id=neurologist.id)],
        ),
    )
    assert ok.status_code == 200, ok.text

    mismatch = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(neuro_service.id, doctor_id=cardiologist.id)],
        ),
    )
    assert mismatch.status_code == 400, mismatch.text


def test_service_without_doctor_requirement_still_allows_no_doctor(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Регрессионный.guard: лабораторная услуга (requires_doctor=false) без врача — как раньше."""
    lab = _make_service(
        db_session,
        code="RQ05A-FREE",
        name="Анализ",
        requires_doctor=False,
    )
    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(lab.id, doctor_id=None)],
        ),
    )

    assert response.status_code == 200, response.text
    visits, _, _ = _counts(db_session, test_patient.id)
    assert visits == before[0] + 1


def test_empty_doctor_specialty_is_ineligible_for_booking(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """An incomplete doctor profile must not bypass the booking gate."""
    service = _make_service(
        db_session,
        code="RQ05A-EMPTYSPEC",
        name="Спец без специальности",
        department_key="cardio",
    )
    doctor = _make_doctor(db_session, specialty="")

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id, doctor_id=doctor.id)],
        ),
    )

    assert response.status_code == 409, response.text
    assert "Профиль врача" in response.json()["detail"]
