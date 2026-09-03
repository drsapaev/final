from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.scripts.migrate_users_to_postgres import (
    _normalize_legacy_role,
    migrate_users,
)


def _create_source_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT,
                full_name TEXT,
                hashed_password TEXT NOT NULL,
                role TEXT,
                is_active INTEGER,
                is_superuser INTEGER,
                must_change_password INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO users (
                id,
                username,
                email,
                full_name,
                hashed_password,
                role,
                is_active,
                is_superuser,
                must_change_password,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    20,
                    "registrar@example.com",
                    "registrar@example.com",
                    "Registrar",
                    "hash-registrar",
                    "Receptionist",
                    1,
                    0,
                    0,
                    "2026-01-01 10:00:00",
                    "2026-01-02 11:00:00",
                ),
                (
                    21,
                    "doctor@example.com",
                    "doctor@example.com",
                    "Doctor",
                    "hash-doctor",
                    "Doctor",
                    1,
                    0,
                    1,
                    "2026-01-03 10:00:00",
                    "2026-01-04 11:00:00",
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _create_target_engine(path: Path):
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    full_name VARCHAR(100),
                    email VARCHAR(120),
                    hashed_password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    is_superuser BOOLEAN NOT NULL,
                    must_change_password BOOLEAN NOT NULL,
                    device_token VARCHAR(255),
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
    return engine


def test_migrate_users_preserves_ids_and_inserts_missing_rows(tmp_path):
    source_db = tmp_path / "legacy.db"
    target_db = tmp_path / "target.db"
    _create_source_db(source_db)
    engine = _create_target_engine(target_db)

    summary = migrate_users(source_sqlite_path=source_db, target_engine=engine)

    assert summary.source_count == 2
    assert summary.inserted_count == 2
    assert summary.updated_count == 0
    assert summary.preserved_id_count == 2
    assert summary.id_mismatch_updates == 0

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, username, email, role, must_change_password
                FROM users
                ORDER BY id
                """
            )
        ).fetchall()

    assert rows == [
        # REC-1 write-freeze (Codex review P1, PR #3025): the legacy source
        # row keeps its original 'Receptionist' spelling (legacy READ
        # accepted), but the migration must WRITE the canonical 'Registrar'.
        (20, "registrar@example.com", "registrar@example.com", "Registrar", 0),
        (21, "doctor@example.com", "doctor@example.com", "Doctor", 1),
    ]


def test_migrate_users_updates_existing_user_without_duplication(tmp_path):
    source_db = tmp_path / "legacy.db"
    target_db = tmp_path / "target.db"
    _create_source_db(source_db)
    engine = _create_target_engine(target_db)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id,
                    username,
                    full_name,
                    email,
                    hashed_password,
                    role,
                    is_active,
                    is_superuser,
                    must_change_password,
                    device_token,
                    created_at,
                    updated_at
                ) VALUES (
                    3,
                    'registrar@example.com',
                    'Old Registrar',
                    'registrar@example.com',
                    'old-hash',
                    'OldRole',
                    0,
                    0,
                    0,
                    NULL,
                    '2025-01-01 00:00:00',
                    '2025-01-01 00:00:00'
                )
                """
            )
        )

    summary = migrate_users(source_sqlite_path=source_db, target_engine=engine)

    assert summary.source_count == 2
    assert summary.inserted_count == 1
    assert summary.updated_count == 1
    assert summary.preserved_id_count == 1
    assert summary.id_mismatch_updates == 1

    with engine.connect() as connection:
        registrar = connection.execute(
            text(
                """
                SELECT id, full_name, hashed_password, role, is_active
                FROM users
                WHERE username = 'registrar@example.com'
                """
            )
        ).one()
        user_count = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()

    # REC-1 write-freeze (Codex review P1, PR #3025): the UPDATE path must
    # store the canonical 'Registrar' even though the legacy source row
    # spells the role 'Receptionist'.
    assert registrar == (3, "Registrar", "hash-registrar", "Registrar", 1)
    assert user_count == 2


def _create_manager_source_db(path: Path) -> None:
    """Legacy source holding a single 'Manager' row (M-1 probe)."""
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                email TEXT,
                full_name TEXT,
                hashed_password TEXT NOT NULL,
                role TEXT,
                is_active INTEGER,
                is_superuser INTEGER,
                must_change_password INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO users (
                id, username, email, full_name, hashed_password, role,
                is_active, is_superuser, must_change_password,
                created_at, updated_at
            ) VALUES (
                20, 'smoke_manager', 'smoke.manager@synthetic.invalid',
                '[SYNTHETIC-SMOKE] Manager', 'hash-manager', 'Manager',
                1, 0, 0, '2026-01-01 10:00:00', '2026-01-02 11:00:00'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


class TestManagerWriteFreeze:
    """M-1 (Manager deprecation, Codex review P1 PR #3029): the migration
    boundary must not create or overwrite a stored 'Manager' role — there
    is no canonical alias, so the boundary rejects the row loudly instead
    of mapping (invented semantics) or silently skipping (vanishing
    account)."""

    def test_normalize_rejects_manager(self) -> None:
        with pytest.raises(ValueError, match="Manager"):
            _normalize_legacy_role("Manager")

    def test_normalize_rejects_manager_case_insensitive(self) -> None:
        with pytest.raises(ValueError, match="Manager"):
            _normalize_legacy_role("manager")

    def test_normalize_keeps_canonical_roles(self) -> None:
        assert _normalize_legacy_role("Admin") == "Admin"
        assert _normalize_legacy_role("Doctor") == "Doctor"
        assert _normalize_legacy_role("Registrar") == "Registrar"

    def test_migrate_users_aborts_on_manager_row_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        source_db = tmp_path / "legacy_manager.db"
        target_db = tmp_path / "target_manager.db"
        _create_manager_source_db(source_db)
        engine = _create_target_engine(target_db)

        with pytest.raises(ValueError, match="Manager"):
            migrate_users(source_sqlite_path=source_db, target_engine=engine)

        # The abort happens at the load boundary, BEFORE any INSERT/UPDATE
        # path runs — the target table stays untouched.
        with engine.connect() as connection:
            user_count = connection.execute(
                text("SELECT COUNT(*) FROM users")
            ).scalar_one()
        assert user_count == 0
