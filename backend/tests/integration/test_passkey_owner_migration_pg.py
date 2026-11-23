"""PostgreSQL migration regression using a disposable DB or local CI service.

The test creates and removes its own temporary schema and uses synthetic rows.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

pytestmark = [pytest.mark.integration, pytest.mark.migration]


def _migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0096_passkey_owner_user.py"
    )
    spec = importlib.util.spec_from_file_location("passkey_owner_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migration_connection():
    url = os.getenv("PASSKEY_OWNER_MIGRATION_TEST_URL")
    if not url and os.getenv("CI") == "true":
        from tests._pg_admin_guard import is_local_admin_dsn

        ci_url = os.getenv("DATABASE_URL", "")
        parsed = make_url(ci_url) if ci_url else None
        if (
            parsed
            and parsed.get_backend_name() == "postgresql"
            and parsed.database == "clinicdb"
            and is_local_admin_dsn(ci_url)
        ):
            url = ci_url
    if not url:
        if os.getenv("CI") == "true":
            pytest.fail(
                "CI requires an explicitly disposable PostgreSQL database for migration proof"
            )
        pytest.skip(
            "set PASSKEY_OWNER_MIGRATION_TEST_URL to a disposable PostgreSQL DB"
        )
    if not url.startswith("postgresql"):
        pytest.fail("migration test requires PostgreSQL")
    engine = sa.create_engine(url)
    schema = f"passkey_owner_test_{uuid4().hex}"
    with engine.connect() as con:
        created = False
        try:
            con.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            created = True
            con.execute(sa.text(f'SET search_path TO "{schema}"'))
            con.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            con.execute(
                sa.text(
                    "CREATE TABLE passkey_credentials (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, active BOOLEAN NOT NULL)"
                )
            )
            con.execute(sa.text("INSERT INTO users (id) VALUES (1), (2)"))
            con.execute(
                sa.text(
                    "INSERT INTO passkey_credentials (id, patient_id, active) VALUES (10, 20, TRUE)"
                )
            )
            con.commit()
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(con))
            yield con, migration, schema
        finally:
            con.rollback()
            if created:
                con.execute(sa.text("SET search_path TO public"))
                con.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                con.commit()
    engine.dispose()


def test_upgrade_preserves_unknown_owners_and_enforces_fk(migration_connection):
    con, migration, schema = migration_connection
    migration.upgrade()
    con.commit()

    assert con.execute(
        sa.text("SELECT passkey_user_handle FROM users ORDER BY id")
    ).scalars().all() == [None, None]
    user_indexes = {
        index["name"]: index
        for index in sa.inspect(con).get_indexes("users", schema=schema)
    }
    assert user_indexes["ix_users_passkey_user_handle"]["unique"]
    con.execute(
        sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 1"),
        {"handle": "a" * 43},
    )
    with pytest.raises(IntegrityError), con.begin_nested():
        con.execute(
            sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 2"),
            {"handle": "a" * 43},
        )
    con.execute(
        sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 2"),
        {"handle": "b" * 43},
    )

    assert (
        con.execute(
            sa.text("SELECT owner_user_id FROM passkey_credentials WHERE id = 10")
        ).scalar_one()
        is None
    )
    column = next(
        c
        for c in sa.inspect(con).get_columns("passkey_credentials", schema=schema)
        if c["name"] == "owner_user_id"
    )
    assert column["nullable"] is True
    fk = next(
        f
        for f in sa.inspect(con).get_foreign_keys("passkey_credentials", schema=schema)
        if f["constrained_columns"] == ["owner_user_id"]
    )
    assert fk["referred_table"] == "users"
    assert fk["options"]["ondelete"] == "SET NULL"
    assert "ix_passkey_credentials_owner_user_id" in {
        index["name"]
        for index in sa.inspect(con).get_indexes("passkey_credentials", schema=schema)
    }

    with pytest.raises(IntegrityError), con.begin_nested():
        con.execute(
            sa.text("UPDATE passkey_credentials SET owner_user_id = 999 WHERE id = 10")
        )
    con.execute(
        sa.text("UPDATE passkey_credentials SET owner_user_id = 1 WHERE id = 10")
    )
    con.execute(sa.text("DELETE FROM users WHERE id = 1"))
    assert (
        con.execute(
            sa.text("SELECT owner_user_id FROM passkey_credentials WHERE id = 10")
        ).scalar_one()
        is None
    )
    con.commit()


def test_downgrade_preserves_credential_rows(migration_connection):
    con, migration, schema = migration_connection
    migration.upgrade()
    con.execute(
        sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 2"),
        {"handle": "b" * 43},
    )
    con.execute(
        sa.text("UPDATE passkey_credentials SET owner_user_id = 2 WHERE id = 10")
    )
    migration.downgrade()
    con.commit()
    assert con.execute(
        sa.text("SELECT id, patient_id, active FROM passkey_credentials")
    ).all() == [(10, 20, True)]
    assert "owner_user_id" not in {
        c["name"]
        for c in sa.inspect(con).get_columns("passkey_credentials", schema=schema)
    }
    assert "passkey_user_handle" not in {
        c["name"] for c in sa.inspect(con).get_columns("users", schema=schema)
    }
    assert "ix_users_passkey_user_handle" not in {
        i["name"] for i in sa.inspect(con).get_indexes("users", schema=schema)
    }
    assert "ix_passkey_credentials_owner_user_id" not in {
        i["name"]
        for i in sa.inspect(con).get_indexes("passkey_credentials", schema=schema)
    }
    assert con.execute(sa.text("SELECT id FROM users ORDER BY id")).scalars().all() == [
        1,
        2,
    ]


def test_model_matches_nullable_fk_contract():
    from app.models.passkey_credential import PasskeyCredential
    from app.models.user import User

    column = PasskeyCredential.__table__.c.owner_user_id
    assert column.nullable
    (foreign_key,) = column.foreign_keys
    assert foreign_key.target_fullname == "users.id"
    assert foreign_key.ondelete == "SET NULL"
    handle = User.__table__.c.passkey_user_handle
    assert handle.nullable and handle.type.length == 43
    assert any(
        index.name == "ix_users_passkey_user_handle" and index.unique
        for index in User.__table__.indexes
    )


def test_sqlite_batch_upgrade_and_downgrade_with_existing_rows(tmp_path):
    """SQLite's table rebuild must preserve rows, indexes and FK behavior."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'passkey-owner.db'}")
    with engine.connect() as con:
        con.execute(sa.text("PRAGMA foreign_keys = ON"))
        con.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        con.execute(
            sa.text(
                "CREATE TABLE passkey_credentials (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, active BOOLEAN NOT NULL)"
            )
        )
        con.execute(
            sa.text(
                "CREATE INDEX ix_passkey_patient_active ON passkey_credentials (patient_id, active)"
            )
        )
        con.execute(sa.text("INSERT INTO users (id) VALUES (1), (2)"))
        con.execute(sa.text("INSERT INTO passkey_credentials VALUES (10, 20, TRUE)"))
        con.commit()
        migration = _migration()
        migration.op = Operations(MigrationContext.configure(con))
        migration.upgrade()
        assert con.execute(
            sa.text("SELECT passkey_user_handle FROM users ORDER BY id")
        ).scalars().all() == [None, None]
        con.execute(
            sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 1"),
            {"handle": "a" * 43},
        )
        with pytest.raises(IntegrityError), con.begin_nested():
            con.execute(
                sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 2"),
                {"handle": "a" * 43},
            )
        con.execute(
            sa.text("UPDATE users SET passkey_user_handle = :handle WHERE id = 2"),
            {"handle": "b" * 43},
        )
        assert (
            con.execute(
                sa.text("SELECT owner_user_id FROM passkey_credentials")
            ).scalar_one()
            is None
        )
        with pytest.raises(IntegrityError), con.begin_nested():
            con.execute(sa.text("UPDATE passkey_credentials SET owner_user_id = 999"))
        con.execute(sa.text("UPDATE passkey_credentials SET owner_user_id = 1"))
        con.execute(sa.text("DELETE FROM users WHERE id = 1"))
        assert (
            con.execute(
                sa.text("SELECT owner_user_id FROM passkey_credentials")
            ).scalar_one()
            is None
        )
        migration.downgrade()
        assert con.execute(
            sa.text("SELECT id, patient_id, active FROM passkey_credentials")
        ).all() == [(10, 20, 1)]
        assert "ix_passkey_patient_active" in {
            i["name"] for i in sa.inspect(con).get_indexes("passkey_credentials")
        }
        assert "ix_passkey_credentials_owner_user_id" not in {
            i["name"] for i in sa.inspect(con).get_indexes("passkey_credentials")
        }
        assert "ix_users_passkey_user_handle" not in {
            i["name"] for i in sa.inspect(con).get_indexes("users")
        }
        assert "passkey_user_handle" not in {
            c["name"] for c in sa.inspect(con).get_columns("users")
        }
        assert con.execute(sa.text("SELECT id FROM users")).scalars().all() == [2]
    engine.dispose()
