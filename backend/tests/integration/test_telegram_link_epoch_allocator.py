"""The deployed 0101 link epoch cannot revive an old RSVP capability."""
import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.appointment import Appointment
from app.models.telegram_config import TelegramUser
from app.services.appointment_rsvp import (
    _mac,
    _masks,
    apply_appointment_decision,
    make_appointment_callback,
    parse_appointment_callback,
)
from tests.integration.test_encounter_migration_pg import _migration


def _apply(conn, filename):
    migration = _migration(filename)
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    return migration


def _setup(conn):
    conn.execute(text("""
      CREATE TABLE telegram_users (
        id INTEGER PRIMARY KEY, patient_id INTEGER, chat_id BIGINT NOT NULL,
        active BOOLEAN NOT NULL, blocked BOOLEAN NOT NULL,
        notifications_enabled BOOLEAN NOT NULL, appointment_reminders BOOLEAN NOT NULL
      )
    """))
    conn.execute(text("INSERT INTO telegram_users(id,patient_id,chat_id,active,blocked,notifications_enabled,appointment_reminders) VALUES (1,1,12345,true,false,true,true)"))
    _apply(conn, "0101_telegram_patient_link_epoch.py")


def _verify_rsvp(data, epoch):
    action, nonce, masked_id, masked_revision, signature = parse_appointment_callback(data)
    id_mask, revision_mask = _masks(12345, 1, epoch, nonce)
    return hmac.compare_digest(signature, _mac(action, masked_id ^ id_mask,
                               masked_revision ^ revision_mask, 12345, 1, epoch, nonce))


def _exercise(conn):
    before = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one()
    signed = make_appointment_callback("c", 19, 0, 12345, 1, before)
    assert _verify_rsvp(signed, before)
    migration = _apply(conn, "0122_telegram_link_epoch.py")
    assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one() == before
    conn.execute(text("UPDATE telegram_users SET patient_id=2 WHERE id=1"))
    middle = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one()
    conn.execute(text("UPDATE telegram_users SET patient_id=1 WHERE id=1"))
    after = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one()
    assert before < middle < after
    assert not _verify_rsvp(signed, after)
    migration.downgrade()
    migration.upgrade()
    conn.execute(text("UPDATE telegram_users SET blocked=true WHERE id=1"))
    latest = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one()
    assert latest > after
    conn.execute(text("DELETE FROM telegram_users WHERE id=1"))
    conn.execute(text("INSERT INTO telegram_users(id,patient_id,chat_id,active,blocked,notifications_enabled,appointment_reminders) VALUES (1,1,12345,true,false,true,true)"))
    reused = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one()
    assert reused > latest and not _verify_rsvp(signed, reused)


@pytest.mark.parametrize("recursive", [0, 1])
def test_sqlite_highwater_aba_and_persistent_clock(recursive):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"PRAGMA recursive_triggers={recursive}")
            _setup(conn)
            conn.execute(text("UPDATE telegram_users SET patient_link_epoch=5000000000000000 WHERE id=1"))
            _exercise(conn)
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text("UPDATE telegram_users SET patient_link_epoch=1 WHERE id=1"))
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text("DELETE FROM telegram_patient_link_generation_clock"))
    finally:
        engine.dispose()


def test_sqlite_exhausted_highwater_fails_upgrade_without_rewriting_epoch():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            _setup(conn)
            conn.execute(text("UPDATE telegram_users SET patient_link_epoch=9223372036854775807 WHERE id=1"))
            with pytest.raises(DBAPIError), conn.begin_nested():
                _apply(conn, "0122_telegram_link_epoch.py")
            assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")).scalar_one() == 9223372036854775807
    finally:
        engine.dispose()


def test_migrated_sqlite_orm_listener_and_real_rsvp_aba(db_session, test_patient):
    _apply(db_session.connection(), "0122_telegram_link_epoch.py")
    appointment = Appointment(patient_id=test_patient.id, appointment_date=(datetime.now(UTC) + timedelta(days=5)).date(),
                              appointment_time="12:00", status="pending", occurrence_revision=0)
    chat_id = uuid.uuid4().int % (1 << 48) + 1
    link = TelegramUser(patient_id=test_patient.id, chat_id=chat_id, active=True, blocked=False,
                        notifications_enabled=True, appointment_reminders=True)
    db_session.add_all([appointment, link])
    db_session.commit()
    signed = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    first = link.patient_link_epoch
    link.patient_id = None
    db_session.flush()
    link.patient_id = test_patient.id
    db_session.commit()
    assert link.patient_link_epoch > first
    assert apply_appointment_decision(db_session, callback_data=signed, chat_id=link.chat_id) == "stale"
    fresh = make_appointment_callback("c", appointment.id, 0, link.chat_id, link.id, link.patient_link_epoch)
    assert apply_appointment_decision(db_session, callback_data=fresh, chat_id=link.chat_id) == "confirmed"


