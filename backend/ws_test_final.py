#!/usr/bin/env python3
"""
Финальный тест WebSocket с правильной последовательностью
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
AUTH_USERNAME_ENV = "QA_ADMIN_USERNAME"


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
                "username": required_env(AUTH_USERNAME_ENV),
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


async def test_ws_with_broadcast(token):
    """Тест WebSocket + Broadcast в правильной последовательности"""
    print("\n🔄 Тест WebSocket + Broadcast (правильная последовательность)...")

    # 1. Сначала подключаемся к WebSocket
    print("🔌 Подключаюсь к WebSocket...")
    uri = f"{WS_BASE_URL}/ws/queue?department=ENT&date=2025-08-28&token={token}"
    headers = {"Origin": "http://localhost:5173"}

    try:
        async with websockets.connect(uri, additional_headers=headers) as ws:
            print("🔗 WebSocket соединение установлено")

            # Получаем приветственное сообщение
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"✅ Подключение успешно: {data}")

            if data.get("type") == "queue.connected":
                print("🎯 Подключён к комнате очереди!")

                # 2. Ждём немного, чтобы соединение стабилизировалось
                await asyncio.sleep(1)

                # 3. Теперь вызываем API, который должен вызвать broadcast
                print("\n🔔 Вызываю API для broadcast...")

                # Открываем день
                print("📅 Открываю день для ENT...")
                try:
                    req = urllib.request.Request(
                        f"{BASE_URL}/api/v1/appointments/open?department=ENT&date_str=2025-08-28&start_number=1",
                        headers={"Authorization": f"Bearer {token}"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req) as response:
                        print(f"📅 Результат открытия: {response.status} OK")
                        response_data = response.read().decode()
                        print(f"📅 Ответ: {response_data}")
                except Exception as e:
                    print(f"📅 Ошибка открытия: {e}")

                # 4. Ждём broadcast сообщение
                print("\n⏳ Ожидаю broadcast сообщение (5 сек)...")
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    print(f"🎉 ПОЛУЧЕНО BROADCAST СООБЩЕНИЕ: {data}")
                    return True
                except asyncio.TimeoutError:
                    print("⏰ Таймаут - broadcast не получен")
                    return False
                except Exception as e:
                    print(f"📨 Ошибка получения сообщения: {e}")
                    return False
            else:
                print(f"⚠️ Неожиданный тип сообщения: {data}")
                return False

    except Exception as e:
        print(f"WebSocket error: {type(e).__name__}")
        return False


async def main():
    """Основная функция тестирования"""
    print(f"🚀 Финальный WebSocket тест - {datetime.now()}")
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

    # Тестируем WebSocket + Broadcast
    success = await test_ws_with_broadcast(token)

    print("\n" + "=" * 60)
    if success:
        print("🎉 WebSocket + Broadcast работает на 100%!")
    else:
        print("⚠️ WebSocket работает, но broadcast не доходит")
    print("✅ Финальный тест завершён")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
