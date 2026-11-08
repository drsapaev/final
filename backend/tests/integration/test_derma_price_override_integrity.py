"""DERMAPRICE-BE-001/002/003/004 (audit #3892, group 15) — price-override integrity.

Fail-first coverage for the dermatology doctor price-override workflow and
the SHARED dental approval implementation:

* **DERMAPRICE-BE-001 (P1/P2)** — ``POST /derma/price-override`` accepted a
  catalogue service NOT attached to the selected visit (no
  ``VisitService(visit_id, service_id)`` membership check); the shared
  approval then silently skipped the price update (``if visit_service:``)
  while still marking the override ``approved`` and returning
  ``success:true`` — a false-positive financial workflow. The dental
  sibling creation path has the same membership gap.
* **DERMAPRICE-BE-002 (P2)** — ``original_price`` records the CATALOGUE
  price, not the visit's actual ``VisitService.price``; the reviewer's
  ``price_difference`` is computed from the catalogue reference.
* **DERMAPRICE-BE-003 (P2)** — ``reason`` accepted empty and
  whitespace-only strings (``String(255)`` non-null does not mean
  non-empty).
* **DERMAPRICE-BE-004 (P2 conditional)** — ``GET /derma/price-overrides``
  is role-allowed for ``Admin`` (DERMA_ROLES) but unconditionally resolved
  the doctor profile: an Admin without a ``Doctor`` row got 404 instead of
  the authorized aggregated view.

Contract under test (from the audit):
  (a) create for a visit/NOT-attached eligible service → 409, no override row;
  (b) create for the attached service → 200 pending with the visit's actual
      price captured as ``visit_price_before`` (BE-002 additive field);
  (c) approval with the VisitService row removed → 409 fail-closed, status
      stays pending, no price change, no success payload;
  (d) valid approval → visit-service price updated exactly once;
  (e) empty / whitespace-only / over-length reason → 422;
  (f) Admin without a Doctor profile lists aggregated overrides (200);
  (g) dermatologist lists only own overrides;
  (h) the dental creation sibling enforces the same membership rule.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration

DERMA_POST = "/api/v1/derma/price-override"
DERMA_LIST = "/api/v1/derma/price-overrides"
DENTAL_POST = "/api/v1/dental/price-override"
DENTAL_APPROVE = "/api/v1/dental/price-override/{override_id}/approve"


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_user(db_session, *, role: str, label: str, password: str = "doctor123"):
    suffix = _suffix()
    user = User(
        username=f"dp_{label}_{suffix}",
        email=f"dp-{label}-{suffix}@test.local",
        full_name=f"DP {label}",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_doctor(db_session, user: User, *, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _create_patient(db_session) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name="Дина",
        last_name=f"Прайс-{suffix[:5]}",
        phone=f"+9989{suffix[:8]}",
        birth_date=date(1991, 2, 2),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_service(db_session, *, label: str, price: Decimal) -> Service:
    service = Service(
        code=f"DP{label[:4].upper()}",
        name=f"Derma price test {label}",
        price=price,
        allow_doctor_price_override=True,
        duration_minutes=30,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_visit_with_service(
    db_session, *, patient: Patient, doctor: Doctor, service: Service, price: Decimal
) -> tuple[Visit, VisitService]:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
        department="dermatology",
    )
    db_session.add(visit)
    db_session.flush()
    visit_service = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=1,
        price=price,
    )
    db_session.add(visit_service)
    db_session.commit()
    db_session.refresh(visit)
    db_session.refresh(visit_service)
    return visit, visit_service


def _login_headers(client, user: User, *, password: str = "doctor123"):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_headers(db_session, admin_user):
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _override_rows(db_session, visit_id: int):
    return (
        db_session.query(DoctorPriceOverride)
        .filter(DoctorPriceOverride.visit_id == visit_id)
        .all()
    )


def test_derma_price_override_rejects_service_not_attached_to_visit(
    client, db_session, admin_auth_headers
):
    """DERMAPRICE-BE-001 (a): eligible catalogue service NOT attached to the
    visit must be refused — the pending-review/approval workflow must never
    start from an unattached service."""
    derma_user = _create_user(db_session, role="derma", label="owner")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    headers = _login_headers(client, derma_user)

    patient = _create_patient(db_session)
    attached = _create_service(db_session, label="attached", price=Decimal("200000"))
    unattached = _create_service(
        db_session, label="unattached", price=Decimal("150000")
    )
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=attached,
        price=Decimal("200000"),
    )

    response = client.post(
        DERMA_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": unattached.id,
            "new_price": 180000,
            "reason": "Скидка постоянному пациенту",
        },
    )
    assert response.status_code == 409, response.text
    assert _override_rows(db_session, visit.id) == []


def test_derma_price_override_accepts_attached_service_and_captures_visit_price(
    client, db_session
):
    """DERMAPRICE-BE-001 (b) + BE-002: the attached service is accepted and
    the visit's ACTUAL price (VisitService.price — may differ from the
    catalogue after discounts) is captured as visit_price_before."""
    derma_user = _create_user(db_session, role="derma", label="cap")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    headers = _login_headers(client, derma_user)

    patient = _create_patient(db_session)
    service = _create_service(db_session, label="catalog", price=Decimal("200000"))
    # The visit was registered at a discounted price.
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("150000"),
    )

    response = client.post(
        DERMA_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 180000,
            "reason": "Скидка постоянному пациенту",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # BE-002: original_price keeps its catalogue-reference semantics...
    assert Decimal(body["original_price"]) == Decimal("200000")
    # ...and the truthful visit-level before-price is exposed additively.
    assert Decimal(body["visit_price_before"]) == Decimal("150000")

    rows = _override_rows(db_session, visit.id)
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].visit_price_before == Decimal("150000")
    assert visit_service.price == Decimal("150000")


def test_price_override_approval_fails_closed_when_visit_service_removed(
    client, db_session, admin_auth_headers
):
    """DERMAPRICE-BE-001 (c): approving an override whose VisitService row no
    longer exists must FAIL CLOSED (409, status stays pending) instead of
    marking approved with a silently skipped price update."""
    derma_user = _create_user(db_session, role="derma", label="orphan")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    headers = _login_headers(client, derma_user)

    patient = _create_patient(db_session)
    service = _create_service(db_session, label="orphansvc", price=Decimal("200000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("200000"),
    )

    create_response = client.post(
        DERMA_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 180000,
            "reason": "Скидка постоянному пациенту",
        },
    )
    assert create_response.status_code == 200, create_response.text
    override_id = create_response.json()["id"]

    # The service row is removed from the visit before the registrar acts.
    db_session.delete(visit_service)
    db_session.commit()

    approval = client.put(
        DENTAL_APPROVE.format(override_id=override_id),
        headers=admin_auth_headers,
        json={"action": "approve"},
    )
    assert approval.status_code == 409, approval.text

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.status == "pending", "fail-closed approval must not mutate status"


def test_price_override_approval_updates_visit_service_price_exactly_once(
    client, db_session, admin_auth_headers
):
    """DERMAPRICE-BE-001 (d) positive control: a valid approval updates the
    visit-service price exactly once and reports success."""
    derma_user = _create_user(db_session, role="derma", label="happy")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    headers = _login_headers(client, derma_user)

    patient = _create_patient(db_session)
    service = _create_service(db_session, label="happysvc", price=Decimal("200000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("200000"),
    )

    create_response = client.post(
        DERMA_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 180000,
            "reason": "Скидка постоянному пациенту",
        },
    )
    assert create_response.status_code == 200, create_response.text
    override_id = create_response.json()["id"]

    approval = client.put(
        DENTAL_APPROVE.format(override_id=override_id),
        headers=admin_auth_headers,
        json={"action": "approve"},
    )
    assert approval.status_code == 200, approval.text
    assert approval.json()["success"] is True

    db_session.expire_all()
    refreshed = db_session.get(VisitService, visit_service.id)
    assert refreshed.price == Decimal("180000")
    assert refreshed.custom_price == Decimal("180000")


@pytest.mark.parametrize(
    "bad_reason",
    ["", "   ", "\t\n ", "x" * 256],
    ids=["empty", "whitespace", "tabs-newlines", "over-255"],
)
def test_price_override_reason_must_be_meaningful(client, db_session, bad_reason):
    """DERMAPRICE-BE-003 (e): empty/whitespace-only/over-length reasons are
    rejected at request validation (422)."""
    derma_user = _create_user(db_session, role="derma", label="reason")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    headers = _login_headers(client, derma_user)

    patient = _create_patient(db_session)
    service = _create_service(db_session, label="reasonsvc", price=Decimal("200000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("200000"),
    )

    response = client.post(
        DERMA_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 180000,
            "reason": bad_reason,
        },
    )
    assert response.status_code == 422, response.text
    assert _override_rows(db_session, visit.id) == []


def test_admin_without_doctor_profile_lists_aggregated_derma_price_overrides(
    client, db_session, admin_user
):
    """DERMAPRICE-BE-004 (f): DERMA_ROLES includes Admin — an administrator
    without a linked Doctor row gets the authorized aggregated list (200),
    not a domain 404 from doctor resolution."""
    admin_headers = _admin_headers(db_session, admin_user)

    derma_user = _create_user(db_session, role="derma", label="listed")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    derma_headers = _login_headers(client, derma_user)

    patient = _create_patient(db_session)
    service = _create_service(db_session, label="listsvc", price=Decimal("200000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("200000"),
    )
    created = client.post(
        DERMA_POST,
        headers=derma_headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 180000,
            "reason": "Скидка постоянному пациенту",
        },
    )
    assert created.status_code == 200, created.text
    override_id = created.json()["id"]

    admin_list = client.get(DERMA_LIST, headers=admin_headers)
    assert admin_list.status_code == 200, admin_list.text
    listed_ids = {item["id"] for item in admin_list.json()}
    assert override_id in listed_ids, (
        "aggregated admin view must include the dermatologist's override"
    )

    # (g) the dermatologist still lists only their own overrides.
    derma_list = client.get(DERMA_LIST, headers=derma_headers)
    assert derma_list.status_code == 200, derma_list.text
    assert [item["id"] for item in derma_list.json()] == [override_id]


def test_dental_price_override_rejects_service_not_attached_to_visit(client, db_session):
    """DERMAPRICE-BE-001 (h) shared-policy: the dental creation sibling
    enforces the same visit-service membership rule (same DoctorPriceOverride
    workflow, same shared approval)."""
    dental_user = _create_user(db_session, role="dentist", label="dental")
    dental_doctor = _create_doctor(db_session, dental_user, specialty="dentistry")
    headers = _login_headers(client, dental_user)

    patient = _create_patient(db_session)
    attached = _create_service(db_session, label="datt", price=Decimal("300000"))
    unattached = _create_service(db_session, label="dunatt", price=Decimal("120000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=dental_doctor,
        service=attached,
        price=Decimal("300000"),
    )

    response = client.post(
        DENTAL_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": unattached.id,
            "new_price": 250000,
            "reason": "Лечение осложнено",
        },
    )
    assert response.status_code == 409, response.text
    assert _override_rows(db_session, visit.id) == []
