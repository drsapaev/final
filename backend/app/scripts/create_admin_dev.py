from __future__ import annotations

import os
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker

# Попытка использовать настройки проекта
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///clinic.db"

# Создаём engine/session на базе DATABASE_URL
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
            # приоритет знакомых имён
            if t.name in candidate_names:
                return t
    # если точных не нашли — берём первую подходящую
    for t in meta.sorted_tables:
        cols = {c.name for c in t.columns}
        if "username" in cols and ({"hashed_password", "password", "pass"} & cols):
            return t
    return None

def upsert_admin() -> None:
    meta = MetaData()
    meta.reflect(bind=engine)

    users = find_users_table(meta)
    if users is None:
        raise SystemExit("❌ Не нашёл таблицу пользователей (с колонками username + hashed_password/password).")

    cols = {c.name for c in users.columns}
    pwd_col = "hashed_password" if "hashed_password" in cols else ("password" if "password" in cols else "pass")

    with engine.begin() as conn:
        # есть ли уже admin?
        exists = conn.execute(select(users).where(users.c.username == "admin")).first()
        if exists:
            print("✅ Пользователь 'admin' уже существует — оставляю как есть.")
            return

        row: Dict[str, Any] = {"username": "admin", pwd_col: "admin"}
        # общие «здоровые» поля, если есть
        for k, v in {
            "is_active": True,
            "is_superuser": True,
            "email": "admin@example.com",
            "full_name": "Administrator",
        }.items():
            if k in cols:
                row[k] = v

        conn.execute(users.insert().values(**row))
        print("✅ Создан пользователь admin/admin (без bcrypt — dev).")

if __name__ == "__main__":
    upsert_admin()
