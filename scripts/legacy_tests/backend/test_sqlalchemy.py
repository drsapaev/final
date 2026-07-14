#!/usr/bin/env python3
from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import select

db = SessionLocal()
stmt = select(User).where(User.id == 19)
result = db.execute(stmt)
user = result.scalar_one_or_none()
print(f"Пользователь найден: {user.username if user else 'None'}")
if user:
    print(f"  ID: {user.id}")
    print(f"  Активен: {user.is_active}")
db.close()
