#!/usr/bin/env python3
"""Детальная диагностика создания базы данных для CI/CD"""

import os
import sys
import time

sys.path.insert(0, '.')


def debug_environment():
    """Отлаживаем окружение"""
    print("🔍 ДИАГНОСТИКА ОКРУЖЕНИЯ:")
    print(f"  Python версия: {sys.version}")
    print(f"  Текущая директория: {os.getcwd()}")
    print(f"  PYTHONPATH: {sys.path[:3]}")
    print(f"  DATABASE_URL: {os.environ.get('DATABASE_URL', 'НЕ УСТАНОВЛЕН')}")
    print(f"  CORS_DISABLE: {os.environ.get('CORS_DISABLE', 'НЕ УСТАНОВЛЕН')}")
    print(f"  WS_DEV_ALLOW: {os.environ.get('WS_DEV_ALLOW', 'НЕ УСТАНОВЛЕН')}")
    print()


def debug_imports():
    """Отлаживаем импорты"""
    print("🔍 ДИАГНОСТИКА ИМПОРТОВ:")
    try:
        from app.db.base import Base

        print("  ✅ app.db.base импортирован")
        print(f"  📊 Количество таблиц в metadata: {len(Base.metadata.tables)}")
        for table_name in sorted(Base.metadata.tables.keys()):
            print(f"    - {table_name}")
    except Exception as e:
        print(f"  ❌ Ошибка импорта app.db.base: {e}")
        return False

    try:
        print("  ✅ app.db.session импортирован")
    except Exception as e:
        print(f"  ❌ Ошибка импорта app.db.session: {e}")
        return False

    try:
        print("  ✅ app.models.user импортирован")
    except Exception as e:
        print(f"  ❌ Ошибка импорта app.models.user: {e}")
        return False

    try:
        print("  ✅ app.core.security импортирован")
    except Exception as e:
        print(f"  ❌ Ошибка импорта app.core.security: {e}")
        return False

    try:
        print("  ✅ sqlalchemy.text импортирован")
    except Exception as e:
        print(f"  ❌ Ошибка импорта sqlalchemy.text: {e}")
        return False

    print()
    return True


def debug_database_creation():
    """Отлаживаем создание базы данных"""
    print("🔍 ДИАГНОСТИКА СОЗДАНИЯ БАЗЫ ДАННЫХ:")

    try:
        from sqlalchemy import text

        from app.core.security import get_password_hash
        from app.db.base import Base
        from app.db.session import engine, SessionLocal
        from app.models.user import User

        # Создаем таблицы
        print("  🔧 Создаем таблицы базы данных...")
        Base.metadata.create_all(bind=engine)
        print("  ✅ База данных создана")

        # Проверяем, что таблица users действительно создана
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
            )
            if not result.fetchone():
                print("  ❌ Таблица users не найдена после создания")
                raise Exception("Таблица users не создана")
            print("  ✅ Таблица users подтверждена")

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
                print("  ✅ Тестовый пользователь admin создан")
            else:
                print("  ✅ Пользователь admin уже существует")
        finally:
            db.close()

        print("  🎉 Все проверки базы данных прошли успешно!")
        return True

    except Exception as e:
        print(f"  ⚠️ Ошибка создания БД: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Основная функция диагностики"""
    print("🚀 ЗАПУСК ДЕТАЛЬНОЙ ДИАГНОСТИКИ CI/CD")
    print("=" * 50)

    debug_environment()

    if not debug_imports():
        print("❌ ДИАГНОСТИКА ЗАВЕРШЕНА С ОШИБКОЙ: Проблемы с импортами")
        return False

    if not debug_database_creation():
        print("❌ ДИАГНОСТИКА ЗАВЕРШЕНА С ОШИБКОЙ: Проблемы с созданием БД")
        return False

    print("=" * 50)
    print("🎉 ДИАГНОСТИКА ЗАВЕРШЕНА УСПЕШНО!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
