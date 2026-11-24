"""Synthetic HTTP checks for the transaction-scoped registrar encounter."""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from app.api.v1.endpoints.registrar_wizard import _cart as cart_module
from app.crud.clinic import clinic_today
from app.models.encounter import Encounter
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.morning_assignment import MorningAssignmentService
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration


@pytest.fixture
def clinic_day(db_session, monkeypatch):
    day = clinic_today(db_session)
    # Queue setup and the request share one date at the clinic's midnight.
    monkeypatch.setattr(cart_module, "clinic_today", lambda _db: day)
    return day


def _service(db):
    item = Service(code=f"EC-{uuid4().hex[:12]}", name="Synthetic encounter service", price=100,
                   duration_minutes=30, active=True, requires_doctor=False, is_consultation=False)
    db.add(item)
    db.commit()
    return item


def _headers(admin):
    return {"Authorization": f"Bearer {mint_access_token(admin)}"}


def _visit(service_id, day):
    return {"doctor_id": None, "visit_date": day.isoformat(), "department": "general",
            "services": [{"service_id": service_id, "quantity": 1}]}


def _payload(patient_id, visits):
    return {"patient_id": patient_id, "discount_mode": "none", "payment_method": "cash", "visits": visits}


def _counts(db, patient_id):
    return (
        db.query(Encounter).filter_by(patient_id=patient_id).count(),
        db.query(Visit).filter_by(patient_id=patient_id).count(),
        db.query(PaymentInvoice).filter_by(patient_id=patient_id).count(),
        db.query(PaymentInvoiceVisit).join(PaymentInvoice).filter(PaymentInvoice.patient_id == patient_id).count(),
        db.query(VisitService).join(Visit).filter(Visit.patient_id == patient_id).count(),
    )


def test_cart_groups_all_dates_but_not_another_cart(
    client, db_session, admin_user, test_patient, clinic_day
):
    service = _service(db_session)
    patient_id = test_patient.id
    future = clinic_day + timedelta(days=5)
    payload = _payload(patient_id, [_visit(service.id, future), _visit(service.id, future + timedelta(days=1))])
    payload.update(registrar_encounter_id_snapshot=999999, registrar_encounter_generation_snapshot=13)
    first = client.post("/api/v1/registrar/cart", json=payload, headers=_headers(admin_user))
    assert first.status_code == 200, first.text
    ids = first.json()["visit_ids"]
    assert len(ids) == 2
    visits = [db_session.get(Visit, visit_id) for visit_id in ids]
    assert all(v.patient_id == patient_id for v in visits)
    assert visits[0].encounter_id is not None
    assert visits[0].encounter_id == visits[1].encounter_id
    group = db_session.get(Encounter, visits[0].encounter_id)
    assert group.patient_id == patient_id and group.provenance == "new"
    invoice = db_session.get(PaymentInvoice, first.json()["invoice_id"])
    assert invoice.registrar_encounter_id_snapshot == group.id
    assert invoice.registrar_encounter_generation_snapshot == group.generation
    links = db_session.query(PaymentInvoiceVisit).filter_by(invoice_id=first.json()["invoice_id"]).all()
    assert {link.visit_id for link in links} == set(ids)

    second = client.post("/api/v1/registrar/cart", json=payload, headers=_headers(admin_user))
    assert second.status_code == 200, second.text
    new_visits = [db_session.get(Visit, vid) for vid in second.json()["visit_ids"]]
    assert new_visits[0].encounter_id == new_visits[1].encounter_id
    assert new_visits[0].encounter_id != group.id
    new_invoice = db_session.get(PaymentInvoice, second.json()["invoice_id"])
    assert new_invoice.registrar_encounter_id_snapshot == new_visits[0].encounter_id
    assert _counts(db_session, patient_id) == (2, 4, 2, 4, 4)


@pytest.mark.parametrize("change", ["generation", "invoice_link"])
def test_cart_rolls_back_if_membership_changes_after_invoice_origin(
    client, db_session, admin_user, test_patient, monkeypatch, change, clinic_day
):
    service = _service(db_session)

    def change_membership(self, visits, **_):
        if change == "generation":
            group = self.db.get(Encounter, visits[0].encounter_id)
            group.generation += 1
        else:
            self.db.flush()
            link = self.db.query(PaymentInvoiceVisit).filter_by(visit_id=visits[0].id).one()
            self.db.delete(link)
        self.db.flush()
        return {}

    monkeypatch.setattr(cart_module.RegistrarWizardQueueAssignmentService, "assign_same_day_queue_numbers", change_membership)
    before = _counts(db_session, test_patient.id)
    response = client.post(
        "/api/v1/registrar/cart", headers=_headers(admin_user),
        json=_payload(test_patient.id, [_visit(service.id, clinic_day + timedelta(days=1))]),
    )
    assert response.status_code == 409, response.text
    assert _counts(db_session, test_patient.id) == before


