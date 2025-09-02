#!/usr/bin/env python3
"""
Быстрая проверка системы ролей
Запускать перед каждым коммитом: python quick_check.py
"""
import subprocess
import sys
import os

def run_command(cmd, description):
    """Запускает команду и возвращает результат"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description}: OK")
            return True
        else:
            print(f"❌ {description}: FAILED")
            print(f"   {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description}: ERROR - {e}")
        return False

def main():
    """Основная функция быстрой проверки"""
    print("Быстрая проверка системы ролей")
    print("=" * 50)
    
    # Проверяем, что мы в правильной директории
    if not os.path.exists('clinic.db'):
        print("❌ База данных не найдена. Запустите из папки backend/")
        sys.exit(1)
    
    # Проверяем доступность сервера
    if not run_command("curl -s http://127.0.0.1:8000/api/v1/health", "Проверка сервера"):
        print("⚠️  Сервер не запущен. Запустите: uvicorn app.main:app --reload")
        sys.exit(1)
    
    # Запускаем тесты
    checks = [
        ("python test_role_routing.py", "Тесты системы ролей"),
        ("python check_system_integrity.py", "Проверка целостности")
    ]
    
    all_passed = True
    for cmd, desc in checks:
        if not run_command(cmd, desc):
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ВСЕ ПРОВЕРКИ ПРОШЛИ! Можно коммитить.")
        sys.exit(0)
    else:
        print("⚠️  ЕСТЬ ПРОБЛЕМЫ! Исправьте перед коммитом.")
        sys.exit(1)

if __name__ == "__main__":
    main()
