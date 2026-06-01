from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit, VisitService


@pytest.mark.integration
def test_full_update_all_free_without_visit_id_does_not_reuse_unrelated_visit(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
    test_doctor,
    test_service,
):
    unrelated_visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="12:00",
        status="open",
        discount_mode="none",
        approval_status="none",
        department="cardiology",
    )
    db_session.add(unrelated_visit)
    db_session.flush()
    unrelated_service = VisitService(
        visit_id=unrelated_visit.id,
        service_id=test_service.id,
        code=test_service.code,
        name=test_service.name,
        qty=1,
        price=test_service.price,
        currency="UZS",
    )
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=77,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        source="online",
        status="waiting",
    )
    db_session.add_all([unrelated_service, entry])
    db_session.commit()
    db_session.refresh(unrelated_visit)
    db_session.refresh(entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": True,
        },
    )

    assert response.status_code == 200, response.text

    db_session.refresh(entry)
    db_session.refresh(unrelated_visit)
    assert entry.visit_id is not None
    assert entry.visit_id != unrelated_visit.id
    assert unrelated_visit.discount_mode == "none"
    assert unrelated_visit.approval_status == "none"
    assert unrelated_visit.status == "open"
    assert (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == unrelated_visit.id)
        .count()
        == 1
    )

    linked_visit = db_session.query(Visit).filter(Visit.id == entry.visit_id).one()
    assert linked_visit.discount_mode == "all_free"
    assert linked_visit.approval_status == "pending"


@pytest.mark.integration
def test_full_update_all_free_rejects_entry_linked_to_other_patient_visit(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
    test_doctor,
    test_service,
):
    other_patient = Patient(
        last_name="Other",
        first_name="Queue",
        phone="+998900001111",
    )
    db_session.add(other_patient)
    db_session.flush()
    other_visit = Visit(
        patient_id=other_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="12:00",
        status="open",
        discount_mode="none",
        approval_status="none",
        department="cardiology",
    )
    db_session.add(other_visit)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=other_visit.id,
            service_id=test_service.id,
            code=test_service.code,
            name=test_service.name,
            qty=1,
            price=test_service.price,
            currency="UZS",
        )
    )
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=78,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=other_visit.id,
        source="online",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    db_session.refresh(other_visit)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": True,
        },
    )

    assert response.status_code == 409, response.text
    assert "does not belong" in response.json()["detail"]

    db_session.refresh(other_visit)
    assert other_visit.discount_mode == "none"
    assert other_visit.approval_status == "none"
    assert other_visit.department == "cardiology"
    assert (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == other_visit.id)
        .count()
        == 1
    )