@pytest.mark.integration
def test_postgres_nonowner_shadow_and_seeded_random_aba():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    url, suffix = make_url(raw), uuid.uuid4().hex
    schema, shadow, role, password = "tg_real_" + suffix, "tg_fake_" + suffix, "tg_role_" + suffix, uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\''))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    login = create_engine(url.set(username=role, password=password), connect_args={"options": f"-csearch_path={shadow},{schema},pg_catalog"})
    try:
        with engine.begin() as conn:
            _setup(conn)
            conn.execute(text(f'ALTER TABLE "{schema}".telegram_users DISABLE TRIGGER trg_telegram_patient_link_epoch'))
            conn.execute(text(f'UPDATE "{schema}".telegram_users SET patient_link_epoch=5000000000000000 WHERE id=1'))
            conn.execute(text(f'ALTER TABLE "{schema}".telegram_users ENABLE TRIGGER trg_telegram_patient_link_epoch'))
            metadata_sql = text("SELECT p.proowner,p.proacl::text FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=:schema AND p.proname='bump_telegram_patient_link_epoch'")
            metadata_before = conn.execute(metadata_sql, {"schema": schema}).one()
            _apply(conn, "0122_telegram_link_epoch.py")
            assert conn.execute(metadata_sql, {"schema": schema}).one() == metadata_before
            conn.execute(text(f'CREATE TABLE "{shadow}".telegram_users AS SELECT * FROM "{schema}".telegram_users'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}","{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}","{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON SEQUENCE "{schema}".telegram_patient_link_generation_seq TO "{role}"'))
            conn.execute(text(f'ALTER TABLE "{schema}".telegram_users ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".telegram_users FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'CREATE POLICY tg_test_runtime ON "{schema}".telegram_users TO "{role}" USING (true) WITH CHECK (true)'))
            before = conn.execute(text(f'SELECT patient_link_epoch FROM "{schema}".telegram_users WHERE id=1')).scalar_one()
            signed = make_appointment_callback("c", 19, 0, 12345, 1, before)
        with login.begin() as conn:
            conn.execute(text('SELECT pg_catalog.setseed(0.2)'))
            conn.execute(text(f'UPDATE "{schema}".telegram_users SET patient_id=2 WHERE id=1'))
            conn.execute(text('SELECT pg_catalog.setseed(0.2)'))
            conn.execute(text(f'UPDATE "{schema}".telegram_users SET patient_id=1 WHERE id=1'))
            after = conn.execute(text(f'SELECT patient_link_epoch FROM "{schema}".telegram_users WHERE id=1')).scalar_one()
            assert after > before and not _verify_rsvp(signed, after)
            assert conn.execute(text(f'SELECT patient_link_epoch FROM "{shadow}".telegram_users WHERE id=1')).scalar_one() == before
            conn.execute(text(f'DELETE FROM "{schema}".telegram_users WHERE id=1'))
            conn.execute(text(f'INSERT INTO "{schema}".telegram_users(id,patient_id,chat_id,active,blocked,notifications_enabled,appointment_reminders) VALUES (1,1,12345,true,false,true,true)'))
            reused = conn.execute(text(f'SELECT patient_link_epoch FROM "{schema}".telegram_users WHERE id=1')).scalar_one()
            assert reused > after and not _verify_rsvp(signed, reused)
            conn.execute(text(f'UPDATE "{schema}".telegram_users SET patient_link_epoch=1 WHERE id=1'))
            assert conn.execute(text(f'SELECT patient_link_epoch FROM "{schema}".telegram_users WHERE id=1')).scalar_one() == reused
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text(f"SELECT pg_catalog.setval('\"{schema}\".telegram_patient_link_generation_seq'::pg_catalog.regclass,1,true)"))
    finally:
        login.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()
