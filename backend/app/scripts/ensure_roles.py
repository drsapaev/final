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
        print("ok")
    finally:
        db.close()


if __name__ == "__main__":
    upsert_users()