def test_idempotent_replay_does_not_create_another_group(
    client, db_session, admin_user, test_patient, clinic_day
):
    service = _service(db_session)
    payload = _payload(test_patient.id, [_visit(service.id, clinic_day + timedelta(days=1))])
    headers = _headers(admin_user) | {"Idempotency-Key": f"encounter-{uuid4()}"}
    first = client.post("/api/v1/registrar/cart", json=payload, headers=headers)
    second = client.post("/api/v1/registrar/cart", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    if second.status_code == 200:
        assert first.json()["visit_ids"] == second.json()["visit_ids"]
        assert first.json()["invoice_id"] == second.json()["invoice_id"]
    else:
        assert second.status_code == 409, second.text
        assert second.json()["code"] == "idempotency_reconciliation_required"
    assert _counts(db_session, test_patient.id) == (1, 1, 1, 1, 1)


def test_late_service_failure_rolls_back_encounter(
    client, db_session, admin_user, test_patient, clinic_day
):
    service = _service(db_session)
    day = clinic_day + timedelta(days=1)
    before = _counts(db_session, test_patient.id)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [_visit(service.id, day), _visit(999999999, day)]))
    assert response.status_code == 404, response.text
    assert _counts(db_session, test_patient.id) == before


def test_invoice_failure_rolls_back_encounter(
    client, db_session, admin_user, test_patient, monkeypatch, clinic_day
):
    service = _service(db_session)
    before = _counts(db_session, test_patient.id)
    def fail_invoice(*args, **kwargs):
        raise RuntimeError("synthetic invoice failure")
    monkeypatch.setattr(cart_module, "PaymentInvoice", fail_invoice)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [_visit(service.id, clinic_day + timedelta(days=1))]))
    assert response.status_code == 500, response.text
    assert _counts(db_session, test_patient.id) == before


def test_deep_queue_rollback_cannot_return_phantom_success(
    client, db_session, admin_user, test_patient, monkeypatch, clinic_day
):
    service = _service(db_session)
    patient_id = test_patient.id
    before = _counts(db_session, patient_id)
    monkeypatch.setattr(MorningAssignmentService, "_get_visit_queue_tags", lambda self, visit: {"synthetic"})
    called = []
    def rollback_then_fail(self, *args, **kwargs):
        called.append(True)
        self.db.rollback()
        raise RuntimeError("synthetic deep queue failure")
    monkeypatch.setattr(MorningAssignmentService, "prepare_wizard_queue_assignment", rollback_then_fail)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(patient_id, [_visit(service.id, clinic_day)]))
    assert called, response.text
    assert response.status_code >= 400, response.text
    assert _counts(db_session, patient_id) == before


def _queue_setup(db, service, day, tag=None):
    from app.models.online_queue import DailyQueue, QueueResource
    tag = tag or f"ec{uuid4().hex[:12]}"
    service.queue_tag = tag
    resource = QueueResource(code=f"R{uuid4().hex[:12]}", queue_tag=tag,
                             display_name="Synthetic resource", active=True)
    db.add(resource)
    db.flush()
    queue = DailyQueue(day=day, queue_resource_id=resource.id, queue_tag=tag, active=True)
    db.add(queue)
    db.commit()
    return queue


def test_same_day_cart_creates_ticket_for_its_encounter(
    client, db_session, admin_user, test_patient, clinic_day
):
    from app.models.online_queue import OnlineQueueEntry
    service = _service(db_session)
    queue = _queue_setup(db_session, service, clinic_day)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [_visit(service.id, clinic_day)]))
    assert response.status_code == 200, response.text
    visit = db_session.get(Visit, response.json()["visit_ids"][0])
    ticket = db_session.query(OnlineQueueEntry).filter_by(queue_id=queue.id, visit_id=visit.id).one()
    assert ticket.patient_id == visit.patient_id
    assert ticket.encounter_id == visit.encounter_id is not None


