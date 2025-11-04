"""
Тестирование API получения очередей с реальными номерами
"""
import requests
import json
from datetime import date

# Логин
print("🔐 Вход в систему...")
login_response = requests.post(
    "http://localhost:8000/api/v1/authentication/login",
    json={"username": "registrar", "password": "registrar123"}
)

if login_response.status_code != 200:
    print(f"❌ Ошибка входа: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json().get("access_token")
print(f"✅ Вход выполнен\n")

# Запрос очередей
today = date.today().strftime('%Y-%m-%d')
url = f"http://localhost:8000/api/v1/registrar/queues/today?target_date={today}"

print(f"📡 Запрос: GET {url}")
response = requests.get(
    url,
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code != 200:
    print(f"❌ Ошибка: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()
print(f"✅ Ответ получен\n")
print(f"Дата: {data.get('date')}")
print(f"Всего очередей: {data.get('total_queues')}\n")

# Проверяем номера в очередях
for queue in data.get('queues', []):
    specialty = queue.get('specialty')
    entries = queue.get('entries', [])

    print(f"📋 Очередь: {specialty}")
    print(f"   Записей: {len(entries)}")

    if len(entries) > 0:
        # Показываем первые 5 записей
        for entry in entries[:5]:
            number = entry.get('number')
            patient_id = entry.get('patient_id')
            patient_name = entry.get('patient_name')
            entry_id = entry.get('id')

            print(f"   #{number} - Patient {patient_id} ({patient_name}) [entry_id: {entry_id}]")

        if len(entries) > 5:
            print(f"   ... и ещё {len(entries) - 5} записей")

    print()

print("✅ Тест завершён!")
