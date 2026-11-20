"""Concurrent notification checks on PostgreSQL with the real 0102 trigger."""

from __future__ import annotations

import asyncio
import os
import threading
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base import Base
from app.db.capability_namespace import capability_schema_name
from app.models.visit import Visit
from app.services.notification_subject_intent_service import (
    dispatch_patient_notification_intent,
)
from tests.integration.test_invitation_subject_nonowner_pg import (
    install_invitation_subject_fence,
)
from tests.integration.test_notification_subject_transfer_sqlite import (
    _intent,
    _seed,
    _sender,
)


@pytest.fixture
def notification_pg_engine(monkeypatch):
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    if not os.getenv("CI") and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable clinic_test database")
    suffix = uuid4().hex
    schema, login, cap = "test_notification_subject_" + suffix, "notify_login_" + suffix, "notify_cap_" + suffix
    password = "synthetic-" + suffix
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.exec_driver_sql(f'CREATE ROLE "{login}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
        owner_name = conn.execute(text("SELECT CURRENT_USER")).scalar_one()
    engine = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
    )
    runtime = None
    try:
        Base.metadata.create_all(engine)
        install_invitation_subject_fence(engine, schema=schema, owner_name=owner_name,
                                         runtime_role=login, subject_cap_role=cap, monkeypatch=monkeypatch)
        with engine.begin() as conn:
            conn.exec_driver_sql(f'GRANT SELECT ON "{schema}".telegram_users, "{schema}".doctors TO "{login}"')
            conn.exec_driver_sql(f'GRANT UPDATE (id) ON "{schema}".doctors TO "{login}"')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".doctors ENABLE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".doctors FORCE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_doctor_select ON "{schema}".doctors FOR SELECT TO "{login}" USING (true)')
            conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_doctor_lock ON "{schema}".doctors FOR UPDATE TO "{login}" USING (true) WITH CHECK (false)')
            for table in ("user_preferences", "user_notification_settings"):
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY')
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY')
                conn.exec_driver_sql(f'GRANT SELECT ON "{schema}"."{table}" TO "{login}"')
                conn.exec_driver_sql(f'GRANT UPDATE (id) ON "{schema}"."{table}" TO "{login}"')
                conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_preference ON "{schema}"."{table}" FOR SELECT TO "{login}" USING (true)')
                conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_preference_lock ON "{schema}"."{table}" FOR UPDATE TO "{login}" USING (true) WITH CHECK (false)')
            conn.exec_driver_sql(f'GRANT SELECT, UPDATE (id) ON "{schema}".payments TO "{login}"')
            conn.exec_driver_sql(f'GRANT SELECT ON "{schema}".payment_visits TO "{login}"')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".payments ENABLE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".payments FORCE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".payment_visits ENABLE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'ALTER TABLE "{schema}".payment_visits FORCE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_payment_select ON "{schema}".payments FOR SELECT TO "{login}" USING (true)')
            conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_payment_lock ON "{schema}".payments FOR UPDATE TO "{login}" USING (true) WITH CHECK (false)')
            conn.exec_driver_sql(f'CREATE POLICY synthetic_notify_payment_link_select ON "{schema}".payment_visits FOR SELECT TO "{login}" USING (true)')
        from app.core.config import settings

        monkeypatch.setattr(settings, "NOTIFY_PREFERENCES_DB_OWNER", owner_name)
        monkeypatch.setattr(settings, "NOTIFY_PREFERENCES_DB_OWNER_MEMBERS", ())
        monkeypatch.setattr(settings, "NOTIFY_PREFERENCES_DB_READ_ROLES", ())
        monkeypatch.setattr(settings, "NOTIFY_PREFERENCES_DB_WRITE_ROLES", ())
        runtime = create_engine(url.set(username=login, password=password),
                                connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"}, hide_parameters=True)
        yield engine, runtime
    finally:
        if runtime is not None:
            runtime.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.exec_driver_sql(f'DROP ROLE "{login}"')
            conn.exec_driver_sql(f'DROP ROLE "{cap}"')
        admin.dispose()


def _worker(intent):
    errors = []

    def run():
        try:
            asyncio.run(dispatch_patient_notification_intent(intent))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def test_transfer_before_locked_recheck_suppresses_scheduled_send(
    notification_pg_engine, monkeypatch
):
    engine, runtime = notification_pg_engine
    bearer, _, other_id, visit_id, _ = _seed(engine)
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id)
    waiting = threading.Event()
    pid = []

    @event.listens_for(runtime, "before_cursor_execute")
    def observe(conn, cursor, statement, parameters, context, executemany):
        if (
            threading.current_thread() is not threading.main_thread()
            and "FROM visits" in statement
            and "FOR UPDATE" in statement
        ):
            pid.append(conn.connection.driver_connection.info.backend_pid)
            waiting.set()

    with Session(engine) as transfer:
        visit = transfer.query(Visit).filter_by(id=visit_id).with_for_update().one()
        visit.patient_id = other_id
        transfer.flush()
        thread, errors = _worker(intent)
        assert waiting.wait(5)
        with engine.connect() as observer:
            assert observer.execute(
                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid[0]}
            ).scalar()
        transfer.commit()
        thread.join(10)
    assert not thread.is_alive() and not errors
    sender.send_push.assert_not_awaited()
    sender.send_email.assert_not_awaited()
    sender.send_sms.assert_not_awaited()


def test_transfer_after_recheck_only_races_neutral_payload(
    notification_pg_engine, monkeypatch
):
    engine, runtime = notification_pg_engine
    bearer, _, other_id, visit_id, _ = _seed(engine)
    sender = _sender(monkeypatch, runtime)
    intent = _intent(runtime, bearer, visit_id)
    in_send = threading.Event()
    resume = threading.Event()

    async def block_send(*args, **kwargs):
        in_send.set()
        assert await asyncio.to_thread(resume.wait, 10)
        return True

    sender.send_push.side_effect = block_send
    thread, errors = _worker(intent)
    try:
        assert in_send.wait(5)
        with Session(engine) as transfer:
            transfer.get(Visit, visit_id).patient_id = other_id
            transfer.commit()
    finally:
        resume.set()
        thread.join(10)
    assert not thread.is_alive() and not errors
    for mock in (sender.send_push, sender.send_email, sender.send_sms):
        mock.assert_awaited_once()
        payload = str(mock.await_args)
        assert "2026-04-01" not in payload
        assert "123.45" not in payload
        assert "synthetic-token" not in payload
