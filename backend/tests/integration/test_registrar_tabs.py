"""Registrar tab registry acceptance on an isolated Alembic-head PostgreSQL DB.

Only REGISTRAR_TABS_PG_ADMIN_URL may select the local provisioning server.
No production/default DATABASE_URL is used and the run-owned database is
removed after success or setup failure. Missing PG is NOT_RUN, never SQLite.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user, get_db
from app.models.audit import AuditLog
from app.models.clinic import ClinicSettings, Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.queue_profile import QueueProfile
from app.models.user import User
from app.schemas.registrar_tabs import RegistrarTabsUpdate
from app.services.registrar_tabs import RegistrarTabsError, RegistrarTabsService
from tests._pg_admin_guard import is_local_admin_dsn

BACKEND_DIR = Path(__file__).resolve().parents[2]
SETTINGS_KEY = "registrar_tabs_v1"


@pytest.fixture(scope="module")
def pg_engine():
    candidate = os.getenv("REGISTRAR_TABS_PG_ADMIN_URL", "").strip()
    if not candidate:
        pytest.skip(
            "Registrar tabs PostgreSQL acceptance NOT_RUN: explicit local PG admin URL is absent"
        )
    if not is_local_admin_dsn(candidate):
        pytest.fail(
            "Registrar tabs test only accepts a verified local PostgreSQL admin URL"
        )
    database = f"registrar_tabs_{uuid.uuid4().hex[:12]}"
    try:
        admin = psycopg.connect(candidate, autocommit=True, connect_timeout=5)
    except psycopg.Error:
        pytest.skip(
            "Registrar tabs PostgreSQL acceptance NOT_RUN: local PG is unavailable"
        )
    scratch = make_url(candidate).set(
        database=database, drivername="postgresql+psycopg"
    )
    engine = None
    created = False
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        created = True
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env={
                **os.environ,
                "DATABASE_URL": scratch.render_as_string(hide_password=False),
                "TESTING": "1",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert (
            result.returncode == 0
        ), "Disposable Registrar tabs DB must migrate to Alembic head"
        engine = create_engine(scratch, future=True)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )
        admin.close()


@pytest.fixture
def world(pg_engine):
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    session.query(ClinicSettings).filter(ClinicSettings.key == SETTINGS_KEY).delete()
    suffix = uuid.uuid4().hex[:8]
    actor = User(
        username=f"synthetic_tabs_admin_{suffix}",
        full_name="SYNTHETIC Admin",
        hashed_password="synthetic-not-used",
        role="Admin",
        is_active=True,
    )
    owner = User(
        username=f"synthetic_tabs_doctor_{suffix}",
        full_name="SYNTHETIC Doctor",
        hashed_password="synthetic-not-used",
        role="Doctor",
        is_active=True,
    )
    session.add_all([actor, owner])
    session.flush()
    profile = QueueProfile(
        key=f"synthetic_tabs_{suffix}",
        title="SYNTHETIC Direction",
        title_ru="SYNTHETIC Направление",
        queue_tags=[f"synthetic_tabs_{suffix}"],
        is_active=True,
        display_order=0,
        show_on_qr_page=False,
    )
    doctor = Doctor(user_id=owner.id, specialty="cardiology", active=True)
    session.add_all([profile, doctor])
    session.commit()
    try:
        yield session, actor, profile, doctor
    finally:
        session.rollback()
        session.close()


def _update(version, rows):
    return RegistrarTabsUpdate.model_validate(
        {
            "expected_version": version,
            "tabs": rows,
            "reason": "configure_registrar_tabs",
        }
    )


def _row(kind, target_id, **values):
    return {
        "target_kind": kind,
        "target_id": target_id,
        "title": None,
        "visible": True,
        **values,
    }


def _save(service, command, actor):
    return service.update(
        command,
        actor_user_id=actor.id,
        request_id="synthetic-registrar-tabs-request",
        actor_role="Admin",
    )


@pytest.mark.integration
def test_legacy_read_has_no_config_audit_or_queue_writes(world):
    session, _, profile, doctor = world
    before = (
        session.query(AuditLog).count(),
        session.query(DailyQueue).count(),
        session.query(OnlineQueueEntry).count(),
    )
    result = RegistrarTabsService(session).read(admin=True)
    assert result.mode == "legacy"
    assert result.version == 0
    assert ("profile", profile.id) in {
        (tab.target_kind, tab.target_id) for tab in result.tabs
    }
    assert ("doctor", doctor.id) in {
        (tab.target_kind, tab.target_id) for tab in result.tabs
    }
    assert session.query(ClinicSettings).filter_by(key=SETTINGS_KEY).first() is None
    assert before == (
        session.query(AuditLog).count(),
        session.query(DailyQueue).count(),
        session.query(OnlineQueueEntry).count(),
    )


@pytest.mark.integration
def test_saved_empty_is_authoritative_and_does_not_auto_add_new_targets(world):
    session, actor, _, _ = world
    service = RegistrarTabsService(session)
    saved = _save(service, _update(0, []), actor)
    assert saved.mode == "configured" and saved.version == 1
    extra = QueueProfile(
        key=f"synthetic_extra_{uuid.uuid4().hex[:8]}",
        title="SYNTHETIC Extra",
        queue_tags=[],
        is_active=True,
    )
    session.add(extra)
    session.commit()
    assert service.read().tabs == []
    assert service.read(admin=True).tabs == []


@pytest.mark.integration
def test_mixed_order_visibility_and_custom_name_do_not_change_targets(world):
    session, actor, profile, doctor = world
    profile_snapshot = (
        profile.title,
        profile.queue_tags[:],
        profile.is_active,
        profile.show_on_qr_page,
    )
    before_queues = (
        session.query(DailyQueue).count(),
        session.query(OnlineQueueEntry).count(),
    )
    service = RegistrarTabsService(session)
    saved = _save(
        service,
        _update(
            0,
            [
                _row("doctor", doctor.id, title="SYNTHETIC custom tab"),
                _row("profile", profile.id, visible=False),
            ],
        ),
        actor,
    )
    assert [(tab.target_kind, tab.target_id) for tab in saved.tabs] == [
        ("doctor", doctor.id),
        ("profile", profile.id),
    ]
    assert [tab.target_kind for tab in service.read().tabs] == ["doctor"]
    assert saved.tabs[0].custom_title == "SYNTHETIC custom tab"
    session.refresh(profile)
    assert profile_snapshot == (
        profile.title,
        profile.queue_tags,
        profile.is_active,
        profile.show_on_qr_page,
    )
    assert before_queues == (
        session.query(DailyQueue).count(),
        session.query(OnlineQueueEntry).count(),
    )


@pytest.mark.integration
def test_stale_update_and_new_invalid_target_are_rejected(world):
    session, actor, profile, _ = world
    service = RegistrarTabsService(session)
    _save(service, _update(0, [_row("profile", profile.id)]), actor)
    with pytest.raises(RegistrarTabsError) as stale:
        _save(service, _update(0, []), actor)
    assert stale.value.status_code == 409
    session.rollback()
    with pytest.raises(RegistrarTabsError) as invalid:
        _save(service, _update(1, [_row("doctor", 2_000_000_000)]), actor)
    assert invalid.value.status_code == 422
    session.rollback()
    assert service.read().version == 1


@pytest.mark.integration
def test_unavailable_retained_target_is_visible_in_admin_only(world):
    session, actor, _, doctor = world
    service = RegistrarTabsService(session)
    _save(service, _update(0, [_row("doctor", doctor.id)]), actor)
    doctor.active = False
    session.commit()
    assert service.read().tabs == []
    admin = service.read(admin=True)
    assert admin.tabs[0].available is False
    assert admin.tabs[0].reason_code == "inactive_target"
    hidden = _save(
        service, _update(1, [_row("doctor", doctor.id, visible=False)]), actor
    )
    assert hidden.version == 2 and hidden.tabs[0].visible is False


@pytest.mark.integration
def test_hidden_inactive_profile_keeps_historical_filter_metadata(world):
    session, actor, profile, _ = world
    service = RegistrarTabsService(session)
    _save(
        service,
        _update(
            0,
            [
                _row(
                    "profile",
                    profile.id,
                    title="SYNTHETIC Historical filter",
                    visible=False,
                ),
            ],
        ),
        actor,
    )
    profile.is_active = False
    session.commit()
    result = service.read()
    assert result.tabs == []
    metadata = next(item for item in result.profile_filters if item.key == profile.key)
    assert metadata.queue_tags == profile.queue_tags
    assert metadata.title == "SYNTHETIC Historical filter"


@pytest.mark.integration
def test_audit_failure_rolls_back_registry_write(world):
    session, actor, profile, _ = world
    service = RegistrarTabsService(session)

    audit_attempted = False

    def reject_audit(db, _flush_context, _instances):
        nonlocal audit_attempted
        if any(isinstance(item, AuditLog) for item in db.new):
            audit_attempted = True
            raise RuntimeError("synthetic audit failure")

    event.listen(session, "before_flush", reject_audit)
    try:
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            _save(service, _update(0, [_row("profile", profile.id)]), actor)
    finally:
        event.remove(session, "before_flush", reject_audit)
        session.rollback()
    assert audit_attempted
    assert session.query(ClinicSettings).filter_by(key=SETTINGS_KEY).first() is None


@pytest.mark.integration
def test_invalid_saved_registry_fails_closed_instead_of_legacy_fallback(world):
    session, _, _, _ = world
    session.add(
        ClinicSettings(
            key=SETTINGS_KEY,
            category="registrar_tabs",
            value={"version": 1, "tabs": "invalid"},
        )
    )
    session.commit()
    with pytest.raises(RegistrarTabsError) as invalid:
        RegistrarTabsService(session).read()
    assert invalid.value.status_code == 503


@pytest.mark.integration
def test_audit_records_safe_ordered_projection_and_actor(world):
    session, actor, profile, _ = world
    custom_title = "SYNTHETIC private custom label"
    _save(
        RegistrarTabsService(session),
        _update(
            0,
            [
                _row("profile", profile.id, title=custom_title, visible=False),
            ],
        ),
        actor,
    )
    audit = (
        session.query(AuditLog)
        .filter_by(actor_user_id=actor.id, action="registrar_tabs_updated")
        .one()
    )
    assert audit.entity_type == "clinic_settings"
    assert audit.actor_role == "Admin"
    assert audit.reason_code == {"code": "configure_registrar_tabs"}
    assert audit.payload["request_id"] == "synthetic-registrar-tabs-request"
    assert audit.payload["old_version"] == 0
    assert audit.payload["new_version"] == 1
    assert audit.payload["new"] == [
        {
            "target_kind": "profile",
            "target_id": profile.id,
            "visible": False,
            "title_sha256": hashlib.sha256(custom_title.encode()).hexdigest(),
        }
    ]
    serialized = json.dumps(audit.payload, ensure_ascii=False)
    assert custom_title not in serialized
    assert "SYNTHETIC Doctor" not in serialized


@pytest.mark.integration
def test_deleted_profile_is_not_rebound_to_new_profile_with_same_key(world):
    session, actor, profile, _ = world
    old_id, key = profile.id, profile.key
    service = RegistrarTabsService(session)
    _save(service, _update(0, [_row("profile", old_id)]), actor)
    session.delete(profile)
    session.commit()
    replacement = QueueProfile(
        key=key, title="SYNTHETIC Replacement", queue_tags=[], is_active=True
    )
    session.add(replacement)
    session.commit()
    assert replacement.id != old_id
    assert service.read().tabs == []
    saved = service.read(admin=True)
    assert len(saved.tabs) == 1
    assert saved.tabs[0].target_id == old_id
    assert saved.tabs[0].reason_code == "missing_target"
    assert any(
        option.target_id == replacement.id and option.target_kind == "profile"
        for option in saved.options
    )


@pytest.mark.integration
def test_parallel_first_save_allows_only_one_expected_version(world, pg_engine):
    _, actor, _, _ = world
    actor_id = actor.id
    start = Barrier(2)

    def save_one():
        with sessionmaker(bind=pg_engine)() as session:
            start.wait(timeout=10)
            try:
                saved = RegistrarTabsService(session).update(
                    _update(0, []),
                    actor_user_id=actor_id,
                    request_id="synthetic-concurrent-save",
                    actor_role="Admin",
                )
                return saved.version
            except RegistrarTabsError as error:
                session.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(save_one)
        second = pool.submit(save_one)
        assert sorted([first.result(timeout=15), second.result(timeout=15)]) == [1, 409]


@pytest.fixture
def api_client(world):
    from app.api.v1.endpoints import admin_clinic
    from app.api.v1.endpoints.registrar_integration import router

    session, actor, _, _ = world
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(admin_clinic.router, prefix="/api/v1/admin")
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: actor
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, actor


@pytest.mark.integration
def test_admin_write_rbac_and_generic_settings_guard(api_client, world):
    client, actor = api_client
    session, _, _, _ = world
    command = {"expected_version": 0, "tabs": [], "reason": "configure_registrar_tabs"}
    actor.role = "Registrar"
    actor.is_superuser = False
    assert client.get("/api/v1/registrar/tabs").status_code == 200
    assert client.put("/api/v1/admin/registrar-tabs", json=command).status_code == 403
    assert client.get("/api/v1/admin/registrar-tabs").status_code == 403
    session.rollback()
    actor.role = "Admin"
    assert client.put("/api/v1/admin/registrar-tabs", json=command).status_code == 200
    create = client.post(
        "/api/v1/admin/clinic/settings",
        json={
            "key": SETTINGS_KEY,
            "category": "clinic",
            "value": {"version": 1, "tabs": []},
        },
    )
    assert create.status_code == 409
    assert create.json()["detail"]["code"] == "use_registrar_tabs_endpoint"
    assert (
        client.put(
            "/api/v1/admin/clinic/settings",
            json={"settings": {SETTINGS_KEY: {"version": 1, "tabs": []}}},
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/v1/admin/clinic/settings/{SETTINGS_KEY}",
            json={"value": {"version": 1, "tabs": []}},
        ).status_code
        == 409
    )
    assert (
        client.get(f"/api/v1/admin/clinic/settings/{SETTINGS_KEY}").status_code == 404
    )
    category = client.get("/api/v1/admin/clinic/settings?category=registrar_tabs")
    assert category.status_code == 200
    assert all(row["key"] != SETTINGS_KEY for row in category.json())
