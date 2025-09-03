#!/usr/bin/env python3
"""
Комплексный тест системы переноса визитов клиники
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"


def test_login():
    """Тестируем логин"""
    print("🔑 Тестируем логин...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    # Пробуем разные комбинации пользователей
    login_attempts = [
        {"username": "admin", "password": "admin"},
        {"username": "test", "password": "test"},
        {"username": "user", "password": "user"}
    ]

    for login_data in login_attempts:
        try:
            form_data = urllib.parse.urlencode(login_data).encode("utf-8")
            req = urllib.request.Request(login_url, data=form_data)
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    response_text = response.read().decode("utf-8")
                    token_data = json.loads(response_text)
                    token = token_data["access_token"]
                    print(f"✅ Логин успешен с {login_data['username']}")
                    return token
        except Exception as e:
            print(f"⚠️ Попытка логина с {login_data['username']}: {e}")
            continue
    
    print("❌ Не удалось авторизоваться ни с одним пользователем")
    print("ℹ️ Продолжаем тест без авторизации (только публичные эндпоинты)")
    return None


def test_create_patient(token):
    """Тестируем создание пациента"""
    print("\n👤 Тестируем создание пациента...")

    patient_data = {
        "first_name": "Мария",
        "last_name": "Сидорова",
        "birth_date": "1985-05-15",
        "gender": "F",
        "phone": "+998901234568",
    }

    patient_url = f"{BASE_URL}/api/v1/patients/patients"

    try:
        req = urllib.request.Request(
            patient_url, data=json.dumps(patient_data).encode("utf-8")
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                response_text = response.read().decode("utf-8")
                patient = json.loads(response_text)
                print(
                    f"✅ Пациент создан: {patient['first_name']} {patient['last_name']} (ID: {patient['id']})"
                )
                return patient["id"]
            else:
                print(f"❌ Ошибка создания пациента: {response.read().decode('utf-8')}")
                return None
    except Exception as e:
        print(f"❌ Ошибка создания пациента: {e}")
        return None


def test_create_visit(token, patient_id):
    """Тестируем создание визита"""
    print("\n🏥 Тестируем создание визита...")

    visit_data = {"patient_id": patient_id, "notes": "Тестовый визит для переноса"}

    visit_url = f"{BASE_URL}/api/v1/visits/visits"

    try:
        req = urllib.request.Request(
            visit_url, data=json.dumps(visit_data).encode("utf-8")
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                response_text = response.read().decode("utf-8")
                visit = json.loads(response_text)
                print(
                    f"✅ Визит создан: ID {visit['id']} для пациента {visit['patient_id']}"
                )
                return visit["id"]
            else:
                print(f"❌ Ошибка создания визита: {response.read().decode('utf-8')}")
                return None
    except Exception as e:
        print(f"❌ Ошибка создания визита: {e}")
        return None


def test_reschedule_visit(token, visit_id):
    """Тестируем перенос визита на другой день"""
    print("\n📅 Тестируем перенос визита на другой день...")

    # Переносим на завтра
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # new_date передаётся как query parameter, а не в JSON body
    reschedule_url = (
        f"{BASE_URL}/api/v1/visits/visits/{visit_id}/reschedule?new_date={tomorrow}"
    )

    try:
        req = urllib.request.Request(reschedule_url)
        req.add_header("Authorization", f"Bearer {token}")
        req.get_method = lambda: "POST"  # Используем POST, а не PUT

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                result = json.loads(response_text)
                print(f"    ✅ Визит перенесён на {tomorrow}: {result}")
                return True
            else:
                print(
                    f"    ❌ Ошибка переноса визита: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка переноса визита: {e}")
        return False


def test_reschedule_tomorrow(token, visit_id):
    """Тестируем перенос визита на завтра (специальный эндпоинт)"""
    print("\n🔄 Тестируем перенос визита на завтра...")

    reschedule_url = f"{BASE_URL}/api/v1/visits/visits/{visit_id}/reschedule/tomorrow"

    try:
        req = urllib.request.Request(reschedule_url)
        req.add_header("Authorization", f"Bearer {token}")
        req.get_method = lambda: "POST"  # Используем POST, а не PUT

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                result = json.loads(response_text)
                print(f"    ✅ Визит перенесён на завтра: {result}")
                return True
            else:
                print(
                    f"    ❌ Ошибка переноса на завтра: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка переноса на завтра: {e}")
        return False


def test_get_visit_status(token, visit_id):
    """Тестируем получение статуса визита после переноса"""
    print("\n📊 Тестируем получение статуса визита...")

    # Эндпоинт /status - это POST для изменения статуса, а не GET для получения
    # Для получения статуса используем основной эндпоинт /visits/{visit_id}
    status_url = f"{BASE_URL}/api/v1/visits/visits/{visit_id}"

    try:
        req = urllib.request.Request(status_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                visit = json.loads(response_text)
                status = visit.get("status", "N/A")
                print(f"    ✅ Статус визита получен: {status}")
                return True
            else:
                print(
                    f"    ❌ Ошибка получения статуса: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения статуса: {e}")
        return False


def test_get_visit_details(token, visit_id):
    """Тестируем получение деталей визита после переноса"""
    print("\n🔍 Тестируем получение деталей визита...")

    details_url = f"{BASE_URL}/api/v1/visits/visits/{visit_id}"

    try:
        req = urllib.request.Request(details_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                result = json.loads(response_text)
                # Эндпоинт возвращает VisitWithServices с полями visit и services
                if "visit" in result:
                    visit = result["visit"]
                    print(
                        f"    ✅ Детали визита получены: ID {visit['id']}, статус: {visit.get('status', 'N/A')}"
                    )
                    return True
                else:
                    print(f"    ⚠️ Неожиданная структура ответа: {result}")
                    return False
            else:
                print(
                    f"    ❌ Ошибка получения деталей: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения деталей: {e}")
        return False


def test_public_endpoints():
    """Тестируем публичные эндпоинты без авторизации"""
    print("\n🌐 Тестируем публичные эндпоинты...")
    
    public_endpoints = [
        "/api/v1/health",
        "/api/v1/status",
        "/api/v1/queue/stats",
        "/api/v1/appointments/stats"
    ]
    
    success_count = 0
    for endpoint in public_endpoints:
        try:
            req = urllib.request.Request(f"{BASE_URL}{endpoint}")
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"✅ {endpoint}: OK")
                    success_count += 1
                else:
                    print(f"⚠️ {endpoint}: HTTP {response.status}")
        except Exception as e:
            print(f"⚠️ {endpoint}: {e}")
    
    print(f"\n📊 Публичные эндпоинты: {success_count}/{len(public_endpoints)} работают")
    return success_count > 0


def main():
    """Основная функция тестирования"""
    print("🚀 Комплексный тест системы переноса визитов клиники")
    print("=" * 70)

    # Шаг 1: Логин
    token = test_login()
    if not token:
        print("⚠️ Продолжаем тест без авторизации (только публичные эндпоинты)")
        # Тестируем только публичные эндпоинты
        test_public_endpoints()
        return

    # Шаг 2: Создание пациента
    patient_id = test_create_patient(token)
    if not patient_id:
        print("❌ Тест прерван: не удалось создать пациента")
        return

    # Шаг 3: Создание визита
    visit_id = test_create_visit(token, patient_id)
    if not visit_id:
        print("❌ Тест прерван: не удалось создать визит")
        return

    # Шаг 4: Перенос визита на другой день
    reschedule_success = test_reschedule_visit(token, visit_id)

    # Шаг 5: Перенос визита на завтра (специальный эндпоинт)
    tomorrow_success = test_reschedule_tomorrow(token, visit_id)

    # Шаг 6: Получение статуса визита
    status_success = test_get_visit_status(token, visit_id)

    # Шаг 7: Получение деталей визита
    details_success = test_get_visit_details(token, visit_id)

    # Итоги тестирования
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ СИСТЕМЫ ПЕРЕНОСА ВИЗИТОВ:")
    print(f"  ✅ Создание пациента: {'УСПЕШНО' if patient_id else 'ОШИБКА'}")
    print(f"  ✅ Создание визита: {'УСПЕШНО' if visit_id else 'ОШИБКА'}")
    print(
        f"  ✅ Перенос визита на другой день: {'УСПЕШНО' if reschedule_success else 'ОШИБКА'}"
    )
    print(
        f"  ✅ Перенос визита на завтра: {'УСПЕШНО' if tomorrow_success else 'ОШИБКА'}"
    )
    print(f"  ✅ Получение статуса визита: {'УСПЕШНО' if status_success else 'ОШИБКА'}")
    print(
        f"  ✅ Получение деталей визита: {'УСПЕШНО' if details_success else 'ОШИБКА'}"
    )

    success_count = sum(
        [
            bool(patient_id),
            bool(visit_id),
            reschedule_success,
            tomorrow_success,
            status_success,
            details_success,
        ]
    )
    total_count = 6

    print(
        f"\n🎯 Общий результат: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)"
    )

    if success_count == total_count:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    elif success_count >= total_count * 0.8:
        print("👍 Большинство тестов прошли успешно!")
    else:
        print("⚠️ Много ошибок, требуется доработка")

    print("\n" + "=" * 70)
    print("🎉 Тест завершён!")


if __name__ == "__main__":
    main()
