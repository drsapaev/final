#!/usr/bin/env python3
"""
Тест импорта _broadcast в appointments.py
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_import_broadcast():
    """Тестируем импорт _broadcast"""
    print("🔔 Тестирую импорт _broadcast...")

    try:
        print("🔔 Импортирую appointments...")
        from app.api.v1.endpoints import appointments

        print("✅ appointments импортирован")

        print("🔔 Проверяю _broadcast...")
        if hasattr(appointments, "_broadcast"):
            print("✅ _broadcast найден в appointments")
        else:
            print("❌ _broadcast не найден в appointments")

        # Проверяем, есть ли импорт в файле
        print("🔔 Проверяю импорты в appointments...")
        if hasattr(appointments, "load_stats"):
            print("✅ load_stats найден в appointments")
        else:
            print("❌ load_stats не найден в appointments")

    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_import_broadcast()
