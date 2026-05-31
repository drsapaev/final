from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.service_mapping import normalize_service_code


def _create_service(
    db_session,
    *,
    code: str,
    name: str,
    queue_tag: str,
    price: Decimal = Decimal("25000"),
    requires_doctor: bool = False,
) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=name,
        price=price,
        active=True,
        requires_doctor=requires_doctor,
        queue_tag=queue_tag,
        department_key=queue_tag,
        is_consultation=requires_doctor,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_queue(
    db_session,
    *,
    specialist_id: int,
    queue_tag: str,
) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_entry(
    db_session,
    *,
    queue: DailyQueue,
    patient,
    service: Service,
    status: str = "waiting",
    visit_id: int | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=9,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        visit_id=visit_id,
        source="desk",
        status=status,
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
        services=[
            {
                "id": service.id,
                "service_id": service.id,
                "code": service.service_code,
                "name": service.name,
                "quantity": 1,
                "price": float(service.price or 0),
            }
        ],
        service_codes=[service.service_code],
        total_amount=int(service.price or 0),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _create_visit(db_session, *, patient, doctor_id: int | None, department: str) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor_id,
        visit_date=date.today(),
        visit_time=None,
        department=department,
        discount_mode="none",
        approval_status="approved",
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _post_edit_delta(client, registrar_auth_headers, *, patient_id: int, services: list[dict], entry_ids: list[int] | None = None):
    return client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json={
            "patient_id": patient_id,
            "target_date": date.today().isoformat(),
            "payment_method": "cash",
            "discount_mode": "none",
            "all_free": False,
            "services": services,
            "existing_queue_entry_ids": entry_ids or [],
        },
    )


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_appends_lab_service_to_waiting_queue_without_duplicate_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    original_service = _create_service(
        db_session,
        code="LAB-OLD-01",
        name="Old Lab",
        queue_tag="laboratory_general",
    )
    added_service = _create_service(
        db_session,
        code="LAB-NEW-01",
        name="New Lab",
        queue_tag="laboratory_general",
    )
    queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    entry = _create_entry(
        db_session,
        queue=queue,
        patient=test_patient,
        service=original_service,
        status="waiting",
    )
    preserved_queue_time = entry.queue_time

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": added_service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["invoice_id"] is not None
    assert Decimal(str(payload["total_amount"])) == Decimal("25000")

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(entries) == 1
    db_session.refresh(entry)
    assert entry.number == 9
    assert entry.queue_time == preserved_queue_time
    assert {svc["service_id"] for svc in entry.services} == {
        original_service.id,
        added_service.id,
    }
    assert set(entry.service_codes) == {
        normalize_service_code("LAB-OLD-01"),
        normalize_service_code("LAB-NEW-01"),
    }
    assert payload["queue_numbers"][str(entry.visit_id)][0]["number"] == 9


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_appends_to_diagnostics_queue_without_new_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    original_service = _create_service(
        db_session,
        code="DIAG-OLD-01",
        name="Old Diagnostics",
        queue_tag="laboratory_general",
    )
    added_service = _create_service(
        db_session,
        code="DIAG-NEW-01",
        name="New Diagnostics",
        queue_tag="laboratory_general",
    )
    queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    entry = _create_entry(
        db_session,
        queue=queue,
        patient=test_patient,
        service=original_service,
        status="diagnostics",
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": added_service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
        == 1
    )
    db_session.refresh(entry)
    assert entry.status == "diagnostics"
    assert {svc["service_id"] for svc in entry.services} == {
        original_service.id,
        added_service.id,
    }


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_different_queue_type_creates_only_new_type_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    lab_service = _create_service(
        db_session,
        code="LAB-BASE-01",
        name="Base Lab",
        queue_tag="laboratory_general",
    )
    cardio_service = _create_service(
        db_session,
        code="CARD-NEW-01",
        name="New Cardiology",
        queue_tag="cardiology_common",
        requires_doctor=True,
    )
    lab_queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    lab_entry = _create_entry(
        db_session,
        queue=lab_queue,
        patient=test_patient,
        service=lab_service,
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {
                "service_id": cardio_service.id,
                "quantity": 1,
                "specialist_id": test_doctor.id,
            }
        ],
        entry_ids=[lab_entry.id],
    )

    assert response.status_code == 200, response.text
    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.id.asc())
        .all()
    )
    assert len(entries) == 2
    assert entries[0].id == lab_entry.id
    assert entries[0].number == 9
    new_entry = entries[1]
    assert new_entry.id != lab_entry.id
    assert new_entry.visit_id is not None
    assert new_entry.services[0]["service_id"] == cardio_service.id


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_readding_same_service_is_noop_and_does_not_invoice(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    service = _create_service(
        db_session,
        code="LAB-SAME-01",
        name="Same Lab",
        queue_tag="laboratory_general",
    )
    queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    entry = _create_entry(db_session, queue=queue, patient=test_patient, service=service)

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["invoice_id"] is None
    assert Decimal(str(payload["total_amount"])) == Decimal("0")
    assert (
        db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id)
        .count()
        == 0
    )
    db_session.refresh(entry)
    assert len(entry.services) == 1


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_pending_invoice_receives_delta(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    original_service = _create_service(
        db_session,
        code="INV-OLD-01",
        name="Old Invoice Lab",
        queue_tag="laboratory_general",
    )
    added_service = _create_service(
        db_session,
        code="INV-NEW-01",
        name="New Invoice Lab",
        queue_tag="laboratory_general",
        price=Decimal("30000"),
    )
    visit = _create_visit(
        db_session,
        patient=test_patient,
        doctor_id=test_doctor.id,
        department="laboratory_general",
    )
    queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    entry = _create_entry(
        db_session,
        queue=queue,
        patient=test_patient,
        service=original_service,
        visit_id=visit.id,
    )
    invoice = PaymentInvoice(
        patient_id=test_patient.id,
        total_amount=Decimal("10000"),
        currency="UZS",
        status="pending",
        payment_method="cash",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=visit.id,
            visit_amount=Decimal("10000"),
        )
    )
    db_session.commit()

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": added_service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["invoice_id"] == invoice.id
    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("40000.00")


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_rejects_queue_entry_linked_to_other_patient_visit(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    original_service = _create_service(
        db_session,
        code="OWNER-OLD-01",
        name="Owner Old Lab",
        queue_tag="laboratory_general",
    )
    added_service = _create_service(
        db_session,
        code="OWNER-NEW-01",
        name="Owner New Lab",
        queue_tag="laboratory_general",
        price=Decimal("30000"),
    )
    other_patient = Patient(
        last_name="Other",
        first_name="Patient",
        phone="+998900000999",
    )
    db_session.add(other_patient)
    db_session.commit()
    db_session.refresh(other_patient)
    other_visit = _create_visit(
        db_session,
        patient=other_patient,
        doctor_id=test_doctor.id,
        department="laboratory_general",
    )
    queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    entry = _create_entry(
        db_session,
        queue=queue,
        patient=test_patient,
        service=original_service,
        visit_id=other_visit.id,
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": added_service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "does not belong" in response.json()["detail"]
    assert (
        db_session.query(VisitService)
        .filter(
            VisitService.visit_id == other_visit.id,
            VisitService.service_id == added_service.id,
        )
        .count()
        == 0
    )
    assert (
        db_session.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.visit_id == other_visit.id)
        .count()
        == 0
    )
    db_session.refresh(entry)
    assert {svc["service_id"] for svc in entry.services} == {original_service.id}


@pytest.mark.integration
@pytest.mark.queue
def test_mark_paid_syncs_pending_edit_delta_invoice_after_visit_payment(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    service = _create_service(
        db_session,
        code="PAY-SYNC-01",
        name="Payment Sync Lab",
        queue_tag="laboratory_general",
        price=Decimal("30000"),
    )
    visit = _create_visit(
        db_session,
        patient=test_patient,
        doctor_id=test_doctor.id,
        department="laboratory_general",
    )
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            code=service.service_code,
            name=service.name,
            qty=1,
            price=service.price,
            currency="UZS",
        )
    )
    invoice = PaymentInvoice(
        patient_id=test_patient.id,
        total_amount=Decimal("30000"),
        currency="UZS",
        status="pending",
        payment_method="cash",
        notes="edit-delta",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=visit.id,
            visit_amount=Decimal("30000"),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=registrar_auth_headers,
        json={
            "action": "mark_paid",
            "amount": 30000,
            "method": "cash",
            "records": [{"record_kind": "visit", "record_id": visit.id}],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["success_count"] == 1

    db_session.refresh(invoice)
    assert invoice.status == "paid"
    assert invoice.paid_at is not None
    assert (
        db_session.query(Payment)
        .filter(Payment.visit_id == visit.id, Payment.status == "paid")
        .count()
        == 1
    )


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_paid_invoice_creates_supplemental_invoice(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    original_service = _create_service(
        db_session,
        code="PAID-OLD-01",
        name="Old Paid Lab",
        queue_tag="laboratory_general",
    )
    added_service = _create_service(
        db_session,
        code="PAID-NEW-01",
        name="New Paid Lab",
        queue_tag="laboratory_general",
        price=Decimal("45000"),
    )
    visit = _create_visit(
        db_session,
        patient=test_patient,
        doctor_id=test_doctor.id,
        department="laboratory_general",
    )
    queue = _create_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="laboratory_general",
    )
    entry = _create_entry(
        db_session,
        queue=queue,
        patient=test_patient,
        service=original_service,
        visit_id=visit.id,
    )
    paid_invoice = PaymentInvoice(
        patient_id=test_patient.id,
        total_amount=Decimal("10000"),
        currency="UZS",
        status="paid",
        payment_method="cash",
    )
    db_session.add(paid_invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=paid_invoice.id,
            visit_id=visit.id,
            visit_amount=Decimal("10000"),
        )
    )
    db_session.commit()

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": added_service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["invoice_id"] != paid_invoice.id
    invoices = (
        db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id)
        .order_by(PaymentInvoice.id.asc())
        .all()
    )
    assert [invoice.status for invoice in invoices] == ["paid", "pending"]
    assert invoices[-1].total_amount == Decimal("45000.00")
