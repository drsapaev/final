#!/usr/bin/env python3
"""
Быстрая проверка подключения к серверу
"""
import requests
import sys
import time


def test_connection(port=8000, timeout=5):
    """Проверяет подключение к серверу"""
    try:
        response = requests.get(
            f"http://localhost:{port}/api/v1/health", timeout=timeout
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Сервер работает на порту {port}")
            print(f"📊 Статус БД: {data.get('db', 'unknown')}")
            return True
        else:
            print(f"❌ Сервер отвечает с кодом {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удается подключиться к серверу на порту {port}")
        return False
    except requests.exceptions.Timeout:
        print(f"⏰ Таймаут подключения к серверу ({timeout}с)")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    print("🔍 Проверка подключения к серверу...")
    if test_connection():
        print("🎉 Сервер готов к работе!")
        sys.exit(0)
    else:
        print("💥 Сервер не отвечает")
        sys.exit(1)
