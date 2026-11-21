"""Synthetic PostgreSQL coverage of edit identity and actual 0102 triggers."""

from __future__ import annotations

import importlib.util
import os
import threading
import time
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.v1.endpoints.registrar_wizard import _cart
from app.api.v1.endpoints.registrar_wizard._helpers import EditDeltaRequest
from app.db.base import Base
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService


@pytest.fixture
def edit_engine():
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    if not os.getenv("CI") and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable clinic_test database")
    schema = "test_edit_patient_lock_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
    )
    try:
        Base.metadata.create_all(engine)
        # Model metadata includes the 0102 column. Remove it only from this
        # synthetic predecessor, then run the actual complete Alembic upgrade.
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        path = (
            Path(__file__).resolve().parents[2]
            / "alembic/versions/0102_visit_confirmation_context.py"
        )
        spec = importlib.util.spec_from_file_location("synthetic_edit_0102", path)
        migration = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(migration)
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE visits DROP COLUMN confirmation_context_epoch")
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _seed(engine):
    with Session(engine, expire_on_commit=False) as db:
        actor = User(
            username="synthetic-registrar",
            hashed_password="synthetic",
            role="Registrar",
            is_active=True,
        )
        linked_user = User(
            username="synthetic-patient",
            hashed_password="synthetic",
            role="Patient",
            is_active=True,
        )
        db.add_all([actor, linked_user])
        db.flush()
        patient = Patient(
            first_name="Synthetic",
            last_name="Patient",
            user_id=linked_user.id,
            phone="synthetic-old",
            birth_date=date(1990, 1, 1),
        )
        other = Patient(first_name="Synthetic", last_name="Other")
        resource = QueueResource(
            code="synthetic", queue_tag="synthetic", display_name="Synthetic"
        )
        db.add_all([patient, other, resource])
        db.flush()
        visits = [
            Visit(
                patient_id=patient.id,
                status="pending_confirmation",
                visit_date=date(2026, 4, 1),
                confirmation_token="synthetic-token",
                reminder_generation=0,
            )
            for _ in range(2)
        ]
        foreign_visit = Visit(
            patient_id=other.id, status="open", visit_date=date(2026, 4, 1)
        )
        queue = DailyQueue(
            day=date(2026, 4, 1),
            queue_resource_id=resource.id,
            queue_tag="synthetic",
            active=True,
        )
        db.add_all([*visits, foreign_visit, queue])
        db.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            patient_id=patient.id,
            visit_id=visits[0].id,
            number=1,
            status="waiting",
            source="desk",
        )
        db.add(entry)
        db.commit()
        return (
            actor.id,
            linked_user.id,
            patient.id,
            [v.id for v in visits],
            foreign_visit.id,
            entry.id,
        )


def _request(patient_id):
    return EditDeltaRequest(
        patient_id=patient_id,
        target_date=date(2026, 4, 1),
        services=[],
        patient_data={"phone": "synthetic-new", "birth_date": "1991-02-03"},
    )


def _blocked(engine, pid, done):
    deadline = time.monotonic() + 8
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            if connection.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}
            ):
                return True
            if done.wait(0.01):
                return False
    return False


