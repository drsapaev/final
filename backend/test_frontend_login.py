#!/usr/bin/env python3
"""
Тест фронтенда - проверка логина
"""

import time

import httpx


def test_frontend():
    """Тестируем фронтенд"""
    print("🧪 Тестируем фронтенд...")

    # Проверяем, что фронтенд доступен
    try:
        with httpx.Client() as client:
            # Проверяем главную страницу фронтенда
            response = client.get("http://localhost:5173/", timeout=5)
            print(f"✅ Фронтенд доступен: {response.status_code}")

            # Проверяем, что можем получить HTML
            if "html" in response.headers.get("content-type", ""):
                print("✅ Фронтенд возвращает HTML")
            else:
                print("⚠️  Фронтенд не возвращает HTML")

    except httpx.ConnectError:
        print("❌ Фронтенд недоступен на localhost:5173")
        print("   Убедитесь, что запущен: npm run dev")
    except Exception as e:
        print(f"❌ Ошибка при тестировании фронтенда: {e}")


def test_backend():
    """Тестируем бэкенд"""
    print("\n🧪 Тестируем бэкенд...")

    try:
        with httpx.Client() as client:
            # Проверяем корневой эндпоинт
            response = client.get("http://localhost:8000/", timeout=5)
            print(f"✅ Бэкенд доступен: {response.status_code}")

            # Проверяем API
            response = client.get("http://localhost:8000/api/v1/", timeout=5)
            print(f"✅ API доступен: {response.status_code}")

    except httpx.ConnectError:
        print("❌ Бэкенд недоступен на localhost:8000")
        print(
            "   Убедитесь, что запущен: uvicorn main:app --reload --host 0.0.0.0 --port 8000"
        )
    except Exception as e:
        print(f"❌ Ошибка при тестировании бэкенда: {e}")


def test_login():
    """Тестируем логин"""
    print("\n🧪 Тестируем логин...")

    try:
        with httpx.Client() as client:
            # Тестируем логин
            data = {
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            }

            response = client.post(
                "http://localhost:8000/api/v1/auth/login", data=data, timeout=5
            )

            if response.status_code == 200:
                token_data = response.json()
                if "access_token" in token_data:
                    print("✅ Логин успешен")
                    print(f"   Токен: {token_data['access_token'][:20]}...")

                    # Тестируем получение профиля
                    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
                    profile_response = client.get(
                        "http://localhost:8000/api/v1/auth/me",
                        headers=headers,
                        timeout=5,
                    )

                    if profile_response.status_code == 200:
                        print("✅ Профиль получен успешно")
                    else:
                        print(
                            f"⚠️  Ошибка получения профиля: {profile_response.status_code}"
                        )

                    # Тестируем доступ к админ-панели
                    admin_response = client.get(
                        "http://localhost:8000/api/v1/admin/providers",
                        headers=headers,
                        timeout=5,
                    )

                    if admin_response.status_code == 200:
                        print("✅ Доступ к админ-панели успешен")
                    else:
                        print(
                            f"⚠️  Ошибка доступа к админ-панели: {admin_response.status_code}"
                        )
                        print(f"   Ответ: {admin_response.text}")
                else:
                    print("❌ В ответе нет access_token")
            else:
                print(f"❌ Ошибка логина: {response.status_code}")
                print(f"   Ответ: {response.text}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании логина: {e}")


if __name__ == "__main__":
    print("🚀 Тестирование системы...")
    print("=" * 50)

    test_backend()
    test_frontend()
    test_login()

    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
