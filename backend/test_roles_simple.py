"""
Упрощенные тесты системы ролей (без эмодзи для Windows)
"""

import json
import sys

import requests

BASE_URL = "http://127.0.0.1:8000"


def test_user_login(username, password, expected_role):
    """Тестирует логин пользователя"""
    print(f"Тестируем пользователя: {username}")

    try:
        # Логин
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": username, "password": password, "grant_type": "password"},
        )

        if response.status_code != 200:
            print(f"FAIL: {username} - логин не удался")
            return False

        token = response.json().get("access_token")
        if not token:
            print(f"FAIL: {username} - токен не получен")
            return False

        # Получение профиля
        profile_response = requests.get(
            f"{BASE_URL}/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

        if profile_response.status_code != 200:
            print(f"FAIL: {username} - профиль не получен")
            return False

        profile = profile_response.json()
        actual_role = profile.get("role")

        if actual_role != expected_role:
            print(f"FAIL: {username} - неправильная роль: {actual_role}")
            return False

        print(f"PASS: {username} - роль {actual_role}")
        return True

    except Exception as e:
        print(f"ERROR: {username} - {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("Тестирование системы ролей")
    print("=" * 50)

    # Критические пользователи
    users = [
        ("admin", "admin123", "Admin"),
        ("registrar", "registrar123", "Registrar"),
        ("lab", "lab123", "Lab"),
        ("doctor", "doctor123", "Doctor"),
        ("cashier", "cashier123", "Cashier"),
        ("cardio", "cardio123", "cardio"),
        ("derma", "derma123", "derma"),
        ("dentist", "dentist123", "dentist"),
    ]

    results = []
    for username, password, expected_role in users:
        result = test_user_login(username, password, expected_role)
        results.append((username, result))

    # Итоги
    print("\nРЕЗУЛЬТАТЫ:")
    print("=" * 50)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for username, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status}: {username}")

    print(f"\nИтого: {passed}/{total} тестов прошли")

    if passed == total:
        print("ВСЕ ТЕСТЫ ПРОШЛИ!")
        return True
    else:
        print("ЕСТЬ ПРОБЛЕМЫ!")
        return False


if __name__ == "__main__":
    # Проверяем сервер
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health")
        if response.status_code != 200:
            print("Сервер недоступен")
            sys.exit(1)
    except:
        print("Сервер недоступен")
        sys.exit(1)

    success = main()
    sys.exit(0 if success else 1)
