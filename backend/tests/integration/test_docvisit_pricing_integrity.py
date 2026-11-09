"""DOCVISIT-BE-001/002/003 + DENTPRICE-BE-001 (audit #3892, group 17) —
doctor visit-service pricing integrity and notification truth.

Fail-first coverage for the doctor-side visit-service mutation plane:

* **DOCVISIT-BE-001 (P1)** — ``VisitService`` has NO mapped ``custom_price``
  field, yet ``GET /doctor/visits/today``, ``GET /doctor/visits/{visit_id}``
  and the ``PUT /doctor/visits/{visit_id}/add-service`` response all
  dereference ``vs.custom_price``. Every read of a visit WITH services
  turned into an HTTP 500, and add-service committed the row and THEN
  failed to serialize the response (persisted-mutation/failed-response
  split). The canonical price-override approval service also assigned an
  ephemeral ``row.custom_price`` attribute that is never persisted; the
  old assertions in the group-15/16 suites passed vacuously through the
  shared-session identity map. Contract now: the persisted ``price`` IS
  the effective (custom or catalogue) price — no phantom alias.
* **DOCVISIT-BE-002 (P1)** — add-service accepted ``quantity=0``/negative
  and negative/NaN/Infinity prices, persisting invalid billable rows
  that billing then multiplies into invoices. Now 422 with no row.
* **DOCVISIT-BE-003 (P1/P2)** — add/delete-service never inspected the
  payment state: a fully paid visit could have its cost basis changed
  (or a paid service row deleted) without refund/re-quote coordination,
  and mutations ran outside the canonical Visit lock used by payments.
  Now the visit is locked first (the payment-flow lock order), in-flight
  ``processing`` invoice reservations are rejected (409), and any net
  settled amount (paid minus completed refunds) fails closed (409).
  Unpaid and fully-refunded visits stay mutable (positive controls).
* **DENTPRICE-BE-001 (P2)** — the dental price-override notification flag
  ``notification_sent`` was set unconditionally: registrars without a
  telegram_id, every-send-failed and notifier-reported-failure all still
  recorded ``True``. Now the flag means at least one CONFIRMED delivery;
  the pending request itself stays committed and reviewable regardless.

Retry-idempotency (from the group-17 fail-first spec): an exact repeat of
the immediately preceding add (same service/qty/effective price within a
short window) returns the existing row with ``idempotent_replay: true``
instead of silently inserting a duplicate line.

REGPRICE-BE-006 (duplicate VisitService lines) was closed by the merged
round 22 (#3945) "apply to ALL matching lines" policy and is not retested
here beyond the chargeable-row convergence already pinned in the
group-16 suite.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.visit import Visit, VisitService

pytestmark = pytest.mark.integration

TODAY_VISITS = "/api/v1/doctor/visits/today"
VISIT_DETAILS = "/api/v1/doctor/visits/{visit_id}"
ADD_SERVICE = "/api/v1/doctor/visits/{visit_id}/add-service"
DELETE_SERVICE = "/api/v1/doctor/visits/{visit_id}/services/{visit_service_id}"
DENTAL_POST = "/api/v1/dental/price-override"

# DOCVISIT-BE-001: window inside which an exact repeat of the same add is
# treated as a retry of a lost response rather than a second clinical line.
RETRY_DEDUP_WINDOW = timedelta(seconds=10)


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_user(db_session, *, role: str, label: str, password: str = "doctor123"):
    suffix = _suffix()
    user = User(
        username=f"dv_{label}_{suffix}",
        email=f"dv-{label}-{suffix}@test.local",
        full_name=f"DV {label}",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_registrar(db_session, *, label: str, chat_id: int | None):
    """Registrar user with an optional ACTIVE TelegramUser link (the only
    real user↔chat association; the User model has no telegram column)."""
    suffix = _suffix()
    user = User(
        username=f"dv_reg_{label}_{suffix}",
        email=f"dv-reg-{label}-{suffix}@test.local",
        full_name=f"DV Registrar {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    if chat_id is not None:
        db_session.add(
            TelegramUser(
                user_id=user.id,
                chat_id=chat_id,
                language_code="ru",
                notifications_enabled=True,
                active=True,
                blocked=False,
            )
        )
        db_session.commit()
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
        first_name="Доквизит",
        last_name=f"Тест-{suffix[:5]}",
        phone=f"+9989{suffix[:8]}",
        birth_date=date(1990, 5, 5),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_service(db_session, *, label: str, price: Decimal) -> Service:
    suffix = _suffix()
    service = Service(
        code=f"DV{suffix[:6].upper()}",
        name=f"Docvisit test {label}",
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
        department="dentistry",
    )
    db_session.add(visit)
    db_session.flush()
    # The pre-existing service line belongs to the visit's earlier state:
    # keep it OUTSIDE the add-service retry-dedup window so API adds in the
    # tests below are always genuine inserts.
    visit_service = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=1,
        price=price,
        created_at=datetime.now(UTC) - timedelta(minutes=15),
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


def _rows_for(db_session, visit_id: int, service_id: int) -> list[VisitService]:
    db_session.expire_all()
    return (
        db_session.query(VisitService)
        .filter(
            VisitService.visit_id == visit_id,
            VisitService.service_id == service_id,
        )
        .all()
    )


def _add(client, headers, *, visit_id: int, service_id: int, **params):
    return client.put(
        ADD_SERVICE.format(visit_id=visit_id),
        headers=headers,
        params={"service_id": service_id, **params},
    )


def _delete(client, headers, *, visit_id: int, visit_service_id: int):
    return client.delete(
        DELETE_SERVICE.format(visit_id=visit_id, visit_service_id=visit_service_id),
        headers=headers,
    )


def _paid_visit(db_session, *, amount: Decimal, refunded: Decimal = Decimal("0")):
    """Doctor + patient + service + visit with one settled payment."""
    doctor_user = _create_user(db_session, role="doctor", label="paid")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="paidsvc", price=Decimal("100000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("100000"),
    )
    payment = Payment(
        visit_id=visit.id,
        amount=amount,
        refunded_amount=refunded,
        method="cash",
        status="paid",
    )
    db_session.add(payment)
    db_session.commit()
    return doctor_user, service, visit, visit_service


def _processing_invoice_visit(db_session):
    doctor_user = _create_user(db_session, role="doctor", label="procinv")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="procsvc", price=Decimal("70000"))
    visit, visit_service = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("70000"),
    )
    invoice = PaymentInvoice(
        patient_id=patient.id,
        total_amount=Decimal("70000"),
        currency="UZS",
        provider=None,
        status="processing",
        payment_method="cash",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=visit.id,
            visit_amount=Decimal("70000"),
        )
    )
    db_session.commit()
    return doctor_user, service, visit, visit_service


# ---------------------------------------------------------------------------
# DOCVISIT-BE-001: no phantom custom_price on read/serialize paths
# ---------------------------------------------------------------------------


def test_today_visits_200_no_ephemeral_custom_price(client, db_session):
    """GET /doctor/visits/today must serialize services from the persisted
    schema. Dereferencing the nonexistent ``custom_price`` attribute made
    every visit WITH services an HTTP 500."""
    doctor_user = _create_user(db_session, role="doctor", label="today")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="todaysvc", price=Decimal("120000"))
    _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("120000"),
    )
    headers = _login_headers(client, doctor_user)

    response = client.get(TODAY_VISITS, headers=headers)
    assert response.status_code == 200, response.text
    visits = response.json()["visits"]
    assert len(visits) == 1
    services = visits[0]["services"]
    assert len(services) == 1
    assert Decimal(str(services[0]["price"])) == Decimal("120000")
    assert services[0]["quantity"] == 1
    assert Decimal(str(services[0]["total"])) == Decimal("120000")
    assert "custom_price" not in services[0], (
        "the persisted schema has no custom_price column — the response must "
        "not fabricate a phantom alias"
    )


def test_visit_details_200_no_ephemeral_custom_price(client, db_session):
    """GET /doctor/visits/{visit_id} must return 200 for a visit with
    services and expose only persisted fields."""
    doctor_user = _create_user(db_session, role="doctor", label="detail")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="detailsvc", price=Decimal("90000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("90000"),
    )
    headers = _login_headers(client, doctor_user)

    response = client.get(VISIT_DETAILS.format(visit_id=visit.id), headers=headers)
    assert response.status_code == 200, response.text
    services = response.json()["visit"]["services"]
    assert len(services) == 1
    assert Decimal(str(services[0]["price"])) == Decimal("90000")
    assert services[0]["quantity"] == 1
    assert "custom_price" not in services[0]


def test_add_service_200_row_persisted_response_from_persisted_state(
    client, db_session
):
    """PUT add-service must return a successful response built from the
    persisted row. Previously the row was committed and THEN the response
    dereferenced ``visit_service.custom_price`` → 500 after commit."""
    doctor_user = _create_user(db_session, role="doctor", label="addok")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="addsvc", price=Decimal("150000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("150000"),
    )
    headers = _login_headers(client, doctor_user)

    response = _add(
        client, headers, visit_id=visit.id, service_id=service.id, quantity=2
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    vs = body["visit_service"]
    assert vs["quantity"] == 2
    assert Decimal(str(vs["price"])) == Decimal("150000")
    assert Decimal(str(vs["total"])) == Decimal("300000")
    assert "custom_price" not in vs

    rows = _rows_for(db_session, visit.id, service.id)
    assert len(rows) == 2, "one new row next to the pre-existing line"
    assert rows[-1].qty == 2


def test_add_service_retry_after_lost_response_no_duplicate_row(
    client, db_session
):
    """A client retry of an add whose HTTP response was lost must not create
    a second identical billable line (group-17 fail-first: idempotency or
    safe dedup)."""
    doctor_user = _create_user(db_session, role="doctor", label="retry")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="retrysvc", price=Decimal("80000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("80000"),
    )
    headers = _login_headers(client, doctor_user)

    first = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert first.status_code == 200, first.text

    # The client never saw the response and retries the exact same request.
    second = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert second.status_code == 200, second.text
    assert second.json().get("idempotent_replay") is True
    assert second.json()["visit_service"]["id"] == first.json()["visit_service"]["id"]

    rows = _rows_for(db_session, visit.id, service.id)
    assert len(rows) == 2, "original line + exactly one added line, no duplicate"


def test_add_service_retry_with_different_price_not_deduped(client, db_session):
    """A genuinely different price is a new clinical/financial decision —
    dedup must not swallow it."""
    doctor_user = _create_user(db_session, role="doctor", label="diffp")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="diffsvc", price=Decimal("60000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("60000"),
    )
    headers = _login_headers(client, doctor_user)

    first = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert first.status_code == 200, first.text
    assert first.json().get("idempotent_replay") is False

    second = _add(
        client,
        headers,
        visit_id=visit.id,
        service_id=service.id,
        custom_price=45000,
    )
    assert second.status_code == 200, second.text
    assert second.json().get("idempotent_replay") is False

    rows = _rows_for(db_session, visit.id, service.id)
    assert len(rows) == 3, "original + catalogue-price add + custom-price add"


def test_add_service_identical_row_outside_window_not_deduped(client, db_session):
    """An identical row older than the retry window is a deliberate second
    line, not a lost-response retry."""
    doctor_user = _create_user(db_session, role="doctor", label="oldrow")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="oldsvc", price=Decimal("40000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("40000"),
    )
    stale = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=1,
        price=Decimal("40000"),
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(stale)
    db_session.commit()

    headers = _login_headers(client, doctor_user)
    response = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert response.status_code == 200, response.text
    assert response.json().get("idempotent_replay") is False

    rows = _rows_for(db_session, visit.id, service.id)
    assert len(rows) == 3, "pre-existing old pair + one new deliberate line"


# ---------------------------------------------------------------------------
# DOCVISIT-BE-002: input validation must fail BEFORE any persistence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("quantity", [0, -2], ids=["zero", "negative"])
def test_add_service_invalid_quantity_rejected_no_row(client, db_session, quantity):
    """quantity=0/negative must be 422 with no row written; previously the
    row was persisted and only the response failed (or 200)."""
    doctor_user = _create_user(db_session, role="doctor", label="qtybad")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="qtysvc", price=Decimal("50000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("50000"),
    )
    headers = _login_headers(client, doctor_user)

    before = len(_rows_for(db_session, visit.id, service.id))
    response = _add(
        client, headers, visit_id=visit.id, service_id=service.id, quantity=quantity
    )
    assert response.status_code == 422, response.text
    after = len(_rows_for(db_session, visit.id, service.id))
    assert after == before, "invalid quantity must not persist a billable row"


@pytest.mark.parametrize(
    "custom_price",
    ["-10000", "nan", "inf", "-inf"],
    ids=["negative", "nan", "infinity", "negative-infinity"],
)
def test_add_service_invalid_price_rejected_no_row(client, db_session, custom_price):
    """Negative/NaN/Infinity custom prices must be 422 with no row written;
    previously an invalid row was already committed when the response blew
    up."""
    doctor_user = _create_user(db_session, role="doctor", label="pricebad")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="pricesvc", price=Decimal("50000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("50000"),
    )
    headers = _login_headers(client, doctor_user)

    before = len(_rows_for(db_session, visit.id, service.id))
    response = _add(
        client,
        headers,
        visit_id=visit.id,
        service_id=service.id,
        custom_price=custom_price,
    )
    assert response.status_code == 422, response.text
    after = len(_rows_for(db_session, visit.id, service.id))
    assert after == before, "invalid price must not persist a billable row"


def test_add_service_valid_custom_price_positive_control(client, db_session):
    """Positive control: qty>=1 with a finite non-negative custom price is
    accepted and persisted exactly once."""
    doctor_user = _create_user(db_session, role="doctor", label="posctl")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="possvc", price=Decimal("100000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("100000"),
    )
    headers = _login_headers(client, doctor_user)

    response = _add(
        client,
        headers,
        visit_id=visit.id,
        service_id=service.id,
        quantity=3,
        custom_price=55000,
    )
    assert response.status_code == 200, response.text
    rows = _rows_for(db_session, visit.id, service.id)
    assert len(rows) == 2
    assert rows[-1].qty == 3
    assert rows[-1].price == Decimal("55000")


# ---------------------------------------------------------------------------
# DOCVISIT-BE-003: payment-state coordination and canonical lock
# ---------------------------------------------------------------------------


def test_add_service_on_paid_visit_rejected(client, db_session):
    """A visit with a net settled amount must not accept new billable rows
    (no refund/re-quote coordination exists on this route)."""
    doctor_user, service, visit, _ = _paid_visit(
        db_session, amount=Decimal("100000")
    )
    headers = _login_headers(client, doctor_user)

    before = len(_rows_for(db_session, visit.id, service.id))
    response = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert response.status_code == 409, response.text
    after = len(_rows_for(db_session, visit.id, service.id))
    assert after == before, "paid visit must not gain new billable rows"


def test_delete_service_on_paid_visit_rejected(client, db_session):
    """Deleting a service row of a paid visit changes the cost basis under
    an unchanged receipt — must fail closed."""
    doctor_user, service, visit, visit_service = _paid_visit(
        db_session, amount=Decimal("100000")
    )
    headers = _login_headers(client, doctor_user)

    response = _delete(
        client, headers, visit_id=visit.id, visit_service_id=visit_service.id
    )
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert db_session.get(VisitService, visit_service.id) is not None


def test_add_service_on_processing_invoice_rejected(client, db_session):
    """In-flight provider invoice reservation must block the mutation with
    409 (the same guard payments use)."""
    doctor_user, service, visit, _ = _processing_invoice_visit(db_session)
    headers = _login_headers(client, doctor_user)

    before = len(_rows_for(db_session, visit.id, service.id))
    response = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert response.status_code == 409, response.text
    after = len(_rows_for(db_session, visit.id, service.id))
    assert after == before


def test_delete_service_on_processing_invoice_rejected(client, db_session):
    doctor_user, service, visit, visit_service = _processing_invoice_visit(db_session)
    headers = _login_headers(client, doctor_user)

    response = _delete(
        client, headers, visit_id=visit.id, visit_service_id=visit_service.id
    )
    assert response.status_code == 409, response.text
    db_session.expire_all()
    assert db_session.get(VisitService, visit_service.id) is not None


def test_mutations_allowed_on_unpaid_visit(client, db_session):
    """Positive control: an unpaid visit stays fully mutable (add and delete
    both succeed)."""
    doctor_user = _create_user(db_session, role="doctor", label="unpaid")
    doctor = _create_doctor(db_session, doctor_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="unpaidsvc", price=Decimal("30000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=doctor,
        service=service,
        price=Decimal("30000"),
    )
    headers = _login_headers(client, doctor_user)

    added = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert added.status_code == 200, added.text
    new_row_id = added.json()["visit_service"]["id"]

    deleted = _delete(
        client, headers, visit_id=visit.id, visit_service_id=new_row_id
    )
    assert deleted.status_code == 200, deleted.text


def test_fully_refunded_visit_is_mutable_again(client, db_session):
    """Positive control: a fully refunded payment has net settled 0 — the
    visit's cost basis is legitimately reworkable."""
    doctor_user, service, visit, _ = _paid_visit(
        db_session, amount=Decimal("100000"), refunded=Decimal("100000")
    )
    headers = _login_headers(client, doctor_user)

    response = _add(client, headers, visit_id=visit.id, service_id=service.id)
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# DENTPRICE-BE-001: notification_sent must mean a confirmed delivery
# ---------------------------------------------------------------------------


