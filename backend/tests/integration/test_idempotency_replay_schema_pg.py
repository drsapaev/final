"""Idempotent replay must authenticate through the actual trusted PG schema."""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
import sqlalchemy as sa
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.api.trusted_financial_auth import financial_reviewer
from app.core.config import settings
from app.middleware import idempotency_middleware as idem
from app.models.authentication import TokenBlacklist
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserAuditLog
from tests.conftest import mint_access_token
from tests.integration.test_invitation_subject_nonowner_pg import subject_environment  # noqa: F401
from tests.integration.test_repeat_settings_writers_pg import (  # noqa: F401
    pg_writer,
    provisioned_database,
)
from tests.integration.test_trusted_schema_pg import trusted_pg  # noqa: F401


@pytest.fixture
def protected_app(trusted_pg, monkeypatch):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qo, qr = map(quote, (schema, owner, runtime))
    with engine.begin() as connection:
        connection.exec_driver_sql(f"SET LOCAL search_path TO {qs}, pg_catalog")
        connection.exec_driver_sql(f"DROP TABLE {qs}.token_blacklist")
        connection.exec_driver_sql(f"DROP TABLE {qs}.users")
        User.__table__.create(connection)
        TokenBlacklist.__table__.create(connection)
        UserAuditLog.__table__.create(connection)
        connection.exec_driver_sql(f"CREATE TABLE {qs}.patients (id integer PRIMARY KEY, user_id integer, is_deleted boolean)")
        for table in ("users", "token_blacklist", "patients"):
            connection.exec_driver_sql(f"ALTER TABLE {qs}.{table} OWNER TO {qo}")
            connection.exec_driver_sql(f"GRANT SELECT ON {qs}.{table} TO {qr}")
        connection.exec_driver_sql(f"ALTER TABLE {qs}.users ENABLE ROW LEVEL SECURITY")
        connection.exec_driver_sql(f"ALTER TABLE {qs}.users FORCE ROW LEVEL SECURITY")
        connection.exec_driver_sql(f"GRANT UPDATE (auth_epoch) ON {qs}.users TO {qr}")
        connection.exec_driver_sql(f"CREATE POLICY replay_user_select ON {qs}.users FOR SELECT TO {qr} USING (true)")
        connection.exec_driver_sql(f"CREATE POLICY replay_user_lock ON {qs}.users FOR UPDATE TO {qr} USING (true) WITH CHECK (false)")
        connection.exec_driver_sql(f"GRANT SELECT, INSERT ON {qs}.user_audit_logs TO {qr}")
        connection.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {qs}.user_audit_logs_id_seq TO {qr}")
        connection.exec_driver_sql(f"ALTER TABLE {qs}.token_blacklist ENABLE ROW LEVEL SECURITY")
        connection.exec_driver_sql(f"ALTER TABLE {qs}.token_blacklist FORCE ROW LEVEL SECURITY")
        connection.exec_driver_sql(f"CREATE POLICY replay_visible ON {qs}.token_blacklist FOR SELECT TO {qr} USING (true)")
        with Session(bind=connection) as db:
            actor = User(username="SYNTHETIC-replay", hashed_password="unused", role="Admin",
                         is_active=True, is_superuser=False, auth_epoch=0)
            db.add(actor)
            db.flush()
            token, actor_id = mint_access_token(actor), actor.id

    for name, value in {
        "TRUSTED_DB_SCHEMA": schema, "TRUSTED_DB_SCHEMA_OWNER": owner,
        "TRUSTED_DB_RUNTIME_ROLE": runtime, "TRUSTED_DB_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_TABLE_OWNER": owner, "TRUSTED_AUTH_USERS_OWNER": owner,
        "TRUSTED_AUTH_OWNER_MEMBERS": (), "TRUSTED_AUTH_READ_ROLES": (),
        "TRUSTED_AUTH_WRITE_ROLES": (), "TRUSTED_AUTH_USERS_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_USERS_WRITE_ROLES": (), "DOCTOR_PRICE_DB_SCHEMA": None,
        "DOCTOR_PRICE_DB_SCHEMA_OWNER": None, "INVITATION_DB_SCHEMA": None,
        "INVITATION_DB_SCHEMA_OWNER": None,
    }.items():
        monkeypatch.setattr(settings, name, value)
    login = sa.create_engine(engine.url.set(username=runtime, password=engine._synthetic_runtime_password))
    with login.connect() as connection:
        assert connection.execute(sa.text("SELECT current_user,session_user")).one() == (runtime, runtime)
    monkeypatch.setattr(login.dialect, "default_schema_name", schema)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: None)
    idem.get_idempotency_cache().clear()
    app = FastAPI()
    app.add_middleware(idem.IdempotencyMiddleware)
    calls = []

    def override_db():
        with Session(login) as db:
            db.execute(sa.text(f"CREATE TEMP TABLE users (LIKE {qs}.users INCLUDING ALL)"))
            db.execute(sa.text(f"CREATE TEMP TABLE token_blacklist (LIKE {qs}.token_blacklist INCLUDING ALL)"))
            db.execute(sa.text("CREATE TEMP TABLE patients (id integer PRIMARY KEY, user_id integer, is_deleted boolean)"))
            db.execute(sa.text(f"INSERT INTO pg_temp.users SELECT * FROM {qs}.users"))
            db.execute(sa.text("UPDATE pg_temp.users SET role='Admin', is_active=true"))
            db.execute(sa.text(f"SET LOCAL search_path TO pg_temp, {qs}, pg_catalog"))
            yield db
            db.rollback()

    app.dependency_overrides[get_db] = override_db

    @app.post("/synthetic")
    async def protected(actor: User = Depends(financial_reviewer),
                        _role=Depends(require_roles("Admin", "SuperAdmin", "Registrar"))):
        calls.append(actor.id)
        return {"outcome": "SYNTHETIC", "actor": actor.id}

    protected.idempotency_replay_global_roles = ("Admin", "SuperAdmin", "Registrar")

    @app.post("/synthetic-unverified")
    async def protected_unverified(actor: User = Depends(financial_reviewer)):
        calls.append(actor.id)
        return {"outcome": "SYNTHETIC", "actor": actor.id}

    @app.post("/api/v1/appointments/synthetic")
    async def audited_route(actor: User = Depends(financial_reviewer)):
        calls.append(actor.id)
        return {"outcome": "SYNTHETIC"}

    audited_route.idempotency_replay_global_roles = ("Admin", "SuperAdmin", "Registrar")

    admin_router = APIRouter(prefix="/api/v1/admin")

    @admin_router.post("/consultations/{visit_id}/deactivate")
    async def nested_audited_route(visit_id: int, actor: User = Depends(financial_reviewer)):
        calls.append(actor.id)
        return {"outcome": "SYNTHETIC", "id": visit_id}

    nested_audited_route.idempotency_replay_global_roles = ("Admin", "SuperAdmin", "Registrar")
    app.include_router(admin_router)

    try:
        with TestClient(app) as client:
            yield client, engine, schema, runtime, token, actor_id, calls
    finally:
        idem.get_idempotency_cache().clear()
        login.dispose()


