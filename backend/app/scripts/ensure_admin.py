from __future__ import annotations

import os
import sys
from sqlalchemy import select
from sqlalchemy.orm import Session

# Разрешаем запуск из корня репозитория:
#   python -m app.scripts.ensure_admin
# или
#   PYTHONPATH=backend python backend/app/scripts/ensure_admin.py
HERE = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # type: ignore[attr-defined]  # noqa: E402


def _hash_or_plain(pw: str) -> str:
    """Вернуть bcrypt-хэш, если passlib доступен, иначе исходную строку (для dev)."""
    try:
        from passlib.hash import bcrypt  # type: ignore
        return bcrypt.hash(pw)
    except Exception:
        return pw


def ensure_admin() -> dict:
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    password = os.getenv("ADMIN_PASSWORD", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    full_name = os.getenv("ADMIN_FULL_NAME", "Administrator").strip()

    with SessionLocal() as db:  # type: Session
        row = db.execute(select(User).where(User.username == username)).scalars().first()
        if row:
            changed = False
            if email and row.email != email:
                row.email = email
                changed = True
            if full_name and row.full_name != full_name:
                row.full_name = full_name
                changed = True
            if os.getenv("ADMIN_RESET_PASSWORD", "").strip().lower() in {"1", "true", "yes"}:
                row.hashed_password = _hash_or_plain(password)
                changed = True
            if row.role != "Admin":
                row.role = "Admin"
                changed = True
            if not row.is_active:
                row.is_active = True
                changed = True
            if changed:
                db.flush()
            return {
                "updated": True,
                "id": row.id,
                "username": row.username,
                "email": row.email,
                "full_name": row.full_name,
                "role": row.role,
            }

        row = User(
            username=username,
            full_name=full_name,
            email=email,
            role="Admin",
            is_active=True,
            hashed_password=_hash_or_plain(password),
        )
        db.add(row)
        db.flush()
        return {
            "created": True,
            "id": row.id,
            "username": row.username,
            "email": row.email,
            "full_name": row.full_name,
            "role": row.role,
        }


if __name__ == "__main__":
    info = ensure_admin()
    print("[ensure_admin]", info)