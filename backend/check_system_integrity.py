"""
Скрипт для проверки целостности системы ролей и маршрутизации
Запускать перед каждым деплоем или после изменений в системе авторизации
"""

import sqlite3
import sys
from pathlib import Path

import requests


def check_database_roles():
    """Проверяет роли в базе данных"""
    print("Проверка ролей в базе данных...")

    try:
        conn = sqlite3.connect("clinic.db")
        cursor = conn.cursor()

        # Проверяем критические роли
        critical_users = [
            "admin",
            "registrar",
            "lab",
            "doctor",
            "cashier",
            "cardio",
            "derma",
            "dentist",
        ]

        for username in critical_users:
            cursor.execute(
                "SELECT role, is_active FROM users WHERE username = ?", (username,)
            )
            result = cursor.fetchone()

            if not result:
                print(f"ОШИБКА: Пользователь {username} не найден в базе данных")
                return False

            role, is_active = result
            if not is_active:
                print(f"ОШИБКА: Пользователь {username} неактивен")
                return False

            print(f"OK: {username}: роль '{role}', активен")

        conn.close()
        return True

    except Exception as e:
        print(f"ОШИБКА: Ошибка при проверке базы данных: {e}")
        return False


def check_api_endpoints():
    """Проверяет доступность API endpoints"""
    print("\nПроверка API endpoints...")

    try:
        # Получаем токен админа
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/auth/login",
            data={
                "username": "admin",
                "password": "admin123",
                "grant_type": "password",
            },
        )

        if response.status_code != 200:
            print("ОШИБКА: Не удалось получить токен админа")
            return False

        token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        # Проверяем специализированные endpoints
        endpoints = [
            ("/api/v1/cardio/ecg", "Cardio API"),
            ("/api/v1/derma/examinations", "Derma API"),
            ("/api/v1/dental/examinations", "Dental API"),
            ("/api/v1/lab/tests", "Lab API"),
        ]

        for endpoint, name in endpoints:
            try:
                response = requests.get(
                    f"http://127.0.0.1:8000{endpoint}", headers=headers
                )
                if response.status_code in [200, 404]:  # 404 нормально, если нет данных
                    print(f"OK: {name}: доступен")
                else:
                    print(f"ОШИБКА: {name}: ошибка {response.status_code}")
                    return False
            except Exception as e:
                print(f"ОШИБКА: {name}: исключение {e}")
                return False

        return True

    except Exception as e:
        print(f"ОШИБКА: Ошибка при проверке API: {e}")
        return False


def check_frontend_files():
    """Проверяет критические файлы frontend"""
    print("\nПроверка файлов frontend...")

    frontend_path = Path("../frontend/src")
    if not frontend_path.exists():
        print("ОШИБКА: Папка frontend не найдена")
        return False

    critical_files = [
        "App.jsx",
        "pages/Login.jsx",
        "pages/UserSelect.jsx",
        "pages/CardiologistPanelUnified.jsx",
        "pages/DermatologistPanelUnified.jsx",
        "pages/DentistPanelUnified.jsx",
    ]

    for file_path in critical_files:
        full_path = frontend_path / file_path
        if not full_path.exists():
            print(f"ОШИБКА: Файл {file_path} не найден")
            return False
        print(f"OK: {file_path}: существует")

    return True


def check_role_consistency():
    """Проверяет консистентность ролей между frontend и backend"""
    print("\nПроверка консистентности ролей...")

    # Проверяем, что все критические роли определены
    expected_roles = [
        "Admin",
        "Registrar",
        "Lab",
        "Doctor",
        "Cashier",
        "cardio",
        "derma",
        "dentist",
    ]

    try:
        conn = sqlite3.connect("clinic.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT role FROM users WHERE role IS NOT NULL")
        db_roles = {row[0] for row in cursor.fetchall()}
        conn.close()

        missing_roles = set(expected_roles) - db_roles
        if missing_roles:
            print(f"ОШИБКА: Отсутствующие роли в БД: {missing_roles}")
            return False

        extra_roles = db_roles - set(expected_roles)
        if extra_roles:
            print(f"ВНИМАНИЕ: Дополнительные роли в БД: {extra_roles}")

        print("OK: Все критические роли присутствуют в БД")
        return True

    except Exception as e:
        print(f"ОШИБКА: Ошибка при проверке консистентности: {e}")
        return False


def main():
    """Основная функция проверки"""
    print("Проверка целостности системы ролей и маршрутизации")
    print("=" * 70)

    checks = [
        ("База данных", check_database_roles),
        ("API endpoints", check_api_endpoints),
        ("Frontend файлы", check_frontend_files),
        ("Консистентность ролей", check_role_consistency),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"ОШИБКА: Ошибка при проверке {name}: {e}")
            results.append((name, False))

    # Итоги
    print("\nРЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print("=" * 70)

    passed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status} {name}")
        if result:
            passed += 1

    print(f"\nИтого: {passed}/{len(results)} проверок прошли успешно")

    if passed == len(results):
        print("УСПЕХ: СИСТЕМА ЦЕЛОСТНА! Все проверки прошли успешно.")
        return True
    else:
        print("ВНИМАНИЕ: ЕСТЬ ПРОБЛЕМЫ! Требуется исправление перед деплоем.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
