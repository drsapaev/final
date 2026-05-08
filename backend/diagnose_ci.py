#!/usr/bin/env python3
"""Diagnose role-test user creation in an isolated temporary database."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")


ROLE_USERS = [
    ("admin", "Admin"),
    ("registrar", "Registrar"),
    ("doctor", "Doctor"),
    ("cashier", "Cashier"),
    ("lab", "Lab"),
    ("cardio", "cardio"),
    ("derma", "derma"),
    ("dentist", "dentist"),
]


def required_password(username: str) -> str:
    env_name = f"DIAGNOSE_CI_{username.upper()}_PASSWORD"
    password = os.getenv(env_name)
    if not password:
        raise RuntimeError(f"{env_name} is required for diagnose_ci.py")
    return password


def require_temp_sqlite_confirmation() -> None:
    if os.getenv("CONFIRM_DIAGNOSE_CI_TEMP_SQLITE") != "1":
        raise RuntimeError(
            "diagnose_ci.py creates schema with SQLAlchemy metadata in an isolated "
            "temporary SQLite database. Set CONFIRM_DIAGNOSE_CI_TEMP_SQLITE=1 only "
            "for an explicit diagnostic run."
        )


def main() -> None:
    require_temp_sqlite_confirmation()

    diagnostic_db_dir = tempfile.TemporaryDirectory(prefix="diagnose-ci-")
    diagnostic_db_path = Path(diagnostic_db_dir.name) / "diagnose_ci.db"

    # This helper is intentionally isolated from runtime DB settings.
    os.environ["DATABASE_URL"] = f"sqlite:///{diagnostic_db_path.as_posix()}"
    os.environ["ALLOW_SQLITE_DATABASE_URL"] = "1"
    os.environ["CORS_DISABLE"] = "0"
    os.environ["WS_DEV_ALLOW"] = "1"

    db = None
    engine = None
    try:
        from app.core.security import get_password_hash, verify_password
        from app.db.base import Base
        from app.db.session import SessionLocal, engine
        from app.models.user import User

        users_data = [
            (username, required_password(username), role)
            for username, role in ROLE_USERS
        ]

        print("Creating diagnostic tables in a temporary SQLite database...")
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()

        print("\nCreating role users...")
        for username, password, role in users_data:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                print(f"  - {username}: already exists")
                continue

            user = User(
                username=username,
                full_name=username.title(),
                role=role,
                hashed_password=get_password_hash(password),
                is_active=True,
            )
            db.add(user)
            print(f"  - {username}: created with role '{role}'")

        db.commit()
        print("\nUsers created.")

        print("\nVerifying passwords:")
        for username, password, role in users_data:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"  FAILED {username}: not found in DB")
                continue

            is_valid = verify_password(password, user.hashed_password)
            if is_valid:
                print(f"  OK {username}: password verified, role = '{user.role}'")
            else:
                print(f"  FAILED {username}: password was not verified")
                print(
                    "      Password value is supplied through the "
                    "DIAGNOSE_CI_*_PASSWORD environment."
                )

    except Exception as exc:
        print(f"\nError: {exc}")
        if db is not None:
            db.rollback()
        raise
    finally:
        if db is not None:
            db.close()
        if engine is not None:
            engine.dispose()
        diagnostic_db_dir.cleanup()
        print("\nTemporary diagnostic DB removed")


if __name__ == "__main__":
    main()