class _FakeSender:
    def __init__(self, *, result: Any = None, raise_exc: Exception | None = None):
        self.result = result
        self.raise_exc = raise_exc
        self.calls: list[int] = []

    async def send_telegram_message(
        self, *, user_id: int, message: str, parse_mode: str = "HTML"
    ) -> dict[str, Any]:
        self.calls.append(user_id)
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.result


def _create_dental_override(client, db_session, *, monkeypatch, sender) -> int:
    monkeypatch.setattr(
        "app.services.dental_api_service.notification_sender_service",
        sender,
    )
    dentist_user = _create_user(db_session, role="doctor", label="dnotif")
    dentist = _create_doctor(db_session, dentist_user, specialty="stomatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="notsvc", price=Decimal("200000"))
    visit, _ = _create_visit_with_service(
        db_session,
        patient=patient,
        doctor=dentist,
        service=service,
        price=Decimal("200000"),
    )
    headers = _login_headers(client, dentist_user)

    response = client.post(
        DENTAL_POST,
        headers=headers,
        json={
            "visit_id": visit.id,
            "service_id": service.id,
            "new_price": 180000,
            "reason": "Скидка постоянному пациенту",
            "treatment_completed": True,
        },
    )
    assert response.status_code == 200, response.text
    override_id = response.json()["id"]

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored is not None, "the pending request stays committed regardless"
    assert stored.status == "pending"
    return override_id


def test_dental_notification_flag_false_without_telegram_id(
    client, db_session, monkeypatch
):
    """Registrars exist but none has an active TelegramUser link → nothing
    was delivered → the flag must stay False. Previously it was set to True
    (and the send was skipped for EVERY registrar because the code probed a
    nonexistent ``telegram_id`` attribute on User)."""
    _create_registrar(db_session, label="notelegram", chat_id=None)
    sender = _FakeSender(result={"success": True})
    override_id = _create_dental_override(
        client, db_session, monkeypatch=monkeypatch, sender=sender
    )

    assert sender.calls == [], "no telegram link — the sender must not be called"
    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.notification_sent is False
    assert stored.notification_sent_at is None


def test_dental_notification_flag_false_when_all_sends_raise(
    client, db_session, monkeypatch
):
    """Every send raising must not produce a 'sent' audit claim."""
    _create_registrar(db_session, label="raising", chat_id=555000111)
    sender = _FakeSender(raise_exc=RuntimeError("telegram down"))
    override_id = _create_dental_override(
        client, db_session, monkeypatch=monkeypatch, sender=sender
    )

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.notification_sent is False


def test_dental_notification_flag_false_when_notifier_reports_failure(
    client, db_session, monkeypatch
):
    """The notifier explicitly reporting failure must not count as sent."""
    _create_registrar(db_session, label="failing", chat_id=555000112)
    sender = _FakeSender(result={"success": False, "error": "blocked"})
    override_id = _create_dental_override(
        client, db_session, monkeypatch=monkeypatch, sender=sender
    )

    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.notification_sent is False
    assert stored.notification_sent_at is None


def test_dental_notification_flag_true_on_one_confirmed_delivery(
    client, db_session, monkeypatch
):
    """Control: one confirmed delivery sets the flag (and only then)."""
    _create_registrar(db_session, label="okone", chat_id=555000113)
    sender = _FakeSender(result={"success": True})
    override_id = _create_dental_override(
        client, db_session, monkeypatch=monkeypatch, sender=sender
    )

    assert sender.calls == [555000113], (
        "the send must target the registrar's REAL TelegramUser chat_id"
    )
    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.notification_sent is True
    assert stored.notification_sent_at is not None


def test_dental_notification_mixed_delivery_counts_confirmed_only(
    client, db_session, monkeypatch
):
    """Two registrars, one confirmed and one failed → the flag is True (at
    least one confirmed delivery) and the failure is not silently 'sent'."""

    class _MixedSender:
        def __init__(self):
            self.calls = 0

        async def send_telegram_message(
            self, *, user_id: int, message: str, parse_mode: str = "HTML"
        ) -> dict[str, Any]:
            self.calls += 1
            # Первый registrar получит отказ, второй — успех.
            return (
                {"success": False, "error": "blocked"}
                if self.calls == 1
                else {"success": True}
            )

    _create_registrar(db_session, label="mixfail", chat_id=555000114)
    _create_registrar(db_session, label="mixok", chat_id=555000115)
    sender = _MixedSender()
    override_id = _create_dental_override(
        client, db_session, monkeypatch=monkeypatch, sender=sender
    )

    assert sender.calls == 2
    db_session.expire_all()
    stored = db_session.get(DoctorPriceOverride, override_id)
    assert stored.notification_sent is True
