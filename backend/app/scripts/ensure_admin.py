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

from app.core.security import get_password_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # type: ignore[attr-defined]  # noqa: E402
from app.models.user_profile import UserProfile  # noqa: E402
from app.services.setup_service import SetupService  # noqa: E402
from app.services.token_blacklist_service import (
    revoke_account_sessions_locked,
)  # noqa: E402

INITIALIZED_OVERRIDE_ENV = "ENSURE_ADMIN_ALLOW_INITIALIZED"
INITIALIZED_OVERRIDE_CONFIRM_ENV = "ENSURE_ADMIN_CONFIRM_INITIALIZED_OVERRIDE"


def _required_admin_password() -> str:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError(
            "ADMIN_PASSWORD must be set before creating or resetting the bootstrap admin user."
        )
    return password


def _required_admin_username() -> str:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    if not username:
        raise RuntimeError(
            "ADMIN_USERNAME must be set before creating or resetting the bootstrap admin user."
        )
    return username


def ensure_admin() -> dict:
    username = _required_admin_username()
    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    full_name = os.getenv("ADMIN_FULL_NAME", "Administrator").strip()
    allow_initialized = os.getenv(INITIALIZED_OVERRIDE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    confirm_initialized_override = os.getenv(
        INITIALIZED_OVERRIDE_CONFIRM_ENV, ""
    ).strip().lower() in {"1", "true", "yes"}

    with SessionLocal() as db:  # type: ignore # type: Session
        if SetupService(db).is_initialized():
            if not allow_initialized or not confirm_initialized_override:
                return {
                    "skipped": True,
                    "reason": (
                        "initialized_instance_requires_explicit_ops_override; "
                        f"set {INITIALIZED_OVERRIDE_ENV}=1 and "
                        f"{INITIALIZED_OVERRIDE_CONFIRM_ENV}=1 for controlled recovery"
                    ),
                }

        row = (
            db.execute(
                select(User)
                .where(User.username == username)
                .with_for_update(key_share=True)
                .execution_options(populate_existing=True)
            )
            .scalars()
            .first()
        )

        if not row and email:
            row = (
                db.execute(
                    select(User)
                    .where(User.email == email)
                    .with_for_update(key_share=True)
                    .execution_options(populate_existing=True)
                )
                .scalars()
                .first()
            )

        if row:
            changed = False
            new_email = None
            if email and row.email != email:
                existing = (
                    db.execute(
                        select(User).where(User.email == email, User.id != row.id)
                    )
                    .scalars()
                    .first()
                )
                if not existing:
                    new_email = email
            reset_password = os.getenv("ADMIN_RESET_PASSWORD", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }
            password_hash = (
                get_password_hash(_required_admin_password())
                if reset_password
                else None
            )
            profile = None
            if new_email:
                profile = (
                    db.execute(
                        select(UserProfile)
                        .where(UserProfile.user_id == row.id)
                        .with_for_update()
                    )
                    .scalars()
                    .first()
                )
            if new_email or reset_password or row.role != "Admin" or not row.is_active:
                revoke_account_sessions_locked(db, row, revoke_password_resets=True)
            if new_email:
                if profile is not None:
                    profile.email_verified = False
                row.email = new_email
                changed = True
            if full_name and row.full_name != full_name:
                row.full_name = full_name
                changed = True
            if reset_password:
                row.hashed_password = password_hash
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

        existing_email = (
            db.execute(
                select(User)
                .where(User.email == email)
                .with_for_update(key_share=True)
                .execution_options(populate_existing=True)
            )
            .scalars()
            .first()
        )
        if existing_email:
            password = _required_admin_password()
            password_hash = get_password_hash(password)
            revoke_account_sessions_locked(
                db, existing_email, revoke_password_resets=True
            )
            existing_email.username = username
            existing_email.role = "Admin"
            existing_email.is_active = True
            existing_email.hashed_password = password_hash
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

        password = _required_admin_password()
        row = User(
            username=username,
            full_name=full_name,
            email=email,
            role="Admin",
            is_active=True,
            hashed_password=get_password_hash(password),
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
