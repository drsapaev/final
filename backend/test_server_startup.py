#!/usr/bin/env python3
"""
Тест для проверки запуска сервера
"""
import os
import sys
import traceback

# Устанавливаем переменные окружения
os.environ["DATABASE_URL"] = "sqlite:///./clinic.db"
os.environ["CORS_DISABLE"] = "1"
os.environ["WS_DEV_ALLOW"] = "1"

def test_imports():
    """Тестируем импорты основных модулей"""
    print("🔍 Тестируем импорты...")
    
    try:
        print("  - Импорт app.main...")
        from app.main import app
        print("  ✅ app.main импортирован успешно")
        
        print("  - Импорт app.db.session...")
        from app.db.session import engine, SessionLocal
        print("  ✅ app.db.session импортирован успешно")
        
        print("  - Импорт app.api.v1.api...")
        from app.api.v1.api import api_router
        print("  ✅ app.api.v1.api импортирован успешно")
        
        print("  - Импорт app.api.v1.endpoints.health...")
        from app.api.v1.endpoints.health import router as health_router
        print("  ✅ app.api.v1.endpoints.health импортирован успешно")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка импорта: {e}")
        traceback.print_exc()
        return False

def test_database_connection():
    """Тестируем подключение к базе данных"""
    print("\n🔍 Тестируем подключение к БД...")
    
    try:
        from app.db.session import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("  ✅ Подключение к БД успешно")
            return True
            
    except Exception as e:
        print(f"  ❌ Ошибка подключения к БД: {e}")
        traceback.print_exc()
        return False

def test_health_endpoint():
    """Тестируем health endpoint"""
    print("\n🔍 Тестируем health endpoint...")
    
    try:
        from app.api.v1.endpoints.health import get_health
        
        result = get_health()
        print(f"  ✅ Health endpoint работает: {result}")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка health endpoint: {e}")
        traceback.print_exc()
        return False

def test_app_creation():
    """Тестируем создание FastAPI приложения"""
    print("\n🔍 Тестируем создание FastAPI приложения...")
    
    try:
        from app.main import app
        
        # Проверяем, что приложение создано
        if hasattr(app, 'router'):
            print("  ✅ FastAPI приложение создано успешно")
            print(f"  📊 Количество маршрутов: {len(app.router.routes)}")
            return True
        else:
            print("  ❌ FastAPI приложение не создано корректно")
            return False
            
    except Exception as e:
        print(f"  ❌ Ошибка создания приложения: {e}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов сервера...")
    print("=" * 50)
    
    # Диагностика окружения
    print("🔍 Диагностика окружения:")
    print(f"  Python version: {sys.version}")
    print(f"  Current working directory: {os.getcwd()}")
    print(f"  PYTHONPATH: {os.environ.get('PYTHONPATH', 'не установлен')}")
    print(f"  DATABASE_URL: {os.environ.get('DATABASE_URL', 'не установлен')}")
    print(f"  CORS_DISABLE: {os.environ.get('CORS_DISABLE', 'не установлен')}")
    print(f"  WS_DEV_ALLOW: {os.environ.get('WS_DEV_ALLOW', 'не установлен')}")
    
    tests = [
        test_imports,
        test_database_connection,
        test_health_endpoint,
        test_app_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            print(f"\n🔍 Запуск теста: {test.__name__}")
            if test():
                passed += 1
                print(f"✅ Тест {test.__name__} прошел успешно")
            else:
                print(f"❌ Тест {test.__name__} не прошел")
        except Exception as e:
            print(f"❌ Тест {test.__name__} упал с ошибкой: {e}")
            print("Детали ошибки:")
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты: {passed}/{total} тестов прошли")
    
    if passed == total:
        print("✅ Все тесты прошли успешно!")
        return 0
    else:
        print("❌ Некоторые тесты не прошли")
        print("🔍 Рекомендуется проверить логи выше для диагностики")
        return 1

if __name__ == "__main__":
    sys.exit(main())
