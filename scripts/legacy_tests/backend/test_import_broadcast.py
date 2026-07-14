#!/usr/bin/env python3
"""
Тест импорта _broadcast
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_import_broadcast():
    """Тестируем импорт _broadcast"""
    print("🔔 Тестирую импорт _broadcast...")

    try:
        print("🔔 Импортирую online_queue...")
        from app.services import online_queue

        print("✅ online_queue импортирован")

        print("🔔 Проверяю _broadcast...")
        if hasattr(online_queue, "_broadcast"):
            print("✅ _broadcast найден в online_queue")
            print(f"🔔 _broadcast: {online_queue._broadcast}")
        else:
            print("❌ _broadcast не найден в online_queue")
            print(f"🔔 Доступные атрибуты: {dir(online_queue)}")

    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_import_broadcast()
