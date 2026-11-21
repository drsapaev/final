from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.qr_queue import _online_entries
from app.core.security import get_password_hash
from app.crud.clinic import clinic_today
from app.models.all_free_request import AllFreeRequest
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.encounter import Encounter
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import (
    ProviderActiveVisitReservation,
    ProviderAttempt,
    ProviderAttemptVisit,
)
from app.models.refund_deposit import DepositTransaction, PatientDeposit
from app.models.service import Service
from app.models.user import User
from app.models.user_profile import UserAuditLog
from app.models.visit import Visit, VisitService
from app.services.all_free_approval import ALL_FREE_DECISION_REQUIRED
from app.services.all_free_request_service import AllFreeRequestService
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.visit_lifecycle_service import VisitLifecycleService
from tests.integration.test_all_free_registrar_workflow import (
    migrated_visit_confirmation_context,  # noqa: F401
)


@pytest.fixture(autouse=True)
def _use_real_doctor_id_for_shared_queue_fixture(request, db_session):
    """These QR tests need a doctor-owned queue, whose FK is Doctor.id."""
    if "test_daily_queue" not in request.fixturenames:
        return
    doctor = request.getfixturevalue("test_doctor")
    queue = request.getfixturevalue("test_daily_queue")
    if queue.specialist_id != doctor.id:
        queue.specialist_id = doctor.id
        db_session.commit()


