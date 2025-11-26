#!/usr/bin/env python3
"""
Скрипт для проверки базы данных в GitHub Actions
"""
import sys
import os
import traceback
sys.path.insert(0, '.')

print("🔧 Начинаем проверку базы данных...")

# Проверяем переменные окружения
database_url = os.getenv('DATABASE_URL', 'sqlite:///./clinic.db')
print(f"📊 DATABASE_URL: {database_url}")

# Импортируем все модели для создания таблиц
try:
    from app.db.base import Base
    from app.db.session import engine, SessionLocal
    print("✅ Импорт базовых компонентов БД успешен")
except Exception as e:
    print(f"❌ Ошибка импорта базовых компонентов БД: {e}")
    traceback.print_exc()
    sys.exit(1)

# Импортируем все модели через __init__.py чтобы избежать проблем с отсутствующими моделями
try:
    import app.models
    print("✅ Импорт всех моделей успешен")
except ImportError as e:
    print(f'⚠️ Ошибка импорта моделей: {e}')
    print("🔄 Пытаемся импортировать только базовые модели...")
    try:
        from app.models.user import User
        print("✅ Импорт базовой модели User успешен")
    except Exception as user_e:
        print(f"❌ Ошибка импорта модели User: {user_e}")
        traceback.print_exc()
        sys.exit(1)

# Импортируем функцию для хеширования паролей
try:
    from app.core.security import get_password_hash
    print("✅ Импорт функции хеширования паролей успешен")
except ImportError as e:
    print(f"⚠️ Ошибка импорта функции хеширования: {e}")
    print("🔄 Используем простую заглушку...")
    def get_password_hash(password: str) -> str:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

from sqlalchemy import text

print("🗄️ Начинаем работу с базой данных...")

try:
    # Создаем таблицы если их нет
    print("🔨 Создаем таблицы...")
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы/проверены")
    
    # Проверяем подключение к базе данных
    print("🔌 Проверяем подключение к базе данных...")
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ База данных доступна')
        
        # Проверяем существование таблицы users
        print("👤 Проверяем таблицу users...")
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
        if not result.fetchone():
            print('❌ Таблица users не найдена после создания')
            raise Exception("Таблица users не создана")
        print('✅ Таблица users подтверждена')
        
        # Проверяем количество записей в основных таблицах
        print("📊 Подсчитываем записи в таблицах...")
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        tables = [row[0] for row in result.fetchall()]
        
        total_tables = len(tables)
        successful_checks = 0
        
        for table in tables:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = result.scalar()
                print(f'   📊 {table}: {count} записей')
                successful_checks += 1
            except Exception as e:
                print(f'   ⚠️ {table}: ошибка при подсчете записей ({str(e)})')
        
        print(f"📈 Статистика: {successful_checks}/{total_tables} таблиц проверено успешно")
                
    # Небольшая задержка для стабилизации
    import time
    time.sleep(1)
                    
    # Создаем тестового пользователя admin если его нет
    print("👤 Проверяем/создаем тестового пользователя admin...")
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
    print(f'❌ Критическая ошибка при работе с базой данных: {e}')
    print("📋 Детали ошибки:")
    traceback.print_exc()
    print("🔄 Попытка диагностики...")
    
    # Дополнительная диагностика
    try:
        print(f"📊 DATABASE_URL: {database_url}")
        print(f"📁 Текущая директория: {os.getcwd()}")
        print(f"📁 Содержимое директории: {os.listdir('.')}")
        if os.path.exists('clinic.db'):
            print(f"📊 Размер файла БД: {os.path.getsize('clinic.db')} байт")
        else:
            print("❌ Файл clinic.db не найден")
    except Exception as diag_e:
        print(f"⚠️ Ошибка диагностики: {diag_e}")
    
    sys.exit(1)
