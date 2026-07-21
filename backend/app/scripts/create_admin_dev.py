from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sqlalchemy import MetaData, Table


def _require_create_admin_dev_confirmation() -> None:
    if os.getenv("CONFIRM_CREATE_ADMIN_DEV") != "1":
        raise SystemExit(
            "Refusing to create or inspect dev admin without "
            "CONFIRM_CREATE_ADMIN_DEV=1."
        )


def _required_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL must be set before running create_admin_dev.py.")
    if database_url.lower().startswith("sqlite"):
        raise SystemExit("create_admin_dev.py requires a PostgreSQL DATABASE_URL.")
    return database_url


def _required_admin_password() -> str:
    password = os.getenv("DEV_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Set DEV_ADMIN_PASSWORD or ADMIN_PASSWORD before creating a dev admin.")
    return password


def _required_admin_username() -> str:
    username = (os.getenv("DEV_ADMIN_USERNAME") or os.getenv("ADMIN_USERNAME") or "").strip()
    if not username:
        raise SystemExit(
            "Set DEV_ADMIN_USERNAME or ADMIN_USERNAME before creating a dev admin."
        )
    return username


def _password_value(column_name: str) -> str:
    password = _required_admin_password()
    if column_name == "hashed_password":
        from app.core.security import get_password_hash

        return get_password_hash(password)
    return password


_require_create_admin_dev_confirmation()
DATABASE_URL = _required_database_url()
ADMIN_USERNAME = _required_admin_username()

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def find_users_table(meta: MetaData) -> Optional[Table]:
    """
    Ищем «похожую» таблицу пользователей: с колонкой username и паролем/хэшем.
    """
    candidate_names = {"users", "user", "auth_users", "accounts"}
    for t in meta.sorted_tables:
        cols = {c.name for c in t.columns}
        if "username" in cols and ({"hashed_password", "password", "pass"} & cols):
            if t.name in candidate_names:
                return t
    for t in meta.sorted_tables:
        cols = {c.name for c in t.columns}
        if "username" in cols and ({"hashed_password", "password", "pass"} & cols):
            return t
    return None


def upsert_admin() -> None:
    admin_username = ADMIN_USERNAME
    admin_email = os.getenv("DEV_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_full_name = os.getenv("DEV_ADMIN_FULL_NAME") or os.getenv(
        "ADMIN_FULL_NAME", "Administrator"
    )

    meta = MetaData()
    meta.reflect(bind=engine)

    users = find_users_table(meta)
    if users is None:
        raise SystemExit(
            "❌ Не нашёл таблицу пользователей (с колонками username + hashed_password/password)."
        )

    cols = {c.name for c in users.columns}
    pwd_col = (
        "hashed_password"
        if "hashed_password" in cols
        else ("password" if "password" in cols else "pass")
    )

    with engine.begin() as conn:
        exists = conn.execute(select(users).where(users.c.username == admin_username)).first()
        if exists:
            print(f"✅ Пользователь '{admin_username}' уже существует — оставляю как есть.")
            return

        row: Dict[str, Any] = {
            "username": admin_username,
            "role": "Admin",  # explicit: this is the admin bootstrapper
            pwd_col: _password_value(pwd_col),
        }
        for key, value in {
            "is_active": True,
            "is_superuser": True,
            "email": admin_email,
            "full_name": admin_full_name,
        }.items():
            if key in cols:
                row[key] = value

        conn.execute(users.insert().values(**row))
        print(f"✅ Создан dev admin '{admin_username}' с паролем из env.")


if __name__ == "__main__":
    upsert_admin()
