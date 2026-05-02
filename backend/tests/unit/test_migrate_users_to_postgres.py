from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text

from app.scripts.migrate_users_to_postgres import migrate_users


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
        (20, "registrar@example.com", "registrar@example.com", "Receptionist", 0),
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

    assert registrar == (3, "Registrar", "hash-registrar", "Receptionist", 1)
    assert user_count == 2