def _create_queue_doctor(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = uuid4().hex[:10]
    user = User(
        username=f"qr_owner_{label}_{suffix}",
        email=f"qr-owner-{label}-{suffix}@test.local",
        full_name=f"QR Owner {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="general",
        active=True,
        cabinet="401",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_queue_entry_for_doctor(
    db_session,
    *,
    doctor: Doctor,
    status: str = "waiting",
) -> OnlineQueueEntry:
    # QD-2C (round-25): the REST call-next day default is the
    # clinic_today SSOT (unified with queue_svc/GQL/quick-call) — the
    # fixture follows it (host date.today() missed the 19:00-24:00Z
    # window).
    queue = DailyQueue(
        day=clinic_today(db_session),
        specialist_id=doctor.id,
        queue_tag=f"qr-owner-{doctor.id}",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_name="Guarded Patient",
        phone="+998900000131",
        source="online",
        status=status,
        services=json.dumps(
            [
                {
                    "service_id": 1,
                    "name": "Consultation",
                    "quantity": 1,
                    "price": 10000,
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.integration
def test_doctor_cannot_generate_qr_token_for_other_doctor_queue(
    client,
    db_session,
) -> None:
    actor_user, actor_doctor = _create_queue_doctor(db_session, label="actor_token")
    _other_user, other_doctor = _create_queue_doctor(db_session, label="other_token")

    response = client.post(
        "/api/v1/queue/admin/qr-tokens/generate",
        headers=_doctor_headers(client, actor_user),
        json={
            "specialist_id": other_doctor.id,
            "department": "general",
        },
    )

    assert actor_doctor.id != other_doctor.id
    assert response.status_code == 403


@pytest.mark.integration
def test_doctor_cannot_call_next_for_other_doctor_queue(
    client,
    db_session,
) -> None:
    actor_user, actor_doctor = _create_queue_doctor(db_session, label="actor_call")
    _other_user, other_doctor = _create_queue_doctor(db_session, label="other_call")
    entry = _create_queue_entry_for_doctor(db_session, doctor=other_doctor)

    response = client.post(
        f"/api/v1/queue/{other_doctor.id}/call-next",
        headers=_doctor_headers(client, actor_user),
    )

    assert actor_doctor.id != other_doctor.id
    assert response.status_code == 403
    db_session.refresh(entry)
    assert entry.status == "waiting"


@pytest.mark.integration
def test_doctor_can_call_next_for_own_doctor_queue(
    client,
    db_session,
) -> None:
    actor_user, actor_doctor = _create_queue_doctor(db_session, label="own_call")
    entry = _create_queue_entry_for_doctor(db_session, doctor=actor_doctor)

    response = client.post(
        f"/api/v1/queue/{actor_doctor.id}/call-next",
        headers=_doctor_headers(client, actor_user),
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    db_session.refresh(entry)
    assert entry.status == "called"
    assert entry.called_by_user_id == actor_user.id


@pytest.mark.integration
def test_doctor_cannot_mark_other_doctor_queue_entry_no_show(
    client,
    db_session,
) -> None:
    actor_user, actor_doctor = _create_queue_doctor(db_session, label="actor_no_show")
    _other_user, other_doctor = _create_queue_doctor(db_session, label="other_no_show")
    entry = _create_queue_entry_for_doctor(db_session, doctor=other_doctor)

    response = client.post(
        f"/api/v1/queue/entry/{entry.id}/no-show",
        headers=_doctor_headers(client, actor_user),
    )

    assert actor_doctor.id != other_doctor.id
    assert response.status_code == 403
    db_session.refresh(entry)
    assert entry.status == "waiting"


@pytest.mark.integration
def test_doctor_cannot_update_other_doctor_online_entry(
    client,
    db_session,
) -> None:
    actor_user, actor_doctor = _create_queue_doctor(db_session, label="actor_update")
    _other_user, other_doctor = _create_queue_doctor(db_session, label="other_update")
    entry = _create_queue_entry_for_doctor(db_session, doctor=other_doctor)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/update",
        headers=_doctor_headers(client, actor_user),
        json={"patient_name": "Tampered Patient"},
    )

    assert actor_doctor.id != other_doctor.id
    assert response.status_code == 403
    db_session.refresh(entry)
    assert entry.patient_name == "Guarded Patient"


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_visit_confirmation_context")
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
    linked_service = (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == linked_visit.id)
        .one()
    )
    assert linked_service.duration_minutes_snapshot == test_service.duration_minutes


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

    other_queue_time = datetime(2026, 5, 31, 7, 0, tzinfo=UTC)
    current_queue_time = datetime(2026, 5, 31, 10, 0, tzinfo=UTC)
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
    wrong_link_sibling = OnlineQueueEntry(
        queue_id=test_daily_queue.id, number=82, patient_id=test_patient.id,
        visit_id=other_visit.id, source="online", status="waiting",
        queue_time=current_queue_time, services=json.dumps([]),
    )
    other_charge = VisitService(
        visit_id=other_visit.id, service_id=test_service.id, name="SYNTHETIC-Other charge",
        qty=2, price=Decimal("125.00"), currency="UZS",
    )
    db_session.add_all([other_entry, current_entry, wrong_link_sibling, other_charge])
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
    assert (
        current_services[0]["queue_time"]
        == current_queue_time.replace(tzinfo=None).isoformat()
    )
    assert current_services[0]["queue_time"] != other_queue_time.isoformat()
    assert other_services[0]["queue_time"] == other_queue_time.isoformat()
    db_session.refresh(wrong_link_sibling)
    assert json.loads(wrong_link_sibling.services) == []
    assert wrong_link_sibling.total_amount in (None, 0)


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
        queue_time=datetime(2026, 5, 31, 9, 30, tzinfo=UTC),
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
    existing_queue_time = datetime(2026, 5, 31, 9, 0, tzinfo=UTC)
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
        phone="+998900000121",
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        queue_time=datetime(2026, 5, 31, 9, 5, tzinfo=UTC),
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


@pytest.fixture
def legacy_service_cancellation_records(
    db_session, test_doctor, test_patient, test_service,
):
    queue = DailyQueue(
        day=clinic_today(db_session), specialist_id=test_doctor.id, queue_tag="cardiology_common", active=True,
    )
    first_encounter = Encounter(patient_id=test_patient.id, provenance="new")
    second_encounter = Encounter(patient_id=test_patient.id, provenance="new")
    db_session.add_all([queue, first_encounter, second_encounter])
    db_session.flush()

    cancelled = {
        "service_id": test_service.id, "name": "SYNTHETIC-Cancellable service", "price": 40000, "quantity": 1,
    }
    retained = {
        "service_id": test_service.id + 1, "name": "SYNTHETIC-Retained service", "price": 5000, "quantity": 1,
    }
    selected = OnlineQueueEntry(
        queue_id=queue.id, number=91, patient_id=test_patient.id, encounter_id=first_encounter.id,
        source="online", status="waiting", total_amount=45000, services=json.dumps([cancelled, retained]),
    )
    separate = OnlineQueueEntry(
        queue_id=queue.id, number=92, patient_id=test_patient.id, encounter_id=second_encounter.id,
        source="online", status="waiting", total_amount=40000, services=json.dumps([cancelled]),
    )
    db_session.add_all([selected, separate])
    db_session.commit()
    return selected, separate


@pytest.mark.integration
@pytest.mark.parametrize(("storage", "price", "quantity"), (
    ("serialized", 5000, 1), ("array", 5000, 1), ("double-encoded", 5000, 1),
    ("serialized", 5000, 2), ("array", 2500.25, 2),
))
def test_qr_service_cancellation_records_one_audit_for_the_addressed_ticket(
    client, db_session, registrar_auth_headers, registrar_user,
    legacy_service_cancellation_records, test_service, storage, price, quantity,
):
    selected, separate = legacy_service_cancellation_records
    services = json.loads(selected.services)
    services[1].update(price=price, quantity=quantity)
    if storage == "array":
        selected.services = services
    elif storage == "double-encoded":
        selected.services = json.dumps(json.dumps(services))
    else:
        selected.services = json.dumps(services)
    db_session.commit()
    separate_snapshot = (separate.services, separate.total_amount, separate.encounter_id)
    path = f"/api/v1/queue/online-entry/{selected.id}/cancel-service"
    payload = {
        "service_id": test_service.id,
        "cancel_reason": "SYNTHETIC-Cancellation reason",
        "was_paid": True,
    }

    response = client.post(path, json=payload, headers=registrar_auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["cancelled_service"]["cancelled_by"] == registrar_user.id
    assert response.json()["new_total_amount"] == 5000
    repeat = client.post(path, json=payload, headers=registrar_auth_headers)
    assert repeat.status_code == 404, repeat.text

    db_session.expire_all()
    assert selected.total_amount == 5000
    cancelled, retained = json.loads(selected.services)
    assert cancelled["cancelled"] is True
    assert cancelled["cancel_reason"] == payload["cancel_reason"]
    assert cancelled["was_paid_before_cancel"] is True
    assert retained.get("cancelled") is not True
    assert (separate.services, separate.total_amount, separate.encounter_id) == separate_snapshot
    audit = db_session.query(UserAuditLog).filter_by(
        action="CANCEL_SERVICE", resource_type="online_queue_entries", resource_id=selected.id,
    ).one()
    assert audit.user_id == registrar_user.id
    assert audit.request_id
    assert audit.old_values == {"service_id": test_service.id, "cancelled": False, "total_amount": 45000}
    assert audit.new_values == {"service_id": test_service.id, "cancelled": True, "total_amount": 5000}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("issue", "expected_status"),
    (
        ("audit-unavailable", 500), ("audit-insert-failure", 500), ("inactive-staff", 403), ("different-doctor", 403),
        ("linked-visit", 409), ("unreconciled-total", 409),
    ),
)
def test_qr_service_cancellation_leaves_the_amount_and_service_on_rejection(
    client, db_session, registrar_auth_headers, registrar_user, legacy_service_cancellation_records,
    test_service, monkeypatch, request, issue, expected_status,
):
    selected, separate = legacy_service_cancellation_records
    headers = registrar_auth_headers
    if issue == "audit-unavailable":
        monkeypatch.setattr(_online_entries, "log_critical_change", lambda **kwargs: None)
    elif issue == "audit-insert-failure":
        log_change = _online_entries.log_critical_change

        def break_audit_insert(**kwargs):
            audit = log_change(**kwargs)
            audit.action = None
            return audit

        monkeypatch.setattr(_online_entries, "log_critical_change", break_audit_insert)
    elif issue == "inactive-staff":
        registrar_user.is_active = False
        db_session.commit()
    elif issue == "different-doctor":
        other_doctor, _ = _create_queue_doctor(db_session, label="cancel_other")
        headers = _doctor_headers(client, other_doctor)
    elif issue == "linked-visit":
        selected.visit_id = request.getfixturevalue("test_visit").id
        db_session.commit()
    elif issue == "unreconciled-total":
        selected.total_amount = 44000
        db_session.commit()

    snapshots = [(entry.services, entry.total_amount, entry.visit_id) for entry in (selected, separate)]
    response = client.post(
        f"/api/v1/queue/online-entry/{selected.id}/cancel-service", headers=headers,
        json={"service_id": test_service.id, "cancel_reason": "SYNTHETIC-Rejected cancellation"},
    )
    assert response.status_code == expected_status, response.text
    db_session.expire_all()
    assert [(entry.services, entry.total_amount, entry.visit_id) for entry in (selected, separate)] == snapshots
    assert db_session.query(UserAuditLog).filter_by(
        action="CANCEL_SERVICE", resource_type="online_queue_entries", resource_id=selected.id,
    ).count() == 0


@pytest.mark.integration
def test_full_update_frontend_aggregated_ids_ignore_unrelated_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_service,
):
    unrelated_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=25,
        patient_id=None,
        patient_name="Unrelated Queue",
        phone=None,
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        queue_time=datetime(2026, 5, 31, 9, 0, tzinfo=UTC),
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
        number=26,
        patient_id=None,
        patient_name="Current Queue",
        phone=None,
        visit_id=None,
        session_id=None,
        source="online",
        status="waiting",
        queue_time=datetime(2026, 5, 31, 9, 5, tzinfo=UTC),
        services=json.dumps([], ensure_ascii=False),
    )
    db_session.add_all([unrelated_entry, current_entry])
    db_session.commit()
    db_session.refresh(unrelated_entry)
    db_session.refresh(current_entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{current_entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": "Current Queue",
                "birth_year": 1990,
                "address": "Queue Street",
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": False,
            "aggregated_ids": [unrelated_entry.id, current_entry.id],
        },
    )

    assert response.status_code == 200, response.text

    db_session.refresh(current_entry)
    db_session.refresh(unrelated_entry)
    current_services = json.loads(current_entry.services)
    unrelated_services = json.loads(unrelated_entry.services)
    assert [service["service_id"] for service in current_services] == [test_service.id]
    assert [service["service_id"] for service in unrelated_services] == [
        test_service.id
    ]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("catalog_currency", "fail_after_staging", "expected_status"),
    [("USD", False, 200), (None, False, 409), ("USD", True, 500)],
    ids=["known-currency", "unknown-currency", "write-failure"],
)
def test_first_qr_fill_records_the_catalog_currency(
    client, db_session, registrar_auth_headers, test_patient, test_service, test_daily_queue,
    monkeypatch, catalog_currency, fail_after_staging, expected_status,
):
    test_service.currency = catalog_currency
    test_service.price = Decimal("123.45")
    test_service.is_consultation = True
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=11,
        queue_time=datetime.now(UTC),
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    entry_id = entry.id

    if fail_after_staging:
        from app.services.qr_queue_service import QRQueueService

        create_visit = QRQueueService._create_visit_for_qr

        def fail_create(self, **kwargs):
            create_visit(self, **kwargs)
            raise RuntimeError("synthetic failure after staging the visit")

        monkeypatch.setattr(QRQueueService, "_create_visit_for_qr", fail_create)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry_id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": False,
        },
    )

    assert response.status_code == expected_status, response.text
    db_session.refresh(entry)
    if expected_status != 200:
        assert entry.visit_id is None
        assert db_session.query(Visit).filter_by(patient_id=test_patient.id).count() == 0
        return

    line = db_session.query(VisitService).filter_by(visit_id=entry.visit_id).one()
    assert line.currency == catalog_currency
    assert line.price == Decimal("123.45")


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_visit_confirmation_context")
@pytest.mark.parametrize(
    "evidence",
    (
        "direct-paid", "direct-processing", "grouped-paid", "invoice-paid",
        "invoice-pending", "invoice-processing", "provider-reservation", "legacy-debit", "confirmed",
        "served", "none", "write-failure",
    ),
)
def test_qr_all_free_protects_financial_history_before_editing(
    client,
    db_session,
    registrar_auth_headers,
    admin_user,
    test_daily_queue,
    test_patient,
    test_doctor,
    test_service,
    evidence,
    monkeypatch,
):
    price = Decimal("100000.25")
    test_service.price = price
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=test_daily_queue.day,
        visit_time="10:30",
        status="confirmed" if evidence == "confirmed" else "open",
        confirmed_at=datetime.now(UTC) if evidence == "confirmed" else None,
        discount_mode="none",
        approval_status="approved",
        department="cardiology",
        confirmation_context_epoch=1,
    )
    db_session.add(visit)
    db_session.flush()
    original_line = VisitService(
        visit_id=visit.id,
        service_id=test_service.id,
        code=test_service.code,
        name="SYNTHETIC-Original QR service",
        qty=1,
        price=price,
        currency="UZS",
    )
    db_session.add(original_line)

    if evidence.startswith("invoice-"):
        invoice = PaymentInvoice(
            patient_id=test_patient.id, total_amount=price, currency="UZS",
            status=evidence.removeprefix("invoice-"), payment_method="cash",
        )
        db_session.add(invoice)
        db_session.flush()
        db_session.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=price))
    elif evidence == "legacy-debit":
        deposit = PatientDeposit(patient_id=test_patient.id, balance=Decimal("0"), currency="UZS")
        db_session.add(deposit)
        db_session.flush()
        db_session.add(DepositTransaction(
            deposit_id=deposit.id, visit_id=visit.id, transaction_type="debit", amount=price,
            balance_after=Decimal("0"), description="SYNTHETIC-Historical visit debit",
        ))
    elif evidence == "provider-reservation":
        attempt = ProviderAttempt(
            public_id=str(uuid4()), target_kind="payment", payment_id_snapshot=1,
            actor_user_id_snapshot=1, provider="click", merchant_hash="a" * 64,
            order_ref="SYNTHETIC-QR-Reservation", fingerprint="b" * 64,
            amount_minor="10000000", currency="UZS", currency_exponent=2, status="prepared",
        )
        db_session.add(attempt)
        db_session.flush()
        reservation_visit = ProviderAttemptVisit(
            attempt_id=attempt.id, visit_id=visit.id, visit_id_snapshot=visit.id,
            patient_id_snapshot=test_patient.id, context_epoch=1, amount_minor="10000000",
        )
        db_session.add(reservation_visit)
        db_session.flush()
        db_session.add(ProviderActiveVisitReservation(
            visit_id=visit.id, attempt_id=attempt.id, attempt_visit_id=reservation_visit.id,
        ))
    elif evidence not in {"confirmed", "served", "none", "write-failure"}:
        primary_visit = visit
        if evidence == "grouped-paid":
            primary_visit = Visit(
                patient_id=test_patient.id, doctor_id=test_doctor.id, visit_date=visit.visit_date,
                status="open", confirmation_context_epoch=1,
            )
            db_session.add(primary_visit)
            db_session.flush()
        payment = Payment(
            visit_id=primary_visit.id, amount=price, currency="UZS", method="cash",
            status=evidence.rsplit("-", 1)[1], receipt_no="SYNTHETIC-QR-Receipt",
        )
        db_session.add(payment)
        db_session.flush()
        if evidence == "grouped-paid":
            db_session.add(PaymentVisit(payment_id=payment.id, visit_id=visit.id, amount=price))

    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=31,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        visit_id=visit.id,
        queue_time=datetime.now(UTC),
        source="online",
        status="served" if evidence == "served" else "waiting",
        discount_mode="none",
        total_amount=int(price),
        services=[{"service_id": test_service.id, "price": int(price), "quantity": 1}],
    )
    db_session.add(entry)
    db_session.commit()
    line_id = original_line.id
    entry_snapshot = (
        entry.patient_name, entry.visit_id, entry.encounter_id, entry.discount_mode, entry.total_amount, entry.services,
    )

    if evidence == "write-failure":
        stage_request = AllFreeRequestService.stage_request

        def fail_after_flush(self, **kwargs):
            stage_request(self, **kwargs)
            raise RuntimeError("SYNTHETIC-QR approval save failure")

        monkeypatch.setattr(AllFreeRequestService, "stage_request", fail_after_flush)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {"patient_name": "SYNTHETIC-Changed QR name"},
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 2}],
            "all_free": True,
        },
    )

    db_session.refresh(entry)
    db_session.refresh(visit)
    if evidence == "none":
        assert response.status_code == 200, response.text
        assert Decimal(str(response.json()["entry"]["total_amount"])) == 2 * price
        assert entry.visit_id == visit.id and entry.encounter_id == visit.encounter_id
        assert (visit.status, visit.approval_status, visit.confirmation_token) == ("pending_confirmation", "pending", None)
        assert db_session.query(AllFreeRequest).filter_by(visit_id=visit.id).one().baseline_total == 2 * price
        with pytest.raises(HTTPException) as payment:
            PaymentInvariantService(db_session).check_payment_allowed(visit.id, 2 * price)
        with pytest.raises(HTTPException) as confirmation:
            VisitLifecycleService(db_session).confirm_visit(visit.id, admin_user)
        for rejected in (payment, confirmation):
            assert rejected.value.status_code == 409
            assert rejected.value.detail == ALL_FREE_DECISION_REQUIRED
        assert db_session.query(Payment.id).filter_by(visit_id=visit.id).first() is None
        return

    assert response.status_code == (500 if evidence == "write-failure" else 409), response.text
    assert (
        entry.patient_name, entry.visit_id, entry.encounter_id, entry.discount_mode, entry.total_amount, entry.services,
    ) == entry_snapshot
    assert (visit.discount_mode, visit.approval_status, visit.department, visit.doctor_id) == (
        "none", "approved", "cardiology", test_doctor.id,
    )
    stored = db_session.query(VisitService).filter_by(visit_id=visit.id).one()
    assert (stored.id, stored.qty, stored.price, stored.currency) == (line_id, 1, price, "UZS")
    assert db_session.query(AllFreeRequest.id).filter_by(visit_id=visit.id).first() is None
    assert db_session.query(AuditLog.id).filter_by(action="all_free_requested").first() is None


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_visit_confirmation_context")
@pytest.mark.parametrize(("action", "approval_status"), (
    (None, "pending"), ("approve", "approved"), ("reject", "rejected"),
))
def test_qr_all_free_worklist_displays_the_decision_and_exact_ticket_prices(
    client, db_session, registrar_auth_headers, admin_auth_headers,
    test_patient, test_doctor, test_service, action, approval_status,
):
    day = clinic_today(db_session)
    primary_queue = DailyQueue(
        day=day, specialist_id=test_doctor.id, queue_tag="cardiology", active=True,
    )
    secondary_queue = DailyQueue(
        day=day, specialist_id=test_doctor.id, queue_tag="synthetic-approval-aux", active=True,
    )
    test_service.price = Decimal("100000.25")
    test_service.is_consultation = True
    test_service.queue_tag = "cardiology"
    secondary_service = Service(
        code="SYNTHETIC-AF-AUX", name="SYNTHETIC-QR additional service", price=Decimal("55.47"),
        currency="UZS", queue_tag=secondary_queue.queue_tag, active=True, requires_doctor=False,
    )
    db_session.add_all([primary_queue, secondary_queue, secondary_service])
    db_session.flush()
    primary_ticket = OnlineQueueEntry(
        queue_id=primary_queue.id, patient_id=test_patient.id, number=21,
        queue_time=datetime.now(UTC), source="online", status="waiting",
    )
    db_session.add(primary_ticket)
    db_session.commit()

    staged = client.put(
        f"/api/v1/queue/online-entry/{primary_ticket.id}/full-update", headers=registrar_auth_headers,
        json={"patient_data": {}, "visit_type": "paid", "discount_mode": "all_free", "services": [
            {"service_id": test_service.id, "quantity": 2},
            {"service_id": secondary_service.id, "quantity": 3},
        ]},
    )
    assert staged.status_code == 200, staged.text
    visit_id = staged.json()["entry"]["visit_id"]
    secondary_ticket = db_session.query(OnlineQueueEntry).filter_by(
        queue_id=secondary_queue.id, visit_id=visit_id,
    ).one()
    if action is not None:
        decision = client.post(
            "/api/v1/admin/all-free-approve", headers=admin_auth_headers,
            json={"visit_id": visit_id, "action": action},
        )
        assert decision.status_code == 200, decision.text

    for ticket, service in ((primary_ticket, test_service), (secondary_ticket, secondary_service)):
        db_session.refresh(ticket)
        snapshot = (ticket.visit_id, ticket.services, ticket.total_amount)
        blocked = client.put(
            f"/api/v1/queue/online-entry/{ticket.id}/full-update", headers=registrar_auth_headers,
            json={"patient_data": {}, "visit_type": "paid", "discount_mode": "none", "services": []},
        )
        assert blocked.status_code == 409, blocked.text
        cancellation = client.post(
            f"/api/v1/queue/online-entry/{ticket.id}/cancel-service", headers=registrar_auth_headers,
            json={"service_id": service.id, "cancel_reason": "SYNTHETIC-Linked visit"},
        )
        assert cancellation.status_code == 409, cancellation.text
        db_session.refresh(ticket)
        assert (ticket.visit_id, ticket.services, ticket.total_amount) == snapshot

    worklist = client.get(
        "/api/v1/registrar/queues/today", headers=admin_auth_headers, params={"target_date": day.isoformat()},
    )
    assert worklist.status_code == 200, worklist.text
    rows = {
        row["queue_entry_id"]: row
        for queue in worklist.json()["queues"] for row in queue["entries"]
        if row["visit_id"] == visit_id
    }
    assert set(rows) == {primary_ticket.id, secondary_ticket.id}
    for ticket, service, quantity in ((primary_ticket, test_service, 2), (secondary_ticket, secondary_service, 3)):
        row = rows[ticket.id]
        expected_unit = Decimal("0.00") if action == "approve" else service.price
        assert row["approval_status"] == approval_status
        assert row["daily_queue_id"] == ticket.queue_id
        assert Decimal(str(row["cost"])) == quantity * expected_unit
        assert [(line["id"], line["quantity"], Decimal(str(line["price"]))) for line in row["service_details"]] == [
            (service.id, quantity, expected_unit),
        ]
        if action is None:
            assert row["can_mark_paid"] is False
        elif action == "reject":
            assert row["can_mark_paid"] is True


