"""Physical nonowner PostgreSQL login for policy writer authorization races."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.clinic import ClinicSettings
from app.models.user import User
from app.services.all_free_policy import _ALL_FREE_POLICY_LOCK
from app.services.authentication_service import authentication_service
from tests.integration.test_doctor_price_producer_races_pg import provisioned_database  # noqa: F401


@pytest.fixture
def pg_writer(monkeypatch, provisioned_database):
    admin_engine, _, schema_owner, _, runtime_role = provisioned_database
    url = make_url(os.environ["DATABASE_URL"])
    synthetic_password = uuid4().hex + uuid4().hex
    with admin_engine.begin() as db:
        db.execute(text("SELECT pg_catalog.set_config('clinic.test_role', :role, true)"), {"role": runtime_role})
        db.execute(text("SELECT pg_catalog.set_config('clinic.test_password', :password, true)"), {"password": synthetic_password})
        db.execute(text("""DO $$ BEGIN EXECUTE pg_catalog.format('ALTER ROLE %I PASSWORD %L',
          pg_catalog.current_setting('clinic.test_role'), pg_catalog.current_setting('clinic.test_password')); END $$"""))
        auth_owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.token_blacklist'::pg_catalog.regclass")).scalar_one()
        users_owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE oid='public.users'::pg_catalog.regclass")).scalar_one()
    runtime_engine = create_engine(url.set(username=runtime_role, password=synthetic_password))
    with runtime_engine.connect() as db:
        assert db.execute(text("SELECT SESSION_USER")).scalar_one() == runtime_role
    admins = sessionmaker(bind=admin_engine, expire_on_commit=False, autoflush=False)
    sessions = sessionmaker(bind=runtime_engine, expire_on_commit=False, autoflush=False)
    with admins() as db:
        suffix = uuid4().hex[:12]
        actor = User(username=f"synthetic_policy_admin_{suffix}", hashed_password="!synthetic", role="Admin", is_active=True)
        db.add(actor)
        row = db.query(ClinicSettings).filter_by(key="repeat_visit_days").first()
        if row is None:
            db.add(ClinicSettings(key="repeat_visit_days", value=21))
        else:
            row.value = 21
        db.commit()
        token = authentication_service.create_access_token({"sub": str(actor.id), "username": actor.username,
            "role": actor.role, "is_active": True, "is_superuser": False, "auth_epoch": actor.auth_epoch})
        actor_id = actor.id
    for name, value in {
        "TRUSTED_DB_SCHEMA": "public", "TRUSTED_DB_SCHEMA_OWNER": schema_owner,
        "TRUSTED_DB_RUNTIME_ROLE": runtime_role, "TRUSTED_DB_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_TABLE_OWNER": auth_owner, "TRUSTED_AUTH_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_READ_ROLES": (), "TRUSTED_AUTH_WRITE_ROLES": (),
        "TRUSTED_AUTH_USERS_OWNER": users_owner, "TRUSTED_AUTH_USERS_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_USERS_WRITE_ROLES": (),
    }.items():
        monkeypatch.setattr(settings, name, value)

    def database():
        with sessions() as db:
            yield db

    old = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client, admins, {"Authorization": f"Bearer {token}"}, actor_id
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)
        runtime_engine.dispose()


@pytest.mark.parametrize("blocked", ["admin_user", "all_free_policy"])
def test_policy_writer_conflict_rolls_back_and_retry_succeeds(pg_writer, blocked):
    client, admins, headers, actor_id = pg_writer
    if blocked == "admin_user":
        path = "/api/v1/admin/clinic/settings/repeat_visit_days"
        method = client.put
        body = {"value": 30}
    else:
        path = "/api/v1/admin/benefit-settings"
        method = client.post
        body = {"repeat_visit_days": 30, "repeat_visit_discount": 15, "all_free_auto_approve": False}
    with admins() as blocker:
        if blocked == "admin_user":
            blocker.query(User).filter_by(id=actor_id).with_for_update().one()
        else:
            blocker.execute(text("SELECT pg_catalog.pg_advisory_xact_lock(:key)"), {"key": _ALL_FREE_POLICY_LOCK})
        response = method(path, headers=headers, json=body)
        assert response.status_code == 409, response.text
        blocker.rollback()
    with admins() as db:
        assert db.query(ClinicSettings).filter_by(key="repeat_visit_days").one().value == 21
    response = method(path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    with admins() as db:
        assert db.query(ClinicSettings).filter_by(key="repeat_visit_days").one().value == 30


def test_admin_deactivation_waits_for_authorized_write_and_revoked_retry_fails(pg_writer, monkeypatch):
    from app.api.v1.endpoints import admin_clinic

    client, admins, headers, actor_id = pg_writer
    ready, release = threading.Event(), threading.Event()
    original = admin_clinic.crud_clinic.update_setting

    def pause_after_auth(*args, **kwargs):
        ready.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(admin_clinic.crud_clinic, "update_setting", pause_after_auth)
    path = "/api/v1/admin/clinic/settings/repeat_visit_days"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.put, path, headers=headers, json={"value": 30})
        try:
            assert ready.wait(10)
            with admins() as deactivation:
                deactivation.execute(text("SET LOCAL lock_timeout='100ms'"))
                with pytest.raises(DBAPIError) as error:
                    deactivation.execute(text("UPDATE users SET is_active=false WHERE id=:id"), {"id": actor_id})
                assert (getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)) == "55P03"
                deactivation.rollback()
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    with admins() as db:
        actor = db.get(User, actor_id)
        actor.is_active = False
        db.commit()
    response = client.put(path, headers=headers, json={"value": 5})
    assert response.status_code in {401, 403}, response.text
    with admins() as db:
        assert db.query(ClinicSettings).filter_by(key="repeat_visit_days").one().value == 30
