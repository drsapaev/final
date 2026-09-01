from __future__ import annotations

import os

USERS = [
    ("admin", "Admin", "admin@ex.com"),
    ("registrar", "Registrar", "reg@ex.com"),
    ("lab", "Lab", "lab@ex.com"),
    ("doctor", "Doctor", "doc@ex.com"),
    ("cardio", "cardio", "cardio@ex.com"),
    ("derma", "derma", "derma@ex.com"),
    ("dentist", "dentist", "dentist@ex.com"),
    ("cashier", "Cashier", "cash@ex.com"),
]


def _require_ensure_roles_confirmation() -> None:
    if os.getenv("CONFIRM_ENSURE_ROLES") != "1":
        raise SystemExit(
            "Refusing to create or update role users without CONFIRM_ENSURE_ROLES=1."
        )


def _password_env_names(username: str) -> list[str]:
    names = [f"ENSURE_ROLES_{username.upper()}_PASSWORD"]
    if username == "admin":
        names.insert(0, "ADMIN_PASSWORD")
    return names


def _role_password(username: str, *, required: bool) -> str | None:
    for env_name in _password_env_names(username):
        password = os.getenv(env_name, "").strip()
        if password:
            return password
    if required:
        expected = " or ".join(_password_env_names(username))
        raise RuntimeError(f"Set {expected} before creating user '{username}'.")
    return None


def upsert_users():
    _require_ensure_roles_confirmation()

    from app.core.security import get_password_hash
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.services.user_mgmt._base import (
        DOCTOR_PROFILE_ROLES,
        DOCTOR_ROLE_DEFAULT_SPECIALTY,
    )

    # D-3 RBAC unification: the lifecycle invariant is
    #   role=Doctor-family  <->  active linked Doctor profile
    # Legacy doctor users (cardio/derma/dentist) used to be created WITHOUT
    # a Doctor row — they could log in but were invisible to queues,
    # schedules and ownership checks that resolve via doctors.user_id.
    # Opt out with ENSURE_ROLES_SKIP_DOCTOR_PROFILES=1 (e.g. for a stripped
    # staging DB that intentionally keeps profiles detached).
    skip_profiles = os.getenv("ENSURE_ROLES_SKIP_DOCTOR_PROFILES") == "1"

    from app.models.clinic import Doctor

    db = SessionLocal()
    try:
        for username, role, email in USERS:
            u = db.query(User).filter(User.username == username).first()
            if not u:
                u = User(
                    username=username,
                    role=role,
                    email=email,
                    hashed_password=get_password_hash(
                        _role_password(username, required=True)
                    ),
                )
                db.add(u)
            else:
                u.role = role
                u.email = email
                password = _role_password(username, required=False)
                if password:
                    u.hashed_password = get_password_hash(password)
                u.is_active = True
            db.commit()

            if skip_profiles or role not in DOCTOR_PROFILE_ROLES:
                continue
            doctor = (
                db.query(Doctor).filter(Doctor.user_id == u.id).first()
            )
            if doctor is None:
                doctor = Doctor(
                    user_id=u.id,
                    specialty=DOCTOR_ROLE_DEFAULT_SPECIALTY.get(role, "general"),
                    active=bool(u.is_active),
                )
                db.add(doctor)
                db.commit()
                print(f"doctor profile ensured for {username} (role={role})")
            elif not doctor.active:
                # Codex round-1 P2: reactivating an existing doctor-family
                # user must also reactivate their Doctor row — otherwise
                # rerunning this recovery/provisioning script after a prior
                # deactivation/demotion leaves an ACTIVE account whose
                # inactive profile is still skipped by ownership checks,
                # queues and schedules (the lifecycle invariant the create
                # path above already honors via active=bool(u.is_active)).
                doctor.active = bool(u.is_active)
                db.commit()
                print(f"doctor profile reactivated for {username} (role={role})")
        print("ok")
    finally:
        db.close()


if __name__ == "__main__":
    upsert_users()
