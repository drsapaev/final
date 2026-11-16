"""Migration contract on synthetic data in disposable SQLite and PostgreSQL."""

from __future__ import annotations

import importlib.util
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url

pytestmark = [pytest.mark.integration, pytest.mark.migration]


def _migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/0097_two_factor_sensitive_totp.py"
    )
    spec = importlib.util.spec_from_file_location("sensitive_totp_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare(con):
    con.execute(
        sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, is_active BOOLEAN)")
    )
    con.execute(
        sa.text(
            "CREATE TABLE user_sessions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
            "refresh_token VARCHAR(128), FOREIGN KEY(user_id) REFERENCES users(id))"
        )
    )
    con.execute(sa.text("CREATE INDEX ix_test_sessions_user ON user_sessions(user_id)"))
    con.execute(
        sa.text(
            "CREATE TABLE refresh_tokens (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
            "token VARCHAR(255) NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))"
        )
    )
    con.execute(sa.text("CREATE INDEX ix_test_refresh_user ON refresh_tokens(user_id)"))
    # The historical migration enforces token uniqueness with a unique index.
    con.execute(
        sa.text("CREATE UNIQUE INDEX ix_refresh_tokens_token ON refresh_tokens(token)")
    )
    timestamp_type = (
        "TIMESTAMP WITH TIME ZONE" if con.dialect.name == "postgresql" else "DATETIME"
    )
    con.execute(
        sa.text(
            "CREATE TABLE token_blacklist (id INTEGER PRIMARY KEY, user_id INTEGER, "
            f"reason VARCHAR(100), expires_at {timestamp_type} NOT NULL)"
        )
    )
    con.execute(
        sa.text(
            "INSERT INTO users (id, is_active) VALUES "
            "(1, TRUE), (2, TRUE), (3, TRUE), (4, TRUE), (5, TRUE), "
            "(6, FALSE), (7, FALSE), (8, NULL), (9, NULL)"
        )
    )
    con.execute(
        sa.text(
            "INSERT INTO user_sessions (id, user_id, refresh_token) VALUES (1, 1, 'SYNTHETIC-short'), (2, 2, NULL)"
        )
    )
    con.execute(
        sa.text(
            "INSERT INTO refresh_tokens (id, user_id, token) VALUES (1, 1, 'SYNTHETIC-refresh')"
        )
    )
    con.execute(
        sa.text(
            "CREATE TABLE two_factor_auth (id INTEGER PRIMARY KEY, "
            "user_id INTEGER NOT NULL UNIQUE, failed_attempts INTEGER NOT NULL, "
            "totp_enabled BOOLEAN NOT NULL)"
        )
    )
    con.execute(
        sa.text(
            "CREATE INDEX ix_test_2fa_failed_attempts "
            "ON two_factor_auth (failed_attempts)"
        )
    )
    con.execute(
        sa.text(
            "INSERT INTO two_factor_auth "
            "(id, user_id, failed_attempts, totp_enabled) "
            "VALUES (1, 101, 2, TRUE), (2, 102, 0, FALSE)"
        )
    )
    con.commit()
    future = (
        "CURRENT_TIMESTAMP + INTERVAL '1 hour'"
        if con.dialect.name == "postgresql"
        else "datetime('now', '+1 hour')"
    )
    past = (
        "CURRENT_TIMESTAMP - INTERVAL '1 hour'"
        if con.dialect.name == "postgresql"
        else "datetime('now', '-1 hour')"
    )
    con.execute(
        sa.text(
            "INSERT INTO token_blacklist (id, user_id, reason, expires_at) VALUES "
            f"(1, 1, 'all_user_tokens:synthetic', {future}), "
            f"(2, 1, 'all_user_tokens:second', {future}), "
            f"(3, 2, 'all_user_tokens:expired', {past}), "
            "(4, 3, 'all_user_tokens:equal', CURRENT_TIMESTAMP), "
            f"(5, 4, 'logout', {future}), "
            f"(6, NULL, 'all_user_tokens:unlinked', {future}), "
            f"(7, 7, 'all_user_tokens:inactive', {future}), "
            f"(8, 9, 'all_user_tokens:null', {future})"
        )
    )
    migration = _migration()
    migration.op = Operations(MigrationContext.configure(con))
    return migration


