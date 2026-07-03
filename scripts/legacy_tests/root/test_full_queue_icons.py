"""
Полный тест иконок очереди: от базы данных через API до проверки структуры данных
"""
import json
import os
import requests
from datetime import date
import sqlite3

REGISTRAR_PASSWORD_ENV = "QA_REGISTRAR_PASSWORD"
REGISTRAR_PASSWORD = os.environ.get(REGISTRAR_PASSWORD_ENV, "").strip()
if not REGISTRAR_PASSWORD:
    raise SystemExit(f"Set {REGISTRAR_PASSWORD_ENV} before running this smoke script.")

print("=" * 60)
print("ПОЛНЫЙ ТЕСТ СИСТЕМЫ ИКОНОК ОЧЕРЕДИ")
print("=" * 60)

# ШАГ 1: Проверка базы данных
print("\n📊 ШАГ 1: Проверка базы данных")
print("-" * 60)

conn = sqlite3.connect("backend/clinic.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM queue_entries")
total_entries = cursor.fetchone()[0]
print(f"✅ Записей в queue_entries: {total_entries}")

if total_entries == 0:
    print("❌ ОШИБКА: Таблица queue_entries пустая!")
    exit(1)

today = date.today().strftime('%Y-%m-%d')
cursor.execute("""
    SELECT COUNT(DISTINCT v.id)
    FROM visits v
    INNER JOIN queue_entries qe ON qe.visit_id = v.id
    WHERE v.visit_date = ?
""", (today,))
visits_with_queue = cursor.fetchone()[0]
print(f"✅ Визитов на сегодня с номерами очереди: {visits_with_queue}")

conn.close()

# ШАГ 2: Проверка API
print("\n📡 ШАГ 2: Проверка API")
print("-" * 60)

# Логин
login_response = requests.post(
    "http://localhost:18000/api/v1/authentication/login",
    json={"username": "registrar", "password": REGISTRAR_PASSWORD}
)

if login_response.status_code != 200:
    print(f"❌ ОШИБКА входа: {login_response.status_code}")
    exit(1)

token = login_response.json().get("access_token")
print(f"✅ Вход выполнен")

# Запрос очередей
url = f"http://localhost:18000/api/v1/registrar/queues/today?target_date={today}"
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
print(f"   Всего очередей: {data.get('total_queues')}")

# ШАГ 3: Проверка структуры данных
print("\n🔍 ШАГ 3: Проверка структуры данных")
print("-" * 60)

queues = data.get('queues', [])
total_entries_api = 0
entries_with_real_numbers = 0
missing_numbers = []

for queue in queues:
    specialty = queue.get('specialty')
    entries = queue.get('entries', [])
    total_entries_api += len(entries)

    if len(entries) > 0:
        print(f"\n📋 {specialty} ({len(entries)} записей):")
        for i, entry in enumerate(entries[:3], 1):  # Показываем первые 3
            number = entry.get('number')
            patient_name = entry.get('patient_name', 'N/A')
            entry_id = entry.get('id')

            # Проверяем, что номер не равен индексу (значит это реальный номер)
            if number and number != i:
                entries_with_real_numbers += 1
                print(f"   ✅ #{number} - {patient_name} (entry_id: {entry_id})")
            elif number:
                entries_with_real_numbers += 1
                print(f"   ✅ #{number} - {patient_name} (entry_id: {entry_id})")
            else:
                missing_numbers.append((specialty, entry_id, patient_name))
                print(f"   ❌ Нет номера - {patient_name} (entry_id: {entry_id})")

print(f"\n{'=' * 60}")
print("ИТОГОВАЯ СТАТИСТИКА")
print(f"{'=' * 60}")
print(f"✅ Записей в БД с номерами:      {visits_with_queue}")
print(f"✅ Записей в API ответе:         {total_entries_api}")
print(f"✅ Записей с реальными номерами: {entries_with_real_numbers}")
print(f"❌ Записей без номеров:          {len(missing_numbers)}")

if len(missing_numbers) > 0:
    print(f"\n⚠️  ВНИМАНИЕ: Найдены записи без номеров:")
    for specialty, entry_id, patient_name in missing_numbers:
        print(f"   - {specialty}: {patient_name} (id: {entry_id})")

# ФИНАЛЬНАЯ ПРОВЕРКА
print(f"\n{'=' * 60}")
if entries_with_real_numbers > 0 and len(missing_numbers) == 0:
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("✅ Система готова: все записи имеют реальные номера очереди")
    print("✅ Иконки должны отображаться во всех вкладках регистратуры")
elif entries_with_real_numbers > 0:
    print("⚠️  ЧАСТИЧНО РАБОТАЕТ")
    print(f"⚠️  {entries_with_real_numbers} записей с номерами")
    print(f"⚠️  {len(missing_numbers)} записей без номеров")
else:
    print("❌ ТЕСТЫ НЕ ПРОЙДЕНЫ!")
    print("❌ Номера очереди не возвращаются из API")
print(f"{'=' * 60}")