def _request(client, token, key):
    return client.post("/synthetic", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key}, json={})


def test_replay_reads_real_users_and_blacklist_with_physical_login(protected_app):
    client, engine, schema, _, token, actor_id, calls = protected_app
    key = uuid4().hex
    first = _request(client, token, key)
    assert first.status_code == 200, first.text
    replay = _request(client, token, key)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert calls == [actor_id]
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog")
        with Session(bind=connection) as db:
            db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            db.flush()
    refused = _request(client, token, key)
    assert refused.status_code in {401, 403}
    assert calls == [actor_id]


@pytest.mark.parametrize("anchor", ["DOCTOR_PRICE_DB_SCHEMA", "DOCTOR_PRICE_DB_SCHEMA_OWNER",
                                    "INVITATION_DB_SCHEMA", "INVITATION_DB_SCHEMA_OWNER",
                                    "default_schema_name"])
def test_replay_refuses_inconsistent_financial_schema_anchor(protected_app, monkeypatch, anchor):
    client, _, _, _, token, actor_id, calls = protected_app
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    if anchor == "default_schema_name":
        source = client.app.dependency_overrides[get_db]()
        db = next(source)
        monkeypatch.setattr(db.get_bind().dialect, "default_schema_name", "synthetic_inconsistent_anchor")
        source.close()
    else:
        monkeypatch.setattr(settings, anchor, "synthetic_inconsistent_anchor")
    refused = _request(client, token, key)
    assert refused.status_code == 503, refused.text
    assert calls == [actor_id]


def test_distributed_replay_rechecks_revocation_with_physical_login(protected_app, monkeypatch):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, engine, schema, _, token, actor_id, calls = protected_app
    claim = _make_claim(FakeRedis())
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    key = uuid4().hex
    first = _request(client, token, key)
    assert first.status_code == 200, first.text
    idem.get_idempotency_cache().clear()
    replay = _request(client, token, key)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert calls == [actor_id]
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog")
        with Session(bind=connection) as db:
            db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            db.flush()
    idem.get_idempotency_cache().clear()
    refused = _request(client, token, key)
    assert refused.status_code in {401, 403}
    assert calls == [actor_id]