@pytest.mark.integration
def test_full_update_visit_id_aggregation_ignores_other_patient_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
    test_doctor,
    test_service,
):
    other_patient = Patient(
        last_name="Other",
        first_name="Queue",
        phone="+998900001112",
    )
    db_session.add(other_patient)
    db_session.flush()
    other_visit = Visit(
        patient_id=other_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="12:00",
        status="open",
        discount_mode="none",
        approval_status="none",
        department="cardiology",
    )
    db_session.add(other_visit)
    db_session.flush()

    other_queue_time = datetime(2026, 5, 31, 7, 0, tzinfo=timezone.utc)
    current_queue_time = datetime(2026, 5, 31, 10, 0, tzinfo=timezone.utc)
    other_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=80,
        patient_id=other_patient.id,
        patient_name="Other Queue",
        phone=other_patient.phone,
        visit_id=other_visit.id,
        source="online",
        status="waiting",
        queue_time=other_queue_time,
        services=json.dumps(
            [
                {
                    "service_id": test_service.id,
                    "name": test_service.name,
                    "code": test_service.code,
                    "quantity": 1,
                    "price": int(test_service.price or 0),
                    "queue_time": other_queue_time.isoformat(),
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
    )
    current_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=81,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=other_visit.id,
        source="online",
        status="waiting",
        queue_time=current_queue_time,
        services=json.dumps([], ensure_ascii=False),
    )
    db_session.add_all([other_entry, current_entry])
    db_session.commit()
    db_session.refresh(current_entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{current_entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": False,
        },
    )

    assert response.status_code == 200, response.text

    db_session.refresh(current_entry)
    db_session.refresh(other_entry)
    current_services = json.loads(current_entry.services)
    other_services = json.loads(other_entry.services)
    assert [service["service_id"] for service in current_services] == [test_service.id]
    assert current_services[0]["queue_time"] == current_queue_time.replace(
        tzinfo=None
    ).isoformat()
    assert current_services[0]["queue_time"] != other_queue_time.isoformat()
    assert other_services[0]["queue_time"] == other_queue_time.isoformat()


@pytest.mark.integration
def test_full_update_without_visit_id_ignores_unrelated_same_day_patient_entries(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
    test_service,
):
    unrelated_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_daily_queue.specialist_id,
        queue_tag=f"unrelated-{test_daily_queue.id}",
        active=True,
    )
    db_session.add(unrelated_queue)
    db_session.flush()

    unrelated_entry = OnlineQueueEntry(
        queue_id=unrelated_queue.id,
        number=10,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        services=json.dumps(
            [
                {
                    "service_id": test_service.id,
                    "name": test_service.name,
                    "code": test_service.code,
                    "quantity": 1,
                    "price": int(test_service.price or 0),
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
    )
    current_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=11,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        queue_time=datetime(2026, 5, 31, 9, 30, tzinfo=timezone.utc),
        services=json.dumps([], ensure_ascii=False),
    )
    db_session.add_all([unrelated_entry, current_entry])
    db_session.commit()
    db_session.refresh(current_entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{current_entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": False,
        },
    )

    assert response.status_code == 200, response.text

    db_session.refresh(current_entry)
    db_session.refresh(unrelated_entry)
    current_services = json.loads(current_entry.services)
    assert [service["service_id"] for service in current_services] == [test_service.id]
    assert unrelated_entry.queue_id == unrelated_queue.id


@pytest.mark.integration
def test_full_update_without_visit_id_matches_same_session_phone_digits(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_service,
):
    existing_queue_time = datetime(2026, 5, 31, 9, 0, tzinfo=timezone.utc)
    existing_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=20,
        patient_id=None,
        patient_name="Phone Format Patient",
        phone="+998 90 123-45-67",
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        queue_time=existing_queue_time,
        services=json.dumps(
            [
                {
                    "service_id": test_service.id,
                    "name": test_service.name,
                    "code": test_service.code,
                    "quantity": 1,
                    "price": int(test_service.price or 0),
                    "queue_time": existing_queue_time.isoformat(),
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
    )
    current_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=21,
        patient_id=None,
        patient_name="Phone Format Patient",
        phone="+998901234567",
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        queue_time=datetime(2026, 5, 31, 9, 5, tzinfo=timezone.utc),
        services=json.dumps([], ensure_ascii=False),
    )
    db_session.add_all([existing_entry, current_entry])
    db_session.commit()
    db_session.refresh(existing_entry)
    db_session.refresh(current_entry)

    before_count = db_session.query(OnlineQueueEntry).count()

    response = client.put(
        f"/api/v1/queue/online-entry/{current_entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": "Phone Format Patient",
                "phone": "901234567",
                "birth_year": 1990,
                "address": "Phone Street",
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": False,
            "aggregated_ids": [existing_entry.id, current_entry.id],
        },
    )

    assert response.status_code == 200, response.text
    assert db_session.query(OnlineQueueEntry).count() == before_count

    db_session.refresh(current_entry)
    current_services = json.loads(current_entry.services)
    assert [service["service_id"] for service in current_services] == [test_service.id]
    assert current_services[0]["queue_time"] == existing_queue_time.isoformat()


@pytest.mark.integration
def test_full_update_all_free_preserves_paid_visit_payment_state(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
    test_doctor,
    test_service,
):
    paid_visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="10:30",
        status="open",
        discount_mode="none",
        approval_status="approved",
        department="cardiology",
    )
    db_session.add(paid_visit)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=paid_visit.id,
            service_id=test_service.id,
            code=test_service.code,
            name=test_service.name,
            qty=1,
            price=test_service.price,
            currency="UZS",
        )
    )
    paid_invoice = PaymentInvoice(
        patient_id=test_patient.id,
        total_amount=Decimal("100000.00"),
        currency="UZS",
        status="paid",
        payment_method="cash",
    )
    db_session.add(paid_invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=paid_invoice.id,
            visit_id=paid_visit.id,
            visit_amount=Decimal("100000.00"),
        )
    )
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=31,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=paid_visit.id,
        source="online",
        status="waiting",
        discount_mode="none",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    db_session.refresh(paid_visit)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": True,
        },
    )

    assert response.status_code == 200, response.text

    db_session.refresh(entry)
    db_session.refresh(paid_visit)
    assert paid_visit.discount_mode == "none"
    assert paid_visit.approval_status == "approved"
    assert paid_visit.department == "cardiology"
    assert paid_visit.doctor_id == test_doctor.id
    assert entry.discount_mode == "none"
