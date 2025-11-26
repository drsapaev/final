#!/usr/bin/env python3
"""
Универсальный скрипт для запуска команд с автоматическим продолжением работы
"""
import subprocess
import sys
import time
import threading
import os
from pathlib import Path


class AutoContinueRunner:
    def __init__(self, command, success_check=None, max_wait_time=30):
        self.command = command
        self.success_check = success_check
        self.max_wait_time = max_wait_time
        self.process = None
        self.success = False

    def run_command(self):
        """Запускает команду"""
        try:
            print(f"🚀 Выполняем команду: {' '.join(self.command)}")
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            # Читаем вывод в реальном времени
            for line in iter(self.process.stdout.readline, ''):
                print(line.rstrip())

            self.process.wait()
            self.success = True

        except Exception as e:
            print(f"❌ Ошибка выполнения команды: {e}")
            self.success = False

    def check_success(self):
        """Проверяет успешность выполнения"""
        if self.success_check:
            return self.success_check()
        return self.success

    def run(self):
        """Запускает команду с автоматическим продолжением"""
        print("=" * 60)
        print("🔄 АВТОМАТИЧЕСКИЙ ЗАПУСК С ПРОВЕРКОЙ СТАТУСА")
        print("=" * 60)

        # Запускаем команду в отдельном потоке
        command_thread = threading.Thread(target=self.run_command, daemon=True)
        command_thread.start()

        # Ждем завершения или таймаута
        start_time = time.time()
        while command_thread.is_alive():
            if time.time() - start_time > self.max_wait_time:
                print(f"⏰ Превышено время ожидания ({self.max_wait_time}с)")
                break
            time.sleep(0.5)

        # Проверяем успешность
        if self.check_success():
            print("=" * 60)
            print("✅ КОМАНДА ВЫПОЛНЕНА УСПЕШНО!")
            print("=" * 60)
            return True
        else:
            print("=" * 60)
            print("❌ КОМАНДА ЗАВЕРШИЛАСЬ С ОШИБКОЙ")
            print("=" * 60)
            return False


def check_server_health():
    """Проверка здоровья сервера"""
    import requests

    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print(
            "Использование: python run_with_auto_continue.py <команда> [аргументы...]"
        )
        print("Примеры:")
        print("  python run_with_auto_continue.py uvicorn app.main:app --reload")
        print("  python run_with_auto_continue.py python test_connection.py")
        sys.exit(1)

    command = sys.argv[1:]

    # Определяем проверку успешности в зависимости от команды
    success_check = None
    if "uvicorn" in command or "run_server" in command:
        success_check = check_server_health
        max_wait = 30
    else:
        max_wait = 10

    # Запускаем с автоматическим продолжением
    runner = AutoContinueRunner(command, success_check, max_wait)
    success = runner.run()

    if success:
        print("🎉 Работа завершена успешно!")
        sys.exit(0)
    else:
        print("💥 Работа завершена с ошибками")
        sys.exit(1)


if __name__ == "__main__":
    main()
