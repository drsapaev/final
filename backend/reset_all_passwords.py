#!/usr/bin/env python3
"""
Скрипт для сброса паролей всех пользователей
"""

from __future__ import annotations

import os


USERS = (
    "admin",
    "registrar",
    "lab",
    "doctor",
    "cashier",
    "cardio",
    "derma",
    "dentist",
)

TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def _require_confirmation() -> None:
    value = os.getenv("CONFIRM_RESET_ALL_PASSWORDS", "").strip().lower()
    if value not in TRUTHY_ENV_VALUES:
        raise RuntimeError(
            "Set CONFIRM_RESET_ALL_PASSWORDS=1 before resetting all user passwords."
        )


def _require_postgres_database_url() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before resetting user passwords.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("reset_all_passwords.py requires a PostgreSQL DATABASE_URL.")


def _password_env_names(username: str) -> list[str]:
    names = [f"RESET_ALL_{username.upper()}_PASSWORD"]
    if username == "admin":
        names.insert(0, "ADMIN_PASSWORD")
    return names


def _required_password(username: str) -> str:
    for env_name in _password_env_names(username):
        password = os.getenv(env_name, "").strip()
        if password:
            return password
    expected = " or ".join(_password_env_names(username))
    raise RuntimeError(f"Set {expected} before resetting user '{username}'.")


def reset_all_passwords():
    """Сброс паролей всех пользователей согласно документации"""
    _require_confirmation()
    _require_postgres_database_url()
    passwords = {username: _required_password(username) for username in USERS}

    from app.core.security import get_password_hash
    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        for username in USERS:
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.hashed_password = get_password_hash(passwords[username])
                print(f"OK: Пароль для {username} сброшен")
            else:
                print(f"ERROR: Пользователь {username} не найден")

        db.commit()
        print("\nOK: Все пароли успешно сброшены!")

    except Exception as e:
        print(f"ERROR: Ошибка при сбросе паролей: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    reset_all_passwords()
