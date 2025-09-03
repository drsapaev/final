#!/usr/bin/env python3
"""
Простой тест логирования
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_logging_simple():
    """Тестируем логирование просто"""
    print("🔔 Тестирую логирование...")

    try:
        import logging

        print("✅ logging импортирован")

        # Проверяем настройки логирования
        root_logger = logging.getLogger()
        print(f"🔔 Root logger level: {root_logger.level}")
        print(f"🔔 Root logger handlers: {len(root_logger.handlers)}")

        # Проверяем logger для ws
        ws_logger = logging.getLogger("ws.queue")
        print(f"🔔 WS logger level: {ws_logger.level}")
        print(f"🔔 WS logger handlers: {len(ws_logger.handlers)}")

        # Тестируем логирование
        print("🔔 Тестирую логирование...")
        ws_logger.info("Test log message from test script")
        print("✅ Логирование протестировано")

    except Exception as e:
        print(f"❌ Ошибка логирования: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_logging_simple()
