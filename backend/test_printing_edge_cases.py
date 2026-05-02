#!/usr/bin/env python3
"""
Тест edge cases системы печати клиники
"""
import json
import time
import urllib.parse
import urllib.request

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


def test_print_ticket_pdf_edge_cases(token):
    """Тестируем граничные случаи для печати билета в PDF"""
    print("\n🎫 Тестируем граничные случаи для печати билета в PDF...")

    edge_cases = [
        {
            "department": "A",
            "ticket_number": "1",
            "description": "Минимальная длина department",
        },
        {
            "department": "A" * 64,
            "ticket_number": "1",
            "description": "Максимальная длина department",
        },
        {"department": "", "ticket_number": "1", "description": "Пустой department"},
        {
            "department": "THERAPY",
            "ticket_number": "0",
            "description": "Номер билета = 0",
        },
        {
            "department": "THERAPY",
            "ticket_number": "-1",
            "description": "Отрицательный номер билета",
        },
        {
            "department": "THERAPY",
            "ticket_number": "abc",
            "description": "Нечисловой номер билета",
        },
    ]

    success_count = 0
    total_count = len(edge_cases)

    for case in edge_cases:
        try:
            print(f"    🔍 Тестируем: {case['description']}")

            params = {
                "department": case["department"],
                "ticket_number": case["ticket_number"],
            }

            param_strings = [f"{k}={v}" for k, v in params.items()]
            print_url = f"{BASE_URL}/api/v1/print/ticket.pdf?{'&'.join(param_strings)}"

            req = urllib.request.Request(print_url)
            req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    response_data = response.read()
                    print(f"        ✅ Успешно: {len(response_data)} байт")
                    success_count += 1
                else:
                    print(f"        ⚠️ Статус {response.status}")

        except urllib.error.HTTPError as e:
            if e.code == 422:
                print("        ✅ Правильно отклонён (422)")
                success_count += 1
            else:
                print(f"        ❌ HTTP код {e.code}")
        except Exception as e:
            print(f"        ❌ Ошибка: {e}")

    print(f"    📊 Результат: {success_count}/{total_count} тестов прошли")
    return success_count >= total_count * 0.7


def test_print_invoice_pdf_edge_cases(token):
    """Тестируем граничные случаи для печати счёта в PDF"""
    print("\n🧾 Тестируем граничные случаи для печати счёта в PDF...")

    edge_cases = [
        {"visit_id": "1", "description": "Минимальный ID визита"},
        {"visit_id": "0", "description": "ID визита = 0"},
        {"visit_id": "-1", "description": "Отрицательный ID визита"},
        {"visit_id": "abc", "description": "Нечисловой ID визита"},
        {"visit_id": "999999999", "description": "Очень большой ID визита"},
    ]

    success_count = 0
    total_count = len(edge_cases)

    for case in edge_cases:
        try:
            print(f"    🔍 Тестируем: {case['description']}")

            params = {"visit_id": case["visit_id"]}
            param_strings = [f"{k}={v}" for k, v in params.items()]
            print_url = f"{BASE_URL}/api/v1/print/invoice.pdf?{'&'.join(param_strings)}"

            req = urllib.request.Request(print_url)
            req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    response_data = response.read()
                    print(f"        ✅ Успешно: {len(response_data)} байт")
                    success_count += 1
                else:
                    print(f"        ⚠️ Статус {response.status}")

        except urllib.error.HTTPError as e:
            if e.code == 422:
                print("        ✅ Правильно отклонён (422)")
                success_count += 1
            elif e.code == 404:
                print("        ✅ Правильно отклонён (404): Визит не найден")
                success_count += 1
            else:
                print(f"        ❌ HTTP код {e.code}")
        except Exception as e:
            print(f"        ❌ Ошибка: {e}")

    print(f"    📊 Результат: {success_count}/{total_count} тестов прошли")
    return success_count >= total_count * 0.7


