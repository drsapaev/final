#!/usr/bin/env python3
"""
Простой тест WebSocket подключения к табло очереди
"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_ws_noauth():
    """Тест WebSocket без аутентификации"""
    print("🔌 Тестирую /ws/noauth...")
    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/noauth") as ws:
            # Получаем приветственное сообщение
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"✅ Подключение успешно: {data}")
            
            # Отправляем тестовое сообщение
            await ws.send("ping")
            print("📤 Отправлено: ping")
            
            # Ждём немного
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

async def test_ws_queue():
    """Тест основного WebSocket очереди"""
    print("\n🔌 Тестирую /ws/queue...")
    try:
        # Подключаемся с параметрами и заголовками
        uri = "ws://127.0.0.1:8000/ws/queue?department=ENT&date=2025-08-28"
        headers = {"Origin": "http://localhost:5173"}
        async with websockets.connect(uri, additional_headers=headers) as ws:
            # Получаем приветственное сообщение
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"✅ Подключение успешно: {data}")
            
            # Ждём обновления
            print("⏳ Ожидаю обновления очереди...")
            await asyncio.sleep(3)
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

async def test_ws_dev_queue():
    """Тест dev WebSocket очереди"""
    print("\n🔌 Тестирую /ws/dev-queue...")
    try:
        uri = "ws://127.0.0.1:8000/ws/dev-queue?department=ENT&date=2025-08-28"
        headers = {"Origin": "http://localhost:5173"}
        async with websockets.connect(uri, additional_headers=headers) as ws:
            # Получаем приветственное сообщение
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"✅ Подключение успешно: {data}")
            
            # Ждём обновления
            print("⏳ Ожидаю обновления очереди...")
            await asyncio.sleep(3)
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

async def main():
    """Основная функция тестирования"""
    print(f"🚀 WebSocket тест табло очереди - {datetime.now()}")
    print("=" * 50)
    
    # Тестируем все WebSocket эндпоинты
    await test_ws_noauth()
    await test_ws_queue()
    await test_ws_dev_queue()
    
    print("\n" + "=" * 50)
    print("✅ WebSocket тестирование завершено")

if __name__ == "__main__":
    asyncio.run(main())
