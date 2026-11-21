"""Real HTTP auth with a hostile temporary schema and a nonowner PG login."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints import dental
from app.api.v1.endpoints.registrar_wizard import _cart
from app.core.config import settings
from app.main import app
from app.models.authentication import TokenBlacklist
from app.models.user import User
from tests.conftest import mint_access_token
from tests.integration.test_trusted_schema_pg import trusted_pg  # noqa: F401


@pytest.mark.parametrize("route", ["registrar", "dental"])
@pytest.mark.parametrize("real_role,revoked,expected", [
    ("Admin", False, 200), ("Doctor", False, 403), ("Admin", True, 401),
])
def test_review_auth_uses_pinned_users_and_blacklist(trusted_pg, monkeypatch, route, real_role, revoked, expected):
    engine, schema, owner, runtime, _, _ = trusted_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    qs, qr = quote(schema), quote(runtime)
    with engine.begin() as connection:
        connection.exec_driver_sql(f"SET LOCAL search_path TO {qs}, pg_catalog")
        # The shared role fixture creates minimal auth tables; replace only
        # these synthetic tables with the real ORM shapes used by HTTP auth.
        connection.exec_driver_sql(f"DROP TABLE {qs}.token_blacklist")
        connection.exec_driver_sql(f"DROP TABLE {qs}.users")
        User.__table__.create(connection)
        TokenBlacklist.__table__.create(connection)
        connection.exec_driver_sql(f"ALTER TABLE {qs}.users OWNER TO {quote(owner)}")
        connection.exec_driver_sql(f"ALTER TABLE {qs}.token_blacklist OWNER TO {quote(owner)}")
        connection.exec_driver_sql(f"GRANT SELECT ON {qs}.users, {qs}.token_blacklist TO {qr}")
        auth_owner = connection.execute(sa.text("""
            SELECT pg_catalog.pg_get_userbyid(c.relowner)
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=:schema AND c.relname='users'
        """), {"schema": schema}).scalar_one()
        with Session(bind=connection) as db:
            actor = User(username="real_auth_subject", hashed_password="unused", role=real_role,
                         is_active=True, is_superuser=False, auth_epoch=0)
            db.add(actor)
            db.flush()
            token = mint_access_token(actor)
            actor_id = actor.id
            if revoked:
                claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                from datetime import UTC, datetime, timedelta

                db.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                      expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
                db.flush()

    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA", schema)
    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA_OWNER", owner)
    monkeypatch.setattr(settings, "TRUSTED_DB_RUNTIME_ROLE", runtime)
    monkeypatch.setattr(settings, "TRUSTED_DB_OWNER_MEMBERS", ())
    monkeypatch.setattr(settings, "TRUSTED_AUTH_TABLE_OWNER", auth_owner)
    monkeypatch.setattr(settings, "TRUSTED_AUTH_USERS_OWNER", auth_owner)
    for name in ("TRUSTED_AUTH_OWNER_MEMBERS", "TRUSTED_AUTH_READ_ROLES", "TRUSTED_AUTH_WRITE_ROLES",
                 "TRUSTED_AUTH_USERS_OWNER_MEMBERS", "TRUSTED_AUTH_USERS_WRITE_ROLES"):
        monkeypatch.setattr(settings, name, ())
    for name in ("DOCTOR_PRICE_DB_SCHEMA", "DOCTOR_PRICE_DB_SCHEMA_OWNER", "INVITATION_DB_SCHEMA", "INVITATION_DB_SCHEMA_OWNER"):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.setattr(engine.dialect, "default_schema_name", schema)
    monkeypatch.setattr(_cart.PriceOverrideApprovalService, "process", Mock(return_value=SimpleNamespace(id=123, status="rejected")))
    monkeypatch.setattr(dental.DentalApiService, "approve_price_override", AsyncMock(return_value={"success": True}))

    def override_db():
        with Session(engine) as db:
            db.execute(sa.text(f"SET LOCAL SESSION AUTHORIZATION {qr}"))
            db.execute(sa.text(f"CREATE TEMP TABLE users (LIKE {qs}.users INCLUDING ALL)"))
            db.execute(sa.text(f"CREATE TEMP TABLE token_blacklist (LIKE {qs}.token_blacklist INCLUDING ALL)"))
            db.execute(sa.text(f"INSERT INTO pg_temp.users SELECT * FROM {qs}.users"))
            db.execute(sa.text("UPDATE pg_temp.users SET role='Admin', is_active=true"))
            # The attacker's empty blacklist conceals the real revocation.
            db.execute(sa.text(f"SET LOCAL search_path TO pg_temp, {qs}, pg_catalog"))
            yield db
            db.rollback()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {token}"}
            if route == "registrar":
                response = client.post("/api/v1/registrar/price-override/approve", headers=headers,
                                       json={"override_id": 123, "action": "reject", "rejection_reason": "synthetic"})
            else:
                response = client.put("/api/v1/dental/price-override/123/approve", headers=headers,
                                      json={"action": "reject", "rejection_reason": "synthetic"})
        assert response.status_code == expected, response.text
    finally:
        app.dependency_overrides.pop(get_db, None)
