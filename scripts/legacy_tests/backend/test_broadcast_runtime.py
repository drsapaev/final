#!/usr/bin/env python3
"""
Тест импорта _broadcast в runtime
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_broadcast_runtime():
    """Тестируем импорт _broadcast в runtime"""
    print("🔔 Тестирую импорт _broadcast в runtime...")

    try:
        print("🔔 Импортирую online_queue...")
        from app.services import online_queue

        print("✅ online_queue импортирован")

        print("🔔 Проверяю _broadcast...")
        if hasattr(online_queue, "_broadcast"):
            print("✅ _broadcast найден в online_queue")
            print(f"🔔 _broadcast: {online_queue._broadcast}")

            # Тестируем вызов _broadcast
            print("🔔 Тестирую вызов _broadcast...")
            try:
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
                online_queue._broadcast("ENT", "2025-08-28", test_stats)
                print("✅ _broadcast вызван успешно")

            except Exception as e:
                print(f"❌ Ошибка вызова _broadcast: {e}")
                import traceback

                traceback.print_exc()

        else:
            print("❌ _broadcast не найден в online_queue")
            print(f"🔔 Доступные атрибуты: {dir(online_queue)}")

    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_broadcast_runtime()