def test_phone_birth_edit_waits_for_visit_and_uses_real_phone_trigger(
    edit_engine, monkeypatch
):
    actor_id, _, patient_id, visit_ids, _, _ = _seed(edit_engine)
    before_visit_lock = threading.Event()
    finished = threading.Event()
    observed = {}
    notifications = AsyncMock()
    provider = Mock()
    import app.ws.cashier_ws as cashier_ws
    import app.ws.queue_ws as queue_ws
    from app.services.notifications import notification_sender_service
    from app.services.payment_providers.manager import PaymentProviderManager

    queue_broadcast = Mock()
    cashier_broadcast = AsyncMock()
    monkeypatch.setattr(PaymentProviderManager, "create_payment", provider)
    monkeypatch.setattr(
        notification_sender_service,
        "send_patient_telegram_event_notification",
        notifications,
    )
    monkeypatch.setattr(queue_ws, "broadcast_queue_update", queue_broadcast)
    monkeypatch.setattr(cashier_ws, "broadcast_cashier_update", cashier_broadcast)

    def observe(conn, cursor, statement, parameters, context, executemany):
        if (
            "FROM visits" in statement
            and "FOR UPDATE" in statement
            and threading.current_thread().name.startswith("edit-")
        ):
            before_visit_lock.set()

    event.listen(edit_engine, "before_cursor_execute", observe)
    try:
        with Session(edit_engine) as visit_writer:
            visit = (
                visit_writer.query(Visit)
                .filter_by(id=visit_ids[0])
                .with_for_update()
                .one()
            )
            visit.notes = "synthetic clinical update"
            visit_writer.flush()

            def edit():
                try:
                    with Session(edit_engine) as db:
                        actor = db.get(User, actor_id)
                        observed["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                        result = _cart.apply_registrar_cart_edit_delta(
                            _request(patient_id), db=db, current_user=actor
                        )
                        observed["success"] = result.success
                finally:
                    finished.set()

            thread = threading.Thread(target=edit, name="edit-phone", daemon=True)
            thread.start()
            try:
                assert before_visit_lock.wait(8)
                assert _blocked(edit_engine, observed["pid"], finished)
                visit_writer.commit()
                assert finished.wait(10)
                assert observed.get("success") is True
            finally:
                visit_writer.rollback()
                thread.join(timeout=10)
        with Session(edit_engine) as db:
            patient = db.get(Patient, patient_id)
            assert patient.phone == "synthetic-new"
            assert patient.birth_date == date(1991, 2, 3)
            assert all(
                db.get(Visit, visit_id).confirmation_token is None
                for visit_id in visit_ids
            )
        provider.assert_not_called()
        notifications.assert_not_called()
        queue_broadcast.assert_not_called()
        cashier_broadcast.assert_not_called()
    finally:
        event.remove(edit_engine, "before_cursor_execute", observe)


def test_dirty_session_fails_without_losing_changes(edit_engine):
    actor_id, _, patient_id, _, _, _ = _seed(edit_engine)
    with Session(edit_engine) as db:
        actor = db.get(User, actor_id)
        patient = db.get(Patient, patient_id)
        patient.birth_date = date(1995, 1, 1)
        with pytest.raises(HTTPException) as exc:
            RegistrarEditDeltaService(db).lock_edit_context(patient_id, actor)
        assert exc.value.status_code == 409
        assert patient.birth_date == date(1995, 1, 1)
        assert db.is_modified(patient)
        db.rollback()
        assert db.get(Patient, patient_id).birth_date == date(1990, 1, 1)


def test_unproven_queue_visit_and_new_phantom_fail_before_visit_lock(edit_engine):
    actor_id, _, patient_id, _, foreign_id, entry_id = _seed(edit_engine)
    with Session(edit_engine) as db:
        actor = db.get(User, actor_id)
        service = RegistrarEditDeltaService(db)
        service.lock_edit_context(patient_id, actor)
        entry = db.get(OnlineQueueEntry, entry_id)
        entry.visit_id = foreign_id
        with pytest.raises(HTTPException) as exc:
            service._validate_locked_entry(entry)
        assert exc.value.status_code == 409
        # A new object not present in the locked routing snapshot cannot be
        # adopted as though it were already covered by the Visit locks.
        entry.visit_id = None
        phantom = OnlineQueueEntry(
            id=999999, patient_id=patient_id, queue_id=entry.queue_id, number=9
        )
        with pytest.raises(HTTPException) as phantom_error:
            service._validate_locked_entry(phantom)
        assert phantom_error.value.status_code == 409
        db.rollback()


