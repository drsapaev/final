import requests
import json

# Токен из логов фронтенда
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMCIsInVzZXJfaWQiOjIwLCJ1c2VybmFtZSI6InJlZ2lzdHJhckBleGFtcGxlLmNvbSIsImV4cCI6MTc1OTMzMzY1OH0.kSlNwHRz0LzXZ6u4AXfLeY41zuJHXhIFqWtXEd_FLMg"

# Тестовые данные для создания записи
test_data = {
    "patient_id": 1,  # Существующий пациент
    "visits": [
        {
            "doctor_id": None,
            "services": [
                {
                    "service_id": 1,  # Предполагаемая услуга кардиологии
                    "quantity": 1
                }
            ],
            "visit_date": "2025-10-01",
            "visit_time": "15:00",
            "department": "cardiology",
            "notes": None
        }
    ],
    "discount_mode": "none",
    "payment_method": "cash",
    "all_free": False,
    "notes": None
}

print("🧪 ТЕСТИРОВАНИЕ СОЗДАНИЯ ЗАПИСИ (прямой вызов API)")
print("=" * 60)

try:
    print("📤 Отправляем запрос на создание записи...")

    response = requests.post(
        'http://localhost:8000/api/v1/registrar/cart',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        json=test_data,
        timeout=10
    )

    print(f"📊 Статус ответа: {response.status_code}")
    print(f"⏱️ Время ответа: {response.elapsed.total_seconds():.2f} сек")

    if response.status_code == 200:
        data = response.json()
        print("✅ Запись создана успешно!"        print(f"   Visit IDs: {data.get('visit_ids', [])}")
        print(f"   Invoice ID: {data.get('invoice_id')}")
        print(f"   Total amount: {data.get('total_amount')}")
        print(f"   Message: {data.get('message')}")

        # Проверим, появилась ли запись в API
        print("\n🔍 Проверяем API после создания...")
        api_response = requests.get(
            'http://localhost:8000/api/v1/registrar/queues/today',
            headers={'Authorization': f'Bearer {token}'},
            timeout=5
        )

        if api_response.status_code == 200:
            api_data = api_response.json()
            total_entries = sum(len(q.get('entries', [])) for q in api_data.get('queues', []))
            print(f"📋 Всего записей в API: {total_entries}")
            print(f"📋 Очередей: {len(api_data.get('queues', []))}")

            if total_entries > 6:
                print("✅ НОВАЯ ЗАПИСЬ ПОЯВИЛАСЬ В API!")
            else:
                print("❌ Новая запись НЕ появилась в API")

        else:
            print(f"❌ Ошибка проверки API: {api_response.status_code}")

    elif response.status_code == 400:
        error_data = response.json()
        print("❌ Ошибка валидации:"        print(f"   Детали: {error_data.get('detail', 'Неизвестная ошибка')}")

    elif response.status_code == 404:
        print("❌ Ресурс не найден (пациент или услуга)")

    elif response.status_code == 500:
        print("❌ Внутренняя ошибка сервера")
        print("Текст ответа:", response.text)

    else:
        print(f"❌ Неизвестная ошибка: {response.status_code}")
        print("Текст ответа:", response.text)

except requests.exceptions.Timeout:
    print("❌ Таймаут запроса (сервер не отвечает)")

except requests.exceptions.ConnectionError:
    print("❌ Ошибка подключения (сервер недоступен)")

except Exception as e:
    print(f"❌ Критическая ошибка: {e}")

