from __future__ import annotations

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User

USERS = [
    ("admin", "Admin", "admin@ex.com", "admin123"),
    ("registrar", "Registrar", "reg@ex.com", "reg123"),
    ("lab", "Lab", "lab@ex.com", "lab123"),
    ("doctor", "Doctor", "doc@ex.com", "doc123"),
    ("cardio", "Doctor", "cardio@ex.com", "doc123"),
    ("derma", "Doctor", "derma@ex.com", "doc123"),
    ("dentist", "Doctor", "dentist@ex.com", "doc123"),
    ("cashier", "Cashier", "cash@ex.com", "cash123"),
]

def upsert_users():
    db = SessionLocal()
    try:
        for username, role, email, pwd in USERS:
            u = db.query(User).filter(User.username == username).first()
            if not u:
                u = User(username=username, role=role, email=email, hashed_password=get_password_hash(pwd))
                db.add(u)
            else:
                u.role = role
                u.email = email
            db.commit()
        print("ok")
    finally:
        db.close()

if __name__ == "__main__":
    upsert_users()
