#!/usr/bin/env python3
"""
Отладка WebSocket и WSManager
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_ws_manager():
    """Тестируем WSManager"""
    print("🔍 Тестирую WSManager...")

    try:
        from app.ws.queue_ws import ws_manager

        print(f"✅ WSManager импортирован: {type(ws_manager)}")
        print(f"✅ Комнаты: {ws_manager.rooms}")
        return ws_manager
    except Exception as e:
        print(f"❌ Ошибка импорта WSManager: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_broadcast():
    """Тестируем broadcast"""
    print("\n🔔 Тестирую broadcast...")

    mgr = test_ws_manager()
    if not mgr:
        print("❌ WSManager недоступен")
        return

    try:
        # Тестируем broadcast
        test_payload = {"type": "test", "message": "Hello from debug script"}
        print(f"📤 Отправляю test payload: {test_payload}")
        mgr.broadcast("test::room", test_payload)
        print("✅ Broadcast отправлен")
    except Exception as e:
        print(f"❌ Ошибка broadcast: {e}")
        import traceback

        traceback.print_exc()


def test_online_queue():
    """Тестируем online_queue"""
    print("\n📊 Тестирую online_queue...")

    try:
        from app.services.online_queue import _ws_manager

        print(f"✅ _ws_manager функция: {_ws_manager}")

        mgr = _ws_manager()
        if mgr:
            print(f"✅ WSManager получен: {type(mgr)}")
        else:
            print("❌ WSManager не получен")

    except Exception as e:
        print(f"❌ Ошибка online_queue: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Отладка WebSocket и WSManager")
    print("=" * 50)

    test_ws_manager()
    test_broadcast()
    test_online_queue()

    print("\n" + "=" * 50)
    print("✅ Отладка завершена")
