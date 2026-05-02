#!/usr/bin/env python3
from app.db.session import SessionLocal
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.id == 19).first()
print(f"Пользователь найден: {user.username if user else 'None'}")
if user:
    print(f"  ID: {user.id}")
    print(f"  Активен: {user.is_active}")
    print(f"  Суперпользователь: {getattr(user, 'is_superuser', 'N/A')}")
db.close()
