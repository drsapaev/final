"""
Manual testing script для batch queue entries endpoint

Usage:
    cd backend
    python test_queue_batch_manual.py

Requirements:
    - Backend server должен быть запущен (localhost:18000)
    - В БД должны быть пользователи: admin или registrar
    - В БД должны быть пациенты, услуги, специалисты
"""
import json
import os
from datetime import date

import requests

# Configuration
API_BASE = os.getenv("QA_BACKEND_API_BASE_URL", "http://localhost:18000/api/v1")
USERNAME = os.getenv("QA_QUEUE_BATCH_USERNAME", "admin")


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Set {name} to run the queue batch manual helper.")
    return value


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def print_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def print_info(message):
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")


def print_warning(message):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")


def print_section(title):
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")


def login():
    """Авторизация и получение токена"""
    print_section("Авторизация")

    response = requests.post(
        f"{API_BASE}/authentication/login",
        json={"username": USERNAME, "password": required_env("QA_QUEUE_BATCH_PASSWORD")}
    )

    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print_success("Авторизация успешна! Token value is not printed")
        return token
    else:
        print_error(f"Ошибка авторизации: {response.status_code}")
        print_error(response.text)
        return None


def get_patients(token):
    """Получить список пациентов"""
    print_section("Получение списка пациентов")

    response = requests.get(
        f"{API_BASE}/patients/",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 200:
        patients = response.json()
        if patients:
            print_success(f"Найдено пациентов: {len(patients)}")
            for i, patient in enumerate(patients[:5], 1):
                patient_id = patient.get('id')
                fio = f"{patient.get('first_name', '')} {patient.get('last_name', '')}"
                phone = patient.get('phone', 'N/A')
                print_info(f"  {i}. ID={patient_id}: {fio}, {phone}")
            return patients[0]  # Возвращаем первого пациента
        else:
            print_warning("Пациентов не найдено")
            return None
    else:
        print_error(f"Ошибка получения пациентов: {response.status_code}")
        return None


def get_services(token):
    """Получить список услуг"""
    print_section("Получение списка услуг")

    response = requests.get(
        f"{API_BASE}/registrar/services",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 200:
        services = response.json()
        if services:
            print_success(f"Найдено услуг: {len(services)}")
            for i, service in enumerate(services[:5], 1):
                service_id = service.get('id')
                name = service.get('name', 'N/A')
                price = service.get('price', 0)
                print_info(f"  {i}. ID={service_id}: {name}, {price} сум")
            return services[:3]  # Возвращаем первые 3 услуги
        else:
            print_warning("Услуг не найдено")
            return []
    else:
        print_error(f"Ошибка получения услуг: {response.status_code}")
        return []


def get_doctors(token):
    """Получить список врачей"""
    print_section("Получение списка врачей/специалистов")

    response = requests.get(
        f"{API_BASE}/registrar/doctors",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 200:
        doctors = response.json()
        if doctors:
            print_success(f"Найдено специалистов: {len(doctors)}")
            for i, doctor in enumerate(doctors[:5], 1):
                doctor_id = doctor.get('user_id') or doctor.get('id')
                name = doctor.get('full_name', 'N/A')
                specialty = doctor.get('specialty', 'N/A')
                print_info(f"  {i}. ID={doctor_id}: {name}, {specialty}")
            return doctors[:2]  # Возвращаем первых 2 специалистов
        else:
            print_warning("Специалистов не найдено")
            return []
    else:
        print_error(f"Ошибка получения специалистов: {response.status_code}")
        return []


def test_batch_create_single_service(token, patient_id, specialist_id, service_id):
    """Тест: Создание одной услуги в очереди"""
    print_section("Тест 1: Создание одной услуги")

    payload = {
        "patient_id": patient_id,
        "source": "desk",
        "services": [
            {
                "specialist_id": specialist_id,
                "service_id": service_id,
                "quantity": 1
            }
        ]
    }

    print_info(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.post(
        f"{API_BASE}/registrar-integration/queue/entries/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )

    print_info(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_success("Запрос успешен!")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if data.get("success"):
            print_success(f"Message: {data.get('message')}")
            for entry in data.get("entries", []):
                print_info(f"  Queue ID: {entry.get('queue_id')}")
                print_info(f"  Number: {entry.get('number')}")
                print_info(f"  Specialist ID: {entry.get('specialist_id')}")
                print_info(f"  Queue Time: {entry.get('queue_time')}")

        return True
    else:
        print_error(f"Ошибка: {response.status_code}")
        print_error(response.text)
        return False


def test_batch_create_multiple_services(token, patient_id, specialists, services):
    """Тест: Создание нескольких услуг у разных специалистов"""
    print_section("Тест 2: Создание нескольких услуг")

    if len(specialists) < 2 or len(services) < 2:
        print_warning("Недостаточно данных для теста (нужно минимум 2 специалиста и 2 услуги)")
        return False

    payload = {
        "patient_id": patient_id,
        "source": "online",
        "services": [
            {
                "specialist_id": specialists[0].get('user_id') or specialists[0].get('id'),
                "service_id": services[0].get('id'),
                "quantity": 1
            },
            {
                "specialist_id": specialists[1].get('user_id') or specialists[1].get('id'),
                "service_id": services[1].get('id'),
                "quantity": 1
            }
        ]
    }

    print_info(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    response = requests.post(
        f"{API_BASE}/registrar-integration/queue/entries/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )

    print_info(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print_success("Запрос успешен!")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if data.get("success"):
            print_success(f"Создано записей: {len(data.get('entries', []))}")

        return True
    else:
        print_error(f"Ошибка: {response.status_code}")
        print_error(response.text)
        return False


def test_source_preservation(token, patient_id, specialist_id, service_id):
    """Тест: Проверка сохранения source='online'"""
    print_section("Тест 3: Проверка сохранения source")

    payload = {
        "patient_id": patient_id,
        "source": "online",  # ⭐ Важно: source='online'
        "services": [
            {
                "specialist_id": specialist_id,
                "service_id": service_id,
                "quantity": 1
            }
        ]
    }

    print_info(f"Создаем с source='online'")

    response = requests.post(
        f"{API_BASE}/registrar-integration/queue/entries/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )

    if response.status_code == 200:
        data = response.json()
        print_success("Запрос успешен!")
        print_info(f"Message: {data.get('message')}")
        print_warning("Проверьте в БД что source='online' сохранен")
        return True
    else:
        print_error(f"Ошибка: {response.status_code}")
        return False


def test_invalid_patient(token, specialist_id, service_id):
    """Тест: Ошибка - несуществующий пациент"""
    print_section("Тест 4: Несуществующий пациент (ожидается 404)")

    payload = {
        "patient_id": 999999,  # Несуществующий ID
        "source": "desk",
        "services": [
            {
                "specialist_id": specialist_id,
                "service_id": service_id,
                "quantity": 1
            }
        ]
    }

    response = requests.post(
        f"{API_BASE}/registrar-integration/queue/entries/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )

    if response.status_code == 404:
        print_success("Получена ожидаемая ошибка 404")
        print_info(f"Detail: {response.json().get('detail')}")
        return True
    else:
        print_error(f"Неожиданный статус: {response.status_code}")
        return False


def test_invalid_source(token, patient_id, specialist_id, service_id):
    """Тест: Ошибка - неверный source"""
    print_section("Тест 5: Неверный source (ожидается 422)")

    payload = {
        "patient_id": patient_id,
        "source": "invalid_source",  # Неверный source
        "services": [
            {
                "specialist_id": specialist_id,
                "service_id": service_id,
                "quantity": 1
            }
        ]
    }

    response = requests.post(
        f"{API_BASE}/registrar-integration/queue/entries/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )

    if response.status_code == 422:
        print_success("Получена ожидаемая ошибка 422 (validation error)")
        return True
    else:
        print_error(f"Неожиданный статус: {response.status_code}")
        return False


def main():
    """Запуск всех тестов"""
    print(f"\n{Colors.BOLD}{'#'*60}")
    print(f"# Manual Testing: Batch Queue Entries Endpoint")
    print(f"{'#'*60}{Colors.END}\n")

    print_info(f"API Base: {API_BASE}")
    print_info(f"Username: {USERNAME}")
    print_info(f"Date: {date.today()}")
    print()

    # Авторизация
    token = login()
    if not token:
        print_error("Не удалось авторизоваться. Проверьте username/password.")
        return

    # Получение данных
    patient = get_patients(token)
    if not patient:
        print_error("Не удалось получить пациента. Создайте пациента в системе.")
        return

    services = get_services(token)
    if not services:
        print_error("Не удалось получить услуги. Создайте услуги в системе.")
        return

    doctors = get_doctors(token)
    if not doctors:
        print_error("Не удалось получить специалистов. Создайте врачей в системе.")
        return

    patient_id = patient.get('id')
    specialist_id = doctors[0].get('user_id') or doctors[0].get('id')
    service_id = services[0].get('id')

    # Запуск тестов
    results = []

    results.append(("Создание одной услуги", test_batch_create_single_service(
        token, patient_id, specialist_id, service_id
    )))

    results.append(("Создание нескольких услуг", test_batch_create_multiple_services(
        token, patient_id, doctors, services
    )))

    results.append(("Сохранение source", test_source_preservation(
        token, patient_id, specialist_id, service_id
    )))

    results.append(("Несуществующий пациент", test_invalid_patient(
        token, specialist_id, service_id
    )))

    results.append(("Неверный source", test_invalid_source(
        token, patient_id, specialist_id, service_id
    )))

    # Итоговый отчет
    print_section("Итоговый отчет")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print()
    print(f"{Colors.BOLD}Результат: {passed}/{total} тестов прошло{Colors.END}")

    if passed == total:
        print_success("Все тесты прошли успешно! 🎉")
    else:
        print_warning(f"Некоторые тесты не прошли ({total - passed} failed)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем.")
    except Exception as e:
        print_error(f"Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