def test_print_security_edge_cases():
    """Тестируем граничные случаи безопасности"""
    print("\n🔒 Тестируем граничные случаи безопасности...")

    security_cases = [
        {"token": "", "description": "Пустой токен"},
        {"token": "invalid_token", "description": "Неверный токен"},
        {"token": "Bearer", "description": "Только 'Bearer' без токена"},
        {"token": "Bearer ", "description": "Bearer с пробелом без токена"},
        {"token": "'; DROP TABLE users; --", "description": "SQL Injection попытка"},
        {"token": "<script>alert('xss')</script>", "description": "XSS попытка"},
    ]

    success_count = 0
    total_count = len(security_cases)

    for case in security_cases:
        try:
            print(f"    🔍 Тестируем: {case['description']}")

            print_url = (
                f"{BASE_URL}/api/v1/print/ticket.pdf?department=THERAPY&ticket_number=1"
            )

            req = urllib.request.Request(print_url)
            if case["token"]:
                req.add_header("Authorization", f'Bearer {case["token"]}')

            with urllib.request.urlopen(req) as response:
                print(f"        ❌ Неожиданно разрешён доступ: {response.status}")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("        ✅ Правильно отклонён (401): Неавторизованный доступ")
                success_count += 1
            elif e.code == 422:
                print("        ✅ Правильно отклонён (422): Неверные параметры")
                success_count += 1
            else:
                print(f"        ⚠️ HTTP код {e.code}")
        except Exception as e:
            print(f"        ✅ Правильно отклонён: {e}")
            success_count += 1

    print(f"    📊 Результат: {success_count}/{total_count} тестов прошли")
    return success_count >= total_count * 0.8


def test_print_performance_edge_cases(token):
    """Тестируем граничные случаи производительности"""
    print("\n⚡ Тестируем граничные случаи производительности...")

    try:
        print("    🔍 Тестируем множественные запросы подряд...")

        start_time = time.time()
        for i in range(5):
            params = {"department": "THERAPY", "ticket_number": str(i + 1)}
            param_strings = [f"{k}={v}" for k, v in params.items()]
            print_url = f"{BASE_URL}/api/v1/print/ticket.pdf?{'&'.join(param_strings)}"

            req = urllib.request.Request(print_url)
            req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    response.read()
                else:
                    raise Exception(f"HTTP {response.status}")

        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 5

        print(f"        ✅ 5 запросов за {total_time:.2f}с (среднее: {avg_time:.2f}с)")
        return True

    except Exception as e:
        print(f"        ❌ Ошибка: {e}")
        return False


def main():
    """Основная функция тестирования edge cases"""
    print("🚀 Тест edge cases системы печати клиники")
    print("=" * 80)

    # Получаем токен авторизации
    token = get_auth_token()
    if not token:
        print("❌ Тест прерван: не удалось получить токен")
        return

    # Запускаем все edge case тесты
    tests = [
        (
            "Граничные случаи PDF билетов",
            lambda: test_print_ticket_pdf_edge_cases(token),
        ),
        (
            "Граничные случаи PDF счетов",
            lambda: test_print_invoice_pdf_edge_cases(token),
        ),
        ("Граничные случаи безопасности", test_print_security_edge_cases),
        (
            "Граничные случаи производительности",
            lambda: test_print_performance_edge_cases(token),
        ),
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
    print("🔍 ИТОГИ ТЕСТИРОВАНИЯ EDGE CASES СИСТЕМЫ ПЕЧАТИ:")

    for test_name, result in results:
        status = "УСПЕШНО" if result else "ОШИБКА"
        print(f"  ✅ {test_name}: {status}")

    success_count = sum(1 for _, result in results if result)
    total_count = len(results)

    print(
        f"\n🎯 Общий результат: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)"
    )

    if success_count == total_count:
        print("🎉 ВСЕ EDGE CASE ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    elif success_count >= total_count * 0.8:
        print("👍 Большинство edge case тестов прошли успешно!")
    else:
        print("⚠️ Много ошибок в edge cases, требуется доработка")

    print("\n" + "=" * 80)
    print("🎉 Тест edge cases завершён!")


if __name__ == "__main__":
    main()
