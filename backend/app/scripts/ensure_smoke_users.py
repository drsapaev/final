"""Idempotently create dedicated nightly-smoke user accounts (server-side).

Created for the nightly functional smoke (scripts/nightly_functional_smoke.py).
2FA is enforced at login for Admin and Cashier, so the smoke uses non-critical
roles that can authenticate with password only: Registrar, Doctor.

M-1 (Manager deprecation): 'smoke_manager' is NO LONGER provisioned —
Manager is a deprecated legacy/synthetic role (canonical write-freeze).
If a legacy smoke_manager row already exists, this script does NOT touch it:
no create, no password re-pin, no role change, no deactivation — the row is
an explicit post-deploy ops decision (recommended: is_active true -> false,
keeping audit/history; never delete).

Accounts are tagged [SYNTHETIC-SMOKE] per the repo synthetic data policy.
The password comes from SMOKE_USER_PASSWORD (backend/.env) — never hardcoded.

Usage:
    powershell -File scripts/run_python.ps1 -m app.scripts.ensure_smoke_users
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

HERE = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # type: ignore[attr-defined]  # noqa: E402

SMOKE_USERS = [
    # (username, role, email) — roles must NOT be in CRITICAL_2FA_ROLES
    # (Admin/Cashier) so password-only login works.
    # M-1 (Manager deprecation): smoke_manager removed from provisioning.
    # Manager is a deprecated legacy/synthetic role: no new accounts, no
    # password re-pin, no role re-pin. The loop below only iterates this
    # list, so an existing legacy smoke_manager row is left untouched.
    ("smoke_registrar", "Registrar", "smoke.registrar@synthetic.invalid"),
    ("smoke_doctor", "Doctor", "smoke.doctor@synthetic.invalid"),
]


def _load_smoke_password() -> str:
    password = os.getenv("SMOKE_USER_PASSWORD", "").strip()
    if password:
        return password
    # Fall back to backend/.env so Task Scheduler does not need env setup.
    env_path = os.path.join(BACKEND_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("SMOKE_USER_PASSWORD="):
                    password = line.split("=", 1)[1].strip().strip("'\"")
                    break
    if not password:
        raise RuntimeError(
            "SMOKE_USER_PASSWORD must be set (env or backend/.env) before "
            "provisioning smoke accounts."
        )
    return password


def _hash_password(pw: str) -> str:
    # Use the app's own CryptContext (argon2 primary, bcrypt legacy) so the
    # hash is guaranteed to verify against production's verifier.
    from app.core.security import pwd_context  # noqa: E402

    return pwd_context.hash(pw)


def ensure_smoke_users() -> list[dict]:
    password = _load_smoke_password()
    hashed = _hash_password(password)
    results = []
    with SessionLocal() as db:  # type: ignore # type: Session
        for username, role, email in SMOKE_USERS:
            row = (
                db.execute(select(User).where(User.username == username))
                .scalars()
                .first()
            )
            if row:
                changed = False
                # Always re-pin password/role so the smoke can always log in.
                if row.hashed_password != hashed:
                    row.hashed_password = hashed
                    changed = True
                if row.role != role:
                    row.role = role
                    changed = True
                if not row.is_active:
                    row.is_active = True
                    changed = True
                if changed:
                    db.commit()
                results.append(
                    {"username": username, "id": row.id, "role": role, "updated": changed}
                )
                continue

            row = User(
                username=username,
                full_name=f"[SYNTHETIC-SMOKE] {role}",
                email=email,
                role=role,
                is_active=True,
                hashed_password=hashed,
            )
            db.add(row)
            db.commit()
            results.append(
                {"username": username, "id": row.id, "role": role, "created": True}
            )
    return results


if __name__ == "__main__":
    for item in ensure_smoke_users():
        print("[ensure_smoke_users]", item)
