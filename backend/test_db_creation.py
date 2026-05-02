#!/usr/bin/env python3
"""Тест создания базы данных для CI/CD"""

import sys
import time

sys.path.insert(0, '.')

from sqlalchemy import text

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User


def test_database_creation():
    try:
        # Создаем таблицы
        print('🔧 Создаем таблицы базы данных...')
        Base.metadata.create_all(bind=engine)
        print('✅ База данных создана')

        # Проверяем, что таблица users действительно создана
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
            )
            if not result.fetchone():
                print('❌ Таблица users не найдена после создания')
                raise Exception("Таблица users не создана")
            print('✅ Таблица users подтверждена')

        # Небольшая задержка для стабилизации
        time.sleep(1)

        # Создаем тестового пользователя admin
        db = SessionLocal()
        try:
            existing_admin = db.query(User).filter(User.username == "admin").first()
            if not existing_admin:
                admin_user = User(
                    username="admin",
                    email="admin@clinic.com",
                    hashed_password=get_password_hash("admin123"),
                    role="Admin",
                    is_active=True,
                    is_superuser=True,
                )
                db.add(admin_user)
                db.commit()
                print('✅ Тестовый пользователь admin создан')
            else:
                print('✅ Пользователь admin уже существует')
        finally:
            db.close()

        print('🎉 Все проверки прошли успешно!')
        return True

    except Exception as e:
        print(f'⚠️ Ошибка: {e}')
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_database_creation()
    sys.exit(0 if success else 1)
