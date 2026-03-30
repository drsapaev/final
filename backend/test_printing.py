#!/usr/bin/env python3
"""
Тест системы печати клиники
"""
import json
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


def test_print_ticket_pdf(token):
    """Тестируем печать билета в PDF"""
    print("\n🎫 Тестируем печать билета в PDF...")

    params = {"department": "THERAPY", "ticket_number": "001"}

    param_strings = [f"{k}={v}" for k, v in params.items()]
    print_url = f"{BASE_URL}/api/v1/print/ticket.pdf?{'&'.join(param_strings)}"

    try:
        req = urllib.request.Request(print_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_data = response.read()
                content_type = response.headers.get("Content-Type", "")

                print(f"    ✅ PDF билет получен: {len(response_data)} байт")
                print(f"    📄 Content-Type: {content_type}")
                return True
            else:
                print(f"    ❌ Ошибка получения PDF билета: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения PDF билета: {e}")
        return False


def test_print_invoice_pdf(token):
    """Тестируем печать счёта в PDF"""
    print("\n🧾 Тестируем печать счёта в PDF...")

    # Для invoice.pdf нужен visit_id, а не department и ticket_number
    params = {"visit_id": "1"}  # Используем существующий ID визита

    param_strings = [f"{k}={v}" for k, v in params.items()]
    print_url = f"{BASE_URL}/api/v1/print/invoice.pdf?{'&'.join(param_strings)}"

    try:
        req = urllib.request.Request(print_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_data = response.read()
                content_type = response.headers.get("Content-Type", "")

                print(f"    ✅ PDF счёт получен: {len(response_data)} байт")
                print(f"    📄 Content-Type: {content_type}")
                return True
            else:
                print(f"    ❌ Ошибка получения PDF счёта: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка получения PDF счёта: {e}")
        return False


def test_print_ticket_escpos(token):
    """Тестируем печать билета на принтер (ESC/POS)"""
    print("\n🖨️ Тестируем печать билета на принтер (ESC/POS)...")

    # Для ESC/POS печати параметры передаются как query parameters
    params = {"department": "THERAPY", "ticket_number": "1"}

    param_strings = [f"{k}={v}" for k, v in params.items()]
    print_url = f"{BASE_URL}/api/v1/print/ticket?{'&'.join(param_strings)}"

    try:
        req = urllib.request.Request(print_url, data=b"")  # Пустое тело для POST
        req.add_header("Authorization", f"Bearer {token}")
        req.get_method = lambda: "POST"  # Явно указываем метод POST

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                print(f"    ✅ Билет отправлен на печать: {response_text}")
                return True
            else:
                print(f"    ❌ Ошибка печати билета: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка печати билета: {e}")
        return False


def test_print_receipt_escpos(token):
    """Тестируем печать чека на принтер (ESC/POS)"""
    print("\n🧾 Тестируем печать чека на принтер (ESC/POS)...")

    # Для ESC/POS печати чека нужны visit_id, amount и currency как query parameters
    params = {"visit_id": "1", "amount": "150000", "currency": "UZS"}

    param_strings = [f"{k}={v}" for k, v in params.items()]
    print_url = f"{BASE_URL}/api/v1/print/receipt?{'&'.join(param_strings)}"

    try:
        req = urllib.request.Request(print_url, data=b"")  # Пустое тело для POST
        req.add_header("Authorization", f"Bearer {token}")
        req.get_method = lambda: "POST"  # Явно указываем метод POST

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                print(f"    ✅ Чек отправлен на печать: {response_text}")
                return True
            else:
                print(f"    ❌ Ошибка печати чека: {response.status}")
                return False
    except Exception as e:
        print(f"    ❌ Ошибка печати чека: {e}")
        return False


def test_print_unauthorized():
    """Тестируем доступ к печати без авторизации"""
    print("\n🚫 Тестируем доступ к печати без авторизации...")

    try:
        print_url = (
            f"{BASE_URL}/api/v1/print/ticket.pdf?department=THERAPY&ticket_number=001"
        )

        req = urllib.request.Request(print_url)

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


def main():
    """Основная функция тестирования"""
    print("🚀 Тест системы печати клиники")
    print("=" * 80)

    # Получаем токен авторизации
    token = get_auth_token()
    if not token:
        print("❌ Тест прерван: не удалось получить токен")
        return

    # Запускаем все тесты
    tests = [
        ("Печать билета в PDF", lambda: test_print_ticket_pdf(token)),
        ("Печать счёта в PDF", lambda: test_print_invoice_pdf(token)),
        ("Печать билета на принтер", lambda: test_print_ticket_escpos(token)),
        ("Печать чека на принтер", lambda: test_print_receipt_escpos(token)),
        ("Доступ без авторизации", test_print_unauthorized),
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
    print("🖨️ ИТОГИ ТЕСТИРОВАНИЯ СИСТЕМЫ ПЕЧАТИ:")

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
