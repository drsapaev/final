#!/usr/bin/env python3
"""
Reset or create critical users with documented passwords/roles.

Docs reference:
- ROLES_AND_ROUTING.md
"""
from __future__ import annotations

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


USERS = [
    ("admin", "admin123", "Admin"),
    ("registrar", "registrar123", "Registrar"),
    ("lab", "lab123", "Lab"),
    ("doctor", "doctor123", "Doctor"),
    ("cashier", "cashier123", "Cashier"),
    ("cardio", "cardio123", "cardio"),
    ("derma", "derma123", "derma"),
    ("dentist", "dentist123", "dentist"),
]


def main() -> None:
    db = SessionLocal()
    try:
        for username, password, role in USERS:
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.hashed_password = get_password_hash(password)
                user.role = role
                user.is_active = True
                print(f"OK: updated {username} role={role}")
            else:
                user = User(
                    username=username,
                    full_name=username.title(),
                    email=f"{username}@clinic.local",
                    hashed_password=get_password_hash(password),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                print(f"OK: created {username} role={role}")
        db.commit()
        print("DONE: critical users ensured")
    except Exception as e:
        db.rollback()
        print("ERROR:", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