def _assert_round_trip(con, schema=None):
    migration = _prepare(con)
    migration.upgrade()
    assert con.execute(
        sa.text("SELECT auth_epoch FROM users ORDER BY id")
    ).scalars().all() == [1, 0, 0, 0, 0, 1, 1, 1, 1]
    assert (
        con.execute(sa.text("SELECT count(*) FROM token_blacklist")).scalar_one() == 8
    )
    user_columns = {
        c["name"]: c for c in sa.inspect(con).get_columns("users", schema=schema)
    }
    assert user_columns["auth_epoch"]["nullable"] is False
    assert isinstance(user_columns["auth_epoch"]["type"], sa.BigInteger)
    session_column = next(
        c
        for c in sa.inspect(con).get_columns("user_sessions", schema=schema)
        if c["name"] == "refresh_token"
    )
    assert session_column["type"].length == 512
    refresh_column = next(
        c
        for c in sa.inspect(con).get_columns("refresh_tokens", schema=schema)
        if c["name"] == "token"
    )
    assert refresh_column["type"].length == 512 and refresh_column["nullable"] is False
    assert con.execute(
        sa.text("SELECT refresh_token FROM user_sessions ORDER BY id")
    ).scalars().all() == ["SYNTHETIC-short", None]
    con.execute(sa.text("INSERT INTO users (id, is_active) VALUES (10, TRUE)"))
    assert (
        con.execute(sa.text("SELECT auth_epoch FROM users WHERE id=10")).scalar_one()
        == 0
    )
    con.execute(
        sa.text("UPDATE users SET auth_epoch = :value WHERE id=2"), {"value": 2**40}
    )
    assert (
        con.execute(sa.text("SELECT auth_epoch FROM users WHERE id=2")).scalar_one()
        == 2**40
    )
    assert con.execute(
        sa.text("SELECT last_sensitive_totp_step FROM two_factor_auth ORDER BY id")
    ).scalars().all() == [None, None]
    column = next(
        column
        for column in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
        if column["name"] == "last_sensitive_totp_step"
    )
    assert column["nullable"] is True
    assert isinstance(column["type"], sa.BigInteger)
    assert column["default"] is None

    columns = {
        column["name"]: column
        for column in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
    }
    assert columns["sensitive_failed_attempts"]["nullable"] is False
    assert columns["sensitive_failed_attempts"]["default"] is not None
    assert columns["sensitive_locked_until"]["nullable"] is True
    assert con.execute(
        sa.text(
            "SELECT sensitive_failed_attempts, sensitive_locked_until "
            "FROM two_factor_auth ORDER BY id"
        )
    ).all() == [(0, None), (0, None)]

    # A real time-step can exceed 32-bit storage; marker zero also is not NULL.
    con.execute(
        sa.text(
            "UPDATE two_factor_auth SET last_sensitive_totp_step = :step WHERE id = 1"
        ),
        {"step": 2**40},
    )
    con.execute(
        sa.text("UPDATE two_factor_auth SET last_sensitive_totp_step = 0 WHERE id = 2")
    )
    con.execute(
        sa.text(
            "UPDATE two_factor_auth SET sensitive_failed_attempts = 4, "
            "sensitive_locked_until = CURRENT_TIMESTAMP WHERE id = 1"
        )
    )
    con.execute(
        sa.text(
            "INSERT INTO two_factor_auth "
            "(id, user_id, failed_attempts, totp_enabled) VALUES (3, 103, 1, TRUE)"
        )
    )
    assert con.execute(
        sa.text("SELECT last_sensitive_totp_step FROM two_factor_auth ORDER BY id")
    ).scalars().all() == [2**40, 0, None]
    assert con.execute(
        sa.text(
            "SELECT sensitive_failed_attempts, sensitive_locked_until IS NOT NULL "
            "FROM two_factor_auth ORDER BY id"
        )
    ).all() == [(4, True), (0, False), (0, False)]
    con.commit()

    # Downgrade cannot silently drop revocation state, even with short tokens.
    with pytest.raises(RuntimeError, match="nonzero user auth epochs"):
        migration.downgrade()
    assert "auth_epoch" in {
        c["name"] for c in sa.inspect(con).get_columns("users", schema=schema)
    }
    assert "last_sensitive_totp_step" in {
        c["name"] for c in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
    }
    assert (
        con.execute(sa.text("SELECT auth_epoch FROM users WHERE id=2")).scalar_one()
        == 2**40
    )

    # A valid minted refresh JWT is longer than 128; refuse without truncation.
    con.execute(sa.text("UPDATE users SET auth_epoch=0"))
    minted = jwt.encode(
        {
            "sub": "1",
            "auth_epoch": 2**40,
            "type": "refresh",
            "jti": str(uuid4()),
            "exp": datetime.now(UTC) + timedelta(days=7),
        },
        secrets.token_urlsafe(32),
        algorithm="HS256",
    )
    assert 128 < len(minted) <= 255
    con.execute(
        sa.text("UPDATE user_sessions SET refresh_token=:token WHERE id=1"),
        {"token": minted},
    )
    con.commit()
    with pytest.raises(RuntimeError, match="exceeds 128 characters"):
        migration.downgrade()
    assert (
        con.execute(
            sa.text("SELECT refresh_token FROM user_sessions WHERE id=1")
        ).scalar_one()
        == minted
    )
    assert "auth_epoch" in {
        c["name"] for c in sa.inspect(con).get_columns("users", schema=schema)
    }
    assert "last_sensitive_totp_step" in {
        c["name"] for c in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
    }

    # A maximum supported user ID and epoch yield a real refresh JWT that is
    # longer than the old 255-character persistent-token column.
    con.execute(
        sa.text("UPDATE user_sessions SET refresh_token='SYNTHETIC-short' WHERE id=1")
    )
    from app.services.auth_svc import AuthenticationService

    max_refresh = AuthenticationService().create_refresh_token(
        2147483647, str(uuid4()), auth_epoch=2**63 - 1
    )
    assert 255 < len(max_refresh) <= 512
    con.execute(
        sa.text("UPDATE refresh_tokens SET token=:token WHERE id=1"),
        {"token": max_refresh},
    )
    con.commit()
    with pytest.raises(RuntimeError, match="stored refresh token exceeds 255"):
        migration.downgrade()
    assert (
        con.execute(sa.text("SELECT token FROM refresh_tokens WHERE id=1")).scalar_one()
        == max_refresh
    )
    assert "auth_epoch" in {
        c["name"] for c in sa.inspect(con).get_columns("users", schema=schema)
    }
    assert "last_sensitive_totp_step" in {
        c["name"] for c in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
    }

    # Synthetic-only reset: a real rollback first rotates keys and revokes sessions.
    con.execute(
        sa.text("UPDATE refresh_tokens SET token='SYNTHETIC-refresh' WHERE id=1")
    )
    migration.downgrade()
    con.commit()
    assert "auth_epoch" not in {
        c["name"] for c in sa.inspect(con).get_columns("users", schema=schema)
    }
    restored = next(
        c
        for c in sa.inspect(con).get_columns("user_sessions", schema=schema)
        if c["name"] == "refresh_token"
    )
    assert restored["type"].length == 128
    restored_refresh = next(
        c
        for c in sa.inspect(con).get_columns("refresh_tokens", schema=schema)
        if c["name"] == "token"
    )
    assert restored_refresh["type"].length == 255
    assert (
        con.execute(sa.text("SELECT token FROM refresh_tokens WHERE id=1")).scalar_one()
        == "SYNTHETIC-refresh"
    )
    assert "ix_test_refresh_user" in {
        i["name"] for i in sa.inspect(con).get_indexes("refresh_tokens", schema=schema)
    }
    assert "ix_refresh_tokens_token" in {
        i["name"]
        for i in sa.inspect(con).get_indexes("refresh_tokens", schema=schema)
        if i["unique"]
    }
    with pytest.raises(sa.exc.IntegrityError), con.begin_nested():
        con.execute(
            sa.text(
                "INSERT INTO refresh_tokens (id, user_id, token) VALUES (2, 1, 'SYNTHETIC-refresh')"
            )
        )
    assert con.execute(
        sa.text("SELECT refresh_token FROM user_sessions ORDER BY id")
    ).scalars().all() == ["SYNTHETIC-short", None]
    assert (
        con.execute(sa.text("SELECT count(*) FROM token_blacklist")).scalar_one() == 8
    )
    assert "ix_test_sessions_user" in {
        i["name"] for i in sa.inspect(con).get_indexes("user_sessions", schema=schema)
    }
    assert "last_sensitive_totp_step" not in {
        col["name"]
        for col in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
    }
    assert not {"sensitive_failed_attempts", "sensitive_locked_until"} & {
        col["name"]
        for col in sa.inspect(con).get_columns("two_factor_auth", schema=schema)
    }
    assert con.execute(
        sa.text(
            "SELECT id, user_id, failed_attempts, totp_enabled "
            "FROM two_factor_auth ORDER BY id"
        )
    ).all() == [(1, 101, 2, True), (2, 102, 0, False), (3, 103, 1, True)]
    assert "ix_test_2fa_failed_attempts" in {
        index["name"]
        for index in sa.inspect(con).get_indexes("two_factor_auth", schema=schema)
    }


