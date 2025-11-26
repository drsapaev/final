#!/usr/bin/env python3
"""
Тест комнат WebSocket
"""
import os
import sys

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))


def test_ws_rooms():
    """Тестируем комнаты WebSocket"""
    print("🔍 Тестирую комнаты WebSocket...")

    try:
        from app.ws.queue_ws import ws_manager

        print(f"✅ WSManager импортирован: {type(ws_manager)}")
        print(f"✅ Комнаты: {ws_manager.rooms}")
        print(f"✅ Ключи комнат: {list(ws_manager.rooms.keys())}")

        for room, connections in ws_manager.rooms.items():
            print(f"🔍 Комната '{room}': {len(connections)} подключений")

        return ws_manager
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_room_format():
    """Тестируем формат комнат"""
    print("\n🔍 Тестирую формат комнат...")

    test_cases = [
        ("ENT", "2025-08-28"),
        ("ENT", "2025-8-28"),
        ("ENT", "2025-08-28"),
        ("ENT", "2025-8-28"),
    ]

    for dept, date in test_cases:
        room = f"{dept.strip()}::{date.strip()}"
        print(f"🔍 Тест: dept='{dept}', date='{date}' -> room='{room}'")


if __name__ == "__main__":
    test_ws_rooms()
    test_room_format()
