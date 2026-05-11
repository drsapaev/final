#!/usr/bin/env python3
"""
Улучшенный тест WebSocket табло с детальной диагностикой
"""
import asyncio
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

import websockets

BASE_URL = os.getenv("QA_BACKEND_BASE_URL", "http://127.0.0.1:18000")
WS_BASE_URL = os.getenv("QA_BACKEND_WS_URL", "ws://127.0.0.1:18000")
AUTH_USERNAME = os.getenv("QA_ADMIN_USERNAME", "admin")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Set {name} to run backend websocket smoke scripts.")
    return value


async def get_auth_token():
    """Получаем JWT токен для аутентификации"""
    try:
        data = urllib.parse.urlencode(
            {
                "username": AUTH_USERNAME,
                "password": required_env("QA_ADMIN_PASSWORD"),
            }
        ).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/login",
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
    except RuntimeError:
        raise
    except Exception as e:
        print(f"❌ Ошибка запроса токена: {e}")
        return None


async def test_ws_queue_auth(token):
    """Тест WebSocket очереди с аутентификацией"""
    print("\n🔌 Тестирую /ws/queue с аутентификацией...")
    try:
        uri = f"{WS_BASE_URL}/ws/queue?department=ENT&date=2025-08-28&token={token}"
        headers = {"Origin": "http://localhost:5173"}

        print("📡 Подключаюсь к /ws/queue; token is not printed")
        async with websockets.connect(uri, additional_headers=headers) as ws:
            print("🔗 WebSocket соединение установлено")

            # Получаем приветственное сообщение
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"✅ Подключение успешно: {data}")

            if data.get("type") == "queue.connected":
                print("🎯 Подключён к комнате очереди!")

                # Ждём обновления с таймаутом
                print("⏳ Ожидаю обновления очереди (5 сек)...")
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    print(f"📨 Получено обновление: {data}")
                except asyncio.TimeoutError:
                    print("⏰ Таймаут - нет обновлений за 5 секунд")
                except Exception as e:
                    print(f"📨 Ошибка получения сообщения: {e}")
            else:
                print(f"⚠️ Неожиданный тип сообщения: {data}")

    except Exception as e:
        print(f"Connection error: {type(e).__name__}")


async def test_broadcast_trigger(token):
    """Тестируем триггер broadcast через API"""
    print("\n🔔 Тестирую триггер broadcast...")

    headers = {"Authorization": f"Bearer {token}"}

    # Открываем день (должно вызвать broadcast)
    print("📅 Открываю день для ENT...")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/appointments/open?department=ENT&date_str=2025-08-28&start_number=1",
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            print(f"📅 Результат открытия: {response.status} OK")
            response_data = response.read().decode()
            print(f"📅 Ответ: {response_data}")
    except urllib.error.HTTPError as e:
        print(f"📅 Ошибка открытия: {e.code}")
        try:
            error_details = e.read().decode()
            print(f"📅 Детали ошибки: {error_details}")
        except Exception:
            pass
    except Exception as e:
        print(f"📅 Ошибка запроса: {e}")

    # Выдаём следующий талон (должно вызвать broadcast)
    print("\n🎫 Выдаю следующий талон...")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/next-ticket?department=ENT&date=2025-08-28",
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            print(f"🎫 Результат выдачи: {response.status} OK")
            response_data = response.read().decode()
            print(f"🎫 Ответ: {response_data}")
    except urllib.error.HTTPError as e:
        print(f"🎫 Ошибка выдачи: {e.code}")
    except Exception as e:
        print(f"🎫 Ошибка запроса: {e}")


async def test_ws_with_broadcast(token):
    """Тест WebSocket с одновременным триггером broadcast"""
    print("\n🔄 Тест WebSocket + Broadcast одновременно...")

    # Запускаем WebSocket в фоне
    ws_task = asyncio.create_task(test_ws_queue_auth(token))

    # Ждём подключения
    await asyncio.sleep(2)

    # Триггерим broadcast
    await test_broadcast_trigger(token)

    # Ждём WebSocket завершения
    try:
        await asyncio.wait_for(ws_task, timeout=10.0)
    except asyncio.TimeoutError:
        print("⏰ WebSocket тест превысил таймаут")
        ws_task.cancel()


async def main():
    """Основная функция тестирования"""
    print(f"🚀 Улучшенный WebSocket тест табло - {datetime.now()}")
    print("=" * 60)

    # Получаем токен
    try:
        token = await get_auth_token()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    if not token:
        print("❌ Не удалось получить токен аутентификации")
        return 1

    print("Token received; value is not printed")

    # Тест 1: Простое WebSocket подключение
    await test_ws_queue_auth(token)

    # Тест 2: API триггеры
    await test_broadcast_trigger(token)

    # Тест 3: WebSocket + Broadcast одновременно
    await test_ws_with_broadcast(token)

    print("\n" + "=" * 60)
    print("✅ Улучшенный WebSocket тест завершён")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
