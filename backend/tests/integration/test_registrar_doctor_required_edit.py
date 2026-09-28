"""Doctor ownership gates on the registrar edit and QR full-update paths."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.crud.clinic import clinic_today
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit


def _doctor(
    db_session, *, specialty: str = "cardiology", active: bool = True
) -> Doctor:
    suffix = uuid4().hex[:10]
    user = User(
        username=f"edit_doctor_{suffix}",
        email=f"edit-doctor-{suffix}@test.local",
        full_name=f"Doctor {suffix}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(user_id=user.id, specialty=specialty, active=active)
    db_session.add(doctor)
    db_session.commit()
    return doctor


def _service(
    db_session,
    *,
    consultation: bool,
    requires_doctor: bool = False,
    queue_tag: str = "cardiology",
) -> Service:
    suffix = uuid4().hex[:8]
    service = Service(
        code=f"EDIT_{suffix}",
        service_code=f"E{suffix}",
        name=f"Test service {suffix}",
        price=Decimal("25000"),
        active=True,
        requires_doctor=requires_doctor,
        is_consultation=consultation,
        queue_tag=queue_tag,
        department_key="cardiology" if consultation else None,
    )
    db_session.add(service)
    db_session.commit()
    return service


def _edit_quote(
    client,
    headers,
    patient_id: int,
    day,
    service_id: int,
    doctor_id=None,
    quantity: int = 1,
):
    item = {"service_id": service_id, "quantity": quantity}
    if doctor_id is not None:
        item["specialist_id"] = doctor_id
    return client.post(
        "/api/v1/registrar/cart/quote",
        headers=headers,
        json={
            "items": [item],
            "pricing_mode": "edit_delta",
            "discount_mode": "none",
            "all_free": False,
            "patient_id": patient_id,
            "target_date": day.isoformat(),
            "preferred_entry_ids": [],
        },
    )


def _edit_save(
    client,
    headers,
    patient_id: int,
    day,
    service_id: int,
    doctor_id=None,
    token=None,
    quantity: int = 1,
):
    item = {"service_id": service_id, "quantity": quantity}
    if doctor_id is not None:
        item["specialist_id"] = doctor_id
    return client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=headers,
        json={
            "patient_id": patient_id,
            "target_date": day.isoformat(),
            "payment_method": "cash",
            "discount_mode": "none",
            "all_free": False,
            "services": [item],
            "existing_queue_entry_ids": [],
            "quote_token": token,
        },
    )


@pytest.mark.integration
def test_edit_delta_consultation_requires_named_doctor_in_quote_and_save(
    client, db_session, registrar_auth_headers, test_patient
):
    service = _service(db_session, consultation=True, requires_doctor=False)
    day = clinic_today(db_session)

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id
    )
    save = _edit_save(client, registrar_auth_headers, test_patient.id, day, service.id)

    assert quote.status_code == 400, quote.text
    assert save.status_code == 400, save.text
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
        == 0
    )


@pytest.mark.integration
def test_edit_delta_uses_selected_eligible_doctors_queue(
    client, db_session, registrar_auth_headers, test_patient
):
    doctor = _doctor(db_session)
    service = _service(db_session, consultation=True, requires_doctor=False)
    day = clinic_today(db_session)

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id, doctor.id
    )
    assert quote.status_code == 200, quote.text
    save = _edit_save(
        client,
        registrar_auth_headers,
        test_patient.id,
        day,
        service.id,
        doctor.id,
        quote.json()["quote_token"],
    )
    assert save.status_code == 200, save.text

    visit = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).one()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .one()
    )
    assert visit.doctor_id == doctor.id
    assert entry.queue.specialist_id == doctor.id
    assert entry.queue.queue_resource_id is None


@pytest.mark.integration
def test_edit_delta_rejects_inactive_doctor_before_write(
    client, db_session, registrar_auth_headers, test_patient
):
    doctor = _doctor(db_session, active=False)
    service = _service(db_session, consultation=True)
    day = clinic_today(db_session)

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id, doctor.id
    )
    save = _edit_save(
        client, registrar_auth_headers, test_patient.id, day, service.id, doctor.id
    )

    assert quote.status_code == 400, quote.text
    assert save.status_code == 400, save.text
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )


def _qr_entry(db_session, *, queue: DailyQueue, patient, services) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        queue_time=datetime.now(UTC),
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        source="online",
        status="waiting",
        services=json.dumps(services),
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def _full_update(client, headers, entry: OnlineQueueEntry, services):
    return client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=headers,
        json={
            "patient_data": {"patient_name": "Changed Test Patient"},
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [
                {"service_id": service.id, "quantity": 1} for service in services
            ],
            "all_free": False,
        },
    )


@pytest.mark.integration
def test_qr_full_update_keeps_source_doctor_when_same_tag_has_two_queues(
    client, db_session, registrar_auth_headers, test_patient
):
    other_doctor = _doctor(db_session)
    source_doctor = _doctor(db_session)
    day = clinic_today(db_session)
    other_queue = DailyQueue(
        day=day, specialist_id=other_doctor.id, queue_tag="cardiology", active=True
    )
    source_queue = DailyQueue(
        day=day, specialist_id=source_doctor.id, queue_tag="cardiology", active=True
    )
    db_session.add_all([other_queue, source_queue])
    db_session.commit()
    old_service = _service(db_session, consultation=False)
    consultation = _service(db_session, consultation=True, requires_doctor=False)
    source_entry = _qr_entry(
        db_session,
        queue=source_queue,
        patient=test_patient,
        services=[{"service_id": old_service.id, "quantity": 1, "price": 25000}],
    )

    response = _full_update(
        client, registrar_auth_headers, source_entry, [old_service, consultation]
    )

    assert response.status_code == 200, response.text
    added = [
        entry
        for entry in db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.id != source_entry.id,
        )
        .all()
        if any(
            item.get("service_id") == consultation.id
            for item in json.loads(entry.services)
        )
    ]
    assert len(added) == 1
    assert added[0].queue.specialist_id == source_doctor.id
    assert added[0].queue_id != other_queue.id


@pytest.mark.integration
def test_qr_first_fill_consultation_sets_visit_doctor(
    client, db_session, registrar_auth_headers, test_patient
):
    doctor = _doctor(db_session)
    day = clinic_today(db_session)
    queue = DailyQueue(
        day=day, specialist_id=doctor.id, queue_tag="cardiology", active=True
    )
    db_session.add(queue)
    db_session.commit()
    entry = _qr_entry(db_session, queue=queue, patient=test_patient, services=[])
    consultation = _service(db_session, consultation=True, requires_doctor=False)

    response = _full_update(client, registrar_auth_headers, entry, [consultation])

    assert response.status_code == 200, response.text
    db_session.refresh(entry)
    assert entry.visit_id is not None
    visit = db_session.query(Visit).filter(Visit.id == entry.visit_id).one()
    assert visit.doctor_id == doctor.id


@pytest.mark.integration
def test_qr_full_update_rejects_new_consultation_on_resource_queue_before_mutation(
    client, db_session, registrar_auth_headers, test_patient
):
    day = clinic_today(db_session)
    suffix = uuid4().hex[:8]
    resource = QueueResource(
        code=f"qr_{suffix}",
        queue_tag=f"lab_{suffix}",
        display_name="Test resource",
        active=True,
    )
    db_session.add(resource)
    db_session.flush()
    queue = DailyQueue(
        day=day,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    entry = _qr_entry(db_session, queue=queue, patient=test_patient, services=[])
    consultation = _service(db_session, consultation=True, requires_doctor=False)
    original_name = entry.patient_name

    response = _full_update(client, registrar_auth_headers, entry, [consultation])

    assert response.status_code == 409, response.text
    db_session.refresh(entry)
    assert entry.patient_name == original_name
    assert entry.services == "[]"
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
        == 1
    )


@pytest.mark.integration
def test_qr_full_update_does_not_copy_existing_doctor_consultation_to_resource(
    client, db_session, registrar_auth_headers, test_patient
):
    doctor = _doctor(db_session)
    consultation = _service(db_session, consultation=True)
    day = clinic_today(db_session)
    resource = QueueResource(
        code=f"qr_mixed_{uuid4().hex[:8]}",
        queue_tag=f"lab_mixed_{uuid4().hex[:8]}",
        display_name="Test resource",
        active=True,
    )
    db_session.add(resource)
    db_session.flush()
    doctor_queue = DailyQueue(
        day=day, specialist_id=doctor.id, queue_tag="cardiology", active=True
    )
    resource_queue = DailyQueue(
        day=day,
        queue_resource_id=resource.id,
        queue_tag=resource.queue_tag,
        active=True,
    )
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=doctor.id,
        visit_date=day,
        department="cardiology",
        status="open",
    )
    db_session.add_all([doctor_queue, resource_queue, visit])
    db_session.commit()
    doctor_entry = _qr_entry(
        db_session,
        queue=doctor_queue,
        patient=test_patient,
        services=[{"service_id": consultation.id, "quantity": 1, "price": 25000}],
    )
    resource_entry = _qr_entry(
        db_session, queue=resource_queue, patient=test_patient, services=[]
    )
    doctor_entry.visit_id = visit.id
    resource_entry.visit_id = visit.id
    db_session.commit()

    response = _full_update(
        client, registrar_auth_headers, resource_entry, [consultation]
    )

    assert response.status_code == 409, response.text
    db_session.refresh(resource_entry)
    db_session.refresh(doctor_entry)
    assert resource_entry.services == "[]"
    assert json.loads(doctor_entry.services)[0]["service_id"] == consultation.id


# ── PR #3438 owner-verdict P1 (round 3): resource-owned services in edit-delta ──
#
# The catalog of THIS PR classifies a non-consultation requires_doctor service
# whose queue_tag routes to an active QueueResource as resource-owned:
# doctor_selection_required=false, regular wizard surface, books WITHOUT a
# doctor into the resource queue (pinned for cart create in
# tests/test_registrar_resource_service_classification.py::
# test_k10_resource_service_books_without_doctor_into_resource_queue).
#
# The edit-delta addition guard treated the same service as doctor work and
# 409-rejected ("нельзя добавить в ресурсную очередь") exactly what the
# catalog offered — a read/write contract drift: the wizard's edit mode uses
# the same catalog, so a registrar could see the service, try to add it, and
# be rejected. The pins below restore parity with the cart write gate:
#
# - non-consultation + resource-owned → doctorless quote/save allowed, the
#   entry lands in the resource queue, an increase of an existing
#   resource-owned position bills only the delta;
# - the same service with a supplied doctor → 409 (decorative doctor,
#   the same fail-closed semantics as cart create);
# - consultation on a resource tag → 409 (ambiguous class, unchanged);
# - doctor-owned requires_doctor service → the doctor contract is unchanged.


def _resource_pair(db_session, *, consultation: bool) -> tuple[Service, QueueResource]:
    """A service on an ACTIVE registry resource tag.

    Non-consultation shape mirrors canonical K10 «ЭКГ»: requires_doctor=True,
    is_consultation=False, the tag has an active QueueResource row. The
    consultation shape keeps this file's convention (requires_doctor=False)
    and a cardiology department key.
    """
    suffix = uuid4().hex[:8]
    tag = f"res_{suffix}"
    service = Service(
        code=f"RS_{suffix}",
        service_code=f"RS{suffix}",
        name=f"ЭКГ {suffix}",
        price=Decimal("25000"),
        active=True,
        requires_doctor=not consultation,
        is_consultation=consultation,
        queue_tag=tag,
        department_key="cardiology" if consultation else "echokg",
    )
    resource = QueueResource(
        code=tag,
        queue_tag=tag,
        display_name="Тестовый ресурс",
        active=True,
    )
    db_session.add_all([service, resource])
    db_session.commit()
    db_session.refresh(service)
    db_session.refresh(resource)
    return service, resource


@pytest.mark.integration
def test_edit_delta_quote_resource_service_without_doctor_is_quoted(
    client, db_session, registrar_auth_headers, test_patient
):
    service, _resource = _resource_pair(db_session, consultation=False)
    day = clinic_today(db_session)

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id
    )

    assert quote.status_code == 200, quote.text
    assert quote.json()["quote_token"]


@pytest.mark.integration
def test_edit_delta_save_resource_service_without_doctor_books_into_resource_queue(
    client, db_session, registrar_auth_headers, test_patient
):
    service, resource = _resource_pair(db_session, consultation=False)
    day = clinic_today(db_session)

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id
    )
    assert quote.status_code == 200, quote.text
    save = _edit_save(
        client,
        registrar_auth_headers,
        test_patient.id,
        day,
        service.id,
        token=quote.json()["quote_token"],
    )
    assert save.status_code == 200, save.text

    visit = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).one()
    assert visit.doctor_id is None
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .one()
    )
    assert entry.queue.queue_resource_id == resource.id
    assert entry.queue.specialist_id is None


@pytest.mark.integration
def test_edit_delta_increases_existing_resource_owned_position(
    client, db_session, registrar_auth_headers, test_patient
):
    service, resource = _resource_pair(db_session, consultation=False)
    day = clinic_today(db_session)

    first_quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id
    )
    first_save = _edit_save(
        client,
        registrar_auth_headers,
        test_patient.id,
        day,
        service.id,
        token=first_quote.json()["quote_token"],
    )
    assert first_save.status_code == 200, first_save.text

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .one()
    )
    assert entry.queue.queue_resource_id == resource.id

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id, quantity=2
    )
    assert quote.status_code == 200, quote.text
    # only the INCREASE is billed: one extra unit at the catalog price
    assert Decimal(str(quote.json()["total_amount"])) == Decimal("25000")

    save = _edit_save(
        client,
        registrar_auth_headers,
        test_patient.id,
        day,
        service.id,
        quantity=2,
        token=quote.json()["quote_token"],
    )
    assert save.status_code == 200, save.text

    db_session.refresh(entry)
    raw_services = entry.services
    payloads = (
        raw_services if isinstance(raw_services, list) else json.loads(raw_services)
    )
    total_qty = sum(
        int(payload["quantity"])
        for payload in payloads
        if payload.get("service_id") == service.id
    )
    assert total_qty == 2
    # the position stays on the resource queue — no doctor-queue fork
    assert entry.queue.queue_resource_id == resource.id
    assert entry.queue.specialist_id is None


@pytest.mark.integration
def test_edit_delta_resource_service_with_doctor_fails_closed(
    client, db_session, registrar_auth_headers, test_patient
):
    service, _resource = _resource_pair(db_session, consultation=False)
    doctor = _doctor(db_session)
    day = clinic_today(db_session)

    before_visits = (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()
    )
    before_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
    )

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id, doctor.id
    )
    save = _edit_save(
        client, registrar_auth_headers, test_patient.id, day, service.id, doctor.id
    )

    assert quote.status_code == 409, quote.text
    assert save.status_code == 409, save.text
    assert "ресурс" in quote.json()["detail"]
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()
        == before_visits
    )
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
        == before_entries
    )


@pytest.mark.integration
def test_edit_delta_consultation_on_resource_tag_stays_rejected(
    client, db_session, registrar_auth_headers, test_patient
):
    service, _resource = _resource_pair(db_session, consultation=True)
    day = clinic_today(db_session)

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id
    )
    save = _edit_save(client, registrar_auth_headers, test_patient.id, day, service.id)

    assert quote.status_code == 409, quote.text
    assert save.status_code == 409, save.text
    assert "ресурс" in quote.json()["detail"]
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
        == 0
    )


@pytest.mark.integration
def test_edit_delta_doctor_owned_service_keeps_doctor_contract(
    client, db_session, registrar_auth_headers, test_patient
):
    doctor = _doctor(db_session)
    service = _service(db_session, consultation=False, requires_doctor=True)
    day = clinic_today(db_session)

    doctorless = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id
    )
    assert doctorless.status_code == 400, doctorless.text
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count() == 0
    )

    quote = _edit_quote(
        client, registrar_auth_headers, test_patient.id, day, service.id, doctor.id
    )
    assert quote.status_code == 200, quote.text
    save = _edit_save(
        client,
        registrar_auth_headers,
        test_patient.id,
        day,
        service.id,
        doctor.id,
        quote.json()["quote_token"],
    )
    assert save.status_code == 200, save.text

    visit = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).one()
    assert visit.doctor_id == doctor.id
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .one()
    )
    assert entry.queue.specialist_id == doctor.id
    assert entry.queue.queue_resource_id is None
