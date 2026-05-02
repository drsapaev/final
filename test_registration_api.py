import requests
import json

# Токен из логов
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMCIsInVzZXJfaWQiOjIwLCJ1c2VybmFtZSI6InJlZ2lzdHJhckBleGFtcGxlLmNvbSIsImV4cCI6MTc1OTMzMzY1OH0.kSlNwHRz0LzXZ6u4AXfLeY41zuJHXhIFqWtXEd_FLMg"

# Тестовые данные для создания записи
test_data = {
    "patient_id": 1,  # Используем существующего пациента
    "visits": [
        {
            "doctor_id": None,
            "services": [
                {
                    "service_id": 1,  # Предполагаемая услуга
                    "quantity": 1
                }
            ],
            "visit_date": "2025-10-01",
            "visit_time": "10:00",
            "department": "cardiology",
            "notes": None
        }
    ],
    "discount_mode": "none",
    "payment_method": "cash",
    "all_free": False,
    "notes": None
}

try:
    print("📤 Отправляем тестовый запрос на создание записи...")

    response = requests.post(
        'http://localhost:18000/api/v1/registrar/cart',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        json=test_data
    )

    print(f"📊 Статус ответа: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("✅ Запись создана успешно!"        print(f"   Visit IDs: {data.get('visit_ids', [])}")
        print(f"   Invoice ID: {data.get('invoice_id')}")
        print(f"   Total amount: {data.get('total_amount')}")
    else:
        print("❌ Ошибка создания записи:"        print(f"   Статус: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   Детали: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Текст: {response.text}")

except Exception as e:
    print(f"❌ Ошибка запроса: {e}")

