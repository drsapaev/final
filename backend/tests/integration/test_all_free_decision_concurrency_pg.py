"""PostgreSQL checks for one All Free decision and its transaction audit."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.v1.endpoints.registrar_wizard import _cart
from app.db.base_class import Base
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit

pytestmark = pytest.mark.integration


@pytest.fixture
def approval_case():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "clinic_test"
    ):
        pytest.skip("requires an explicitly disposable clinic_test PostgreSQL database")

    schema = f"all_free_decision_{uuid4().hex}"
    schema_engine = create_engine(url)
    with schema_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=10000 -clock_timeout=8000"
        },
    )

    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            admins = [
                User(
                    username=f"synthetic_admin_{number}",
                    hashed_password="!fixture",
                    role="Admin",
                )
                for number in (1, 2)
            ]
            patient = Patient(first_name="Synthetic", last_name="Patient")
            db.add_all([*admins, patient])
            db.flush()
            visit = Visit(
                patient_id=patient.id,
                status="confirmed",
                discount_mode="all_free",
                approval_status="pending",
                visit_date=date(2030, 1, 1),
                source="desk",
                notes="Original notes",
            )
            db.add(visit)
            db.flush()
            visit_id, admin_ids = visit.id, [admin.id for admin in admins]
            db.commit()
        yield engine, visit_id, admin_ids
    finally:
        engine.dispose()
        with schema_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        schema_engine.dispose()


def test_one_concurrent_decision_commits_one_audit_and_notification(
    approval_case, monkeypatch
):
    engine, visit_id, admin_ids = approval_case
    notify = AsyncMock()
    monkeypatch.setattr(
        _cart.notification_sender_service, "send_all_free_decision_notification", notify
    )
    aligned = Event()
    locks_ready = Barrier(2, action=aligned.set, timeout=8)

    @event.listens_for(engine, "before_cursor_execute")
    def align_locks(_conn, _cursor, statement, _params, _context, _executemany):
        if statement.rstrip().endswith("FOR UPDATE OF visits"):
            locks_ready.wait()

    def decide(action, actor_id):
        with Session(engine) as db:
            request = _cart.AllFreeApprovalRequest(
                visit_id=visit_id,
                action=action,
                rejection_reason="Synthetic review reason",
            )
            try:
                result = _cart.approve_all_free_request(
                    request, db, db.get(User, actor_id)
                )
            except HTTPException as exc:
                return exc.status_code, None, actor_id
            return 200, result["new_status"], actor_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        approve = pool.submit(decide, "approve", admin_ids[0])
        reject = pool.submit(decide, "reject", admin_ids[1])
        winner, conflict = sorted(
            [approve.result(timeout=15), reject.result(timeout=15)]
        )

    assert aligned.is_set()
    assert winner[0] == 200
    assert conflict[0] == 409
    with Session(engine) as db:
        visit = db.get(Visit, visit_id)
        audit = db.scalars(
            select(AuditLog).where(AuditLog.action == "all_free_decision")
        ).one()
        assert visit.approval_status == winner[1]
        assert audit.entity_id == visit_id
        assert audit.actor_user_id == winner[2]
        assert audit.payload == {"previous_status": "pending", "new_status": winner[1]}
    notify.assert_awaited_once()


def test_failed_audit_rolls_back_decision_and_notes(approval_case, monkeypatch):
    engine, visit_id, admin_ids = approval_case
    notify = AsyncMock()
    monkeypatch.setattr(
        _cart.notification_sender_service, "send_all_free_decision_notification", notify
    )

    log = _cart.crud_audit.log

    def fail_after_flush(*args, **kwargs):
        log(*args, **kwargs)
        raise RuntimeError("Synthetic audit failure")

    audit_write = Mock(side_effect=fail_after_flush)
    monkeypatch.setattr(_cart.crud_audit, "log", audit_write)
    with Session(engine) as db:
        request = _cart.AllFreeApprovalRequest(
            visit_id=visit_id,
            action="reject",
            rejection_reason="Synthetic review reason",
        )
        with pytest.raises(HTTPException) as error:
            _cart.approve_all_free_request(request, db, db.get(User, admin_ids[0]))
        assert error.value.status_code == 500

    with Session(engine) as db:
        visit = db.get(Visit, visit_id)
        assert visit.approval_status == "pending"
        assert visit.notes == "Original notes"
        assert db.scalars(select(AuditLog)).first() is None
    audit_write.assert_called_once()
    notify.assert_not_awaited()
