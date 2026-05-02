#!/usr/bin/env python3
"""
Тест WebSocket табло с аутентификацией и проверкой broadcast
"""
import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime

import websockets


async def get_auth_token():
    """Получаем JWT токен для аутентификации"""
    try:
        data = urllib.parse.urlencode(
            {"username": "admin", "password": "admin"}
        ).encode()
        req = urllib.request.Request(
"http://127.0.0.1:18000/api/v1/login",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("access_token")
            else:
                print(f"❌ Ошибка получения токена: {response.status}")
                return None
    except Exception as e:
        print(f"❌ Ошибка запроса токена: {e}")
        return None


async def test_ws_queue_auth(token):
    """Тест WebSocket очереди с аутентификацией"""
    print("\n🔌 Тестирую /ws/queue с аутентификацией...")
    try:
        uri = (
"ws://127.0.0.1:18000/ws/queue?department=ENT&date=2025-08-28&token=" + token
        )
        headers = {"Origin": "http://localhost:5173"}
        async with websockets.connect(uri, additional_headers=headers) as ws:
            # Получаем приветственное сообщение
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"✅ Подключение успешно: {data}")

            if data.get("type") == "queue.connected":
                print("🎯 Подключён к комнате очереди!")

                # Ждём обновления
                print("⏳ Ожидаю обновления очереди...")
                await asyncio.sleep(5)

                # Проверяем, есть ли сообщения (без settimeout)
                try:
                    # Используем asyncio.wait_for для таймаута
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)
                    print(f"📨 Получено обновление: {data}")
                except asyncio.TimeoutError:
                    print("⏰ Таймаут - нет обновлений")
                except Exception as e:
                    print(f"📨 Ошибка получения сообщения: {e}")
            else:
                print(f"⚠️ Неожиданный тип сообщения: {data}")

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")


async def test_broadcast_trigger():
    """Тестируем триггер broadcast через API"""
    print("\n🔔 Тестирую триггер broadcast...")
    try:
        # Получаем токен
        token = await get_auth_token()
        if not token:
            print("❌ Не удалось получить токен")
            return

        headers = {"Authorization": f"Bearer {token}"}

        # Открываем день (должно вызвать broadcast)
        print("📅 Открываю день для ENT...")
        req = urllib.request.Request(
"http://127.0.0.1:18000/api/v1/appointments/open?department=ENT&date=2025-08-28&start_number=1",
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as response:
                print(f"📅 Результат открытия: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"📅 Ошибка открытия: {e.code}")
            # Читаем детали ошибки
            try:
                error_details = e.read().decode()
                print(f"📅 Детали ошибки: {error_details}")
            except Exception:
                pass

        # Выдаём следующий талон (должно вызвать broadcast)
        print("🎫 Выдаю следующий талон...")
        req = urllib.request.Request(
"http://127.0.0.1:18000/api/v1/next-ticket?department=ENT&date=2025-08-28",
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as response:
                print(f"🎫 Результат выдачи: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"🎫 Ошибка выдачи: {e.code}")

    except Exception as e:
        print(f"❌ Ошибка тестирования broadcast: {e}")


async def main():
    """Основная функция тестирования"""
    print(f"🚀 WebSocket тест табло с аутентификацией - {datetime.now()}")
    print("=" * 60)

    # Получаем токен
    token = await get_auth_token()
    if not token:
        print("❌ Не удалось получить токен аутентификации")
        return

    print(f"🔑 Токен получен: {token[:20]}...")

    # Тестируем WebSocket с аутентификацией
    await test_ws_queue_auth(token)

    # Тестируем триггер broadcast
    await test_broadcast_trigger()

    print("\n" + "=" * 60)
    print("✅ WebSocket тестирование с аутентификацией завершено")


if __name__ == "__main__":
    asyncio.run(main())
