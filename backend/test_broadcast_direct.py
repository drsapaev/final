#!/usr/bin/env python3
"""
Прямой тест broadcast без WebSocket
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_broadcast_direct():
    """Тестируем broadcast напрямую"""
    print("🔔 Тестирую broadcast напрямую...")

    try:
        from app.services.online_queue import _broadcast

        print("✅ Импорты успешны")

        # Создаём тестовые данные
        from app.services.online_queue import DayStats

        test_stats = DayStats(
            department="ENT",
            date_str="2025-08-28",
            is_open=True,
            start_number=1,
            last_ticket=10,
            waiting=10,
            serving=0,
            done=0,
        )

        print(f"✅ Тестовые данные созданы: {test_stats}")

        # Вызываем broadcast напрямую
        print("🔔 Вызываю _broadcast...")
        _broadcast("ENT", "2025-08-28", test_stats)
        print("✅ _broadcast вызван")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_broadcast_direct()
