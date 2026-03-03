#!/usr/bin/env python3
"""
Автоматический запуск FastAPI сервера с проверкой статуса
"""
import uvicorn
import threading
import time
import requests
import sys
import os
from pathlib import Path


def check_server_health(port=8000, max_attempts=30, delay=1):
    """Проверяет, что сервер запустился и отвечает на запросы"""
    base_url = f"http://localhost:{port}"

    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{base_url}/api/v1/health", timeout=2)
            if response.status_code == 200:
                print(f"✅ Сервер успешно запущен на порту {port}")
                return True
        except requests.exceptions.RequestException:
            pass

        print(f"⏳ Ожидание запуска сервера... (попытка {attempt + 1}/{max_attempts})")
        time.sleep(delay)

    print(f"❌ Сервер не запустился за {max_attempts} попыток")
    return False


def run_server():
    """Запускает сервер в отдельном потоке"""
    print("🚀 Запускаем FastAPI сервер...")

    # Импортируем приложение
    from app.main import app

    # Запускаем сервер
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=False,  # Отключаем подробные логи для чистоты вывода
    )


def main():
    """Основная функция"""
    print("=" * 50)
    print("🏥 КЛИНИЧЕСКАЯ СИСТЕМА - АВТОМАТИЧЕСКИЙ ЗАПУСК")
    print("=" * 50)

    # Устанавливаем переменные окружения
    os.environ.setdefault("WS_DEV_ALLOW", "1")
    os.environ.setdefault("CORS_DISABLE", "0")
    os.environ.setdefault("REQUIRE_LICENSE", "0")

    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Ждем запуска сервера
    if check_server_health():
        print("=" * 50)
        print("✅ СИСТЕМА ГОТОВА К РАБОТЕ!")
        print("🌐 Сервер доступен по адресу: http://localhost:8000")
        print("📊 API документация: http://localhost:8000/docs")
        print("=" * 50)
        print("💡 Сервер работает в фоновом режиме")
        print("🔄 Для остановки нажмите Ctrl+C")
        print("=" * 50)

        # Продолжаем работу - сервер работает в фоне
        try:
            # Держим основной поток живым
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Остановка сервера...")
            sys.exit(0)
    else:
        print("❌ Не удалось запустить сервер")
        sys.exit(1)


if __name__ == "__main__":
    main()
