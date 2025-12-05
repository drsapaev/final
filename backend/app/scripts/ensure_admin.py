from __future__ import annotations

import os
import sys

from sqlalchemy import select

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
    # SECURITY WARNING: В продакшене ОБЯЗАТЕЛЬНО установите ADMIN_PASSWORD через переменную окружения!
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    password = os.getenv("ADMIN_PASSWORD", "admin")  # ⚠️ DEV ONLY: используйте сильный пароль в продакшене!
    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    full_name = os.getenv("ADMIN_FULL_NAME", "Administrator").strip()

    with SessionLocal() as db:  # type: ignore # type: Session
        # Check by username first
        row = (
            db.execute(select(User).where(User.username == username)).scalars().first()
        )
        
        # If not found by username, check by email
        if not row and email:
            row = (
                db.execute(select(User).where(User.email == email)).scalars().first()
            )
        
        if row:
            changed = False
            # Only update email if it's different and doesn't conflict
            if email and row.email != email:
                # Check if new email already exists
                existing = db.execute(select(User).where(User.email == email, User.id != row.id)).scalars().first()
                if not existing:
                    row.email = email
                    changed = True
            if full_name and row.full_name != full_name:
                row.full_name = full_name
                changed = True
            if os.getenv("ADMIN_RESET_PASSWORD", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }:
                row.hashed_password = _hash_or_plain(password)
                changed = True
            if row.role != "Admin":
                row.role = "Admin"
                changed = True
            if not row.is_active:
                row.is_active = True
                changed = True
            if changed:
                db.commit()
            return {
                "updated": changed,
                "id": row.id,
                "username": row.username,
                "email": row.email,
                "full_name": row.full_name,
                "role": row.role,
            }

        # Check if email already exists
        existing_email = db.execute(select(User).where(User.email == email)).scalars().first()
        if existing_email:
            # Update existing user to admin
            existing_email.username = username
            existing_email.role = "Admin"
            existing_email.is_active = True
            existing_email.hashed_password = _hash_or_plain(password)
            existing_email.full_name = full_name
            db.commit()
            return {
                "updated": True,
                "id": existing_email.id,
                "username": existing_email.username,
                "email": existing_email.email,
                "full_name": existing_email.full_name,
                "role": existing_email.role,
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
        db.commit()
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
