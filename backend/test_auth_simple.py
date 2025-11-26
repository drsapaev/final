#!/usr/bin/env python3
"""Простой тест аутентификации"""

from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User

def test_auth():
    # 1. Создаем токен
    payload = {'sub': 'admin@example.com', 'user_id': 19, 'username': 'admin@example.com'}
    token = jwt.encode({**payload, 'exp': datetime.utcnow() + timedelta(hours=1)},
                      settings.SECRET_KEY,
                      algorithm=getattr(settings, 'ALGORITHM', 'HS256'))
    print(f"✅ Токен создан: {token[:50]}...")

    # 2. Декодируем токен
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[getattr(settings, 'ALGORITHM', 'HS256')])
    print(f"✅ Токен декодирован: {decoded}")

    # 3. Проверяем пользователя в БД
    db = SessionLocal()
    user = db.query(User).filter(User.username == 'admin@example.com').first()
    print(f"✅ Пользователь в БД: {user.username if user else 'None'}")
    db.close()

if __name__ == "__main__":
    test_auth()