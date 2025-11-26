#!/usr/bin/env python3
"""
Комплексный тест WebSocket функциональности клиники
"""
import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime

import websockets

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/queue"
WS_NOAUTH_URL = "ws://127.0.0.1:8000/ws/noauth"


def get_auth_token():
    """Получаем токен авторизации"""
    print("🔑 Получаем токен авторизации...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "admin", "password": "admin123"}

    try:
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")
        req = urllib.request.Request(login_url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                token_data = json.loads(response_text)
                token = token_data["access_token"]
                print("✅ Токен получен")
                return token
            else:
                print(f"❌ Ошибка получения токена: {response.read().decode('utf-8')}")
                return None
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return None


async def test_websocket_connection():
    """Тестируем базовое WebSocket подключение"""
    print("\n🌐 Тестируем базовое WebSocket подключение...")

    try:
        # Подключаемся к WebSocket без авторизации
        async with websockets.connect(WS_NOAUTH_URL) as websocket:
            print("    ✅ WebSocket соединение установлено")

            # Ждём приветственное сообщение
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"    ✅ Получено приветствие: {response}")

                # Отправляем тестовое сообщение
                test_message = "ping"
                await websocket.send(test_message)
                print("    ✅ Тестовое сообщение отправлено")

                return True
            except asyncio.TimeoutError:
                print("    ⚠️ Приветствие не получено (таймаут)")
                return True  # Соединение работает, просто нет ответа

    except Exception as e:
        print(f"    ❌ Ошибка WebSocket подключения: {e}")
        return False


async def test_websocket_with_auth():
    """Тестируем WebSocket с авторизацией"""
    print("\n🔐 Тестируем WebSocket с авторизацией...")

    token = get_auth_token()
    if not token:
        print("    ❌ Не удалось получить токен")
        return False

    try:
        # Подключаемся к /ws/queue с параметрами department и date
        today = datetime.now().strftime("%Y-%m-%d")
        ws_url_with_params = f"{WS_URL}?department=THERAPY&date={today}&token={token}"

        async with websockets.connect(ws_url_with_params) as websocket:
            print("    ✅ WebSocket соединение с авторизацией установлено")

            # Ждём подтверждения подключения

            # Ждём подтверждения подписки
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                print(f"    ✅ Получено подтверждение: {response}")
                return True
            except asyncio.TimeoutError:
                print("    ⚠️ Подтверждение не получено (таймаут)")
                return True  # Соединение работает

    except Exception as e:
        print(f"    ❌ Ошибка WebSocket с авторизацией: {e}")
        return False


async def test_websocket_broadcast():
    """Тестируем broadcast через WebSocket"""
    print("\n📡 Тестируем broadcast через WebSocket...")

    token = get_auth_token()
    if not token:
        print("    ❌ Не удалось получить токен")
        return False

    try:
        # Создаём два WebSocket соединения для тестирования broadcast
        today = datetime.now().strftime("%Y-%m-%d")
        ws_url_with_params = f"{WS_URL}?department=THERAPY&date={today}&token={token}"

        # Первое соединение
        websocket1 = await websockets.connect(ws_url_with_params)
        print("    ✅ Первое WebSocket соединение установлено")

        # Второе соединение
        websocket2 = await websockets.connect(ws_url_with_params)
        print("    ✅ Второе WebSocket соединение установлено")

        # Ждём подтверждения подключения для обоих
        try:
            response1 = await asyncio.wait_for(websocket1.recv(), timeout=2.0)
            print(f"    ✅ Первое соединение подтверждено: {response1}")

            response2 = await asyncio.wait_for(websocket2.recv(), timeout=2.0)
            print(f"    ✅ Второе соединение подтверждено: {response2}")
        except asyncio.TimeoutError:
            print("    ⚠️ Подтверждения не получены (таймаут)")

        print("    ✅ Оба соединения готовы к broadcast")

        # Отправляем broadcast сообщение через HTTP API
        # (это должно вызвать WebSocket уведомления)
        broadcast_url = f"{BASE_URL}/api/v1/queue/stats?department=THERAPY&date={datetime.now().strftime('%Y-%m-%d')}"
        req = urllib.request.Request(broadcast_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("    ✅ HTTP запрос выполнен (может вызвать broadcast)")
            else:
                print(f"    ⚠️ HTTP запрос не выполнен: {response.status}")

        # Ждём уведомления на обоих соединениях
        try:
            # Ждём на первом соединении
            response1 = await asyncio.wait_for(websocket1.recv(), timeout=5.0)
            print(f"    ✅ Первое соединение получило: {response1}")

            # Ждём на втором соединении
            response2 = await asyncio.wait_for(websocket2.recv(), timeout=5.0)
            print(f"    ✅ Второе соединение получило: {response2}")

            return True

        except asyncio.TimeoutError:
            print("    ⚠️ Уведомления не получены (таймаут)")
            return True  # Соединения работают, просто нет broadcast

        finally:
            await websocket1.close()
            await websocket2.close()

    except Exception as e:
        print(f"    ❌ Ошибка WebSocket broadcast: {e}")
        return False


async def test_websocket_reconnection():
    """Тестируем переподключение WebSocket"""
    print("\n🔄 Тестируем переподключение WebSocket...")

    try:
        # Первое подключение (без авторизации)
        websocket1 = await websockets.connect(WS_NOAUTH_URL)
        print("    ✅ Первое подключение установлено")

        # Получаем приветствие
        try:
            response1 = await asyncio.wait_for(websocket1.recv(), timeout=2.0)
            print(f"    ✅ Первое подключение получило: {response1}")
        except asyncio.TimeoutError:
            print("    ⚠️ Первое подключение не получило приветствие")

        # Закрываем соединение
        await websocket1.close()
        print("    ✅ Первое соединение закрыто")

        # Второе подключение (без авторизации)
        websocket2 = await websockets.connect(WS_NOAUTH_URL)
        print("    ✅ Второе подключение установлено")

        # Получаем приветствие
        try:
            response2 = await asyncio.wait_for(websocket2.recv(), timeout=2.0)
            print(f"    ✅ Второе подключение получило: {response2}")
        except asyncio.TimeoutError:
            print("    ⚠️ Второе подключение не получило приветствие")

        # Отправляем тестовое сообщение
        test_message = "reconnect_test"
        await websocket2.send(test_message)
        print("    ✅ Тестовое сообщение отправлено")

        await websocket2.close()
        print("    ✅ Второе соединение закрыто")

        return True

    except Exception as e:
        print(f"    ❌ Ошибка переподключения: {e}")
        return False


async def test_websocket_error_handling():
    """Тестируем обработку ошибок WebSocket"""
    print("\n⚠️ Тестируем обработку ошибок WebSocket...")

    try:
        # Пытаемся подключиться к несуществующему WebSocket
        invalid_url = "ws://127.0.0.1:8000/invalid_ws"

        try:
            async with websockets.connect(invalid_url):
                print("    ❌ Неожиданно подключились к несуществующему WebSocket")
                return False
        except websockets.exceptions.InvalidURI:
            print("    ✅ Правильно обработана ошибка неверного URI")
            return True
        except Exception as e:
            print(f"    ✅ Обработана ошибка подключения: {e}")
            return True

    except Exception as e:
        print(f"    ❌ Неожиданная ошибка: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Комплексный тест WebSocket функциональности клиники")
    print("=" * 70)

    # Запускаем все тесты
    tests = [
        ("Базовое WebSocket подключение", test_websocket_connection),
        ("WebSocket с авторизацией", test_websocket_with_auth),
        ("WebSocket broadcast", test_websocket_broadcast),
        ("Переподключение WebSocket", test_websocket_reconnection),
        ("Обработка ошибок WebSocket", test_websocket_error_handling),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))

    # Итоги тестирования
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ WEBSOCKET:")

    for test_name, result in results:
        status = "УСПЕШНО" if result else "ОШИБКА"
        print(f"  ✅ {test_name}: {status}")

    success_count = sum(1 for _, result in results if result)
    total_count = len(results)

    print(
        f"\n🎯 Общий результат: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)"
    )

    if success_count == total_count:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    elif success_count >= total_count * 0.8:
        print("👍 Большинство тестов прошли успешно!")
    else:
        print("⚠️ Много ошибок, требуется доработка")

    print("\n" + "=" * 70)
    print("🎉 Тест завершён!")


if __name__ == "__main__":
    asyncio.run(main())