@pytest.mark.integration
def test_full_update_rejects_zero_quantity_before_quote_revalidation(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_service,
    test_doctor,
    test_daily_queue,
):
    """Codex R9 #3095 (P2): the documented full-update API accepts a loose
    list[dict]. A client submitting numeric quantity: 0 used to pass token
    revalidation (0 coerced to 1 there) while the mutation read the original
    zero — the row was saved with quantity zero and charged 0 against a
    one-unit quote. The command itself must be normalized/validated BEFORE
    the token check: quantity < 1 is a loud 400 and nothing is persisted."""
    queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag=f"zero-qty-{test_doctor.id}",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=9,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
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
            "services": [
                {"service_id": test_service.id, "quantity": 0},
                {"service_id": test_service.id, "quantity": 1},
            ],
            "all_free": False,
        },
    )

    assert response.status_code == 400, response.text
    assert "не меньше 1" in response.json()["detail"]
    # Nothing persisted: the entry is untouched by the rejected command
    db_session.expire_all()
    fresh = (
        db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry.id).one()
    )
    assert fresh.visit_id is None
    visits = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()
    assert visits == 0, "a rejected command must not create visits"


@pytest.mark.integration
def test_full_update_non_numeric_quantity_rejected(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_service,
    test_doctor,
):
    """Non-numeric quantity is a loud 400, not a silent coercion — the same
    normalization guards both the token check and the mutation."""
    queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag=f"zero-qty-bad-{test_doctor.id}",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=10,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": "abc"}],
            "all_free": False,
        },
    )

    assert response.status_code == 400, response.text
    assert "Некорректное количество" in response.json()["detail"]
