"""REGPRICE-BE-001/002/003/004/005 (audit #3892, group 16) — price-override
approval integrity across the two independently exposed routes.

Fail-first coverage for the registrar/dental price-override approval split:

* **REGPRICE-BE-001 (P1)** — the registrar ``POST
  /registrar/price-override/approve`` route wrote the
  ``Visit.doctor_price_override`` JSON mirror but NOT the chargeable
  ``VisitService.price`` (billing sums ``VisitService.price * qty``), while
  the dental ``PUT /dental/price-override/{id}/approve`` route did the
  opposite. Both routes now delegate to ONE canonical approval service and
  produce the IDENTICAL outcome (status + chargeable rows + JSON mirror).
* **REGPRICE-BE-002 (P1 candidate)** — both routes read the override with an
  unlocked ``.first()``; two approvers could both see ``pending`` and commit
  conflicting terminal decisions. The canonical service locks the Visit row
  then the override row (``SELECT ... FOR UPDATE``, the same order payment
  flows use) and the post-lock non-pending check turns the loser into 409.
* **REGPRICE-BE-003 (P1/P2)** — two sequential pending overrides for the
  same visit/service could be approved in reverse order (each validated
  against the SAME stale ``visit_price_before``). Creation now refuses a
  second pending intent (409) and approval refuses a stale intent (409).
* **REGPRICE-BE-004 (P2)** — the registrar queue returned a bare 100-row
  newest-first array with no total/offset: request #101 stayed unreachable.
  The list is now offset-paginated over a deterministic
  ``(created_at DESC, id DESC)`` order with the full filtered total in
  ``X-Total-Count``; the dental pending endpoint gained the same offset.
* **REGPRICE-BE-005 (P2)** — the registrar rejection accepted absent/blank
  reasons even though the dental route and the frontend modal require one.
  The canonical service enforces a non-blank trimmed reason (400) for both
  routes with no status transition.

Contract under test:
  (a) registrar approve → VisitService.price AND JSON mirror updated,
      billing calculation reflects the approved price;
  (b) dental approve → the SAME canonical outcome (both writes present);
  (c) already-processed override (any route) → 409, no contradictory state;
  (d) second pending creation for the same visit/service → 409 (derma and
      dental creation paths);
  (e) approval with a stale captured before-price → 409, status stays
      pending, price untouched;
  (f) registrar queue pagination: 101 pending rows, page 1 = 100 newest,
      page 2 = the oldest, deterministic order, X-Total-Count exposed;
  (g) dental pending endpoint honors offset;
  (h) reject without/with blank reason → 400 and no transition (registrar
      AND dental), justified refusal is persisted verbatim;
  (i) registrar list exposes visit_price_before / visit_price_difference.
"""

from datetime import UTC, date, datetime, timedelta
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
from app.services.billing_service_pkg import BillingService
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration

