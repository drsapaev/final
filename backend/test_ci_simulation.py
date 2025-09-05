#!/usr/bin/env python3
"""
Симуляция CI/CD тестов для проверки работоспособности
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path


def run_command(cmd, description):
    """Запускает команду и возвращает результат"""
    print(f"Выполняем: {description}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd="."
        )
        if result.returncode == 0:
            print(f"OK: {description}: OK")
            if result.stdout:
                print(f"  Вывод: {result.stdout.strip()}")
            return True
        else:
            print(f"ERROR: {description}: FAILED")
            if result.stderr:
                print(f"  Ошибка: {result.stderr.strip()}")
            if result.stdout:
                print(f"  Вывод: {result.stdout.strip()}")
            return False
    except Exception as e:
        print(f"ERROR: {description}: ERROR - {e}")
        return False


def test_ci_simulation():
    """Симулирует CI/CD процесс"""
    print("СИМУЛЯЦИЯ CI/CD ТЕСТОВ")
    print("=" * 50)

    # Устанавливаем переменные окружения как в CI
    os.environ["DATABASE_URL"] = "sqlite:///./test_clinic.db"
    os.environ["CORS_DISABLE"] = "1"
    os.environ["WS_DEV_ALLOW"] = "1"

    success = True

    # 1. Установка зависимостей
    if not run_command("pip install -r requirements.txt", "Установка зависимостей"):
        success = False

    if not run_command(
        "pip install requests argon2-cffi", "Установка дополнительных зависимостей"
    ):
        success = False

    # 2. Создание тестовой базы данных
    if not run_command(
        "python -c \"from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine); print('База данных создана')\"",
        "Создание тестовой БД",
    ):
        success = False

    # 3. Создание тестовых пользователей
    if not run_command(
        "python reset_all_passwords.py", "Создание тестовых пользователей"
    ):
        success = False

    # 4. Запуск сервера
    print("\nЗапуск тестового сервера...")
    server_process = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Ждем запуска сервера
    time.sleep(10)

    # Проверяем доступность сервера
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("OK: Сервер запущен и доступен")
        else:
            print(f"ERROR: Сервер недоступен: {response.status_code}")
            success = False
    except Exception as e:
        print(f"ERROR: Сервер недоступен: {e}")
        success = False

    if success:
        # 5. Запуск тестов
        if not run_command("python test_role_routing.py", "Тесты системы ролей"):
            success = False

        if not run_command("python check_system_integrity.py", "Проверка целостности"):
            success = False

        if not run_command(
            "python -c \"from app.core.role_validation import validate_critical_user_roles; print('OK: Role validation passed' if validate_critical_user_roles() else 'ERROR: Role validation failed')\"",
            "Валидация ролей",
        ):
            success = False

    # Останавливаем сервер
    try:
        server_process.terminate()
        server_process.wait(timeout=5)
        print("OK: Сервер остановлен")
    except:
        server_process.kill()
        print("OK: Сервер принудительно остановлен")

    print("\n" + "=" * 50)
    if success:
        print("УСПЕХ: ВСЕ ТЕСТЫ CI/CD ПРОШЛИ УСПЕШНО!")
        return True
    else:
        print("ERROR: ЕСТЬ ПРОБЛЕМЫ В CI/CD ТЕСТАХ!")
        return False


if __name__ == "__main__":
    success = test_ci_simulation()
    sys.exit(0 if success else 1)
