"""Registrar encounter behavior on a disposable, migrated PostgreSQL database."""
from __future__ import annotations

import os
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1.endpoints.registrar_wizard._cart import create_cart_appointments
from app.api.v1.endpoints.registrar_wizard._helpers import (
    CartRequest,
    ServiceItemRequest,
    VisitRequest,
)
from app.models.encounter import Encounter
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.services.morning_assignment import MorningAssignmentService

pytestmark = pytest.mark.integration


@pytest.fixture
def migrated_cart_session():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires a disposable clinic_test PostgreSQL database migrated through 0104")
    engine = create_engine(url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != "0104_encounters":
            pytest.skip("requires the actual 0104 migration")
        session = Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def _seed(db):
    suffix = uuid4().hex[:12]
    admin = User(username=f"encounter_{suffix}", hashed_password="!synthetic", role="Admin", is_active=True)
    patient = Patient(first_name="Synthetic", last_name=f"Patient{suffix}", is_deleted=False)
    service = Service(code=f"EC-{suffix}", name="Synthetic cart service", price=100,
                      duration_minutes=30, active=True, requires_doctor=False, is_consultation=False)
    db.add_all([admin, patient, service])
    db.commit()
    return admin, patient, service


def _cart(db, admin, patient, service, days):
    request = CartRequest(patient_id=patient.id, discount_mode="none", payment_method="cash", visits=[
        VisitRequest(doctor_id=None, visit_date=day, department="general", services=[
            ServiceItemRequest(service_id=service.id, quantity=1)
        ]) for day in days
    ])
    return create_cart_appointments(cart_data=request, db=db, current_user=SimpleNamespace(id=admin.id))


def test_migrated_cart_groups_visits_and_separates_registrations(migrated_cart_session):
    db = migrated_cart_session
    admin, patient, service = _seed(db)
    tomorrow = date.today() + timedelta(days=1)
    first = _cart(db, admin, patient, service, [tomorrow, tomorrow + timedelta(days=1)])
    second = _cart(db, admin, patient, service, [tomorrow])
    visits = [db.get(Visit, visit_id) for visit_id in first.visit_ids]
    other = db.get(Visit, second.visit_ids[0])
    assert visits[0].encounter_id == visits[1].encounter_id != other.encounter_id
    group = db.get(Encounter, visits[0].encounter_id)
    assert group.patient_id == patient.id and group.provenance == "new"


def test_migrated_deep_queue_rollback_cannot_return_phantom_success(migrated_cart_session, monkeypatch):
    db = migrated_cart_session
    admin, patient, service = _seed(db)
    patient_id = patient.id
    monkeypatch.setattr(MorningAssignmentService, "_get_visit_queue_tags", lambda self, visit: {"synthetic"})
    called = []
    def rollback_then_fail(self, *args, **kwargs):
        called.append(True)
        self.db.rollback()
        raise RuntimeError("synthetic deep queue failure")
    monkeypatch.setattr(MorningAssignmentService, "prepare_wizard_queue_assignment", rollback_then_fail)
    with pytest.raises(HTTPException) as exc:
        _cart(db, admin, patient, service, [date.today()])
    assert called and exc.value.status_code >= 400
    assert db.query(Visit).filter_by(patient_id=patient_id).count() == 0
    assert db.query(Encounter).filter_by(patient_id=patient_id).count() == 0


@pytest.mark.parametrize("reuse", [False, True])
def test_migrated_queue_entry_keeps_same_patient_and_encounter(migrated_cart_session, reuse):
    db = migrated_cart_session
    admin, patient, service = _seed(db)
    suffix = uuid4().hex[:12]
    service.queue_tag = f"ec{suffix}"
    resource = QueueResource(code=f"R{suffix}", queue_tag=service.queue_tag,
                             display_name="Synthetic resource", active=True)
    db.add(resource)
    db.flush()
    queue = DailyQueue(day=date.today(), queue_resource_id=resource.id,
                       queue_tag=service.queue_tag, active=True)
    db.add(queue)
    db.flush()
    if reuse:
        db.add(OnlineQueueEntry(queue_id=queue.id, number=1, patient_id=patient.id,
                                source="online", status="waiting"))
    db.commit()
    result = _cart(db, admin, patient, service, [date.today()])
    visit = db.get(Visit, result.visit_ids[0])
    ticket = db.query(OnlineQueueEntry).filter_by(queue_id=queue.id).one()
    assert ticket.patient_id == visit.patient_id
    assert ticket.visit_id == visit.id
    assert ticket.encounter_id == visit.encounter_id is not None