@pytest.mark.parametrize("damage", ["malformed", "empty", "body", "valid_body", "missing_provenance", "payload"])
def test_corrupt_or_old_outcome_is_preserved_without_reexecution(protected_app, monkeypatch, damage):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, _, _, _, token, actor_id, calls = protected_app
    redis = FakeRedis()
    claim = _make_claim(redis)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: False)
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    redis_key = claim._resp_key(idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic"), key)
    snapshot = json.loads(redis.store[redis_key])
    if damage == "malformed":
        raw = "{broken"
    elif damage == "empty":
        raw = ""
    else:
        if damage == "body":
            snapshot["body_b64"] = "!!!"
        elif damage == "valid_body":
            snapshot["body_b64"] = "eyJvdXRjb21lIjoiZm9yZ2VkIn0="
        elif damage == "missing_provenance":
            snapshot.pop("provenance_version")
        else:
            snapshot.pop("payload_hash")
        raw = json.dumps(snapshot)
    redis.store[redis_key] = raw
    idem.get_idempotency_cache().clear()
    retry = _request(client, token, key)
    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_reconciliation_required"
    assert redis.store[redis_key] == raw
    assert calls == [actor_id]


def test_snapshot_cannot_move_to_another_key_or_survive_signing_key_rotation(protected_app, monkeypatch):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, _, _, _, token, actor_id, calls = protected_app
    redis = FakeRedis()
    claim = _make_claim(redis)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: False)
    original_key, copied_key = uuid4().hex, uuid4().hex
    assert _request(client, token, original_key).status_code == 200
    namespace = idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic")
    raw = redis.store[claim._resp_key(namespace, original_key)]
    redis.store[claim._resp_key(namespace, copied_key)] = raw
    idem.get_idempotency_cache().clear()
    copied = _request(client, token, copied_key)
    assert copied.status_code == 409 and copied.json()["code"] == "idempotency_reconciliation_required"
    assert redis.store[claim._resp_key(namespace, copied_key)] == raw
    other_namespace = idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic-unverified")
    redis.store[claim._resp_key(other_namespace, original_key)] = raw
    other = client.post("/synthetic-unverified", headers={"Authorization": f"Bearer {token}",
                        "Idempotency-Key": original_key}, json={})
    assert other.status_code == 409 and other.json()["code"] == "idempotency_reconciliation_required"
    assert redis.store[claim._resp_key(other_namespace, original_key)] == raw
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    monkeypatch.setattr(settings, "SECRET_KEY", "synthetic-rotated-signing-key")
    replacement_token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    rotated = _request(client, replacement_token, original_key)
    assert rotated.status_code == 409 and rotated.json()["code"] == "idempotency_reconciliation_required"
    assert redis.store[claim._resp_key(namespace, original_key)] == raw
    assert calls == [actor_id]


@pytest.mark.parametrize("contended", [False, True])
def test_old_legacy_stamped_outcome_cannot_be_promoted(protected_app, monkeypatch, contended):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, _, _, _, token, actor_id, calls = protected_app
    redis = FakeRedis()
    claim = _make_claim(redis)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: False)
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    current = idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic")
    legacy = idem.IdempotencyMiddleware._namespace(actor_id)
    old = json.loads(redis.store.pop(claim._resp_key(current, key)))
    old.pop("provenance_version")
    old["operation_scope"] = "POST:/synthetic"
    raw = json.dumps(old)
    legacy_key = claim._resp_key(legacy, key)
    redis.store[legacy_key] = raw
    lock_key = claim._claim_key(legacy, key)
    if contended:
        redis.store[lock_key] = "another-worker"
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: True)
    idem.get_idempotency_cache().clear()
    retry = _request(client, token, key)
    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_reconciliation_required"
    assert redis.store[legacy_key] == raw
    assert redis.store.get(lock_key) == ("another-worker" if contended else None)
    assert claim._resp_key(current, key) not in redis.store
    assert calls == [actor_id]


def test_corrupt_outcome_discovered_after_claim_releases_our_claim(protected_app, monkeypatch):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, _, _, _, token, actor_id, calls = protected_app
    redis = FakeRedis()
    claim = _make_claim(redis)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: False)
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    namespace = idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic")
    response_key = claim._resp_key(namespace, key)
    redis.store.pop(response_key)
    idem.get_idempotency_cache().clear()
    load = claim.load_response
    reads = []

    def inject_after_claim(user_id, idem_key):
        reads.append(1)
        if len(reads) == 2:
            redis.store[response_key] = "{broken"
        return load(user_id, idem_key)

    monkeypatch.setattr(claim, "load_response", inject_after_claim)
    retry = _request(client, token, key)
    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_reconciliation_required"
    assert redis.store[response_key] == "{broken"
    assert claim._claim_key(namespace, key) not in redis.store
    assert calls == [actor_id]


