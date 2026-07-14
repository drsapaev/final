#!/usr/bin/env python3
"""
Тест логирования в runtime
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_logging_runtime():
    """Тестируем логирование в runtime"""
    print("🔔 Тестирую логирование в runtime...")

    try:
        print("🔔 Импортирую queue_ws...")
        from app.ws import queue_ws

        print("✅ queue_ws импортирован")

        print("🔔 Проверяю logger...")
        if hasattr(queue_ws, "log"):
            print("✅ logger найден в queue_ws")
            print(f"🔔 logger: {queue_ws.log}")
            print(f"🔔 logger level: {queue_ws.log.level}")
            print(f"🔔 logger handlers: {len(queue_ws.log.handlers)}")

            # Тестируем логирование
            print("🔔 Тестирую логирование...")
            queue_ws.log.info("Test log message from runtime test")
            print("✅ Логирование протестировано")

        else:
            print("❌ logger не найден в queue_ws")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_logging_runtime()
