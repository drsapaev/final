#!/usr/bin/env python3
"""
Отладка запуска сервера
"""

import sys
import traceback

def test_imports():
    """Тестирование импортов"""
    print("🔍 Тестирование импортов...")
    
    try:
        print("  - Импорт FastAPI...")
        from fastapi import FastAPI
        print("  ✅ FastAPI импортирован")
        
        print("  - Импорт app.main...")
        from app.main import app
        print("  ✅ app.main импортирован")
        
        print("  - Проверка типа app...")
        print(f"  ✅ app тип: {type(app)}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка импорта: {e}")
        traceback.print_exc()
        return False

def test_uvicorn_start():
    """Тестирование запуска uvicorn"""
    print("\n🚀 Тестирование запуска uvicorn...")
    
    try:
        import uvicorn
        print("  ✅ uvicorn импортирован")
        
        # Попробуем запустить сервер
        print("  - Попытка запуска сервера...")
        
        # Импортируем приложение
        from app.main import app
        
        # Запускаем сервер (это заблокирует выполнение)
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="debug",
            reload=False  # Отключаем reload для отладки
        )
        
    except Exception as e:
        print(f"  ❌ Ошибка запуска uvicorn: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Диагностика запуска сервера")
    print("=" * 50)
    
    # Тестируем импорты
    if not test_imports():
        print("\n❌ Ошибка на этапе импорта. Завершение.")
        sys.exit(1)
    
    # Тестируем запуск uvicorn
    print("\n⚠️  Внимание: следующий тест запустит сервер!")
    print("Нажмите Ctrl+C для остановки сервера")
    input("Нажмите Enter для продолжения...")
    
    test_uvicorn_start()