@pytest.mark.parametrize("foreign_replacement", [False, True])
def test_post_claim_authorization_failure_releases_only_owned_claim(protected_app, monkeypatch, foreign_replacement):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, _, _, _, token, actor_id, calls = protected_app
    redis = FakeRedis()
    claim = _make_claim(redis)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: False)
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    namespace = idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic")
    response_key, lock_key = claim._resp_key(namespace, key), claim._claim_key(namespace, key)
    original_outcome = redis.store.pop(response_key)
    idem.get_idempotency_cache().clear()
    load = claim.load_response
    reads = []

    def inject_outcome(user_id, idem_key):
        reads.append(1)
        if len(reads) == 2:
            redis.store[response_key] = original_outcome
        return load(user_id, idem_key)

    async def unavailable(*args, **kwargs):
        if foreign_replacement:
            redis.store[lock_key] = "foreign-owner"
        raise idem.IdempotencyAuthorizationUnavailable

    with monkeypatch.context() as scoped:
        scoped.setattr(claim, "load_response", inject_outcome)
        scoped.setattr(idem.IdempotencyMiddleware, "_principal_authorized", unavailable)
        assert _request(client, token, key).status_code == 503
    assert redis.store.get(lock_key) == ("foreign-owner" if foreign_replacement else None)
    assert redis.store[response_key] == original_outcome and calls == [actor_id]
    if foreign_replacement:
        redis.store.pop(lock_key)
    assert _request(client, token, key).status_code == 200
    assert calls == [actor_id]


def test_legacy_authorization_failure_releases_our_fence(protected_app, monkeypatch):
    from tests.unit.test_idempotency_distributed_claim import FakeRedis, _make_claim

    client, _, _, _, token, actor_id, calls = protected_app
    redis = FakeRedis()
    claim = _make_claim(redis)
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: False)
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    current = idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic")
    legacy = idem.IdempotencyMiddleware._namespace(actor_id)
    response, payload_hash, role = claim.load_response(current, key)
    assert claim.store_response(legacy, key, response, payload_hash=payload_hash,
                                principal_role=role, operation_scope="POST:/synthetic")
    redis.store.pop(claim._resp_key(current, key))
    idem.get_idempotency_cache().clear()
    monkeypatch.setattr(idem, "_legacy_bridge_active", lambda: True)

    async def unavailable(*args, **kwargs):
        raise idem.IdempotencyAuthorizationUnavailable

    with monkeypatch.context() as scoped:
        scoped.setattr(idem.IdempotencyMiddleware, "_principal_authorized", unavailable)
        assert _request(client, token, key).status_code == 503
    assert claim._claim_key(legacy, key) not in redis.store
    assert _request(client, token, key).status_code == 200
    assert calls == [actor_id]


@pytest.mark.redis
def test_real_redis_replay_rechecks_revocation_with_physical_login(protected_app, monkeypatch):
    import redis

    from tests.unit.test_idempotency_distributed_claim import _make_claim

    url = os.environ.get("TEST_IDEMPOTENCY_REDIS_URL")
    if not url:
        pytest.skip("requires disposable local Redis")
    from urllib.parse import urlsplit

    assert urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}
    redis_client = redis.Redis.from_url(url, decode_responses=True)
    redis_client.ping()
    claim = _make_claim(redis_client)
    claim._prefix = "synthetic-idem-" + uuid4().hex
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: claim)
    client, engine, schema, _, token, actor_id, calls = protected_app
    try:
        key = uuid4().hex
        first = _request(client, token, key)
        assert first.status_code == 200, first.text
        idem.get_idempotency_cache().clear()
        replay = _request(client, token, key)
        assert replay.status_code == 200 and replay.json() == first.json()
        assert calls == [actor_id]
        outcome_key = claim._resp_key(idem.IdempotencyMiddleware._namespace(actor_id, "POST:/synthetic"), key)
        original = redis_client.get(outcome_key)
        old = json.loads(original)
        old.pop("provenance_version")
        old_raw = json.dumps(old)
        redis_client.set(outcome_key, old_raw, ex=600)
        idem.get_idempotency_cache().clear()
        refused_old = _request(client, token, key)
        assert refused_old.status_code == 409, refused_old.text
        assert refused_old.json()["code"] == "idempotency_reconciliation_required"
        assert redis_client.get(outcome_key) == old_raw and calls == [actor_id]
        redis_client.set(outcome_key, original, ex=600)
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        quote = engine.dialect.identifier_preparer.quote_identifier
        with engine.begin() as connection:
            connection.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog")
            with Session(bind=connection) as db:
                db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
                db.flush()
        idem.get_idempotency_cache().clear()
        refused = _request(client, token, key)
        assert refused.status_code in {401, 403}
        assert calls == [actor_id]
    finally:
        for existing in redis_client.scan_iter(f"{claim._prefix}:*"):
            redis_client.delete(existing)
        redis_client.close()


