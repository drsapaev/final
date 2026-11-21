"""Test decision contention and audit rollback with a restricted PostgreSQL login."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.v1.endpoints.registrar_wizard import _cart
from app.models.all_free_request import AllFreeRequest, AllFreeRequestEvent
from app.models.audit import AuditLog
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.all_free_request_service import AllFreeRequestService
from app.services.patient_subject_lock import lock_patient_subject
from app.services.profile_contact_security import capture_profile_bearer
from tests.conftest import mint_access_token
from tests.integration.test_registrar_benefit_decision_pg import (
    RUNTIME,
    benefit_client,  # noqa: F401
    configured_benefit_db,  # noqa: F401
)

pytestmark = pytest.mark.integration

BASELINE = Decimal("25.40")
APPROVAL_URL = "/api/v1/admin/all-free-approve"


@pytest.fixture(scope="module")
def decision_engines(configured_benefit_db):
    admin, runtime = configured_benefit_db
    with admin.begin() as connection:
        privileges_by_table = {
            "visits": (
                "UPDATE (approval_status, notes, updated_at, confirmation_context_epoch, "
                "confirmation_token, confirmation_expires_at, reminder_sent_at, reminder_generation)"
            ),
            "visit_services": "UPDATE (price)",
            "encounters": "UPDATE (id)",
            "audit_logs": "INSERT",
            "appointments": "SELECT",
            "clinic_settings": "SELECT",
            "emr_records": "SELECT",
        }
        for table, privileges in privileges_by_table.items():
            connection.exec_driver_sql(f"GRANT {privileges} ON {table} TO {RUNTIME}")
            rls = connection.exec_driver_sql(
                f"SELECT relrowsecurity FROM pg_class WHERE oid='{table}'::regclass"
            ).scalar_one()
            if rls:
                command = privileges.split()[0]
                clause = {
                    "INSERT": "WITH CHECK (true)",
                    "UPDATE": "USING (true) WITH CHECK (true)",
                    "SELECT": "USING (true)",
                }[command]
                connection.exec_driver_sql(
                    f"CREATE POLICY synthetic_decision_runtime ON {table} FOR {command} TO {RUNTIME} {clause}"
                )
        connection.exec_driver_sql(f"GRANT SELECT (id) ON audit_logs TO {RUNTIME}")
        connection.exec_driver_sql(f"GRANT USAGE ON SEQUENCE audit_logs_id_seq TO {RUNTIME}")
        if connection.exec_driver_sql(
            "SELECT relrowsecurity FROM pg_class WHERE oid='audit_logs'::regclass"
        ).scalar_one():
            connection.exec_driver_sql(
                f"CREATE POLICY synthetic_decision_audit_id ON audit_logs FOR SELECT TO {RUNTIME} USING (true)"
            )
    with runtime.connect() as connection:
        confirmation_privileges = connection.exec_driver_sql("""
            SELECT pg_catalog.has_sequence_privilege('public.visit_confirmation_generation_seq','USAGE'),
                   pg_catalog.has_sequence_privilege('public.visit_confirmation_generation_seq','SELECT, UPDATE, USAGE WITH GRANT OPTION')
        """).one()
        assert tuple(confirmation_privileges) == (True, False)
    return admin, runtime


@pytest.fixture
def approval_case(decision_engines, benefit_client):
    admin, runtime = decision_engines
    suffix = uuid4().hex[:12]
    with Session(admin, expire_on_commit=False) as db:
        actors = [
            User(username=f"synthetic-all-free-{suffix}-{i}", hashed_password="!", role="Admin", is_active=True)
            for i in range(2)
        ]
        patient = Patient(first_name="SYNTHETIC", last_name=f"ALL-FREE-{suffix}", is_deleted=False)
        service = Service(
            code=f"SAF-{suffix}", name="Synthetic price line", price=BASELINE, currency="UZS", active=True
        )
        db.add_all([*actors, patient, service])
        db.flush()
        encounter = Encounter(patient_id=patient.id, provenance="new")
        db.add(encounter)
        db.flush()
        visit = Visit(
            patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2030, 1, 1),
            status="pending_confirmation", discount_mode="all_free", approval_status="pending",
            source="desk", notes="Synthetic original notes",
        )
        db.add(visit)
        db.flush()
        db.add(VisitService(visit_id=visit.id, service_id=service.id, name=service.name, qty=1, price=BASELINE, currency="UZS"))
        db.flush()
        db.refresh(visit)
        db.commit()
        headers = [{"Authorization": f"Bearer {mint_access_token(actor)}"} for actor in actors]
        request = Request({
            "type": "http",
            "headers": [(b"authorization", headers[0]["Authorization"].encode("ascii"))],
        })
        bearer = capture_profile_bearer(request, actors[0])
    with Session(runtime, autoflush=False) as db:
        service = AllFreeRequestService(db)
        service.lock_staging_inputs(bearer)
        assert lock_patient_subject(db, visit.patient_id)
        receipt = service.stage_request(
            visit_id=visit.id, expected_epoch=visit.confirmation_context_epoch, bearer=bearer,
            require_financial_group=True,
        )
        request_id = receipt.id
        db.commit()
    return admin, runtime, benefit_client, visit.id, request_id, headers, [actor.id for actor in actors]


def test_one_concurrent_decision_commits_one_audit_and_notification(approval_case, monkeypatch):
    admin, _runtime, client, visit_id, request_id, headers, actor_ids = approval_case
    notify = AsyncMock()
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", notify)
    aligned = Event()
    decision_ready = Barrier(2, action=aligned.set, timeout=10)
    decide_request = AllFreeRequestService._apply_unpublished_decision

    def align_pending_read(service, **kwargs):
        decision_ready.wait()
        return decide_request(service, **kwargs)

    monkeypatch.setattr(AllFreeRequestService, "_apply_unpublished_decision", align_pending_read)
    def decide(action, index):
        response = client.post(APPROVAL_URL, headers=headers[index], json={
            "visit_id": visit_id, "action": action, "rejection_reason": "Synthetic review reason",
        })
        return response.status_code, response.json(), actor_ids[index]

    with ThreadPoolExecutor(max_workers=2) as pool:
        approve = pool.submit(decide, "approve", 0)
        reject = pool.submit(decide, "reject", 1)
        winner, conflict = sorted(
            (approve.result(20), reject.result(20)), key=lambda result: result[0],
        )
    assert aligned.is_set()
    assert winner[0] == 200, winner[1]
    assert conflict[0] == 409, conflict[1]
    status = winner[1]["new_status"]
    assert status in {"approved", "rejected"}
    with Session(admin) as db:
        stored = db.get(AllFreeRequest, request_id)
        audit = db.scalars(select(AuditLog).filter_by(action="all_free_decided", entity_id=request_id)).one()
        decision = db.scalars(select(AllFreeRequestEvent).filter_by(request_id=request_id, event_type=status)).one()
        line = db.scalars(select(VisitService).filter_by(visit_id=visit_id)).one()
        assert db.get(Visit, visit_id).approval_status == stored.status == status
        assert line.price == (Decimal("0.00") if status == "approved" else BASELINE)
        assert stored.decided_by_user_id == audit.actor_user_id == decision.actor_user_id == winner[2]
        assert audit.payload == {"decision": status, "kind": "admin", "event_id": decision.id}
    notify.assert_awaited_once()


def test_failed_audit_rolls_back_decision_and_notes(approval_case, monkeypatch):
    admin, runtime, client, visit_id, request_id, headers, _actor_ids = approval_case
    notify = AsyncMock()
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", notify)
    attempted = Event()

    def fail_decision_audit(_conn, _cursor, statement, parameters, _context, _executemany):
        if statement.startswith("INSERT INTO audit_logs") and parameters.get("action") == "all_free_decided":
            attempted.set()
            raise RuntimeError("Synthetic audit failure")

    event.listen(runtime, "before_cursor_execute", fail_decision_audit)
    try:
        response = client.post(APPROVAL_URL, headers=headers[0], json={
            "visit_id": visit_id, "action": "reject", "rejection_reason": "Synthetic review reason",
        })
    finally:
        event.remove(runtime, "before_cursor_execute", fail_decision_audit)
    assert attempted.is_set(), response.text
    assert response.status_code == 500
    with Session(admin) as db:
        visit = db.get(Visit, visit_id)
        assert visit.approval_status == db.get(AllFreeRequest, request_id).status == "pending"
        assert visit.notes == "Synthetic original notes"
        assert db.scalars(select(VisitService.price).filter_by(visit_id=visit_id)).one() == BASELINE
        assert db.scalars(select(AllFreeRequestEvent.event_type).filter_by(request_id=request_id)).all() == ["requested"]
        assert db.scalars(select(AuditLog).filter_by(action="all_free_decided", entity_id=request_id)).first() is None
    notify.assert_not_awaited()
