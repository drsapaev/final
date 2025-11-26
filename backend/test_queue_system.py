#!/usr/bin/env python3
"""
Комплексный тест системы очередей клиники
"""
import json
import time
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def test_login():
    """Тестируем логин"""
    print("🔑 Тестируем логин...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    # Пробуем разные комбинации пользователей
    login_attempts = [
        {"username": "admin", "password": "admin123"},
        {"username": "test", "password": "test"},
        {"username": "user", "password": "user"},
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
        "first_name": "Иван",
        "last_name": "Петров",
        "birth_date": "1990-01-01",
        "gender": "M",
        "phone": "+998901234567",
    }

    patient_url = f"{BASE_URL}/api/v1/patients/patients"

    try:
        req = urllib.request.Request(
            patient_url, data=json.dumps(patient_data).encode("utf-8")
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:  # 200 OK или 201 Created
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

    visit_data = {"patient_id": patient_id, "notes": "Тестовый визит для очереди"}

    visit_url = f"{BASE_URL}/api/v1/visits/visits"

    try:
        req = urllib.request.Request(
            visit_url, data=json.dumps(visit_data).encode("utf-8")
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:  # 200 OK или 201 Created
                response_text = response.read().decode("utf-8")
                visit = json.loads(response_text)
                print(
                    f"✅ Визит создан: ID {visit['id']} для пациента {visit['patient_id']}"
                )
                return visit["id"]
            else:
                print(f"❌ Ошибка создания визита: {response.read().decode('utf-8')}")
                return False
    except Exception as e:
        print(f"❌ Ошибка создания визита: {e}")
        return None


def test_queue_operations(token, visit_id):
    """Тестируем операции с очередью"""
    print("\n📋 Тестируем операции с очередью...")

    # Тест 1: Получение текущего состояния очереди
    print("  📊 Получаем текущее состояние очереди...")
    today = time.strftime("%Y-%m-%d")
    queue_url = f"{BASE_URL}/api/v1/queue/stats?department=THERAPY&date={today}"

    try:
        req = urllib.request.Request(queue_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                queue_state = json.loads(response_text)
                print(f"    ✅ Очередь получена: {queue_state}")
                return True
            else:
                print(
                    f"    ❌ Ошибка получения очереди: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения очереди: {e}")
        return False


def test_online_queue(token):
    """Тестируем онлайн очередь"""
    print("\n🌐 Тестируем онлайн очередь...")

    # Тест 1: Получение статистики онлайн очереди
    print("  📊 Получаем статистику онлайн очереди...")
    today = time.strftime("%Y-%m-%d")
    stats_url = f"{BASE_URL}/api/v1/online-queue/stats?department=THERAPY&date={today}"

    try:
        req = urllib.request.Request(stats_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                stats = json.loads(response_text)
                print(f"    ✅ Статистика получена: {stats}")
                return True
            else:
                print(
                    f"    ❌ Ошибка получения статистики: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения статистики: {e}")
        return False


def test_appointments(token):
    """Тестируем управление приёмами"""
    print("\n📅 Тестируем управление приёмами...")

    # Тест 1: Получение статистики приёмов
    print("  📊 Получаем статистику приёмов...")
    today = time.strftime("%Y-%m-%d")
    appointments_url = (
        f"{BASE_URL}/api/v1/appointments/stats?department=THERAPY&date={today}"
    )

    try:
        req = urllib.request.Request(appointments_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                appointments = json.loads(response_text)
                print(f"    ✅ Статистика приёмов получена: {appointments}")
                return True
            else:
                print(
                    f"    ❌ Ошибка получения статистики приёмов: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения статистики приёмов: {e}")
        return False


def test_display_board(token):
    """Тестируем дисплей-борд"""
    print("\n📺 Тестируем дисплей-борд...")

    # Тест 1: Получение состояния дисплей-борда
    print("  📊 Получаем состояние дисплей-борда...")
    today = time.strftime("%Y-%m-%d")
    board_url = f"{BASE_URL}/api/v1/board/state?department=THERAPY&date={today}"

    try:
        req = urllib.request.Request(board_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                board_state = json.loads(response_text)
                print(f"    ✅ Состояние дисплей-борда получено: {board_state}")
                return True
            else:
                print(
                    f"    ❌ Ошибка получения состояния дисплей-борда: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения состояния дисплей-борда: {e}")
        return False


def test_printing(token, visit_id):
    """Тестируем систему печати"""
    print("\n🖨️ Тестируем систему печати...")

    # Тест 1: Генерация билета PDF
    print("  🎫 Генерируем билет PDF...")
    time.strftime("%Y-%m-%d")
    ticket_url = (
        f"{BASE_URL}/api/v1/print/ticket.pdf?department=THERAPY&ticket_number=1"
    )

    try:
        req = urllib.request.Request(ticket_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                content_type = response.headers.get("content-type", "")
                if "application/pdf" in content_type:
                    print(
                        f"    ✅ Билет PDF сгенерирован (размер: {len(response.read())} байт)"
                    )
                    return True
                else:
                    print(f"    ⚠️ Получен не PDF: {content_type}")
                    return False
            else:
                print(
                    f"    ❌ Ошибка генерации билета: {response.read().decode('utf-8')}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка генерации билета: {e}")
        return False


def test_public_endpoints():
    """Тестируем публичные эндпоинты без авторизации"""
    print("\n🌐 Тестируем публичные эндпоинты...")

    public_endpoints = [
        "/api/v1/health",
        "/api/v1/status",
        "/api/v1/queue/stats?department=general&date=2024-01-01",
        "/api/v1/appointments/stats?department=general&date=2024-01-01",
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
    print("🚀 Комплексный тест системы очередей клиники")
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

    # Шаг 4: Тестирование очереди
    queue_success = test_queue_operations(token, visit_id)

    # Шаг 5: Тестирование онлайн очереди
    online_success = test_online_queue(token)

    # Шаг 6: Тестирование приёмов
    appointments_success = test_appointments(token)

    # Шаг 7: Тестирование дисплей-борда
    board_success = test_display_board(token)

    # Шаг 8: Тестирование печати
    print_success = test_printing(token, visit_id)

    # Итоги тестирования
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ СИСТЕМЫ ОЧЕРЕДЕЙ:")
    print(f"  ✅ Создание пациента: {'УСПЕШНО' if patient_id else 'ОШИБКА'}")
    print(f"  ✅ Создание визита: {'УСПЕШНО' if visit_id else 'ОШИБКА'}")
    print(f"  ✅ Операции с очередью: {'УСПЕШНО' if queue_success else 'ОШИБКА'}")
    print(f"  ✅ Онлайн очередь: {'УСПЕШНО' if online_success else 'ОШИБКА'}")
    print(
        f"  ✅ Управление приёмами: {'УСПЕШНО' if appointments_success else 'ОШИБКА'}"
    )
    print(f"  ✅ Дисплей-борд: {'УСПЕШНО' if board_success else 'ОШИБКА'}")
    print(f"  ✅ Система печати: {'УСПЕШНО' if print_success else 'ОШИБКА'}")

    success_count = sum(
        [
            bool(patient_id),
            bool(visit_id),
            queue_success,
            online_success,
            appointments_success,
            board_success,
            print_success,
        ]
    )
    total_count = 7

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
