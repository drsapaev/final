#!/usr/bin/env python3
"""
Тест новых специализированных API эндпоинтов
"""
import httpx
import time
import json

def test_specialized_apis():
    """Тестируем новые специализированные API"""
    print("🧪 Тестируем специализированные API...")

    # 1. Ждем, пока сервер запустится
    print("⏳ Ждем запуска сервера...")
    for i in range(30):
        try:
            response = httpx.get("http://localhost:8000/_routes", timeout=1)
            if response.status_code == 200:
                print("✅ Сервер запущен!")
                break
        except Exception:
            time.sleep(1)
    else:
        print("❌ Сервер не запустился за 30 секунд")
        return

    try:
        with httpx.Client(timeout=10) as client:
            # 2. Логинимся как админ
            print("\n2. Логинимся как админ...")
            login_data = {
                "username": "admin",
                "password": "admin123",
                "grant_type": "password"
            }
            login_response = client.post(
                "http://localhost:8000/api/v1/auth/login",
                data=login_data
            )

            if login_response.status_code != 200:
                print(f"❌ Ошибка логина: {login_response.status_code}")
                print(f"   Ответ: {login_response.text}")
                return

            token_data = login_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                print("❌ В ответе нет access_token")
                return

            print(f"✅ Логин успешен, токен: {access_token[:20]}...")
            headers = {"Authorization": f"Bearer {access_token}"}

            # 3. Тестируем новые эндпоинты
            print("\n3. Тестируем новые специализированные эндпоинты...")

            # Кардиология
            print("\n🫀 Кардиологические эндпоинты:")
            endpoints = [
                ("GET", "/api/v1/cardio/ecg"),
                ("GET", "/api/v1/cardio/blood-tests"),
                ("GET", "/api/v1/cardio/risk-assessment"),
            ]

            for method, endpoint in endpoints:
                try:
                    response = client.request(method, f"http://localhost:8000{endpoint}", headers=headers)
                    print(f"   {method} {endpoint}: {response.status_code} {'✅' if response.status_code == 200 else '⚠️'}")
                except Exception as e:
                    print(f"   {method} {endpoint}: Ошибка - {e}")

            # Дерматология
            print("\n🧴 Дерматологические эндпоинты:")
            endpoints = [
                ("GET", "/api/v1/derma/examinations"),
                ("GET", "/api/v1/derma/procedures"),
                ("GET", "/api/v1/derma/photo-gallery"),
            ]

            for method, endpoint in endpoints:
                try:
                    response = client.request(method, f"http://localhost:8000{endpoint}", headers=headers)
                    print(f"   {method} {endpoint}: {response.status_code} {'✅' if response.status_code == 200 else '⚠️'}")
                except Exception as e:
                    print(f"   {method} {endpoint}: Ошибка - {e}")

            # Стоматология
            print("\n🦷 Стоматологические эндпоинты:")
            endpoints = [
                ("GET", "/api/v1/dental/examinations"),
                ("GET", "/api/v1/dental/treatments"),
                ("GET", "/api/v1/dental/prosthetics"),
                ("GET", "/api/v1/dental/xray"),
            ]

            for method, endpoint in endpoints:
                try:
                    response = client.request(method, f"http://localhost:8000{endpoint}", headers=headers)
                    print(f"   {method} {endpoint}: {response.status_code} {'✅' if response.status_code == 200 else '⚠️'}")
                except Exception as e:
                    print(f"   {method} {endpoint}: Ошибка - {e}")

            # Лаборатория
            print("\n🧪 Лабораторные эндпоинты:")
            endpoints = [
                ("GET", "/api/v1/lab/tests"),
                ("GET", "/api/v1/lab/results"),
                ("GET", "/api/v1/lab/reference-ranges"),
                ("GET", "/api/v1/lab/equipment"),
                ("GET", "/api/v1/lab/reports"),
            ]

            for method, endpoint in endpoints:
                try:
                    response = client.request(method, f"http://localhost:8000{endpoint}", headers=headers)
                    print(f"   {method} {endpoint}: {response.status_code} {'✅' if response.status_code == 200 else '⚠️'}")
                except Exception as e:
                    print(f"   {method} {endpoint}: Ошибка - {e}")

            # 4. Тестируем CORS
            print("\n4. Тестируем CORS...")
            try:
                # Проверяем, что OPTIONS запросы работают
                cors_response = client.options(
                    "http://localhost:8000/api/v1/patients",
                    headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"}
                )
                if cors_response.status_code in [200, 204]:
                    print("   ✅ CORS OPTIONS работает")
                else:
                    print(f"   ⚠️ CORS OPTIONS: {cors_response.status_code}")
            except Exception as e:
                print(f"   ❌ CORS тест провалился: {e}")

            print("\n✅ Тестирование специализированных API завершено!")

    except Exception as e:
        print(f"❌ Общая ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Тестирование специализированных API...")
    print("=" * 60)
    test_specialized_apis()
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