def test_hidden_blacklist_is_unavailable_and_does_not_execute(protected_app):
    client, engine, schema, runtime, token, actor_id, calls = protected_app
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.exec_driver_sql(f"DROP POLICY replay_visible ON {quote(schema)}.token_blacklist")
        connection.exec_driver_sql(f"CREATE POLICY replay_hidden ON {quote(schema)}.token_blacklist "
                                   f"FOR SELECT TO {quote(runtime)} USING (false)")
    refused = _request(client, token, key)
    assert refused.status_code == 503, refused.text
    assert calls == [actor_id]


def test_replay_never_passes_an_inflight_logout_lock(protected_app):
    client, engine, schema, _, token, actor_id, calls = protected_app
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.exec_driver_sql(f"SET LOCAL search_path TO {quote(schema)}, pg_catalog")
        with Session(bind=connection) as db:
            assert db.query(User.id).filter(User.id == actor_id).with_for_update().one()
            pending = _request(client, token, key)
            assert pending.status_code == 503, pending.text
            assert calls == [actor_id]
            db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            db.flush()
    refused = _request(client, token, key)
    assert refused.status_code in {401, 403}
    assert calls == [actor_id]


def test_legacy_bearer_without_revocable_jti_never_executes(protected_app):
    client, _, _, _, _, actor_id, calls = protected_app
    token = jwt.encode({"sub": str(actor_id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
                       settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = _request(client, token, uuid4().hex)
    assert response.status_code == 403, response.text
    assert calls == []


def test_authorization_database_error_never_logs_jti(caplog):
    secret = "SYNTHETIC-jti-must-not-appear-in-logs"

    class BrokenDB:
        def execute(self, _statement):
            raise sa.exc.StatementError("synthetic failure", "SELECT :jti", {"jti": secret}, Exception("failure"))

    assert idem._user_authorized_in_db(BrokenDB(), 1, None, secret)[0] is False
    assert secret not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_unknown_resource_policy_preserves_outcome_without_execution(protected_app):
    client, _, _, _, token, actor_id, calls = protected_app
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex}
    first = client.post("/synthetic-unverified", headers=headers, json={})
    assert first.status_code == 200, first.text
    retry = client.post("/synthetic-unverified", headers=headers, json={})
    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_reconciliation_required"
    assert calls == [actor_id]


@pytest.mark.parametrize("audit_available", [True, False])
def test_role_denial_audits_without_reexecuting(protected_app, audit_available, caplog):
    client, engine, schema, runtime, token, actor_id, calls = protected_app
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex}
    path = "/api/v1/appointments/synthetic"
    first = client.post(path, headers=headers, json={})
    assert first.status_code == 200, first.text
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE {quote(schema)}.users SET role='Cashier' WHERE id=:id"),
                           {"id": actor_id})
        if not audit_available:
            connection.exec_driver_sql(f"REVOKE INSERT ON {quote(schema)}.user_audit_logs FROM {quote(runtime)}")
    denied = client.post(path, headers=headers, json={})
    assert denied.status_code == 403, denied.text
    assert calls == [actor_id]
    with engine.connect() as connection:
        rows = connection.execute(sa.text(f"SELECT action, resource_type FROM {quote(schema)}.user_audit_logs")).all()
    assert rows == ([("ACCESS_DENIED", "appointments")] if audit_available else [])
    assert token not in caplog.text
    assert jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["jti"] not in caplog.text


@pytest.mark.parametrize("audit_available", [True, False])
def test_inactive_actor_denial_is_audited_without_execution(protected_app, audit_available, caplog):
    client, engine, schema, runtime, token, actor_id, calls = protected_app
    key = uuid4().hex
    assert _request(client, token, key).status_code == 200
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE {quote(schema)}.users SET is_active=false WHERE id=:id"), {"id": actor_id})
        if not audit_available:
            connection.exec_driver_sql(f"REVOKE INSERT ON {quote(schema)}.user_audit_logs FROM {quote(runtime)}")
    assert _request(client, token, key).status_code == 403
    assert calls == [actor_id]
    with engine.connect() as connection:
        rows = connection.execute(sa.text(f"SELECT user_id, action, new_values FROM {quote(schema)}.user_audit_logs")).all()
    if audit_available:
        assert len(rows) == 1
        assert rows[0].user_id == actor_id and rows[0].action == "ACCESS_DENIED"
        assert rows[0].new_values["denial_reason"] == "user_deactivated"
    else:
        assert rows == []
    assert token not in caplog.text


def test_inactive_actor_is_audited_on_first_keyed_request(protected_app):
    client, engine, schema, _, token, actor_id, calls = protected_app
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE {quote(schema)}.users SET is_active=false WHERE id=:id"), {"id": actor_id})
    assert _request(client, token, uuid4().hex).status_code == 403
    assert not calls
    with engine.connect() as connection:
        rows = connection.execute(sa.text(f"SELECT user_id, action FROM {quote(schema)}.user_audit_logs")).all()
    assert rows == [(actor_id, "ACCESS_DENIED")]


