#!/usr/bin/env python3
"""
Reset or create critical users with explicit environment-provided passwords/roles.

Docs reference:
- ROLES_AND_ROUTING.md
"""
from __future__ import annotations

import os


USERS = [
    ("admin", "Admin"),
    ("registrar", "Registrar"),
    ("lab", "Lab"),
    ("doctor", "Doctor"),
    ("cashier", "Cashier"),
    ("cardio", "cardio"),
    ("derma", "derma"),
    ("dentist", "dentist"),
]


def _require_confirmation() -> None:
    value = os.getenv("CONFIRM_RESET_CRITICAL_PASSWORDS", "").strip().lower()
    if value not in {"1", "true", "yes", "on"}:
        raise RuntimeError(
            "Set CONFIRM_RESET_CRITICAL_PASSWORDS=1 before ensuring critical users."
        )


def _require_postgres_database_url() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before ensuring critical users.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError(
            "reset_critical_passwords.py requires a PostgreSQL DATABASE_URL."
        )


def _password_env_names(username: str) -> list[str]:
    names = [f"RESET_CRITICAL_{username.upper()}_PASSWORD"]
    if username == "admin":
        names.insert(0, "ADMIN_PASSWORD")
    return names


def _required_password(username: str) -> str:
    for env_name in _password_env_names(username):
        password = os.getenv(env_name, "").strip()
        if password:
            return password
    expected = " or ".join(_password_env_names(username))
    raise RuntimeError(f"Set {expected} before ensuring user '{username}'.")


def main() -> None:
    _require_confirmation()
    _require_postgres_database_url()

    from app.core.security import get_password_hash
    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        passwords = {username: _required_password(username) for username, _role in USERS}
        for username, role in USERS:
            password = passwords[username]
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.hashed_password = get_password_hash(password)
                user.role = role
                user.is_active = True
                print(f"OK: updated {username} role={role}")
            else:
                user = User(
                    username=username,
                    full_name=username.title(),
                    email=f"{username}@clinic.local",
                    hashed_password=get_password_hash(password),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                print(f"OK: created {username} role={role}")
        db.commit()
        print("DONE: critical users ensured")
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