DERMA_POST = "/api/v1/derma/price-override"
DENTAL_POST = "/api/v1/dental/price-override"
DENTAL_APPROVE = "/api/v1/dental/price-override/{override_id}/approve"
DENTAL_PENDING = "/api/v1/dental/price-overrides/pending"
REGISTRAR_APPROVE = "/api/v1/registrar/price-override/approve"
REGISTRAR_LIST = "/api/v1/registrar/price-overrides"


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_user(db_session, *, role: str, label: str, password: str = "doctor123"):
    suffix = _suffix()
    user = User(
        username=f"rp_{label}_{suffix}",
        email=f"rp-{label}-{suffix}@test.local",
        full_name=f"RP {label}",
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
        first_name="Прайс",
        last_name=f"Рег-{suffix[:5]}",
        phone=f"+9989{suffix[:8]}",
        birth_date=date(1990, 5, 5),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_service(db_session, *, label: str, price: Decimal) -> Service:
    service = Service(
        code=f"RP{label[:4].upper()}",
        name=f"Regprice test {label}",
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


def _create_pending_via_derma(client, db_session, *, doctor_user, visit, service, new_price):
    """Create a pending override through the derma doctor route."""
    headers = _login_headers(client, doctor_user)
    response = client.post(
        DERMA_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": new_price,
            "reason": "Скидка постоянному пациенту",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _override_row(db_session, override_id: int) -> DoctorPriceOverride:
    db_session.expire_all()
    return db_session.get(DoctorPriceOverride, override_id)


# ---------------------------------------------------------------------------
# REGPRICE-BE-001: both routes converge on the SAME canonical outcome
# ---------------------------------------------------------------------------


def test_registrar_approve_updates_chargeable_price_and_json_mirror(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-001: the registrar route — the one the registrar UI
    actually calls — must update the chargeable ``VisitService.price``
    (billing SSOT) AND the ``Visit.doctor_price_override`` JSON mirror in
    the same transaction. Previously it wrote ONLY the JSON, so the invoice
    kept the old price after an approved change."""
    derma_user = _create_user(db_session, role="derma", label="reg1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="regsvc", price=Decimal("150000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("150000"),
    )

    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=180000,
    )

    response = client.post(
        REGISTRAR_APPROVE,
        headers=admin_auth_headers,
        json={"override_id": override_id, "action": "approve"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["new_status"] == "approved"

    db_session.expire_all()
    refreshed_visit_service = db_session.get(VisitService, visit_service.id)
    assert refreshed_visit_service.price == Decimal("180000"), (
        "registrar approval must update the chargeable VisitService.price"
    )
    # DOCVISIT-BE-001 (group 17): VisitService has no custom_price column —
    # the canonical service must not leave an ephemeral attribute on the
    # shared-session instance. The persisted price above is the whole truth.
    assert not hasattr(refreshed_visit_service, "custom_price"), (
        "custom_price is not a mapped field; an ephemeral attribute here means "
        "a non-persisted write leaked through the identity map"
    )

    refreshed_visit = db_session.get(Visit, visit.id)
    mirror = (refreshed_visit.doctor_price_override or {}).get(str(service.id))
    assert mirror is not None, "registrar approval must keep the JSON mirror"
    assert Decimal(str(mirror["new_price"])) == Decimal("180000")

    # The billing calculation (which sums VisitService.price * qty) must
    # reflect the approved price.
    total = BillingService(db_session).calculate_total(visit_id=visit.id)
    assert Decimal(str(total["subtotal"])) == Decimal("180000")


def test_dental_approve_updates_json_mirror_and_chargeable_price(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-001: the dental route must produce the SAME canonical
    outcome — previously it updated VisitService.price but left the
    Visit.doctor_price_override JSON mirror stale."""
    derma_user = _create_user(db_session, role="derma", label="dent1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="dentsvc", price=Decimal("120000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("120000"),
    )

    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=145000,
    )

    response = client.put(
        DENTAL_APPROVE.format(override_id=override_id),
        headers=admin_auth_headers,
        json={"action": "approve"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True

    db_session.expire_all()
    refreshed_visit_service = db_session.get(VisitService, visit_service.id)
    assert refreshed_visit_service.price == Decimal("145000")
    # DOCVISIT-BE-001 (group 17): no ephemeral custom_price may survive the
    # canonical approval — only the persisted price exists.
    assert not hasattr(refreshed_visit_service, "custom_price")

    refreshed_visit = db_session.get(Visit, visit.id)
    mirror = (refreshed_visit.doctor_price_override or {}).get(str(service.id))
    assert mirror is not None, (
        "dental approval must ALSO update the Visit JSON mirror (canonical outcome)"
    )
    assert Decimal(str(mirror["new_price"])) == Decimal("145000")

    total = BillingService(db_session).calculate_total(visit_id=visit.id)
    assert Decimal(str(total["subtotal"])) == Decimal("145000")


# ---------------------------------------------------------------------------
# REGPRICE-BE-002: a processed override can never be processed again
# ---------------------------------------------------------------------------


def test_second_decision_on_processed_override_returns_409(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-002: once a terminal decision is committed, ANY route
    must refuse a second decision with 409 — the loser of a concurrent race
    must never report success nor mutate the price/audit state."""
    derma_user = _create_user(db_session, role="derma", label="race1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="racesvc", price=Decimal("90000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("90000"),
    )

    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=110000,
    )

    first = client.put(
        DENTAL_APPROVE.format(override_id=override_id),
        headers=admin_auth_headers,
        json={"action": "approve"},
    )
    assert first.status_code == 200, first.text

    # The other route arrives after the decision — it must conflict, not
    # succeed, and must not touch the price again.
    second = client.post(
        REGISTRAR_APPROVE,
        headers=admin_auth_headers,
        json={"override_id": override_id, "action": "approve"},
    )
    assert second.status_code == 409, second.text

    db_session.expire_all()
    refreshed_visit_service = db_session.get(VisitService, visit_service.id)
    assert refreshed_visit_service.price == Decimal("110000")
    assert db_session.get(DoctorPriceOverride, override_id).status == "approved"


# ---------------------------------------------------------------------------
# REGPRICE-BE-003: no duplicate pending intent, no stale approval
# ---------------------------------------------------------------------------


def test_second_pending_creation_for_same_visit_service_is_refused(
    client, db_session, admin_user
):
    """REGPRICE-BE-003: a second pending override for the same visit/service
    must be refused at CREATION time (derma AND dental paths) — two
    sequential pending intents can be approved in reverse order."""
    derma_user = _create_user(db_session, role="derma", label="dup1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="dupsvc", price=Decimal("100000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("100000"),
    )

    first_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=120000,
    )
    derma_headers = _login_headers(client, derma_user)

    second = client.post(
        DERMA_POST,
        headers=derma_headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 130000,
            "reason": "Вторая заявка на ту же услугу",
        },
    )
    assert second.status_code == 409, second.text

    # The dental creation sibling feeds the SAME workflow — same rule.
    dental_user = _create_user(db_session, role="doctor", label="dup2")
    dental_doctor = _create_doctor(db_session, dental_user, specialty="stomatology")
    # Re-own the visit for the dental doctor path (the visit must belong to
    # the requesting doctor).
    visit.doctor_id = dental_doctor.id
    db_session.commit()

    dental_headers = _login_headers(client, dental_user)
    dental_second = client.post(
        DENTAL_POST,
        headers=dental_headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 130000,
            "reason": "Стоматологическая заявка на ту же услугу",
            "treatment_completed": True,
        },
    )
    assert dental_second.status_code == 409, dental_second.text

    db_session.expire_all()
    pending = (
        db_session.query(DoctorPriceOverride)
        .filter(
            DoctorPriceOverride.visit_id == visit.id,
            DoctorPriceOverride.status == "pending",
        )
        .all()
    )
    assert len(pending) == 1, "exactly one pending intent per visit/service"
    assert pending[0].id == first_id


def test_stale_override_is_refused_at_approval_time(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-003: if the visit price changed after the request was
    created (e.g. another change was applied meanwhile), approving the stale
    intent must fail with 409 — the doctor re-creates the request with a
    fresh snapshot instead of silently overwriting the newer price."""
    derma_user = _create_user(db_session, role="derma", label="stale1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="stalesvc", price=Decimal("100000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("100000"),
    )

    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=120000,
    )

    # The chargeable price moved after the request was created (an earlier
    # legacy override was approved, a manual correction, etc.).
    visit_service.price = Decimal("110000")
    db_session.commit()

    response = client.put(
        DENTAL_APPROVE.format(override_id=override_id),
        headers=admin_auth_headers,
        json={"action": "approve"},
    )
    assert response.status_code == 409, response.text

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.status == "pending", "stale approval must not transition status"
    refreshed_visit_service = db_session.get(VisitService, visit_service.id)
    assert refreshed_visit_service.price == Decimal("110000"), (
        "stale approval must not overwrite the current price"
    )
    mirror = (db_session.get(Visit, visit.id).doctor_price_override or {}).get(
        str(service.id)
    )
    assert mirror is None, "stale approval must not write the JSON mirror"


def test_legacy_null_before_price_remains_approvable(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-003: overrides created before the visit_price_before
    snapshot existed carry NULL — their staleness is not verifiable, so the
    approval proceeds (documented policy) and the canonical outcome is
    still applied."""
    derma_user = _create_user(db_session, role="derma", label="legacy1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="legacysvc", price=Decimal("80000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("80000"),
    )
    legacy = DoctorPriceOverride(
        visit_id=visit.id,
        doctor_id=derma_doctor.id,
        service_id=service.id,
        original_price=Decimal("80000"),
        new_price=Decimal("95000"),
        reason="Историческая заявка",
        status="pending",
        visit_price_before=None,
    )
    db_session.add(legacy)
    db_session.commit()
    db_session.refresh(legacy)

    response = client.put(
        DENTAL_APPROVE.format(override_id=legacy.id),
        headers=admin_auth_headers,
        json={"action": "approve"},
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    refreshed = db_session.get(VisitService, visit_service.id)
    assert refreshed.price == Decimal("95000")


# ---------------------------------------------------------------------------
# REGPRICE-BE-004: paginated queue with deterministic order and full total
# ---------------------------------------------------------------------------


def test_registrar_queue_is_fully_paginable_beyond_100(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-004: with 101 pending requests the oldest was absent from
    the bare newest-first 100-row array and unreachable. The endpoint now
    exposes the full total via X-Total-Count and honors offset pagination
    over a deterministic (created_at DESC, id DESC) order."""
    derma_user = _create_user(db_session, role="derma", label="page1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="pagesvc", price=Decimal("50000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("50000"),
    )

    base = datetime.now(UTC) - timedelta(hours=48)
    total_expected = 101
    rows = []
    for index in range(total_expected):
        rows.append(
            DoctorPriceOverride(
                visit_id=visit.id,
                doctor_id=derma_doctor.id,
                service_id=service.id,
                original_price=Decimal("50000"),
                new_price=Decimal("55000"),
                reason=f"Пагинация #{index}",
                status="pending",
                visit_price_before=Decimal("50000"),
                created_at=base + timedelta(minutes=index),
            )
        )
    db_session.add_all(rows)
    db_session.commit()

    page1 = client.get(
        REGISTRAR_LIST,
        headers=admin_auth_headers,
        params={"status_filter": "pending", "limit": 100, "offset": 0},
    )
    assert page1.status_code == 200, page1.text
    assert page1.headers.get("X-Total-Count") == str(total_expected), (
        "the FULL filtered total must be exposed"
    )
    items1 = page1.json()
    assert len(items1) == 100

    page2 = client.get(
        REGISTRAR_LIST,
        headers=admin_auth_headers,
        params={"status_filter": "pending", "limit": 100, "offset": 100},
    )
    assert page2.status_code == 200, page2.text
    items2 = page2.json()
    assert len(items2) == total_expected - 100, "the oldest page must be reachable"
    oldest_id = rows[0].id
    assert int(items2[0]["id"]) == oldest_id, (
        "oldest pending request must be retrievable via offset pagination"
    )
    assert int(items1[0]["id"]) == rows[-1].id, (
        "newest-first deterministic order (created_at DESC, id DESC)"
    )


def test_dental_pending_endpoint_honors_offset(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-004: the alternative dental pending list gained the same
    offset pagination and a truthful full total_count."""
    derma_user = _create_user(db_session, role="derma", label="page2")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="dentsvc2", price=Decimal("60000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("60000"),
    )

    base = datetime.now(UTC) - timedelta(hours=24)
    rows = []
    for index in range(7):
        rows.append(
            DoctorPriceOverride(
                visit_id=visit.id,
                doctor_id=derma_doctor.id,
                service_id=service.id,
                original_price=Decimal("60000"),
                new_price=Decimal("65000"),
                reason=f"Dental pending #{index}",
                status="pending",
                visit_price_before=Decimal("60000"),
                created_at=base + timedelta(minutes=index),
            )
        )
    db_session.add_all(rows)
    db_session.commit()

    page1 = client.get(DENTAL_PENDING, headers=admin_auth_headers, params={"limit": 5})
    assert page1.status_code == 200, page1.text
    body1 = page1.json()
    assert body1["total_count"] == 7, "total_count is the FULL pending total"
    assert len(body1["overrides"]) == 5
    assert body1["offset"] == 0

    page2 = client.get(
        DENTAL_PENDING, headers=admin_auth_headers, params={"limit": 5, "offset": 5}
    )
    assert page2.status_code == 200, page2.text
    body2 = page2.json()
    assert len(body2["overrides"]) == 2
    assert body2["offset"] == 5

    ids1 = {row["id"] for row in body1["overrides"]}
    ids2 = {row["id"] for row in body2["overrides"]}
    assert ids1.isdisjoint(ids2), "pages must not overlap"
    assert ids1 | ids2 == {row.id for row in rows}


# ---------------------------------------------------------------------------
# REGPRICE-BE-005: rejection reason is mandatory on BOTH routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_reason", [None, "", "   ", "\t\n "])
def test_registrar_reject_requires_non_blank_reason(
    client, db_session, admin_user, admin_auth_headers, bad_reason
):
    """REGPRICE-BE-005: the registrar route must refuse absent/empty/
    whitespace-only rejection reasons with 400 and leave the override
    pending — a refusal without a justification must not enter the audit
    trail."""
    derma_user = _create_user(db_session, role="derma", label="rej1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="rejsvc", price=Decimal("70000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("70000"),
    )
    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=85000,
    )

    payload = {"override_id": override_id, "action": "reject"}
    if bad_reason is not None:
        payload["rejection_reason"] = bad_reason
    response = client.post(REGISTRAR_APPROVE, headers=admin_auth_headers, json=payload)
    assert response.status_code == 400, response.text

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.status == "pending", "no transition without a justified refusal"
    assert stored.rejection_reason is None
    refreshed_visit_service = db_session.get(VisitService, visit_service.id)
    assert refreshed_visit_service.price == Decimal("70000")


def test_registrar_reject_persists_justified_refusal(
    client, db_session, admin_user, admin_auth_headers
):
    """REGPRICE-BE-005 positive control: a meaningful reason is persisted
    verbatim (after trimming)."""
    derma_user = _create_user(db_session, role="derma", label="rej2")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="rejsvc2", price=Decimal("70000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("70000"),
    )
    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=85000,
    )

    reason = "Пациент отказался от процедуры по стоимости"
    response = client.post(
        REGISTRAR_APPROVE,
        headers=admin_auth_headers,
        json={
            "override_id": override_id,
            "action": "reject",
            "rejection_reason": f"  {reason}  ",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["new_status"] == "rejected"

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.status == "rejected"
    assert stored.rejection_reason == reason


@pytest.mark.parametrize("bad_reason", [None, "", "   "])
def test_dental_reject_whitespace_only_reason_is_refused(
    client, db_session, admin_user, admin_auth_headers, bad_reason
):
    """REGPRICE-BE-005: the dental route previously refused only a MISSING
    reason — whitespace-only strings passed. The canonical service enforces
    a trimmed non-blank reason for both routes."""
    derma_user = _create_user(db_session, role="derma", label="rej3")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="rejsvc3", price=Decimal("75000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("75000"),
    )
    override_id = _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=88000,
    )

    payload = {"action": "reject"}
    if bad_reason is not None:
        payload["rejection_reason"] = bad_reason
    response = client.put(
        DENTAL_APPROVE.format(override_id=override_id),
        headers=admin_auth_headers,
        json=payload,
    )
    assert response.status_code == 400, response.text

    db_session.expire_all()
    assert db_session.get(DoctorPriceOverride, override_id).status == "pending"


# ---------------------------------------------------------------------------
# DERMAPRICE-BE-002 end-to-end refinement: the registrar reviewer sees the
# visit's ACTUAL before-price, not only the catalogue reference
# ---------------------------------------------------------------------------


def test_registrar_list_exposes_visit_price_before_and_difference(
    client, db_session, admin_user, admin_auth_headers
):
    """DERMAPRICE-BE-002 end-to-end (group 16 follow-up): the registrar list
    response carries visit_price_before / visit_price_difference so the
    reviewer compares the ACTUAL visit price, not the catalogue reference."""
    derma_user = _create_user(db_session, role="derma", label="vpb1")
    derma_doctor = _create_doctor(db_session, derma_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="vpbsvc", price=Decimal("200000"))
    # The visit was registered at a discounted price — the catalogue
    # original_price (200000) intentionally differs from the visit price.
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=derma_doctor,
        service=service,
        price=Decimal("180000"),
    )
    _create_pending_via_derma(
        client, db_session, doctor_user=derma_user, visit=visit, service=service,
        new_price=190000,
    )

    response = client.get(
        REGISTRAR_LIST, headers=admin_auth_headers, params={"status_filter": "pending"}
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    entry = items[0]
    assert Decimal(str(entry["original_price"])) == Decimal("200000")
    assert Decimal(str(entry["visit_price_before"])) == Decimal("180000")
    assert Decimal(str(entry["visit_price_difference"])) == Decimal("10000")
