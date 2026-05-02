#!/usr/bin/env python3
"""
Простой тест логина
"""

import httpx


def test_login():
    """Тестируем логин"""
    print("🧪 Тестируем логин...")

    try:
        with httpx.Client() as client:
            # Тестируем логин
            data = {
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            }

            print(f"Отправляем данные: {data}")

            response = client.post(
                "http://localhost:18000/api/v1/auth/login", data=data, timeout=5
            )

            print(f"Статус ответа: {response.status_code}")
            print(f"Заголовки: {dict(response.headers)}")

            if response.status_code == 200:
                try:
                    token_data = response.json()
                    print(f"JSON ответ: {token_data}")

                    if "access_token" in token_data:
                        print("✅ Логин успешен")
                        print(f"   Токен: {token_data['access_token'][:20]}...")
                        print(f"   Тип токена: {token_data.get('token_type', 'N/A')}")

                        # Тестируем получение профиля
                        headers = {
                            "Authorization": f"Bearer {token_data['access_token']}"
                        }
                        profile_response = client.get(
                            "http://localhost:18000/api/v1/auth/me",
                            headers=headers,
                            timeout=5,
                        )

                        print(f"Профиль статус: {profile_response.status_code}")
                        if profile_response.status_code == 200:
                            print("✅ Профиль получен успешно")
                        else:
                            print(
                                f"⚠️  Ошибка получения профиля: {profile_response.status_code}"
                            )
                            print(f"   Ответ: {profile_response.text}")
                    else:
                        print("❌ В ответе нет access_token")
                        print(f"   Доступные поля: {list(token_data.keys())}")
                except Exception as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
                    print(f"   Текст ответа: {response.text}")
            else:
                print(f"❌ Ошибка логина: {response.status_code}")
                print(f"   Ответ: {response.text}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании логина: {e}")


if __name__ == "__main__":
    print("🚀 Тестирование логина...")
    print("=" * 50)

    test_login()

    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