def test_inactive_actor_audit_uses_nested_route_template(protected_app):
    client, engine, schema, _, token, actor_id, calls = protected_app
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex}
    path = "/api/v1/admin/consultations/123/deactivate"
    assert client.post(path, headers=headers, json={}).status_code == 200
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE {quote(schema)}.users SET is_active=false WHERE id=:id"), {"id": actor_id})
    assert client.post(path, headers=headers, json={}).status_code == 403
    assert calls == [actor_id]
    with engine.connect() as connection:
        rows = connection.execute(sa.text(
            f"SELECT user_id, action, resource_type, resource_id FROM {quote(schema)}.user_audit_logs"
        )).all()
    assert rows == [(actor_id, "ACCESS_DENIED", "consultations", 123)]


def test_patient_replay_is_bound_to_ownership_generation(subject_environment, monkeypatch):
    owner, runtime, _, _ = subject_environment
    with Session(owner) as db:
        actor = User(username="SYNTHETIC-patient-" + uuid4().hex, hashed_password="!", role="Patient", is_active=True)
        other = User(username="SYNTHETIC-patient-" + uuid4().hex, hashed_password="!", role="Patient", is_active=True)
        db.add_all([actor, other])
        db.flush()
        patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", user_id=actor.id)
        db.add(patient)
        db.flush()
        patient_id, actor_id, other_id, token = patient.id, actor.id, other.id, mint_access_token(actor)
        db.commit()
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: None)
    idem.get_idempotency_cache().clear()
    app = FastAPI()
    app.add_middleware(idem.IdempotencyMiddleware)
    calls = []

    def database():
        with Session(runtime) as db:
            yield db

    app.dependency_overrides[get_db] = database

    @app.post("/patient-synthetic")
    async def patient_route(actor=Depends(require_roles("Patient"))):
        calls.append(actor.id)
        return {"outcome": "SYNTHETIC"}

    patient_route.idempotency_replay_global_roles = ("Patient",)

    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex}
    try:
        with TestClient(app) as client:
            first = client.post("/patient-synthetic", headers=headers, json={})
            assert first.status_code == 200, first.text
            replay = client.post("/patient-synthetic", headers=headers, json={})
            assert replay.status_code == 200 and replay.json() == first.json()
            with Session(owner) as db:
                db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=other_id))
                db.commit()
                no_card = client.post("/patient-synthetic", headers=headers, json={})
                assert no_card.status_code == 409, no_card.text
                assert no_card.json()["code"] == "idempotency_reconciliation_required"
                assert calls == [actor_id]
                db.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=actor_id))
                db.commit()
            refused = client.post("/patient-synthetic", headers=headers, json={})
            assert refused.status_code == 409, refused.text
            assert refused.json()["code"] == "idempotency_scope_mismatch"
            assert calls == [actor_id]
    finally:
        idem.get_idempotency_cache().clear()


