#!/usr/bin/env python3
"""
Скрипт проверки готовности системы к ручному тестированию
"""
import requests
import sys
import os
from pathlib import Path

def check_backend():
    """Проверка доступности backend"""
    print("🔍 Проверка Backend сервера (http://localhost:18000)...")
    try:
        response = requests.get("http://localhost:18000/api/v1/health", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print("✅ Backend доступен")
            print(f"   Статус БД: {data.get('db', 'unknown')}")
            return True
        else:
            print(f"❌ Backend отвечает с кодом {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Backend недоступен на http://localhost:18000")
        print("   Запустите: cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Ошибка проверки backend: {e}")
        return False

def check_frontend():
    """Проверка доступности frontend"""
    print("\n🔍 Проверка Frontend сервера (http://localhost:5173)...")
    try:
        response = requests.get("http://localhost:5173", timeout=3)
        if response.status_code == 200:
            print("✅ Frontend доступен")
            return True
        else:
            print(f"⚠️ Frontend отвечает с кодом {response.status_code}")
            return True  # Все равно может работать
    except requests.exceptions.ConnectionError:
        print("❌ Frontend недоступен на http://localhost:5173")
        print("   Запустите: cd frontend && npm run dev")
        return False
    except Exception as e:
        print(f"⚠️ Ошибка проверки frontend: {e}")
        return True  # Может быть проблема с CORS, но это не критично

def check_files():
    """Проверка наличия ключевых файлов"""
    print("\n🔍 Проверка ключевых файлов...")
    files_to_check = [
        "frontend/src/pages/CardiologistPanelUnified.jsx",
        "frontend/src/pages/DermatologistPanelUnified.jsx",
        "frontend/src/pages/DentistPanelUnified.jsx",
        "frontend/src/pages/LabPanel.jsx",
        "frontend/src/components/medical/EMRSystem.jsx",
        "frontend/src/services/queue.js",
        "frontend/src/components/QueueIntegration.jsx"
    ]
    
    all_exist = True
    for file_path in files_to_check:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - не найден")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 70)
    print("🧪 ПРОВЕРКА ГОТОВНОСТИ К РУЧНОМУ ТЕСТИРОВАНИЮ")
    print("=" * 70)
    print()
    
    backend_ok = check_backend()
    frontend_ok = check_frontend()
    files_ok = check_files()
    
    print("\n" + "=" * 70)
    if backend_ok and frontend_ok and files_ok:
        print("✅ Система готова к тестированию!")
        print("\n📋 Следующие шаги:")
        print("1. Откройте браузер: http://localhost:5173")
        print("2. Войдите в систему с учетной записью врача")
        print("3. Откройте DevTools (F12) → вкладка Console")
        print("4. Начните тестирование с панели кардиолога:")
        print("   http://localhost:5173/cardiologist?tab=queue")
        print("\n📖 Подробный план тестирования в файле .plan.md")
        return 0
    else:
        print("❌ Система не готова. Исправьте ошибки выше.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

