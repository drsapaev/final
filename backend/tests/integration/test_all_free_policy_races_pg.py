"""Synthetic all-free policy locking, including absent-row writer races."""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.v1.endpoints.admin_clinic import (
    create_clinic_setting,
    update_clinic_setting,
    update_clinic_settings_batch,
)
from app.api.v1.endpoints.registrar_wizard._cart import BenefitSettingsRequest
from app.api.v1.endpoints.registrar_wizard._settings import update_benefit_settings
from app.crud.clinic import (
    create_setting,
    update_setting,
    update_settings_batch,
)
from app.models.clinic import ClinicSettings
from app.schemas.clinic import (
    ClinicSettingsBatch,
    ClinicSettingsCreate,
    ClinicSettingsUpdate,
)
from app.services.all_free_policy import (
    load_all_free_auto_approve,
    lock_all_free_policy,
)
from app.services.profile_contact_security import ProfileBearerContext
from app.services.repeat_policy_input import RepeatSettingsWriter

KEY = "all_free_auto_approve"


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    if not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test database")
    schema = "test_policy_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(sa.text("INSERT INTO users (id) VALUES (1)"))
            ClinicSettings.__table__.create(connection)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _wait_until_blocked(engine, pid, future):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert not future.done(), "policy writer did not wait"
        with engine.connect() as inspector:
            blocked = inspector.execute(sa.text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}).scalar_one()
        if blocked:
            return
        time.sleep(0.02)
    pytest.fail("policy lock did not block competing transaction")


def _write(db, kind, value):
    writer = RepeatSettingsWriter(
        actor=SimpleNamespace(id=1),
        bearer=ProfileBearerContext(user_id=1, auth_epoch=0, jti=None, expires_at=None, patient_id=None),
        values={},
    )
    if kind == "create":
        create_setting(db, ClinicSettingsCreate(key=KEY, value=value, category="benefits"), user_id=1)
    elif kind == "update":
        assert update_setting(db, KEY, ClinicSettingsUpdate(value=value), user_id=1) is not None
    elif kind == "batch":
        update_settings_batch(db, "clinic", {KEY: value}, user_id=1)
    elif kind == "registrar":
        update_benefit_settings(BenefitSettingsRequest(all_free_auto_approve=value), db=db, writer=writer)
    elif kind == "admin_create":
        create_clinic_setting(ClinicSettingsCreate(key=KEY, value=value), db=db, writer=writer)
    elif kind == "admin_update":
        update_clinic_setting(KEY, ClinicSettingsUpdate(value=value), db=db, writer=writer)
    elif kind == "admin_batch":
        update_clinic_settings_batch(ClinicSettingsBatch(settings={KEY: value}), db=db, writer=writer)
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["create", "batch", "registrar", "admin_create", "admin_batch"])
def test_absent_policy_reader_serializes_writer(pg_engine, kind):
    started, pids = threading.Event(), []

    def writer():
        with Session(pg_engine) as db:
            pids.append(db.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            _write(db, kind, True)

    with Session(pg_engine) as reader:
        assert load_all_free_auto_approve(reader) is False
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(writer)
            try:
                assert started.wait(5)
                _wait_until_blocked(pg_engine, pids[0], future)
            finally:
                reader.commit()
            future.result(timeout=15)
    with Session(pg_engine) as db:
        assert load_all_free_auto_approve(db) is True


@pytest.mark.parametrize("kind", ["update", "batch", "registrar", "admin_update", "admin_batch"])
def test_enabled_policy_reader_serializes_disable(pg_engine, kind):
    with Session(pg_engine) as db:
        _write(db, "create", True)
    started, pids = threading.Event(), []

    def writer():
        with Session(pg_engine) as db:
            pids.append(db.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            _write(db, kind, False)

    with Session(pg_engine) as reader:
        assert load_all_free_auto_approve(reader) is True
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(writer)
            try:
                assert started.wait(5)
                _wait_until_blocked(pg_engine, pids[0], future)
            finally:
                reader.commit()
            future.result(timeout=15)
    with Session(pg_engine) as db:
        assert load_all_free_auto_approve(db) is False


def test_stale_identity_map_reloads_after_policy_lock(pg_engine):
    with Session(pg_engine) as db:
        _write(db, "create", True)
    with Session(pg_engine) as reader:
        cached = reader.query(ClinicSettings).filter_by(key=KEY).one()
        assert cached.value is True
        with Session(pg_engine) as writer:
            _write(writer, "update", False)
        assert cached.value is True
        assert load_all_free_auto_approve(reader) is False
        assert cached.value is False


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_postgres_stale_snapshot_is_rejected(pg_engine, isolation):
    with pg_engine.connect().execution_options(isolation_level=isolation) as connection:
        with Session(connection) as db:
            with pytest.raises(RuntimeError, match="read committed"):
                lock_all_free_policy(db)


@pytest.mark.parametrize("value", [None, "false", 1.0, 0, {}, []])
def test_unrecognized_values_do_not_enable_policy(pg_engine, value):
    with Session(pg_engine) as db:
        _write(db, "create", value)
    with Session(pg_engine) as db:
        assert load_all_free_auto_approve(db) is False


@pytest.mark.parametrize("existing", [False, True])
def test_sqlite_reservation_blocks_conflicting_writer_and_busy_can_retry(tmp_path, existing):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'policy.sqlite'}", connect_args={"timeout": 0.1, "check_same_thread": False})
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(sa.text("INSERT INTO users (id) VALUES (1)"))
            ClinicSettings.__table__.create(connection)
        if existing:
            with Session(engine) as db:
                _write(db, "create", True)
        with Session(engine) as reader:
            assert load_all_free_auto_approve(reader) is existing
            with Session(engine) as writer:
                with pytest.raises(sa.exc.OperationalError):
                    _write(writer, "update" if existing else "create", False)
                writer.rollback()
            reader.commit()
        with Session(engine) as writer:
            _write(writer, "update" if existing else "create", False)
        with Session(engine) as reader:
            assert load_all_free_auto_approve(reader) is False
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", ["update", "batch", "registrar", "admin_update", "admin_batch"])
def test_reader_waits_for_disable_and_refreshes_stale_identity(pg_engine, kind):
    with Session(pg_engine) as db:
        _write(db, "create", True)
    staged, release, started = threading.Event(), threading.Event(), threading.Event()
    pids = []

    def writer():
        with Session(pg_engine) as db:
            commit = db.commit
            def pause_before_commit():
                staged.set()
                assert release.wait(10)
                commit()
            db.commit = pause_before_commit
            _write(db, kind, False)

    with Session(pg_engine) as reader:
        cached = reader.query(ClinicSettings).filter_by(key=KEY).one()
        assert cached.value is True
        with ThreadPoolExecutor(max_workers=2) as pool:
            written = pool.submit(writer)
            try:
                assert staged.wait(5)
                def read_after_lock():
                    pids.append(reader.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
                    started.set()
                    return load_all_free_auto_approve(reader)
                loaded = pool.submit(read_after_lock)
                assert started.wait(5)
                _wait_until_blocked(pg_engine, pids[0], loaded)
            finally:
                release.set()
            written.result(timeout=15)
            assert loaded.result(timeout=15) is False
            assert cached.value is False


@pytest.mark.parametrize("value", [True, 1, "1", "true", "yes", "on", "  YES  "])
def test_canonical_truthy_values_enable_policy(pg_engine, value):
    with Session(pg_engine) as db:
        _write(db, "create", value)
    with Session(pg_engine) as db:
        assert load_all_free_auto_approve(db) is True
