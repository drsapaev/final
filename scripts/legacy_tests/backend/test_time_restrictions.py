#!/usr/bin/env python3
"""
Тест временных ограничений для QR очередей
"""

import requests
import json
import os
from datetime import datetime

BASE_URL = os.getenv("QA_BACKEND_BASE_URL", "http://localhost:18000")
AUTH_USERNAME_ENV = "QA_ADMIN_USERNAME"


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Set {name} to run the QR time restrictions helper.")
    return value

def test_time_restrictions():
    """Тестирует временные ограничения QR системы"""

    print("🕐 Тестирование временных ограничений QR очередей")
    print("=" * 60)

    # Получаем токен авторизации
    login_data = {
        "username": required_env(AUTH_USERNAME_ENV),
        "password": required_env("QA_ADMIN_PASSWORD"),
    }
    login_response = requests.post(f"{BASE_URL}/api/v1/authentication/login", data=login_data)

    if login_response.status_code != 200:
        print(f"❌ Ошибка авторизации: {login_response.status_code}")
        return

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("✅ Авторизация успешна")

    # Генерируем QR токен
    qr_data = {
        "specialist_id": 1,
        "department": "cardiology",
        "expires_hours": 24
    }

    qr_response = requests.post(
        f"{BASE_URL}/api/v1/admin/qr-tokens/generate",
        json=qr_data,
        headers=headers
    )

    if qr_response.status_code != 200:
        print(f"❌ Ошибка генерации QR токена: {qr_response.status_code}")
        print(qr_response.text)
        return

    qr_token = qr_response.json()["token"]
    print("✅ QR токен сгенерирован; значение не печатается")

    # Проверяем информацию о токене
    token_info_response = requests.get(f"{BASE_URL}/api/v1/qr-tokens/{qr_token}/info")

    if token_info_response.status_code == 200:
        token_info = token_info_response.json()
        print(f"📊 Информация о токене:")
        print(f"   - Специалист: {token_info.get('specialist_name', 'N/A')}")
        print(f"   - Отделение: {token_info.get('department', 'N/A')}")
        print(f"   - Статус: {token_info.get('status', 'N/A')}")
        print(f"   - Разрешено: {token_info.get('allowed', 'N/A')}")
        print(f"   - Сообщение: {token_info.get('message', 'N/A')}")

        if 'start_time' in token_info:
            print(f"   - Время начала: {token_info['start_time']}")
        if 'end_time' in token_info:
            print(f"   - Время окончания: {token_info['end_time']}")
        if 'max_entries' in token_info:
            print(f"   - Максимум записей: {token_info['max_entries']}")
        if 'current_entries' in token_info:
            print(f"   - Текущих записей: {token_info['current_entries']}")
        if 'remaining_slots' in token_info:
            print(f"   - Свободных мест: {token_info['remaining_slots']}")
    else:
        print(f"❌ Ошибка получения информации о токене: {token_info_response.status_code}")
        print(token_info_response.text)
        return

    # Пытаемся начать сессию присоединения
    session_response = requests.post(f"{BASE_URL}/api/v1/queue/join/start", json={"token": qr_token})

    if session_response.status_code == 200:
        session_data = session_response.json()
        print(f"✅ Сессия присоединения начата:")
        print("   - Токен сессии: значение не печатается")
        print(f"   - Истекает: {session_data['expires_at']}")

        # Пытаемся завершить присоединение
        join_data = {
            "session_token": session_data["session_token"],
            "patient_name": "Тестовый Пациент",
            "phone": "+998901234567"
        }

        complete_response = requests.post(f"{BASE_URL}/api/v1/queue/join/complete", json=join_data)

        if complete_response.status_code == 200:
            result = complete_response.json()
            print(f"🎉 Присоединение к очереди успешно:")
            print(f"   - Номер в очереди: {result.get('queue_number', 'N/A')}")
            print(f"   - Дубликат: {result.get('duplicate', False)}")
        else:
            print(f"❌ Ошибка завершения присоединения: {complete_response.status_code}")
            print(complete_response.text)

    elif session_response.status_code == 400:
        error_data = session_response.json()
        print(f"⚠️ Присоединение заблокировано:")
        print(f"   - Причина: {error_data.get('detail', 'Неизвестная ошибка')}")
    else:
        print(f"❌ Ошибка начала сессии: {session_response.status_code}")
        print(session_response.text)

    print("\n" + "=" * 60)
    print(f"🕐 Текущее время: {datetime.now().strftime('%H:%M:%S')}")
    print("✅ Тест завершен")

if __name__ == "__main__":
    test_time_restrictions()
