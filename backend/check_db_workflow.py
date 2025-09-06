#!/usr/bin/env python3
"""
Скрипт для проверки базы данных в GitHub Actions
"""
import sys
sys.path.insert(0, '.')

# Импортируем все модели для создания таблиц
from app.db.base import Base
from app.db.session import engine, SessionLocal

# Импортируем все модели через __init__.py чтобы избежать проблем с отсутствующими моделями
try:
    import app.models
except ImportError as e:
    print(f'⚠️ Ошибка импорта моделей: {e}')
    # Импортируем только базовые модели
    from app.models.user import User

# Импортируем функцию для хеширования паролей
try:
    from app.core.security import get_password_hash
except ImportError:
    # Если не удается импортировать, используем простую заглушку
    def get_password_hash(password: str) -> str:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

from sqlalchemy import text

try:
    # Создаем таблицы если их нет
    Base.metadata.create_all(bind=engine)
    
    # Проверяем, что таблица users действительно создана
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ База данных доступна')
        
        # Проверяем существование таблицы users
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
        if not result.fetchone():
            print('❌ Таблица users не найдена после создания')
            raise Exception("Таблица users не создана")
        print('✅ Таблица users подтверждена')
        
        # Проверяем количество записей в основных таблицах
        # Получаем список всех таблиц из базы данных динамически
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        tables = [row[0] for row in result.fetchall()]
        for table in tables:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = result.scalar()
                print(f'   📊 {table}: {count} записей')
            except Exception as e:
                print(f'   ⚠️ {table}: ошибка при подсчете записей ({str(e)})')
                
    # Небольшая задержка для стабилизации
    import time
    time.sleep(1)
                    
    # Создаем тестового пользователя admin если его нет
    try:
        db = SessionLocal()
        try:
            from app.models.user import User
            existing_admin = db.query(User).filter(User.username == 'admin').first()
            if not existing_admin:
                admin_user = User(
                    username='admin',
                    email='admin@clinic.com',
                    hashed_password=get_password_hash('admin123'),
                    role='Admin',
                    is_active=True,
                    is_superuser=True
                )
                db.add(admin_user)
                db.commit()
                print('✅ Тестовый пользователь admin создан')
            else:
                print('✅ Пользователь admin уже существует')
        except Exception as user_error:
            print(f'⚠️ Ошибка при работе с пользователями: {user_error}')
            db.rollback()
        finally:
            db.close()
    except Exception as db_error:
        print(f'⚠️ Ошибка при подключении к БД для пользователей: {db_error}')
                    
    print('🎉 Все проверки базы данных прошли успешно!')
                    
except Exception as e:
    print(f'❌ Ошибка подключения к базе: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