def test_same_day_cart_reuses_patient_ticket_for_its_encounter(
    client, db_session, admin_user, test_patient, clinic_day
):
    from app.models.online_queue import OnlineQueueEntry
    service = _service(db_session)
    queue = _queue_setup(db_session, service, clinic_day)
    ticket = OnlineQueueEntry(queue_id=queue.id, number=1, patient_id=test_patient.id,
                              source="online", status="waiting")
    db_session.add(ticket)
    db_session.commit()
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [_visit(service.id, clinic_day)]))
    assert response.status_code == 200, response.text
    visit = db_session.get(Visit, response.json()["visit_ids"][0])
    db_session.refresh(ticket)
    assert ticket.visit_id == visit.id and ticket.encounter_id == visit.encounter_id is not None
    assert db_session.query(OnlineQueueEntry).filter_by(queue_id=queue.id).count() == 1


def test_same_day_cart_rejects_ticket_from_another_encounter(
    client, db_session, admin_user, test_patient, clinic_day
):
    from app.models.online_queue import OnlineQueueEntry
    service = _service(db_session)
    queue = _queue_setup(db_session, service, clinic_day)
    previous = Encounter(patient_id=test_patient.id, provenance="new")
    db_session.add(previous)
    db_session.flush()
    ticket = OnlineQueueEntry(queue_id=queue.id, number=1, patient_id=test_patient.id,
                              encounter_id=previous.id, source="online", status="waiting")
    db_session.add(ticket)
    db_session.commit()
    before = _counts(db_session, test_patient.id)
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [_visit(service.id, clinic_day)]))
    assert response.status_code == 422, response.text
    db_session.refresh(ticket)
    assert ticket.visit_id is None and ticket.encounter_id == previous.id
    assert _counts(db_session, test_patient.id) == before


def test_anonymous_reused_ticket_does_not_gain_encounter_provenance(
    client, db_session, admin_user, test_patient, clinic_day
):
    from app.models.online_queue import OnlineQueueEntry
    service = _service(db_session)
    queue = _queue_setup(db_session, service, clinic_day)
    ticket = OnlineQueueEntry(queue_id=queue.id, number=1, patient_id=None,
                              phone=test_patient.phone, source="online", status="waiting")
    db_session.add(ticket)
    db_session.commit()
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [_visit(service.id, clinic_day)]))
    assert response.status_code == 200, response.text
    visit = db_session.get(Visit, response.json()["visit_ids"][0])
    db_session.refresh(ticket)
    assert ticket.patient_id == visit.patient_id and ticket.visit_id == visit.id
    assert ticket.encounter_id is None


def test_later_queue_failure_restores_reused_ticket_encounter(
    client, db_session, admin_user, test_patient, monkeypatch, clinic_day
):
    from app.models.online_queue import OnlineQueueEntry
    first_service, second_service = _service(db_session), _service(db_session)
    unique = uuid4().hex[:10]
    first_tag, second_tag = f"a{unique}", f"b{unique}"
    first_queue = _queue_setup(db_session, first_service, clinic_day, first_tag)
    _queue_setup(db_session, second_service, clinic_day, second_tag)
    ticket = OnlineQueueEntry(queue_id=first_queue.id, number=1, patient_id=test_patient.id,
                              source="online", status="waiting")
    db_session.add(ticket)
    db_session.commit()
    original = MorningAssignmentService.prepare_wizard_queue_assignment
    calls = []
    def fail_second(self, visit, queue_tag, *args, **kwargs):
        calls.append(queue_tag)
        if queue_tag == second_tag:
            # Ensure the first binding reached the database before failure.
            self.db.flush()
            raise RuntimeError("synthetic later direction failure")
        return original(self, visit, queue_tag, *args, **kwargs)
    monkeypatch.setattr(MorningAssignmentService, "prepare_wizard_queue_assignment", fail_second)
    payload_visit = _visit(first_service.id, clinic_day)
    payload_visit["services"].append({"service_id": second_service.id, "quantity": 1})
    response = client.post("/api/v1/registrar/cart", headers=_headers(admin_user),
                           json=_payload(test_patient.id, [payload_visit]))
    assert calls == [first_tag, second_tag], response.text
    assert response.status_code == 200, response.text
    db_session.refresh(ticket)
    assert ticket.patient_id == test_patient.id and ticket.visit_id is None and ticket.encounter_id is None
    assert db_session.query(OnlineQueueEntry).filter_by(queue_id=first_queue.id).count() == 1
