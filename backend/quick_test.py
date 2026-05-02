#!/usr/bin/env python3
import requests
import random
from datetime import date

# Получаем токен
token_response = requests.post("http://localhost:18000/api/v1/auth/login", data={
    "username": "registrar@example.com",
    "password": "registrar123"
})

if token_response.status_code != 200:
    print(f"❌ Ошибка получения токена: {token_response.status_code}")
    exit(1)

token = token_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Создаём пациента с уникальным номером
phone = f"+998901{random.randint(100000, 999999)}"
print(f"📞 Создаём пациента с телефоном: {phone}")

patient_data = {
    "first_name": "Тестовый",
    "last_name": "Пациент", 
    "middle_name": "Иванович",
    "phone": phone,
    "birth_date": "1990-01-01",
    "address": "Тестовый адрес, 123"
}

patient_response = requests.post("http://localhost:18000/api/v1/patients", json=patient_data, headers=headers)
print(f"📋 Статус создания пациента: {patient_response.status_code}")

if patient_response.status_code not in [200, 201]:
    print(f"❌ Ошибка создания пациента: {patient_response.text}")
    exit(1)

patient = patient_response.json()
patient_id = patient["id"]
print(f"✅ Пациент создан: ID {patient_id}")

# Проверяем количество записей ДО создания визита
queues_before = requests.get("http://localhost:18000/api/v1/registrar/queues/today", headers=headers)
total_before = sum(len(q.get("entries", [])) for q in queues_before.json().get("queues", []))
print(f"📊 Записей в очереди ДО: {total_before}")

# Создаём визит
print(f"🏥 Создаём визит для пациента {patient_id}...")

cart_data = {
    "patient_id": patient_id,
    "visits": [{
        "doctor_id": None,
        "services": [{"service_id": 40, "quantity": 1}],
        "visit_date": date.today().isoformat(),
        "visit_time": None,
        "department": "cardiology",
        "notes": None
    }],
    "discount_mode": "none",
    "payment_method": "cash",
    "notes": "Тестовая запись через API"
}

print(f"📤 Отправляем данные визита...")
cart_response = requests.post("http://localhost:18000/api/v1/registrar/cart", json=cart_data, headers=headers)
print(f"📋 Статус создания визита: {cart_response.status_code}")

if cart_response.status_code == 200:
    result = cart_response.json()
    print(f"✅ Визит создан успешно!")
    print(f"   Visit IDs: {result.get('visit_ids')}")
    print(f"   Invoice ID: {result.get('invoice_id')}")
    print(f"   Сумма: {result.get('total_amount')}")
else:
    print(f"❌ Ошибка создания визита: {cart_response.text}")

# Проверяем количество записей ПОСЛЕ создания визита
queues_after = requests.get("http://localhost:18000/api/v1/registrar/queues/today", headers=headers)
total_after = sum(len(q.get("entries", [])) for q in queues_after.json().get("queues", []))
print(f"📊 Записей в очереди ПОСЛЕ: {total_after}")

print(f"📈 РЕЗУЛЬТАТ: {total_after - total_before} новых записей")

if cart_response.status_code == 200 and total_after > total_before:
    print("✅ ТЕСТ ПРОЙДЕН: Визит создан и появился в очереди!")
elif cart_response.status_code == 200 and total_after == total_before:
    print("⚠️ ПРОБЛЕМА: Визит создан, но НЕ появился в очереди!")
else:
    print("❌ ТЕСТ НЕ ПРОЙДЕН: Ошибка создания визита!")
