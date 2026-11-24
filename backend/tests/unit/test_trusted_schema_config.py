from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.trusted_schema import TrustedSchemaUnavailable, pin_application_schema


def test_owner_members_environment_uses_explicit_json_array(monkeypatch):
    monkeypatch.setenv("TRUSTED_DB_SCHEMA", "clinical")
    monkeypatch.setenv("TRUSTED_DB_SCHEMA_OWNER", "owner")
    monkeypatch.setenv("TRUSTED_DB_RUNTIME_ROLE", "backend")
    monkeypatch.setenv("TRUSTED_DB_OWNER_MEMBERS", '["migration_group","operator"]')
    monkeypatch.setenv("TRUSTED_AUTH_TABLE_OWNER", "auth_owner")
    monkeypatch.setenv("TRUSTED_AUTH_OWNER_MEMBERS", '["auth_operator"]')
    monkeypatch.setenv("TRUSTED_AUTH_READ_ROLES", '["auth_reader"]')
    monkeypatch.setenv("TRUSTED_AUTH_WRITE_ROLES", '["auth_writer"]')
    monkeypatch.setenv("TRUSTED_AUTH_USERS_OWNER", "users_owner")
    monkeypatch.setenv("TRUSTED_AUTH_USERS_OWNER_MEMBERS", '["users_operator"]')
    monkeypatch.setenv("TRUSTED_AUTH_USERS_WRITE_ROLES", '["users_writer"]')
    config = Settings(_env_file=None, SECRET_KEY="synthetic-secret-" * 3)
    assert config.TRUSTED_DB_SCHEMA == "clinical"
    assert config.TRUSTED_DB_SCHEMA_OWNER == "owner"
    assert config.TRUSTED_DB_RUNTIME_ROLE == "backend"
    assert config.TRUSTED_DB_OWNER_MEMBERS == ("migration_group", "operator")
    assert config.TRUSTED_AUTH_TABLE_OWNER == "auth_owner"
    assert config.TRUSTED_AUTH_OWNER_MEMBERS == ("auth_operator",)
    assert config.TRUSTED_AUTH_READ_ROLES == ("auth_reader",)
    assert config.TRUSTED_AUTH_WRITE_ROLES == ("auth_writer",)
    assert config.TRUSTED_AUTH_USERS_OWNER == "users_owner"
    assert config.TRUSTED_AUTH_USERS_OWNER_MEMBERS == ("users_operator",)
    assert config.TRUSTED_AUTH_USERS_WRITE_ROLES == ("users_writer",)


def test_sqlite_does_not_start_transaction_or_require_pg_configuration():
    engine = sa.create_engine("sqlite://")
    try:
        with Session(engine) as db:
            assert not db.in_transaction()
            pin_application_schema(db, schema=None, expected_owner=None, expected_runtime_role=None)
            assert not db.in_transaction()
    finally:
        engine.dispose()


def test_unsupported_dialect_fails_closed_without_disclosing_identifiers():
    db = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="mysql")))
    with pytest.raises(TrustedSchemaUnavailable) as error:
        pin_application_schema(db, schema="synthetic-private", expected_owner="synthetic-owner",
                               expected_runtime_role="synthetic-role")
    assert "synthetic" not in str(error.value)
