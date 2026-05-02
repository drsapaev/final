#!/usr/bin/env python3
"""
Комплексный тест системы отчётности клиники
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:18000"


def get_auth_token():
    """Получаем токен авторизации"""
    print("🔑 Получаем токен авторизации...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "admin", "password": "admin123"}

    try:
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")
        req = urllib.request.Request(login_url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                token_data = json.loads(response_text)
                token = token_data["access_token"]
                print("✅ Токен получен")
                return token
            else:
                print(f"❌ Ошибка получения токена: {response.read().decode('utf-8')}")
                return None
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return None


def test_reports_summary_basic(token):
    """Тестируем базовый отчёт по сводке"""
    print("\n📊 Тестируем базовый отчёт по сводке...")

    # Базовые параметры для отчёта (используем правильные параметры)
    today = datetime.now().strftime("%Y-%m-%d")
    params = {"from": today, "to": today}

    param_strings = [f"{k}={v}" for k, v in params.items()]
    reports_url = f"{BASE_URL}/api/v1/reports/summary?{'&'.join(param_strings)}"

    try:
        req = urllib.request.Request(reports_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                report_data = json.loads(response_text)

                print(f"    ✅ Отчёт получен: {len(response_text)} символов")

                # Проверяем структуру отчёта
                if isinstance(report_data, dict):
                    print("    ✅ Структура отчёта корректна (JSON объект)")

                    # Выводим ключи отчёта для анализа
                    if report_data:
                        print(f"    📋 Ключи отчёта: {list(report_data.keys())}")
                    else:
                        print("    ⚠️ Отчёт пустой (нет данных)")

                    return True
                else:
                    print(f"    ❌ Неожиданная структура отчёта: {type(report_data)}")
                    return False
            else:
                print(f"    ❌ Ошибка получения отчёта: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения отчёта: {e}")
        return False


def test_reports_summary_different_departments(token):
    """Тестируем отчёты для разных периодов"""
    print("\n📅 Тестируем отчёты для разных периодов...")

    periods = [
        (
            "сегодня",
            datetime.now().strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d"),
        ),
        (
            "вчера",
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        ),
        (
            "неделя",
            (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d"),
        ),
        (
            "месяц",
            (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            datetime.now().strftime("%Y-%m-%d"),
        ),
    ]

    success_count = 0

    for period_name, date_from, date_to in periods:
        try:
            reports_url = (
                f"{BASE_URL}/api/v1/reports/summary?from={date_from}&to={date_to}"
            )

            req = urllib.request.Request(reports_url)
            req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"        ✅ Отчёт за {period_name}: получен")
                    success_count += 1
                else:
                    print(f"        ⚠️ Отчёт за {period_name}: статус {response.status}")

        except Exception as e:
            print(f"        ❌ Ошибка отчёта за {period_name}: {e}")

    print(f"    📊 Успешно получено отчётов: {success_count}/{len(periods)}")
    return success_count > 0


def test_reports_summary_different_dates(token):
    """Тестируем отчёты для разных дат"""
    print("\n📅 Тестируем отчёты для разных дат...")

    dates = [
        datetime.now().strftime("%Y-%m-%d"),  # Сегодня
        (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),  # Вчера
        (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),  # Неделю назад
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),  # Месяц назад
    ]

    success_count = 0

    for date in dates:
        try:
            reports_url = f"{BASE_URL}/api/v1/reports/summary?from={date}&to={date}"

            req = urllib.request.Request(reports_url)
            req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"        ✅ Отчёт за {date}: получен")
                    success_count += 1
                else:
                    print(f"        ⚠️ Отчёт за {date}: статус {response.status}")

        except Exception as e:
            print(f"        ❌ Ошибка отчёта за {date}: {e}")

    print(f"    📊 Успешно получено отчётов: {success_count}/{len(dates)}")
    return success_count > 0


def test_reports_summary_missing_parameters(token):
    """Тестируем отчёты с отсутствующими параметрами"""
    print("\n⚠️ Тестируем отчёты с отсутствующими параметрами...")

    # Тест без параметра 'from'
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        reports_url = f"{BASE_URL}/api/v1/reports/summary?to={today}"

        req = urllib.request.Request(reports_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 422:
                print("    ✅ Правильно отклонён запрос без параметра 'from' (422)")
                return True
            else:
                print(
                    f"    ❌ Неожиданный статус без параметра 'from': {response.status}"
                )
                return False
    except urllib.error.HTTPError as e:
        if e.code == 422:
            print("    ✅ Правильно отклонён запрос без параметра 'from' (422)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код без параметра 'from': {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования без параметра 'from': {e}")
        return False


def test_reports_summary_invalid_parameters(token):
    """Тестируем отчёты с неверными параметрами"""
    print("\n❌ Тестируем отчёты с неверными параметрами...")

    # Тест с неверным форматом даты
    try:
        reports_url = (
            f"{BASE_URL}/api/v1/reports/summary?from=invalid-date&to=2025-08-29"
        )

        req = urllib.request.Request(reports_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 422:
                print("    ✅ Правильно отклонён запрос с неверным форматом даты (422)")
                return True
            else:
                print(
                    f"    ❌ Неожиданный статус с неверным форматом даты: {response.status}"
                )
                return False
    except urllib.error.HTTPError as e:
        if e.code == 422:
            print("    ✅ Правильно отклонён запрос с неверным форматом даты (422)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код с неверным форматом даты: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования с неверным форматом даты: {e}")
        return False


def test_reports_summary_unauthorized():
    """Тестируем доступ к отчётам без авторизации"""
    print("\n🚫 Тестируем доступ к отчётам без авторизации...")

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        reports_url = f"{BASE_URL}/api/v1/reports/summary?from={today}&to={today}"

        req = urllib.request.Request(reports_url)

        with urllib.request.urlopen(req) as response:
            print(f"    ❌ Неожиданно разрешён доступ без токена: {response.status}")
            return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    ✅ Правильно отклонён доступ без токена (401)")
            return True
        else:
            print(f"    ❌ Неожиданный HTTP код без токена: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования без токена: {e}")
        return False


def test_reports_summary_invalid_token():
    """Тестируем доступ к отчётам с неверным токеном"""
    print("\n🚫 Тестируем доступ к отчётам с неверным токеном...")

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        reports_url = f"{BASE_URL}/api/v1/reports/summary?from={today}&to={today}"
        invalid_token = "invalid_token_12345"

        req = urllib.request.Request(reports_url)
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
            print(f"    ❌ Неожиданный HTTP код с неверным токеном: {e.code}")
            return False
    except Exception as e:
        print(f"    ❌ Ошибка тестирования с неверным токеном: {e}")
        return False


def test_reports_summary_data_analysis(token):
    """Тестируем анализ данных отчёта"""
    print("\n🔍 Тестируем анализ данных отчёта...")

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        reports_url = f"{BASE_URL}/api/v1/reports/summary?from={today}&to={today}"

        req = urllib.request.Request(reports_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                report_data = json.loads(response_text)

                print("    📊 Анализ структуры отчёта:")

                # Анализируем структуру отчёта
                if isinstance(report_data, dict):
                    for key, value in report_data.items():
                        if isinstance(value, (int, float)):
                            print(f"        📈 {key}: {value} (числовое значение)")
                        elif isinstance(value, str):
                            print(f"        📝 {key}: {value} (текстовое значение)")
                        elif isinstance(value, list):
                            print(f"        📋 {key}: список из {len(value)} элементов")
                        elif isinstance(value, dict):
                            print(f"        🗂️ {key}: объект с {len(value)} полями")
                        else:
                            print(f"        ❓ {key}: {type(value).__name__}")

                    return True
                else:
                    print(f"    ❌ Отчёт не является объектом: {type(report_data)}")
                    return False
            else:
                print(
                    f"    ❌ Не удалось получить отчёт для анализа: {response.status}"
                )
                return False
    except Exception as e:
        print(f"    ❌ Ошибка анализа отчёта: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Комплексный тест системы отчётности клиники")
    print("=" * 80)

    # Получаем токен авторизации
    token = get_auth_token()
    if not token:
        print("❌ Тест прерван: не удалось получить токен")
        return

    # Запускаем все тесты
    tests = [
        ("Базовый отчёт по сводке", lambda: test_reports_summary_basic(token)),
        (
            "Отчёты для разных периодов",
            lambda: test_reports_summary_different_departments(token),
        ),
        ("Отчёты для разных дат", lambda: test_reports_summary_different_dates(token)),
        (
            "Отчёты с отсутствующими параметрами",
            lambda: test_reports_summary_missing_parameters(token),
        ),
        (
            "Отчёты с неверными параметрами",
            lambda: test_reports_summary_invalid_parameters(token),
        ),
        ("Доступ без авторизации", test_reports_summary_unauthorized),
        ("Доступ с неверным токеном", test_reports_summary_invalid_token),
        ("Анализ данных отчёта", lambda: test_reports_summary_data_analysis(token)),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))

    # Итоги тестирования
    print("\n" + "=" * 80)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ СИСТЕМЫ ОТЧЁТНОСТИ:")

    for test_name, result in results:
        status = "УСПЕШНО" if result else "ОШИБКА"
        print(f"  ✅ {test_name}: {status}")

    success_count = sum(1 for _, result in results if result)
    total_count = len(results)

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
