#!/usr/bin/env python3
"""
Тест Docker сборки для проверки исправлений
"""
import subprocess
import sys
import os
from pathlib import Path

def test_docker_build():
    """Тестирует Docker сборку"""
    print("🐳 Тестируем Docker сборку...")

    # Проверяем наличие файлов
    required_files = [
        "ops/backend.Dockerfile",
        "ops/backend.entrypoint.sh",
        "backend/requirements.txt",
        "backend/app/main.py"
    ]

    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ Файл не найден: {file_path}")
            return False
        else:
            print(f"✅ Файл найден: {file_path}")

    # Проверяем права доступа к entrypoint
    entrypoint_path = Path("ops/backend.entrypoint.sh")
    if not os.access(entrypoint_path, os.R_OK):
        print(f"❌ Нет прав на чтение: {entrypoint_path}")
        return False

    print("✅ Все файлы найдены и доступны")

    # Тестируем Docker build (только проверка синтаксиса)
    try:
        print("🔍 Проверяем синтаксис Dockerfile...")
        result = subprocess.run([
            "docker", "build",
            "--file", "ops/backend.Dockerfile",
            "--target", "base",
            "--no-cache",
            "."
        ], capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            print("✅ Docker сборка прошла успешно!")
            return True
        else:
            print(f"❌ Ошибка Docker сборки:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("⏰ Таймаут Docker сборки")
        return False
    except FileNotFoundError:
        print("❌ Docker не установлен или не доступен")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    if test_docker_build():
        print("🎉 Тест Docker сборки пройден!")
        sys.exit(0)
    else:
        print("💥 Тест Docker сборки провален!")
        sys.exit(1)