def test_sensitive_totp_model_and_revision_contract():
    from app.models.authentication import RefreshToken, UserSession
    from app.models.two_factor_auth import TwoFactorAuth
    from app.models.user import User

    epoch = User.__table__.c.auth_epoch
    assert isinstance(epoch.type, sa.BigInteger) and not epoch.nullable
    assert epoch.default.arg == 0 and epoch.server_default is not None
    assert UserSession.__table__.c.refresh_token.type.length == 512
    assert RefreshToken.__table__.c.token.type.length == 512

    column = TwoFactorAuth.__table__.c.last_sensitive_totp_step
    assert column.nullable is True
    assert isinstance(column.type, sa.BigInteger)
    assert column.default is None and column.server_default is None
    failures = TwoFactorAuth.__table__.c.sensitive_failed_attempts
    lockout = TwoFactorAuth.__table__.c.sensitive_locked_until
    assert not failures.nullable
    assert isinstance(failures.type, sa.Integer)
    assert failures.default.arg == 0 and failures.server_default is not None
    assert lockout.nullable and lockout.type.timezone
    migration = _migration()
    assert migration.revision == "0097_two_factor_sensitive_totp"
    assert migration.down_revision == "0096_passkey_owner_user"


def test_sensitive_totp_migration_sqlite(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'sensitive-totp.db'}")
    try:
        with engine.connect() as con:
            _assert_round_trip(con)
    finally:
        engine.dispose()


def test_sensitive_totp_migration_postgres():
    from tests._pg_admin_guard import is_local_admin_dsn

    url = os.getenv("SENSITIVE_TOTP_MIGRATION_TEST_URL")
    if not url and os.getenv("CI") == "true":
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
                "CI requires a disposable PostgreSQL database for migration proof"
            )
        pytest.skip(
            "set SENSITIVE_TOTP_MIGRATION_TEST_URL to a disposable PostgreSQL DB"
        )
    if make_url(url).get_backend_name() != "postgresql":
        pytest.fail("migration test requires PostgreSQL")
    if not is_local_admin_dsn(url):
        pytest.fail("migration test requires a local disposable PostgreSQL database")

    engine = sa.create_engine(url)
    schema = f"sensitive_totp_test_{uuid4().hex}"
    try:
        with engine.connect() as con:
            created = False
            try:
                con.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
                created = True
                con.execute(sa.text(f'SET search_path TO "{schema}"'))
                _assert_round_trip(con, schema=schema)
            finally:
                con.rollback()
                if created:
                    con.execute(sa.text("SET search_path TO public"))
                    con.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                    con.commit()
    finally:
        engine.dispose()
