import os
import sys
import requests
import json

token = os.environ.get("REGISTRAR_API_TOKEN")
if not token:
    print("Set REGISTRAR_API_TOKEN to a locally generated bearer token before running this smoke script.")
    sys.exit(2)

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
        print("✅ Запись создана успешно!")
        print(f"   Visit IDs: {data.get('visit_ids', [])}")
        print(f"   Invoice ID: {data.get('invoice_id')}")
        print(f"   Total amount: {data.get('total_amount')}")
    else:
        print("❌ Ошибка создания записи:")
        print(f"   Статус: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   Детали: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Текст: {response.text}")

except Exception as e:
    print(f"❌ Ошибка запроса: {e}")
