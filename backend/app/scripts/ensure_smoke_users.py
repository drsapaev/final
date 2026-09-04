"""Idempotently create dedicated nightly-smoke user accounts (server-side).

Created for the nightly functional smoke (scripts/nightly_functional_smoke.py).
2FA is enforced at login for Admin and Cashier, so the smoke uses non-critical
roles that can authenticate with password only: Registrar, Doctor.

Accounts are tagged [SYNTHETIC-SMOKE] per the repo synthetic data policy.
The password comes from SMOKE_USER_PASSWORD (backend/.env) — never hardcoded.

M-1 (Manager deprecation): smoke_manager is no longer provisioned, pinned or
password-reset here — the deprecated Manager role carries zero privileges
after M-1D and the nightly smoke was repointed to smoke_doctor. A legacy
smoke_manager row that already exists in production (inventory 2026-09-03:
id=20, is_active=true) is deliberately NOT deleted, NOT deactivated and NOT
modified by this script: deactivation is a production data operation owned by
the post-deploy ops step (DEACTIVATE, not DELETE — audit history preserved).

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
    # M-1: smoke_manager removed — Manager is a deprecated legacy/synthetic
    # role (privileged grants removed in M-1D); the nightly smoke uses
    # smoke_doctor for the analytics step since M-1A.
    ("smoke_registrar", "Registrar", "smoke.registrar@synthetic.invalid"),
    ("smoke_doctor", "Doctor", "smoke.doctor@synthetic.invalid"),
]

# Deprecated smoke accounts this script must never provision again, but
# whose EXISTING production rows must not be touched by code either —
# see the module docstring (post-deploy ops owns the deactivation).
RETIRED_SMOKE_USERNAMES = ("smoke_manager",)


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

        # The nightly functional smoke books a VISIT as smoke_doctor, and the
        # visits write-guard requires an ACTIVE Doctor profile for the acting
        # doctor with payload.doctor_id == that profile. Provision it here
        # (idempotent, canonical catalog specialty) so the E2E doctor path
        # stays alive; ORM-direct, so catalog API guards are not involved.
        from app.models.clinic import Doctor  # noqa: E402

        doctor_user = (
            db.execute(select(User).where(User.username == "smoke_doctor"))
            .scalars()
            .first()
        )
        if doctor_user is not None:
            profile = (
                db.query(Doctor).filter(Doctor.user_id == doctor_user.id).first()
            )
            if profile is None:
                profile = Doctor(
                    user_id=doctor_user.id,
                    specialty="cardiology",
                    cabinet="SMOKE",
                    active=True,
                )
                db.add(profile)
                db.commit()
                results.append(
                    {"doctor_profile": {"id": profile.id, "created": True}}
                )
            elif not profile.active or profile.specialty == "general":
                profile.active = True
                profile.specialty = "cardiology"
                db.commit()
                results.append(
                    {"doctor_profile": {"id": profile.id, "repaired": True}}
                )

        # M-1: report — never touch — any retired smoke account that still
        # exists. No password re-pin, no role rewrite, no activation flip:
        # the row's lifecycle belongs to the post-deploy ops step only.
        for retired_username in RETIRED_SMOKE_USERNAMES:
            legacy = (
                db.execute(select(User).where(User.username == retired_username))
                .scalars()
                .first()
            )
            if legacy:
                results.append(
                    {
                        "username": retired_username,
                        "id": legacy.id,
                        "role": legacy.role,
                        "is_active": bool(legacy.is_active),
                        "retired": True,
                        "untouched": True,
                    }
                )
    return results


if __name__ == "__main__":
    for item in ensure_smoke_users():
        print("[ensure_smoke_users]", item)