@pytest.mark.parametrize("transfer_first", [True, False])
def test_patient_replay_and_transfer_serialize(subject_environment, monkeypatch, transfer_first):
    from app.services import patient_subject_lock

    owner, runtime, _, login = subject_environment
    with Session(owner) as db:
        actor = User(username="SYNTHETIC-owner-" + uuid4().hex, hashed_password="!", role="Patient", is_active=True)
        other = User(username="SYNTHETIC-owner-" + uuid4().hex, hashed_password="!", role="Patient", is_active=True)
        db.add_all([actor, other])
        db.flush()
        patient = Patient(first_name="SYNTHETIC", last_name="LOCK", user_id=actor.id)
        db.add(patient)
        db.flush()
        patient_id, actor_id, other_id, token = patient.id, actor.id, other.id, mint_access_token(actor)
        db.commit()
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: None)
    idem.get_idempotency_cache().clear()
    app = FastAPI()
    app.add_middleware(idem.IdempotencyMiddleware)
    calls = []

    def database():
        with Session(runtime) as db:
            yield db

    app.dependency_overrides[get_db] = database

    @app.post("/patient-lock")
    async def patient_route(actor=Depends(require_roles("Patient"))):
        calls.append(actor.id)
        return {"outcome": "SYNTHETIC"}

    patient_route.idempotency_replay_global_roles = ("Patient",)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": uuid4().hex}
    try:
        with TestClient(app) as client:
            assert client.post("/patient-lock", headers=headers, json={}).status_code == 200
            ready, release = threading.Event(), threading.Event()
            if transfer_first:
                original_lock = patient_subject_lock.lock_patient_subject

                def signal_lock(db, subject_id):
                    ready.set()
                    return original_lock(db, subject_id)

                monkeypatch.setattr(patient_subject_lock, "lock_patient_subject", signal_lock)
                with Session(owner) as transfer, ThreadPoolExecutor(max_workers=1) as pool:
                    transfer.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=other_id))
                    retry = pool.submit(client.post, "/patient-lock", headers=headers, json={})
                    assert ready.wait(5)
                    deadline = time.monotonic() + 1.5
                    blocked = False
                    while time.monotonic() < deadline:
                        with owner.connect() as monitor:
                            blocked = bool(monitor.execute(sa.text("""
                                SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_stat_activity
                                  WHERE usename=:login AND wait_event_type='Lock' AND state='active')
                            """), {"login": login}).scalar_one())
                        if blocked:
                            break
                        time.sleep(0.01)
                    assert blocked, "replay did not wait for the patient transfer lock"
                    transfer.commit()
                    refused = retry.result(timeout=5)
                    assert refused.status_code == 403, refused.text
            else:
                original_check = idem._user_authorized_in_db

                def pause_after_subject_lock(*args, **kwargs):
                    ready.set()
                    assert release.wait(5)
                    return original_check(*args, **kwargs)

                monkeypatch.setattr(idem, "_user_authorized_in_db", pause_after_subject_lock)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    retry = pool.submit(client.post, "/patient-lock", headers=headers, json={})
                    try:
                        assert ready.wait(5)
                        with Session(owner) as transfer:
                            transfer.execute(sa.text("SET LOCAL lock_timeout='100ms'"))
                            with pytest.raises(sa.exc.DBAPIError) as error:
                                transfer.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=other_id))
                            assert (getattr(error.value.orig, "sqlstate", None)
                                    or getattr(error.value.orig, "pgcode", None)) == "55P03"
                            transfer.rollback()
                    finally:
                        release.set()
                    assert retry.result(timeout=5).status_code == 200
            assert calls == [actor_id]
    finally:
        idem.get_idempotency_cache().clear()


