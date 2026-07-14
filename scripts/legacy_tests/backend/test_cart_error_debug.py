"""
Тест создания корзины с полным traceback
"""
import requests
import json
import os

BASE_URL = "http://localhost:18000"


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Set {name} to run backend cart debug helper scripts.")
    return value

# Получаем токен
login_data = {
    "username": os.getenv("QA_REGISTRAR_USERNAME", "registrar@example.com"),
    "password": required_env("QA_REGISTRAR_PASSWORD")
}

print("🔐 Авторизация...")
try:
    # FastAPI OAuth2 expects form data, not JSON
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data=login_data  # Changed from json= to data=
    )
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✅ Токен получен; значение не печатается")
    else:
        print(f"❌ Ошибка авторизации: {response.status_code}")
        print(response.text)
        exit(1)
except Exception as e:
    print(f"❌ Ошибка: {e}")
    exit(1)

# Создаем тестовые данные корзины
cart_data = {
    "patient_id": 1,  # Используем существующего пациента
    "visits": [
        {
            "visit_date": "2025-11-28",
            "visit_time": "10:00",
            "department": "general",  # Строка - возможно тут проблема
            "doctor_id": None,
            "notes": "Test visit",
            "services": [
                {
                    "service_id": 3,
                    "quantity": 1,
                    "custom_price": None
                }
            ]
        }
    ],
    "discount_mode": "none",
    "payment_method": "cash",
    "notes": "Test cart"
}

print("\n📦 Создание корзины...")
print(f"Данные: {json.dumps(cart_data, indent=2, ensure_ascii=False)}")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/v1/registrar/cart",
        json=cart_data,
        headers=headers
    )

    print(f"\n📊 Статус ответа: {response.status_code}")

    if response.status_code == 200:
        print("✅ Корзина создана успешно!")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print("\n📋 Детали ошибки:")
        try:
            error_detail = response.json()
            print(json.dumps(error_detail, indent=2, ensure_ascii=False))
        except:
            print(response.text)

except Exception as e:
    print(f"❌ Исключение: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("ВАЖНО: Проверьте терминал где запущен backend!")
print("Там должен быть полный traceback с точным местом ошибки")
print("="*60)
