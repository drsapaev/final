"""
Тест проверки данных для бейджей вкладок (иконка часов)
"""
import json
import os
import requests
from datetime import date

REGISTRAR_PASSWORD_ENV = "QA_REGISTRAR_PASSWORD"
REGISTRAR_PASSWORD = os.environ.get(REGISTRAR_PASSWORD_ENV, "").strip()
if not REGISTRAR_PASSWORD:
    raise SystemExit(f"Set {REGISTRAR_PASSWORD_ENV} before running this smoke script.")

print("=" * 60)
print("ТЕСТ БЕЙДЖЕЙ ВКЛАДОК (ИКОНКА ЧАСОВ)")
print("=" * 60)

# Логин
print("\n🔐 Вход в систему...")
login_response = requests.post(
    "http://localhost:18000/api/v1/authentication/login",
    json={"username": "registrar", "password": REGISTRAR_PASSWORD}
)

if login_response.status_code != 200:
    print(f"❌ ОШИБКА входа: {login_response.status_code}")
    exit(1)

token = login_response.json().get("access_token")
print(f"✅ Вход выполнен\n")

# Запрос очередей
today = date.today().strftime('%Y-%m-%d')
url = f"http://localhost:18000/api/v1/registrar/queues/today?target_date={today}"

print(f"📡 Запрос: GET {url}\n")
response = requests.get(
    url,
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code != 200:
    print(f"❌ ОШИБКА API: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()
print(f"✅ Получены данные API")
print(f"   Дата: {data.get('date')}")
print(f"   Всего очередей: {data.get('total_queues')}\n")

# Проверка departmentStats логики
print("🔍 Проверка логики hasActiveQueue для каждого отдела:\n")
print("-" * 60)

queues = data.get('queues', [])
department_map = {
    'cardiology': 'cardio',
    'dermatology': 'derma',
    'dentistry': 'dental',
    'laboratory': 'lab',
    'procedures': 'procedures',
    'echokg': 'echokg'
}

results = {}

for queue in queues:
    specialty = queue.get('specialty')
    entries = queue.get('entries', [])

    # Проверяем каждую запись на наличие queue_numbers
    entries_with_queue = []
    for entry in entries:
        # Имитируем проверку из RegistrarPanel.jsx
        # В реальности фронтенд создаст queue_numbers из данных API
        if entry.get('number'):  # Если есть номер, значит будет queue_numbers
            entries_with_queue.append(entry)

    dept_key = department_map.get(specialty, specialty)
    has_queue = len(entries_with_queue) > 0

    results[dept_key] = {
        'total_entries': len(entries),
        'entries_with_queue': len(entries_with_queue),
        'hasActiveQueue': has_queue
    }

    icon = "✅ 🟡⏰" if has_queue else "❌"
    print(f"{icon} {specialty:15s} (dept_key: {dept_key:10s})")
    print(f"    Всего записей: {len(entries)}")
    print(f"    С номерами очереди: {len(entries_with_queue)}")
    print(f"    hasActiveQueue: {has_queue}")

    if has_queue:
        print(f"    ✅ Иконка часов ДОЛЖНА отображаться на вкладке")
    else:
        print(f"    ⚠️  Иконка часов НЕ будет отображаться")
    print()

# Итоговая статистика
print("=" * 60)
print("ИТОГ:")
print("=" * 60)

departments_with_icon = sum(1 for r in results.values() if r['hasActiveQueue'])
total_departments = len(results)

print(f"✅ Отделов с иконкой часов: {departments_with_icon} из {total_departments}")

if departments_with_icon == total_departments and total_departments > 0:
    print("\n✅ ВСЕ ОТДЕЛЫ ИМЕЮТ ИКОНКИ!")
    print("✅ Желтые кружки с часами должны отображаться на всех вкладках")
elif departments_with_icon > 0:
    print(f"\n⚠️  Иконки будут только на {departments_with_icon} вкладках")
else:
    print("\n❌ ИКОНКИ НЕ БУДУТ ОТОБРАЖАТЬСЯ!")
    print("❌ Проверьте, что API возвращает поле 'number' для записей")

print("=" * 60)