@pytest.mark.parametrize("user_active,deleted,superuser", [
    (False, False, False), (True, True, False), (False, True, False),
    (False, True, True), (True, True, True),
])
@pytest.mark.parametrize("transfer_first", [False, True])
def test_patient_keyed_denial_audits_only_valid_bearer(subject_environment, monkeypatch, user_active, deleted, superuser, transfer_first):
    from app.models.patient_access_audit import PatientAccessAuditLog
    from app.services import patient_access_audit, patient_subject_lock

    owner, runtime, schema, login = subject_environment
    quote = owner.dialect.identifier_preparer.quote_identifier
    with owner.begin() as connection:
        connection.execute(sa.schema.CreateTable(PatientAccessAuditLog.__table__, include_foreign_key_constraints=[]))
        connection.exec_driver_sql(f"GRANT SELECT, INSERT ON {quote(schema)}.patient_access_audit_logs TO {quote(login)}")
        connection.exec_driver_sql(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {quote(schema)} TO {quote(login)}")
    with Session(owner) as db:
        actor = User(username="SYNTHETIC-deleted-" + uuid4().hex, hashed_password="!", role="Patient", is_active=user_active, is_superuser=superuser)
        db.add(actor)
        db.flush()
        patient = Patient(first_name="SYNTHETIC", last_name="PATIENT", user_id=actor.id, is_deleted=deleted)
        db.add(patient)
        db.flush()
        patient_id, actor_id, token = patient.id, actor.id, mint_access_token(actor)
        db.commit()
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: None)
    app = FastAPI()
    app.add_middleware(idem.IdempotencyMiddleware)
    calls = []

    def database():
        with Session(runtime) as db:
            yield db

    app.dependency_overrides[get_db] = database

    @app.post("/api/v1/patients/booking")
    async def booking():
        calls.append(1)
        return {"outcome": "unexpected"}

    with TestClient(app) as client:
        response = client.post("/api/v1/patients/booking", headers={"Authorization": f"Bearer {token}",
                               "Idempotency-Key": uuid4().hex}, json={})
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        for bound_patient in (patient_id, patient_id + 10000):
            scoped_claims = {**claims, "scope": "patient_portal", "patient_id": bound_patient}
            scoped_claims.pop("username", None)
            scoped_token = jwt.encode(scoped_claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            assert client.post("/api/v1/patients/booking", headers={"Authorization": f"Bearer {scoped_token}",
                               "Idempotency-Key": uuid4().hex}, json={}).status_code in {403, 409}
    assert response.status_code == (409 if user_active else 403) and not calls
    with Session(owner) as db:
        row = db.query(PatientAccessAuditLog).one()
        assert row.subject_patient_id == patient_id and row.actor_patient_id == patient_id
        assert row.outcome == "denied" and row.resource_type == "appointment" and row.action == "create"
        assert row.extra_data["reason"] == ("patient_link_invalid" if user_active else "user_deactivated")
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                              expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        db.commit()
    with TestClient(app) as client:
        refused = client.post("/api/v1/patients/booking", headers={"Authorization": f"Bearer {token}",
                              "Idempotency-Key": uuid4().hex}, json={})
    assert refused.status_code in {403, 409} and not calls
    with Session(owner) as db:
        assert db.query(PatientAccessAuditLog).count() == 1

    race_claims = {**claims, "jti": uuid4().hex}
    race_token = jwt.encode(race_claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    race_headers = {"Authorization": f"Bearer {race_token}", "Idempotency-Key": uuid4().hex}
    with Session(owner) as logout, TestClient(app) as client:
        assert logout.query(User.id).filter(User.id == actor_id).with_for_update().one()
        assert client.post("/api/v1/patients/booking", headers=race_headers, json={}).status_code in {403, 409}
        logout.add(TokenBlacklist(jti=race_claims["jti"], user_id=actor_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        logout.commit()
        assert client.post("/api/v1/patients/booking", headers=race_headers, json={}).status_code in {403, 409}
    with Session(owner) as db:
        assert db.query(PatientAccessAuditLog).count() == 1

    fresh_claims = {**claims, "jti": uuid4().hex}
    fresh_token = jwt.encode(fresh_claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {fresh_token}", "Idempotency-Key": uuid4().hex}
    ready, release = threading.Event(), threading.Event()
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        if transfer_first:
            original_lock = patient_subject_lock.lock_patient_subject

            def signal_lock(db, subject_id):
                ready.set()
                return original_lock(db, subject_id)

            monkeypatch.setattr(patient_subject_lock, "lock_patient_subject", signal_lock)
            with Session(owner) as transfer:
                transfer.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=None))
                result = pool.submit(client.post, "/api/v1/patients/booking", headers=headers, json={})
                assert ready.wait(5)
                deadline = time.monotonic() + 1.5
                blocked = False
                while time.monotonic() < deadline:
                    with owner.connect() as monitor:
                        blocked = bool(monitor.execute(sa.text("""
                            SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_stat_activity
                              WHERE usename=:login AND wait_event_type='Lock' AND state='active')
                        """), {"login": login}).scalar_one())
                    if blocked:
                        break
                    time.sleep(0.01)
                assert blocked, "denial audit did not wait for ownership change"
                transfer.commit()
                assert result.result(timeout=5).status_code in {403, 409}
            expected_rows = 1
        else:
            original_audit = patient_access_audit.log_patient_access

            def pause_before_audit(*args, **kwargs):
                ready.set()
                assert release.wait(5)
                return original_audit(*args, **kwargs)

            monkeypatch.setattr(patient_access_audit, "log_patient_access", pause_before_audit)
            result = pool.submit(client.post, "/api/v1/patients/booking", headers=headers, json={})
            try:
                assert ready.wait(5)
                with Session(owner) as transfer:
                    transfer.execute(sa.text("SET LOCAL lock_timeout='100ms'"))
                    with pytest.raises(sa.exc.DBAPIError) as error:
                        transfer.execute(sa.update(Patient).where(Patient.id == patient_id).values(user_id=None))
                    assert (getattr(error.value.orig, "sqlstate", None)
                            or getattr(error.value.orig, "pgcode", None)) == "55P03"
                    transfer.rollback()
            finally:
                release.set()
            assert result.result(timeout=5).status_code in {403, 409}
            expected_rows = 2
    with Session(owner) as db:
        assert db.query(PatientAccessAuditLog).count() == expected_rows


def test_real_settings_route_replays_once_and_refuses_revoked_session(pg_writer, monkeypatch):
    from app.api.v1.endpoints import admin_clinic

    client, admins, headers, actor_id = pg_writer
    monkeypatch.setattr(idem, "get_distributed_claim", lambda: None)
    idem.get_idempotency_cache().clear()
    calls = []
    original = admin_clinic.crud_clinic.update_setting

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(admin_clinic.crud_clinic, "update_setting", counted)
    headers = {**headers, "Idempotency-Key": uuid4().hex}
    path = "/api/v1/admin/clinic/settings/repeat_visit_days"
    try:
        first = client.put(path, headers=headers, json={"value": 30})
        assert first.status_code == 200, first.text
        replay = client.put(path, headers=headers, json={"value": 30})
        assert replay.status_code == 200 and replay.json() == first.json()
        assert calls == [1]
        claims = jwt.decode(headers["Authorization"].split(" ", 1)[1], settings.SECRET_KEY,
                            algorithms=[settings.ALGORITHM])
        with admins() as db:
            db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
            db.commit()
        refused = client.put(path, headers=headers, json={"value": 30})
        assert refused.status_code in {401, 403}, refused.text
        assert calls == [1]
    finally:
        idem.get_idempotency_cache().clear()