def test_real_deadlock_returns_retryable_409_without_partial_state(
    edit_engine, monkeypatch
):
    from app.models.payment import Payment
    from app.models.payment_invoice import PaymentInvoice
    from app.services.payment_providers.manager import PaymentProviderManager

    actor_id, _, patient_id, visit_ids, _, _ = _seed(edit_engine)
    lock_attempt = threading.Event()
    finished = threading.Event()
    observed = {}
    external = Mock()
    monkeypatch.setattr(PaymentProviderManager, "create_payment", external)

    def observe(conn, cursor, statement, parameters, context, executemany):
        if (
            "FROM visits" in statement
            and "FOR UPDATE" in statement
            and threading.current_thread().name == "deadlock-edit"
        ):
            lock_attempt.set()

    event.listen(edit_engine, "before_cursor_execute", observe)
    try:
        with Session(edit_engine) as blocker:
            blocker.execute(text("SET LOCAL deadlock_timeout='5s'"))
            blocker.query(Visit).filter_by(id=visit_ids[0]).with_for_update().one()

            def edit():
                try:
                    with Session(edit_engine) as db:
                        db.execute(text("SET LOCAL deadlock_timeout='100ms'"))
                        actor = db.get(User, actor_id)
                        observed["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                        try:
                            _cart.apply_registrar_cart_edit_delta(
                                _request(patient_id), db=db, current_user=actor
                            )
                            observed["success"] = True
                        except HTTPException as exc:
                            observed["status"] = exc.status_code
                finally:
                    finished.set()

            thread = threading.Thread(target=edit, name="deadlock-edit", daemon=True)
            thread.start()
            try:
                assert lock_attempt.wait(8)
                assert _blocked(edit_engine, observed["pid"], finished)
                # Patient->Visit vs Visit->Patient: the real 0102 trigger is
                # installed. The editor has the shorter detector timeout.
                blocker.execute(
                    text(
                        "UPDATE patients SET phone='synthetic-contender' WHERE id=:id"
                    ),
                    {"id": patient_id},
                )
                blocker.rollback()
                assert finished.wait(10)
                assert observed.get("status") == 409
                assert "success" not in observed
            finally:
                blocker.rollback()
                thread.join(timeout=10)
        with Session(edit_engine) as db:
            patient = db.get(Patient, patient_id)
            assert patient.phone == "synthetic-old"
            assert patient.birth_date == date(1990, 1, 1)
            assert all(
                db.get(Visit, ident).confirmation_token == "synthetic-token"
                for ident in visit_ids
            )
            assert db.query(Payment).count() == 0
            assert db.query(PaymentInvoice).count() == 0
        external.assert_not_called()
    finally:
        event.remove(edit_engine, "before_cursor_execute", observe)


@pytest.mark.parametrize(
    "sqlstate,expected", [("40P01", 409), ("40001", 500), ("55P03", 500)]
)
def test_database_error_rolls_back_and_only_deadlock_is_retryable(
    edit_engine, monkeypatch, sqlstate, expected
):
    actor_id, _, patient_id, visit_ids, _, _ = _seed(edit_engine)
    real_quote = _cart._assert_quote_token_matches
    observed = {}

    def quote(db, **kwargs):
        context = db.info.get("registrar_edit_lock_context")
        assert context is not None and context.patient_id == patient_id
        observed["quote_after_lock"] = True
        return real_quote(db, **kwargs)

    def fail_after_patient_change(self, **kwargs):
        self.db.flush()  # execute phone trigger before the transaction fails
        self.db.execute(
            text(
                f"DO $$ BEGIN RAISE EXCEPTION 'synthetic' USING ERRCODE = '{sqlstate}'; END $$"
            )
        )

    monkeypatch.setattr(_cart, "_assert_quote_token_matches", quote)
    monkeypatch.setattr(
        RegistrarEditDeltaService, "_apply_invoice_delta", fail_after_patient_change
    )
    with Session(edit_engine) as db:
        actor = db.get(User, actor_id)
        with pytest.raises(HTTPException) as exc:
            _cart.apply_registrar_cart_edit_delta(
                _request(patient_id), db=db, current_user=actor
            )
        assert exc.value.status_code == expected
    assert observed["quote_after_lock"]
    with Session(edit_engine) as db:
        patient = db.get(Patient, patient_id)
        assert patient.phone == "synthetic-old"
        assert patient.birth_date == date(1990, 1, 1)
        assert all(
            db.get(Visit, ident).confirmation_token == "synthetic-token"
            for ident in visit_ids
        )


def test_patient_user_rebind_after_hint_is_rejected(edit_engine):
    actor_id, linked_user_id, patient_id, _, _, _ = _seed(edit_engine)
    before_users_lock = threading.Event()
    finished = threading.Event()
    observed = {}

    with Session(edit_engine) as setup:
        replacement = User(
            username="synthetic-new-patient-user",
            hashed_password="synthetic",
            role="Patient",
            is_active=True,
        )
        setup.add(replacement)
        setup.commit()
        replacement_id = replacement.id

    def observe(conn, cursor, statement, parameters, context, executemany):
        if (
            "FROM users" in statement
            and "FOR UPDATE" in statement
            and threading.current_thread().name == "rebind-edit"
        ):
            before_users_lock.set()

    event.listen(edit_engine, "before_cursor_execute", observe)
    try:
        with Session(edit_engine) as blocker:
            blocker.query(User).filter_by(id=linked_user_id).with_for_update().one()

            def edit():
                try:
                    with Session(edit_engine) as db:
                        actor = db.get(User, actor_id)
                        observed["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                        try:
                            _cart.apply_registrar_cart_edit_delta(
                                _request(patient_id), db=db, current_user=actor
                            )
                            observed["success"] = True
                        except HTTPException as exc:
                            observed["status"] = exc.status_code
                finally:
                    finished.set()

            thread = threading.Thread(target=edit, name="rebind-edit", daemon=True)
            thread.start()
            try:
                assert before_users_lock.wait(8)
                assert _blocked(edit_engine, observed["pid"], finished)
                blocker.execute(
                    text("UPDATE patients SET user_id=:user_id WHERE id=:id"),
                    {"user_id": replacement_id, "id": patient_id},
                )
                blocker.commit()
                assert finished.wait(10)
                assert observed.get("status") == 409
                assert "success" not in observed
            finally:
                blocker.rollback()
                thread.join(timeout=10)
        with Session(edit_engine) as db:
            patient = db.get(Patient, patient_id)
            assert patient.user_id == replacement_id
            assert patient.phone == "synthetic-old"
    finally:
        event.remove(edit_engine, "before_cursor_execute", observe)


def test_new_patient_queue_entry_waits_until_snapshot_transaction_finishes(edit_engine):
    actor_id, _, patient_id, visit_ids, _, entry_id = _seed(edit_engine)
    started = threading.Event()
    finished = threading.Event()
    observed = {}
    with Session(edit_engine) as locker:
        actor = locker.get(User, actor_id)
        service = RegistrarEditDeltaService(locker)
        service.lock_edit_context(patient_id, actor)
        existing = locker.get(OnlineQueueEntry, entry_id)
        queue_id = existing.queue_id
        assert entry_id in locker.info["registrar_edit_lock_context"].entry_visits

        def insert():
            try:
                with Session(edit_engine) as db:
                    observed["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                    started.set()
                    db.add(
                        OnlineQueueEntry(
                            queue_id=queue_id,
                            patient_id=patient_id,
                            visit_id=visit_ids[0],
                            number=2,
                            status="waiting",
                            source="desk",
                        )
                    )
                    db.commit()
                    observed["success"] = True
            finally:
                finished.set()

        thread = threading.Thread(target=insert, name="phantom-queue", daemon=True)
        thread.start()
        try:
            assert started.wait(8)
            assert _blocked(edit_engine, observed["pid"], finished)
            assert len(locker.info["registrar_edit_lock_context"].entry_visits) == 1
            locker.rollback()
            assert finished.wait(10)
            assert observed.get("success") is True
        finally:
            locker.rollback()
            thread.join(timeout=10)


def test_http_deadlock_response_rolls_back_without_external_effects(
    edit_engine, monkeypatch
):
    from fastapi import Depends
    from fastapi.testclient import TestClient

    from app.api import deps
    from app.main import app
    from app.models.payment import Payment
    from app.services.notifications import notification_sender_service
    from app.services.payment_providers.manager import PaymentProviderManager

    actor_id, _, patient_id, visit_ids, _, _ = _seed(edit_engine)
    provider = Mock()
    notify = AsyncMock()
    monkeypatch.setattr(PaymentProviderManager, "create_payment", provider)
    monkeypatch.setattr(
        notification_sender_service, "send_patient_telegram_event_notification", notify
    )

    def session_override():
        with Session(edit_engine) as db:
            yield db

    def actor_override(db=Depends(deps.get_db)):
        return db.get(User, actor_id)

    def fail_after_change(self, **kwargs):
        self.db.flush()
        self.db.execute(
            text(
                "DO $$ BEGIN RAISE EXCEPTION 'synthetic' USING ERRCODE = '40P01'; END $$"
            )
        )

    monkeypatch.setattr(
        RegistrarEditDeltaService, "_apply_invoice_delta", fail_after_change
    )
    app.dependency_overrides[deps.get_db] = session_override
    app.dependency_overrides[deps.get_current_user] = actor_override
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/registrar/cart/edit-delta",
                json={
                    "patient_id": patient_id,
                    "target_date": "2026-04-01",
                    "services": [],
                    "patient_data": {
                        "phone": "synthetic-new",
                        "birth_date": "1991-02-03",
                    },
                },
            )
        assert response.status_code == 409, response.text
        with Session(edit_engine) as db:
            patient = db.get(Patient, patient_id)
            assert patient.phone == "synthetic-old"
            assert patient.birth_date == date(1990, 1, 1)
            assert all(
                db.get(Visit, ident).confirmation_token == "synthetic-token"
                for ident in visit_ids
            )
            assert db.query(Payment).count() == 0
        provider.assert_not_called()
        notify.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_actor_deactivation_while_waiting_revokes_edit(edit_engine):
    actor_id, _, patient_id, _, _, _ = _seed(edit_engine)
    before_users_lock = threading.Event()
    finished = threading.Event()
    observed = {}

    def observe(conn, cursor, statement, parameters, context, executemany):
        if (
            "FROM users" in statement
            and "FOR UPDATE" in statement
            and threading.current_thread().name == "actor-revoke"
        ):
            before_users_lock.set()

    event.listen(edit_engine, "before_cursor_execute", observe)
    try:
        with Session(edit_engine) as blocker:
            actor_row = (
                blocker.query(User).filter_by(id=actor_id).with_for_update().one()
            )

            def edit():
                try:
                    with Session(edit_engine) as db:
                        actor = db.get(User, actor_id)
                        observed["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
                        try:
                            _cart.apply_registrar_cart_edit_delta(
                                _request(patient_id), db=db, current_user=actor
                            )
                            observed["success"] = True
                        except HTTPException as exc:
                            observed["status"] = exc.status_code
                finally:
                    finished.set()

            thread = threading.Thread(target=edit, name="actor-revoke", daemon=True)
            thread.start()
            try:
                assert before_users_lock.wait(8)
                assert _blocked(edit_engine, observed["pid"], finished)
                actor_row.is_active = False
                blocker.commit()
                assert finished.wait(10)
                assert observed.get("status") == 403
                assert "success" not in observed
            finally:
                blocker.rollback()
                thread.join(timeout=10)
        with Session(edit_engine) as db:
            assert db.get(Patient, patient_id).phone == "synthetic-old"
    finally:
        event.remove(edit_engine, "before_cursor_execute", observe)


def test_rolled_back_savepoint_does_not_reuse_released_locks(edit_engine):
    actor_id, _, patient_id, _, _, _ = _seed(edit_engine)
    with Session(edit_engine) as db:
        actor = db.get(User, actor_id)
        service = RegistrarEditDeltaService(db)
        nested = db.begin_nested()
        service.lock_edit_context(patient_id, actor)
        before = db.info["registrar_edit_lock_context"]
        assert before.nested_transaction is nested
        nested.rollback()
        service.lock_edit_context(patient_id, actor)
        after = db.info["registrar_edit_lock_context"]
        assert after is not before
        assert after.nested_transaction is None
        db.rollback()


def test_identity_visit_catalog_and_queue_locks_are_ordered(edit_engine):
    from app.models.service import Service

    actor_id, _, patient_id, _, _, _ = _seed(edit_engine)
    with Session(edit_engine) as seed:
        catalog_service = Service(
            code="synthetic-lock-order",
            name="Synthetic",
            price=10,
            active=True,
            queue_tag="synthetic",
        )
        seed.add(catalog_service)
        seed.commit()
        service_id = catalog_service.id

    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement:
            statements.append(statement)

    event.listen(edit_engine, "before_cursor_execute", observe)
    try:
        with Session(edit_engine) as db:
            actor = db.get(User, actor_id)
            RegistrarEditDeltaService(db).lock_edit_context(
                patient_id, actor, service_ids=(service_id,)
            )
            db.rollback()
    finally:
        event.remove(edit_engine, "before_cursor_execute", observe)
    names = ["users", "patients", "visits", "services", "queue_entries", "daily_queues"]
    positions = [
        next(i for i, sql in enumerate(statements) if f"FROM {name}" in sql)
        for name in names
    ]
    assert positions == sorted(positions)
    assert "ORDER BY users.id" in statements[positions[0]]
    assert "ORDER BY visits.id" in statements[positions[2]]
    assert "ORDER BY queue_entries.id" in statements[positions[4]]
