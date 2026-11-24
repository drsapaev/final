"""PostgreSQL lock ordering for source-linked cashier payments."""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1.endpoints.cashier import _payments
from app.db.capability_namespace import capability_schema_name
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_staff_confirmation_guard_pg import (
    _module,
    isolated_staff_guard_postgres,
)


@pytest.fixture
def pg_cashier(monkeypatch):
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    ci_service = (
        os.getenv("CI", "").lower() == "true"
        and url.database == "clinicdb"
        and url.host in {"localhost", "127.0.0.1", "::1"}
    )
    if url.get_backend_name() != "postgresql" or not (
        ci_service or (url.database or "").startswith("clinic_test")
    ):
        pytest.skip("requires a disposable PostgreSQL database")

    with isolated_staff_guard_postgres(url, monkeypatch) as (owner, runtime, ids):
        root = Path(__file__).resolve().parents[3]
        with owner.begin() as db:
            quote = db.dialect.identifier_preparer.quote_identifier
            schema_name = db.dialect.default_schema_name
            schema = quote(schema_name)
            runtime_role = runtime.url.username
            table = f"{schema}.appointments"
            role = quote(runtime_role)
            private = quote(capability_schema_name(schema_name))
            migration = _module(root / "backend/alembic/versions/0123_reconciliation_fence.py")
            migration.op = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema_name}))
            migration.upgrade()
            db.exec_driver_sql(f"ALTER TABLE {schema}.click_callback_receipts ENABLE ROW LEVEL SECURITY")
            db.exec_driver_sql(f"ALTER TABLE {schema}.click_callback_receipts FORCE ROW LEVEL SECURITY")
            expected_owner = db.scalar(text("SELECT CURRENT_USER"))
            capability = db.scalar(text("""
                SELECT pg_catalog.pg_get_userbyid(proowner) FROM pg_catalog.pg_proc
                WHERE oid=pg_catalog.to_regprocedure(:signature)
            """), {"signature": f"{private}.financial_lock_rows(text,integer[])"})
            db.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            db.exec_driver_sql(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            # A row lock needs column UPDATE privilege. RLS allows locking
            # an appointment but refuses any update by this synthetic role.
            db.exec_driver_sql(f"GRANT SELECT, UPDATE (id) ON {table} TO {role}")
            db.exec_driver_sql(f"CREATE POLICY cashier_read ON {table} FOR SELECT TO {role} USING (true)")
            db.exec_driver_sql(
                f"CREATE POLICY cashier_lock ON {table} FOR UPDATE TO {role} USING (true) WITH CHECK (false)"
            )
        reconciliation = _module(root / "scripts/provision_reconciliation_fence_role.py")
        reconciliation.provision(
            owner, schema=schema_name, expected_owner=expected_owner,
            backend_role=runtime_role, capability_role=capability,
        )
        yield owner, runtime, ids


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


def _run_payment(engine, visit_id, appointment_id, actor_id, start=None):
    with Session(engine) as db:
        request = _payments.CreatePaymentRequest(
            visit_id=visit_id, appointment_id=appointment_id, amount=1, method='card'
        )
        if start is not None:
            start.wait(timeout=10)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(_payments.create_payment(request, db=db, current_user=SimpleNamespace(id=actor_id)))
        return exc.value.status_code, exc.value.detail


def test_cross_linked_cashier_requests_reject_without_deadlock(pg_cashier, monkeypatch):
    owner, runtime, ids = pg_cashier
    actor_id = ids["stage"]
    visits, appointments = _seed(owner)
    barrier = Barrier(2)
    resolved = []

    class ObservedService(CanonicalVisitService):
        def resolve_canonical_visit(self, appointment_id, **kwargs):
            resolved.append(appointment_id)
            return super().resolve_canonical_visit(appointment_id, **kwargs)

    monkeypatch.setattr(_payments, 'CanonicalVisitService', ObservedService)
    with ThreadPoolExecutor(max_workers=2) as pool:
        # Start both requests before the reconciliation mutex serializes them.
        futures = [pool.submit(_run_payment, runtime, visits[0], appointments[1], actor_id, barrier),
                   pool.submit(_run_payment, runtime, visits[1], appointments[0], actor_id, barrier)]
        assert [future.result(timeout=20) for future in futures] == [(409, "appointment_id does not match visit_id")] * 2
    assert sorted(resolved) == sorted(appointments)
    with Session(owner) as db:
        assert not db.query(Payment.id).filter(Payment.visit_id.in_(visits)).first()


def test_source_changed_after_hint_is_rechecked_by_cashier(pg_cashier, monkeypatch):
    owner, runtime, ids = pg_cashier
    actor_id = ids["stage"]
    visits, appointments = _seed(owner)
    have_hint = Event()
    proceed = Event()

    class PausedRepository(CanonicalVisitRepository):
        def read_payment_source_context(self, visit_id):
            assert visit_id == visits[0]
            have_hint.set()
            assert proceed.wait(timeout=10)
            return super().read_payment_source_context(visit_id)

    class PausedService(CanonicalVisitService):
        def __init__(self, db):
            super().__init__(db, repository=PausedRepository(db))

    monkeypatch.setattr(_payments, 'CanonicalVisitService', PausedService)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_payment, runtime, visits[0], appointments[0], actor_id)
        assert have_hint.wait(timeout=10)
        try:
            with Session(owner) as modifier:
                appointment = modifier.get(Appointment, appointments[0])
                appointment.source_visit_id = visits[1]
                modifier.commit()
        finally:
            proceed.set()
        assert future.result(timeout=20) == (409, "appointment_id does not match visit_id")
    with Session(owner) as db:
        assert not db.query(Payment.id).filter(Payment.visit_id.in_(visits)).first()


def test_grouped_source_resolution_uses_existing_locks_without_encounter_update(pg_cashier):
    owner, runtime, ids = pg_cashier
    with Session(owner, expire_on_commit=False) as db:
        visit = db.get(Visit, ids["visit"])
        appointment = Appointment(
            patient_id=visit.patient_id, encounter_id=visit.encounter_id,
            appointment_date=visit.visit_date, status="paid", source_visit_id=visit.id,
        )
        db.add(appointment)
        db.commit()
        appointment_id = appointment.id

    def resolve(db):
        return CanonicalVisitService(db).resolve_canonical_visit(
            appointment_id, create_if_missing=False, expected_visit_id=ids["visit"],
            require_payment_preflight=True,
        )

    with Session(runtime) as db:
        assert db.scalar(text("SELECT has_any_column_privilege(CURRENT_USER,'encounters','UPDATE')")) is False
        with pytest.raises(CanonicalVisitResolutionError) as unproven:
            resolve(db)
        assert unproven.value.status_code == 409
        PaymentInvariantService(db).preflight_payment_groups([ids["visit"]])
        assert resolve(db) == ids["visit"]


@pytest.mark.parametrize('mode,expected', [('source', 200), ('visit_only', 200), ('legacy', 409)])
def test_cashier_compatible_and_legacy_payment_paths(
    mode, expected, client, db_session, admin_auth_headers, test_patient, test_service, monkeypatch
):
    import app.ws.cashier_ws as cashier_ws
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
