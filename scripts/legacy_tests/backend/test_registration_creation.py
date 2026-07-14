#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания записей через API регистратуры
"""
import requests
import json
import os
from datetime import date

# Конфигурация
BASE_URL = "http://localhost:18000"
REGISTRAR_USERNAME = os.getenv("QA_REGISTRAR_USERNAME", "registrar@example.com")


def required_registrar_password():
    password = os.getenv("QA_REGISTRAR_PASSWORD")
    if not password:
        raise RuntimeError("Set QA_REGISTRAR_PASSWORD to run registration creation helper scripts.")
    return password

def get_auth_token():
    """Получить токен авторизации для регистратора"""
    print("🔐 Получаем токен авторизации...")

    login_data = {
        "username": REGISTRAR_USERNAME,
        "password": required_registrar_password()
    }

    response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)

    if response.status_code == 200:
        token_data = response.json()
        print("✅ Токен получен; значение не печатается")
        return token_data['access_token']
    else:
        print(f"❌ Ошибка получения токена: {response.status_code}")
        print(f"   Ответ: {response.text}")
        return None

def create_test_patient(token):
    """Создать тестового пациента"""
    print("👤 Создаём тестового пациента...")

    headers = {"Authorization": f"Bearer {token}"}

    patient_data = {
        "first_name": "Тестовый",
        "last_name": "Пациент",
        "middle_name": "Иванович",
        "phone": "+998901234999",
        "birth_date": "1990-01-01",
        "address": "Тестовый адрес, 123"
    }

    response = requests.post(f"{BASE_URL}/api/v1/patients", json=patient_data, headers=headers)

    if response.status_code in [200, 201]:
        patient = response.json()
        full_name = f"{patient['last_name']} {patient['first_name']} {patient.get('middle_name', '')}"
        print(f"✅ Пациент создан: ID {patient['id']}, {full_name}")
        return patient['id']
    elif response.status_code == 400 and "уже существует" in response.text:
        print("⚠️ Пациент уже существует, ищем его...")
        # Поиск по телефону
        search_response = requests.get(f"{BASE_URL}/api/v1/patients/search",
                                     params={"phone": "+998901234999"},
                                     headers=headers)
        if search_response.status_code == 200:
            patients = search_response.json()
            if patients:
                patient_id = patients[0]['id']
                print(f"✅ Найден существующий пациент: ID {patient_id}")
                return patient_id

    print(f"❌ Ошибка создания пациента: {response.status_code}")
    print(f"   Ответ: {response.text}")
    return None

def create_test_visit(token, patient_id):
    """Создать тестовый визит через API корзины"""
    print("🏥 Создаём тестовый визит...")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    cart_data = {
        "patient_id": patient_id,
        "visits": [
            {
                "doctor_id": None,
                "services": [
                    {"service_id": "K01", "quantity": 1}
                ],
                "visit_date": date.today().isoformat(),
                "visit_time": None,
                "department": "cardiology",
                "notes": None
            }
        ],
        "discount_mode": "none",
        "payment_method": "cash",
        "notes": "Тестовая запись через API"
    }

    print(f"📤 Отправляем данные: {json.dumps(cart_data, indent=2, ensure_ascii=False)}")

    response = requests.post(f"{BASE_URL}/api/v1/registrar/cart", json=cart_data, headers=headers)

    print(f"📥 Статус ответа: {response.status_code}")
    print(f"📥 Заголовки ответа: {dict(response.headers)}")

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Визит создан успешно!")
        print(f"   Invoice ID: {result.get('invoice_id')}")
        print(f"   Visit IDs: {result.get('visit_ids')}")
        print(f"   Сумма: {result.get('total_amount')}")
        return result
    else:
        print(f"❌ Ошибка создания визита: {response.status_code}")
        print(f"   Ответ: {response.text}")
        try:
            error_data = response.json()
            print(f"   JSON ошибка: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
        except:
            pass
        return None

def check_today_queues(token):
    """Проверить очереди на сегодня"""
    print("📋 Проверяем очереди на сегодня...")

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(f"{BASE_URL}/api/v1/registrar/queues/today", headers=headers)

    if response.status_code == 200:
        data = response.json()
        total_entries = sum(len(queue.get('entries', [])) for queue in data.get('queues', []))
        print(f"✅ Очереди получены: {data.get('total_queues', 0)} очередей, {total_entries} записей")

        for queue in data.get('queues', []):
            queue_name = queue.get('queue_name', 'Unknown')
            entries_count = len(queue.get('entries', []))
            print(f"   📊 {queue_name}: {entries_count} записей")

            # Показываем последние 3 записи
            for i, entry in enumerate(queue.get('entries', [])[-3:]):
                print(f"      {i+1}. ID:{entry.get('id')} - {entry.get('patient_fio')} ({entry.get('created_at', 'N/A')})")

        return data
    else:
        print(f"❌ Ошибка получения очередей: {response.status_code}")
        print(f"   Ответ: {response.text}")
        return None

def main():
    """Основная функция тестирования"""
    print("🚀 Начинаем тестирование API регистрации...")
    print("=" * 60)

    # 1. Получаем токен
    token = get_auth_token()
    if not token:
        return

    print("\n" + "=" * 60)

    # 2. Проверяем текущее состояние очередей
    print("📊 СОСТОЯНИЕ ДО СОЗДАНИЯ:")
    queues_before = check_today_queues(token)
    total_before = sum(len(q.get('entries', [])) for q in queues_before.get('queues', [])) if queues_before else 0

    print("\n" + "=" * 60)

    # 3. Создаём пациента
    patient_id = create_test_patient(token)
    if not patient_id:
        return

    print("\n" + "=" * 60)

    # 4. Создаём визит
    visit_result = create_test_visit(token, patient_id)

    print("\n" + "=" * 60)

    # 5. Проверяем состояние после создания
    print("📊 СОСТОЯНИЕ ПОСЛЕ СОЗДАНИЯ:")
    queues_after = check_today_queues(token)
    total_after = sum(len(q.get('entries', [])) for q in queues_after.get('queues', [])) if queues_after else 0

    print("\n" + "=" * 60)
    print("📈 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print(f"   Записей до: {total_before}")
    print(f"   Записей после: {total_after}")
    print(f"   Изменение: {total_after - total_before}")

    if visit_result and total_after > total_before:
        print("✅ ТЕСТ ПРОЙДЕН: Запись создана и появилась в очереди!")
    elif visit_result and total_after == total_before:
        print("⚠️ ПРОБЛЕМА: Запись создана, но НЕ появилась в очереди!")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН: Ошибка создания записи!")

if __name__ == "__main__":
    main()
