"""PostgreSQL lock ordering for source-linked cashier payments."""
from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.v1.endpoints.cashier import _payments
from app.db.base import Base
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository
from app.services.canonical_visit_service import CanonicalVisitService


@pytest.fixture
def pg_engine():
    raw = os.environ.get('DATABASE_URL', '')
    if not raw or make_url(raw).get_backend_name() != 'postgresql':
        pytest.skip('requires disposable PostgreSQL')
    url = make_url(raw)
    if os.environ.get('CI', '').lower() != 'true' and not (url.database or '').startswith('clinic_test'):
        pytest.skip('requires an explicitly disposable clinic_test database')
    schema = 'test_cashier_source_' + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=15000'})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _seed(engine):
    with Session(engine, expire_on_commit=False) as db:
        patient = Patient(first_name='Synthetic', last_name='Patient')
        db.add(patient)
        db.flush()
        visits = [Visit(patient_id=patient.id, visit_date=date(2026, 4, 1),
                        visit_time='10:00', status='open') for _ in range(2)]
        db.add_all(visits)
        db.flush()
        appointments = [Appointment(patient_id=patient.id, appointment_date=date(2026, 4, 1),
                                    appointment_time='10:00', status='paid', source_visit_id=visit.id)
                        for visit in visits]
        db.add_all(appointments)
        db.commit()
        return [visit.id for visit in visits], [appointment.id for appointment in appointments]


def _run_payment(engine, visit_id, appointment_id):
    with Session(engine) as db:
        request = _payments.CreatePaymentRequest(
            visit_id=visit_id, appointment_id=appointment_id, amount=1, method='card'
        )
        with pytest.raises(HTTPException) as exc:
            asyncio.run(_payments.create_payment(request, db=db, current_user=SimpleNamespace(id=1)))
        return exc.value.status_code


def test_cross_linked_cashier_requests_reject_without_deadlock(pg_engine, monkeypatch):
    visits, appointments = _seed(pg_engine)
    barrier = Barrier(2)

    class BarrierService(CanonicalVisitService):
        def resolve_canonical_visit(self, *args, **kwargs):
            # The cashier endpoint has acquired its requested Visit by now.
            barrier.wait(timeout=10)
            return super().resolve_canonical_visit(*args, **kwargs)

    monkeypatch.setattr(_payments, 'CanonicalVisitService', BarrierService)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run_payment, pg_engine, visits[0], appointments[1]),
                   pool.submit(_run_payment, pg_engine, visits[1], appointments[0])]
        assert [future.result(timeout=20) for future in futures] == [409, 409]


def test_source_changed_after_hint_is_rechecked_by_cashier(pg_engine, monkeypatch):
    visits, appointments = _seed(pg_engine)
    have_hint = Event()
    proceed = Event()

    class PausedRepository(CanonicalVisitRepository):
        def lock_source_visit(self, visit_id):
            assert visit_id == visits[0]
            have_hint.set()
            assert proceed.wait(timeout=10)
            return super().lock_source_visit(visit_id)

    class PausedService(CanonicalVisitService):
        def __init__(self, db):
            super().__init__(db, repository=PausedRepository(db))

    monkeypatch.setattr(_payments, 'CanonicalVisitService', PausedService)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_payment, pg_engine, visits[0], appointments[0])
        assert have_hint.wait(timeout=10)
        try:
            with Session(pg_engine) as modifier:
                appointment = modifier.get(Appointment, appointments[0])
                appointment.source_visit_id = visits[1]
                modifier.commit()
        finally:
            proceed.set()
        assert future.result(timeout=20) == 409


@pytest.mark.parametrize('mode,expected', [('source', 200), ('visit_only', 200), ('legacy', 409)])
def test_cashier_compatible_and_legacy_payment_paths(
    mode, expected, client, db_session, admin_auth_headers, test_patient, test_service, monkeypatch
):
    import app.ws.cashier_ws as cashier_ws
    from app.models.payment import Payment
    from app.models.visit import VisitService

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(_payments, '_emit_payment_notification', noop)
    monkeypatch.setattr(cashier_ws, 'broadcast_cashier_update', noop)
    visit = Visit(patient_id=test_patient.id, visit_date=date(2026, 4, 1),
                  visit_time='10:00', status='open', discount_mode='none',
                  confirmation_context_epoch=1)
    db_session.add(visit)
    db_session.flush()
    db_session.add(VisitService(visit_id=visit.id, service_id=test_service.id,
                                name='Synthetic service', qty=1, price=100, currency='UZS'))
    appointment = Appointment(patient_id=test_patient.id, appointment_date=visit.visit_date,
                              appointment_time=visit.visit_time, status='paid',
                              source_visit_id=visit.id if mode == 'source' else None)
    db_session.add(appointment)
    db_session.commit()
    body = {'visit_id': visit.id, 'amount': 10, 'method': 'card'}
    if mode != 'visit_only':
        body['appointment_id'] = appointment.id
    response = client.post('/api/v1/cashier/payments', headers=admin_auth_headers, json=body)
    assert response.status_code == expected, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == (expected == 200)
