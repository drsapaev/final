#!/usr/bin/env python3
"""
Тест прокси - проверяем, что фронтенд может обращаться к бэкенду через прокси
"""

import httpx


def test_proxy():
    """Тестируем прокси"""
    print("🧪 Тестируем прокси...")

    try:
        with httpx.Client() as client:
            # Тестируем логин через прокси (имитируем фронтенд)
            data = {
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            }

            print("Отправляем запрос через прокси...")

            # Имитируем запрос от фронтенда (localhost:5173) к бэкенду через прокси
            response = client.post(
                "http://localhost:5173/api/v1/auth/login", data=data, timeout=5
            )

            print(f"Статус ответа: {response.status_code}")
            print(f"Заголовки: {dict(response.headers)}")

            if response.status_code == 200:
                try:
                    token_data = response.json()
                    print(f"JSON ответ: {token_data}")

                    if "access_token" in token_data:
                        print("✅ Прокси работает!")
                        print(f"   Токен: {token_data['access_token'][:20]}...")
                    else:
                        print("❌ В ответе нет access_token")
                        print(f"   Доступные поля: {list(token_data.keys())}")
                except Exception as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
                    print(f"   Текст ответа: {response.text}")
            else:
                print(f"❌ Ошибка прокси: {response.status_code}")
                print(f"   Ответ: {response.text}")

    except httpx.ConnectError:
        print("❌ Фронтенд недоступен на localhost:5173")
        print("   Убедитесь, что запущен: npm run dev")
    except Exception as e:
        print(f"❌ Ошибка при тестировании прокси: {e}")


if __name__ == "__main__":
    print("🚀 Тестирование прокси...")
    print("=" * 50)

    test_proxy()

    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
