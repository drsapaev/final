#!/usr/bin/env python3
import requests
import random
from datetime import date

print("🧪 Простой тест создания визита без очередей...")

# Получаем токен
token_response = requests.post("http://localhost:8000/api/v1/auth/login", data={
    "username": "registrar@example.com",
    "password": "registrar123"
})

token = token_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Создаём пациента
phone = f"+998901{random.randint(100000, 999999)}"
patient_data = {
    "first_name": "Простой",
    "last_name": "Тест", 
    "middle_name": "Иванович",
    "phone": phone,
    "birth_date": "1990-01-01",
    "address": "Тестовый адрес, 123"
}

patient_response = requests.post("http://localhost:8000/api/v1/patients", json=patient_data, headers=headers)
patient_id = patient_response.json()["id"]
print(f"✅ Пациент создан: ID {patient_id}")

# Создаём визит на ЗАВТРА (чтобы избежать присвоения очередей)
tomorrow = date.today().replace(day=date.today().day + 1).isoformat()
print(f"📅 Создаём визит на ЗАВТРА: {tomorrow}")

cart_data = {
    "patient_id": patient_id,
    "visits": [{
        "doctor_id": None,
        "services": [{"service_id": 40, "quantity": 1}],
        "visit_date": tomorrow,  # ЗАВТРА!
        "visit_time": None,
        "department": "cardiology",
        "notes": None
    }],
    "discount_mode": "none",
    "payment_method": "cash",
    "notes": "Тестовая запись на завтра"
}

cart_response = requests.post("http://localhost:8000/api/v1/registrar/cart", json=cart_data, headers=headers)
print(f"📋 Статус создания визита: {cart_response.status_code}")

if cart_response.status_code == 200:
    result = cart_response.json()
    visit_id = result.get('visit_ids', [None])[0]
    print(f"✅ Визит создан! Visit ID: {visit_id}")
    
    # Проверяем в базе
    import sqlite3
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM visits WHERE id = ?', (visit_id,))
    visit = cursor.fetchone()
    if visit:
        print(f"✅ Визит найден в базе: ID {visit[0]}, Date {visit[3]}, Status {visit[8]}")
    else:
        print(f"❌ Визит ID {visit_id} НЕ найден в базе!")
    conn.close()
else:
    print(f"❌ Ошибка: {cart_response.text}")