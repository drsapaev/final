"""
Тестирование API очереди ЭКГ
"""
import json
import os
import requests
from datetime import date

REGISTRAR_PASSWORD_ENV = "QA_REGISTRAR_PASSWORD"
REGISTRAR_PASSWORD = os.environ.get(REGISTRAR_PASSWORD_ENV, "").strip()
if not REGISTRAR_PASSWORD:
    raise SystemExit(f"Set {REGISTRAR_PASSWORD_ENV} before running this smoke script.")

# Получаем токен из localStorage (нужно вставить вручную из браузера)
# Или используем тестовый токен
token = input("Введите токен авторизации (или нажмите Enter для пропуска): ").strip()

if not token:
    print("Токен не указан. Пытаемся войти как admin...")
    # Попробуем залогиниться
    login_response = requests.post(
        "http://localhost:18000/api/v1/authentication/login",
        json={"username": "registrar", "password": REGISTRAR_PASSWORD}
    )

    if login_response.status_code == 200:
        data = login_response.json()
        token = data.get("access_token")
        print(f"✅ Вход выполнен, получен токен")
    else:
        print(f"❌ Не удалось войти: {login_response.status_code}")
        print(login_response.text)
        exit(1)

# Запрашиваем очереди
today = date.today().strftime('%Y-%m-%d')
url = f"http://localhost:18000/api/v1/registrar/queues/today?target_date={today}"

print(f"\n📡 Запрос: GET {url}")
response = requests.get(
    url,
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code != 200:
    print(f"❌ Ошибка: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()
print(f"\n✅ Ответ получен!")
print(f"Всего очередей: {data.get('total_queues')}")
print(f"Дата: {data.get('date')}")

# Ищем очередь echokg
echokg_queue = None
for queue in data.get('queues', []):
    specialty = queue.get('specialty')
    entries_count = len(queue.get('entries', []))
    print(f"\n📋 Очередь: {specialty}, записей: {entries_count}")

    if specialty == 'echokg':
        echokg_queue = queue
        print(f"  ⭐ Найдена очередь ЭКГ!")
        if entries_count > 0:
            for entry in queue['entries']:
                print(f"    - ID: {entry.get('id')}, Пациент: {entry.get('patient_name')}")
                print(f"      Услуги: {entry.get('services')}")
                print(f"      Коды: {entry.get('service_codes')}")
        else:
            print(f"    ⚠️  Очередь ЭКГ пустая!")

if not echokg_queue:
    print(f"\n❌ Очередь echokg НЕ НАЙДЕНА в ответе!")
else:
    print(f"\n=== Детали очереди ЭКГ ===")
    print(json.dumps(echokg_queue, indent=2, ensure_ascii=False))
