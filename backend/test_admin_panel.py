#!/usr/bin/env python3
"""
Тест админ-панели - создание и управление провайдерами
"""


import httpx


def test_admin_panel():
    """Тестируем админ-панель"""
    print("🧪 Тестируем админ-панель...")

    try:
        with httpx.Client() as client:
            # 1. Логинимся как админ
            print("1. Логинимся как админ...")
            login_data = {
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            }

            login_response = client.post(
                "http://localhost:18000/api/v1/auth/login", data=login_data, timeout=10
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

            # 2. Получаем список провайдеров
            print("\n2. Получаем список провайдеров...")
            headers = {"Authorization": f"Bearer {access_token}"}

            providers_response = client.get(
                "http://localhost:18000/api/v1/admin/providers",
                headers=headers,
                timeout=10,
            )

            print(f"Статус: {providers_response.status_code}")
            if providers_response.status_code == 200:
                providers = providers_response.json()
                print(f"✅ Найдено провайдеров: {len(providers)}")
                for provider in providers:
                    print(f"   - {provider.get('name')} ({provider.get('code')})")
            else:
                print(f"❌ Ошибка получения провайдеров: {providers_response.text}")

            # 3. Создаем тестового провайдера
            print("\n3. Создаем тестового провайдера...")
            test_provider = {
                "name": "Test Payme Provider",
                "code": "payme_test",
                "is_active": True,
                "webhook_url": "https://test.example.com/webhook",
                "api_key": "test_api_key_123",
                "secret_key": "test_secret_key_456",
                "commission_percent": 2,
                "min_amount": 1000,
                "max_amount": 1000000,
            }

            create_response = client.post(
                "http://localhost:18000/api/v1/admin/providers",
                headers={**headers, "Content-Type": "application/json"},
                json=test_provider,
                timeout=10,
            )

            if create_response.status_code == 200:
                created_provider = create_response.json()
                provider_id = created_provider.get("id")
                print(f"✅ Провайдер создан с ID: {provider_id}")
                print(f"   Название: {created_provider.get('name')}")
                print(f"   Код: {created_provider.get('code')}")
            else:
                print(f"❌ Ошибка создания провайдера: {create_response.status_code}")
                print(f"   Ответ: {create_response.text}")
                return

            # 4. Получаем обновленный список провайдеров
            print("\n4. Получаем обновленный список провайдеров...")
            providers_response = client.get(
                "http://localhost:18000/api/v1/admin/providers",
                headers=headers,
                timeout=10,
            )

            if providers_response.status_code == 200:
                providers = providers_response.json()
                print(f"✅ Теперь провайдеров: {len(providers)}")
                for provider in providers:
                    print(
                        f"   - {provider.get('name')} ({provider.get('code')}) - ID: {provider.get('id')}"
                    )
            else:
                print(
                    f"❌ Ошибка получения обновленного списка: {providers_response.text}"
                )

            # 5. Тестируем провайдера
            print(f"\n5. Тестируем провайдера {provider_id}...")
            test_response = client.get(
                f"http://localhost:18000/api/v1/admin/providers/{provider_id}/test",
                headers=headers,
                timeout=10,
            )

            if test_response.status_code == 200:
                test_result = test_response.json()
                print(f"✅ Тест провайдера: {test_result.get('message', 'Успешно')}")
            else:
                print(f"⚠️  Тест провайдера: {test_response.status_code}")
                print(f"   Ответ: {test_response.text}")

            # 6. Удаляем тестового провайдера
            print(f"\n6. Удаляем тестового провайдера {provider_id}...")
            delete_response = client.delete(
                f"http://localhost:18000/api/v1/admin/providers/{provider_id}",
                headers=headers,
                timeout=10,
            )

            if delete_response.status_code == 200:
                print("✅ Тестовый провайдер удален")
            else:
                print(f"⚠️  Ошибка удаления: {delete_response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")


if __name__ == "__main__":
    print("🚀 Тестирование админ-панели...")
    print("=" * 50)

    test_admin_panel()

    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")
