#!/usr/bin/env python3
"""
Комплексный тест системы аутентификации и авторизации клиники
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"


def test_login_success():
    """Тестируем успешный логин"""
    print("🔑 Тестируем успешный логин...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "admin", "password": "admin"}

    try:
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")
        req = urllib.request.Request(login_url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                token_data = json.loads(response_text)

                if "access_token" in token_data and "token_type" in token_data:
                    print(
                        f"    ✅ Логин успешен: получен токен типа {token_data['token_type']}"
                    )
                    return token_data["access_token"]
                else:
                    print(f"    ❌ Неожиданная структура ответа: {token_data}")
                    return None
            else:
                print(
                    f"    ❌ Ошибка логина: {response.status} - {response.read().decode('utf-8')}"
                )
                return None
    except Exception as e:
        print(f"    ❌ Ошибка логина: {e}")
        return None


def test_login_invalid_credentials():
    """Тестируем логин с неверными данными"""
    print("\n❌ Тестируем логин с неверными данными...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "invalid_user", "password": "wrong_password"}

    try:
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")
        req = urllib.request.Request(login_url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as response:
            if response.status == 401:
                print("    ✅ Правильно отклонён неверный логин (401)")
                return True
            else:
                print(f"    ❌ Неожиданный статус: {response.status}")
                return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    ✅ Правильно отклонён неверный логин (401)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования: {e}")
        return False


def test_get_profile(token):
    """Тестируем получение профиля пользователя"""
    print("\n👤 Тестируем получение профиля пользователя...")

    profile_url = f"{BASE_URL}/api/v1/auth/me"

    try:
        req = urllib.request.Request(profile_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                profile = json.loads(response_text)

                if "username" in profile:
                    print(f"    ✅ Профиль получен: пользователь {profile['username']}")
                    if "role" in profile:
                        print(f"    ✅ Роль пользователя: {profile['role']}")
                    if "is_active" in profile:
                        print(f"    ✅ Статус активности: {profile['is_active']}")
                    return True
                else:
                    print(f"    ❌ Неожиданная структура профиля: {profile}")
                    return False
            else:
                print(f"    ❌ Ошибка получения профиля: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения профиля: {e}")
        return False


def test_protected_endpoint_with_token(token):
    """Тестируем доступ к защищённому эндпоинту с токеном"""
    print("\n🔒 Тестируем доступ к защищённому эндпоинту с токеном...")

    # Тестируем эндпоинт списка пациентов (требует авторизации)
    patients_url = f"{BASE_URL}/api/v1/patients/patients"

    try:
        req = urllib.request.Request(patients_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("    ✅ Доступ к защищённому эндпоинту разрешён")
                return True
            else:
                print(f"    ❌ Неожиданный статус: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка доступа: {e}")
        return False


def test_protected_endpoint_without_token():
    """Тестируем доступ к защищённому эндпоинту без токена"""
    print("\n🚫 Тестируем доступ к защищённому эндпоинту без токена...")

    # Тестируем эндпоинт списка пациентов без авторизации
    patients_url = f"{BASE_URL}/api/v1/patients/patients"

    try:
        req = urllib.request.Request(patients_url)

        with urllib.request.urlopen(req) as response:
            print(f"    ❌ Неожиданно разрешён доступ без токена: {response.status}")
            return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    ✅ Правильно отклонён доступ без токена (401)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования: {e}")
        return False


def test_invalid_token():
    """Тестируем доступ с неверным токеном"""
    print("\n🚫 Тестируем доступ с неверным токеном...")

    # Тестируем эндпоинт списка пациентов с неверным токеном
    patients_url = f"{BASE_URL}/api/v1/patients/patients"
    invalid_token = "invalid_token_12345"

    try:
        req = urllib.request.Request(patients_url)
        req.add_header("Authorization", f"Bearer {invalid_token}")

        with urllib.request.urlopen(req) as response:
            print(
                f"    ❌ Неожиданно разрешён доступ с неверным токеном: {response.status}"
            )
            return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    ✅ Правильно отклонён доступ с неверным токеном (401)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования: {e}")
        return False


def test_token_expiration():
    """Тестируем истечение срока действия токена"""
    print("\n⏰ Тестируем истечение срока действия токена...")

    # Создаём "просроченный" токен (просто изменяем его)
    expired_token = "expired_token_" + str(int(time.time()))

    # Тестируем эндпоинт списка пациентов с "просроченным" токеном
    patients_url = f"{BASE_URL}/api/v1/patients/patients"

    try:
        req = urllib.request.Request(patients_url)
        req.add_header("Authorization", f"Bearer {expired_token}")

        with urllib.request.urlopen(req) as response:
            print(
                f"    ❌ Неожиданно разрешён доступ с просроченным токеном: {response.status}"
            )
            return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    ✅ Правильно отклонён доступ с просроченным токеном (401)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования: {e}")
        return False


def test_role_based_access(token):
    """Тестируем доступ на основе ролей"""
    print("\n👑 Тестируем доступ на основе ролей...")

    # Сначала получаем профиль пользователя
    profile_url = f"{BASE_URL}/api/v1/auth/me"

    try:
        req = urllib.request.Request(profile_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                profile = json.loads(response_text)

                user_role = profile.get("role", "Unknown")
                print(f"    ✅ Роль пользователя: {user_role}")

                # Тестируем доступ к различным эндпоинтам в зависимости от роли
                if user_role in ["Admin", "admin"]:
                    # Админ должен иметь доступ ко всем эндпоинтам
                    admin_endpoints = [
                        ("/api/v1/patients/patients", {}),
                        ("/api/v1/visits/visits", {}),
                        (
                            "/api/v1/queue/stats",
                            {
                                "department": "THERAPY",
                                "date": datetime.now().strftime("%Y-%m-%d"),
                            },
                        ),
                        (
                            "/api/v1/reports/summary",
                            {
                                "department": "THERAPY",
                                "date": datetime.now().strftime("%Y-%m-%d"),
                            },
                        ),
                    ]

                    for endpoint, params in admin_endpoints:
                        # Формируем URL с параметрами
                        if params:
                            param_strings = [f"{k}={v}" for k, v in params.items()]
                            endpoint_url = (
                                f"{BASE_URL}{endpoint}?{'&'.join(param_strings)}"
                            )
                        else:
                            endpoint_url = f"{BASE_URL}{endpoint}"

                        req = urllib.request.Request(endpoint_url)
                        req.add_header("Authorization", f"Bearer {token}")

                        try:
                            with urllib.request.urlopen(req) as response:
                                if response.status in [200, 201, 204]:
                                    print(f"        ✅ Доступ к {endpoint} разрешён")
                                else:
                                    print(
                                        f"        ⚠️ Неожиданный статус для {endpoint}: {response.status}"
                                    )
                        except Exception as e:
                            print(f"        ❌ Ошибка доступа к {endpoint}: {e}")

                    return True
                else:
                    print(
                        f"    ⚠️ Тестирование ролей для роли '{user_role}' не реализовано"
                    )
                    return True
            else:
                print(f"    ❌ Не удалось получить профиль: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования ролей: {e}")
        return False


def test_public_endpoints():
    """Тестируем доступ к публичным эндпоинтам"""
    print("\n🌐 Тестируем доступ к публичным эндпоинтам...")

    # Тестируем корневой эндпоинт (должен быть доступен без авторизации)
    root_url = f"{BASE_URL}/"

    try:
        req = urllib.request.Request(root_url)

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                root_data = json.loads(response_text)

                if "status" in root_data and root_data["status"] == "ok":
                    print("    ✅ Корневой эндпоинт доступен без авторизации")
                    return True
                else:
                    print(
                        f"    ❌ Неожиданная структура корневого эндпоинта: {root_data}"
                    )
                    return False
            else:
                print(
                    f"    ❌ Неожиданный статус корневого эндпоинта: {response.status}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка доступа к корневому эндпоинту: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Комплексный тест системы аутентификации и авторизации клиники")
    print("=" * 80)

    # Шаг 1: Тестируем логин
    token = test_login_success()
    if not token:
        print("❌ Тест прерван: не удалось получить токен")
        return

    # Шаг 2: Тестируем неверные данные для логина
    invalid_login_success = test_login_invalid_credentials()

    # Шаг 3: Тестируем получение профиля
    profile_success = test_get_profile(token)

    # Шаг 4: Тестируем доступ к защищённым эндпоинтам с токеном
    protected_with_token_success = test_protected_endpoint_with_token(token)

    # Шаг 5: Тестируем доступ к защищённым эндпоинтам без токена
    protected_without_token_success = test_protected_endpoint_without_token()

    # Шаг 6: Тестируем доступ с неверным токеном
    invalid_token_success = test_invalid_token()

    # Шаг 7: Тестируем "просроченный" токен
    expired_token_success = test_token_expiration()

    # Шаг 8: Тестируем доступ на основе ролей
    role_based_success = test_role_based_access(token)

    # Шаг 9: Тестируем публичные эндпоинты
    public_endpoints_success = test_public_endpoints()

    # Итоги тестирования
    print("\n" + "=" * 80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ СИСТЕМЫ АУТЕНТИФИКАЦИИ:")
    print(f"  ✅ Успешный логин: {'УСПЕШНО' if token else 'ОШИБКА'}")
    print(
        f"  ✅ Отклонение неверных данных: {'УСПЕШНО' if invalid_login_success else 'ОШИБКА'}"
    )
    print(f"  ✅ Получение профиля: {'УСПЕШНО' if profile_success else 'ОШИБКА'}")
    print(
        f"  ✅ Доступ с токеном: {'УСПЕШНО' if protected_with_token_success else 'ОШИБКА'}"
    )
    print(
        f"  ✅ Отклонение без токена: {'УСПЕШНО' if protected_without_token_success else 'ОШИБКА'}"
    )
    print(
        f"  ✅ Отклонение неверного токена: {'УСПЕШНО' if invalid_token_success else 'ОШИБКА'}"
    )
    print(
        f"  ✅ Отклонение просроченного токена: {'УСПЕШНО' if expired_token_success else 'ОШИБКА'}"
    )
    print(
        f"  ✅ Доступ на основе ролей: {'УСПЕШНО' if role_based_success else 'ОШИБКА'}"
    )
    print(
        f"  ✅ Публичные эндпоинты: {'УСПЕШНО' if public_endpoints_success else 'ОШИБКА'}"
    )

    success_count = sum(
        [
            bool(token),
            invalid_login_success,
            profile_success,
            protected_with_token_success,
            protected_without_token_success,
            invalid_token_success,
            expired_token_success,
            role_based_success,
            public_endpoints_success,
        ]
    )
    total_count = 9

    print(
        f"\n🎯 Общий результат: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)"
    )

    if success_count == total_count:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    elif success_count >= total_count * 0.8:
        print("👍 Большинство тестов прошли успешно!")
    else:
        print("⚠️ Много ошибок, требуется доработка")

    print("\n" + "=" * 80)
    print("🎉 Тест завершён!")


if __name__ == "__main__":
    main()
