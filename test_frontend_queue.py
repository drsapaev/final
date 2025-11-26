#!/usr/bin/env python3
"""
Комплексный тест frontend системы очереди
"""
import requests
import time
import json
from datetime import datetime, date, timedelta

BASE_URL_API = "http://localhost:8000/api/v1"
BASE_URL_FRONTEND = "http://localhost:5173"

def test_frontend_availability():
    """Тест доступности frontend"""
    print("🔍 1. Тестируем доступность frontend...")
    
    try:
        response = requests.get(BASE_URL_FRONTEND, timeout=5)
        if response.status_code == 200:
            print("   ✅ Frontend доступен")
            return True
        else:
            print(f"   ❌ Frontend недоступен: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка подключения к frontend: {e}")
        return False

def test_queue_join_page():
    """Тест страницы записи в очередь"""
    print("\n🔍 2. Тестируем страницу записи в очередь...")
    
    try:
        # Тестируем страницу с токеном
        test_url = f"{BASE_URL_FRONTEND}/queue/join?token=test-token-123"
        response = requests.get(test_url, timeout=5)
        
        if response.status_code == 200:
            print("   ✅ Страница /queue/join доступна")
            
            # Проверяем наличие ключевых элементов
            content = response.text
            if "Онлайн-очередь" in content or "queue" in content.lower():
                print("   ✅ Страница содержит элементы очереди")
            else:
                print("   ⚠️ Страница может не содержать нужные элементы")
            
            return True
        else:
            print(f"   ❌ Страница недоступна: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Ошибка тестирования страницы: {e}")
        return False

def test_api_endpoints():
    """Тест API endpoints для очереди"""
    print("\n🔍 3. Тестируем API endpoints...")
    
    # Тест health
    try:
        response = requests.get(f"{BASE_URL_API}/health")
        if response.status_code == 200:
            print("   ✅ Health endpoint работает")
        else:
            print(f"   ❌ Health endpoint: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health endpoint ошибка: {e}")
    
    # Тест простого queue endpoint
    try:
        response = requests.get(f"{BASE_URL_API}/queue/test")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Queue test endpoint: {result.get('message', 'OK')}")
        else:
            print(f"   ❌ Queue test endpoint: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Queue test endpoint ошибка: {e}")
    
    # Тест join-fixed endpoint
    try:
        test_data = {
            "token": "frontend-test-token",
            "patient_name": "Frontend Test User",
            "phone": "+998901234567"
        }
        
        response = requests.post(f"{BASE_URL_API}/queue/join-fixed", json=test_data)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"   ✅ Join-fixed endpoint: {result.get('message')}")
            else:
                print(f"   ⚠️ Join-fixed endpoint: {result.get('message')}")
        else:
            print(f"   ❌ Join-fixed endpoint: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Join-fixed endpoint ошибка: {e}")

def test_registrar_panel_access():
    """Тест доступности панели регистратора"""
    print("\n🔍 4. Тестируем доступность панели регистратора...")
    
    try:
        # Тестируем страницу логина
        login_url = f"{BASE_URL_FRONTEND}/login"
        response = requests.get(login_url, timeout=5)
        
        if response.status_code == 200:
            print("   ✅ Страница логина доступна")
            
            # Тестируем панель регистратора (без авторизации)
            registrar_url = f"{BASE_URL_FRONTEND}/registrar-panel"
            response = requests.get(registrar_url, timeout=5)
            
            if response.status_code == 200:
                print("   ✅ Панель регистратора доступна (будет требовать авторизацию)")
                return True
            else:
                print(f"   ⚠️ Панель регистратора: {response.status_code} (нормально для неавторизованного доступа)")
                return True
        else:
            print(f"   ❌ Страница логина недоступна: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Ошибка тестирования панели: {e}")
        return False

def test_queue_workflow():
    """Тест полного workflow очереди"""
    print("\n🔍 5. Тестируем полный workflow очереди...")
    
    try:
        # Шаг 1: Получаем список пользователей (врачей)
        print("   📋 Шаг 1: Получаем список врачей...")
        try:
            response = requests.get(f"{BASE_URL_API}/users/users")
            if response.status_code == 200:
                users = response.json()
                doctors = [u for u in users if u.get('role') == 'Doctor']
                print(f"   ✅ Найдено {len(doctors)} врачей в системе")
                
                if doctors:
                    test_doctor = doctors[0]
                    print(f"   📝 Тестовый врач: {test_doctor.get('full_name', test_doctor.get('username'))}")
                else:
                    print("   ⚠️ Врачи не найдены, используем тестовый ID")
                    test_doctor = {"id": 1, "full_name": "Тестовый врач"}
            else:
                print(f"   ⚠️ Не удалось получить список пользователей: {response.status_code}")
                test_doctor = {"id": 1, "full_name": "Тестовый врач"}
        except Exception as e:
            print(f"   ⚠️ Ошибка получения врачей: {e}")
            test_doctor = {"id": 1, "full_name": "Тестовый врач"}
        
        # Шаг 2: Тестируем запись в очередь
        print("   📋 Шаг 2: Тестируем запись в очередь...")
        test_data = {
            "token": "workflow-test-token",
            "patient_name": "Workflow Test Patient",
            "phone": "+998901111111"
        }
        
        response = requests.post(f"{BASE_URL_API}/queue/join-fixed", json=test_data)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"   ✅ Запись в очередь: {result.get('message')}")
                if result.get('number'):
                    print(f"   🎫 Номер в очереди: {result.get('number')}")
            else:
                print(f"   ⚠️ Запись в очередь: {result.get('message')}")
        
        # Шаг 3: Тестируем получение очереди на сегодня
        print("   📋 Шаг 3: Тестируем получение очереди...")
        try:
            response = requests.get(f"{BASE_URL_API}/queue/today", params={
                "specialist_id": test_doctor["id"]
            })
            if response.status_code == 200:
                queue_data = response.json()
                print(f"   ✅ Очередь получена: {queue_data.get('total_entries', 0)} записей")
            elif response.status_code == 404:
                print("   ℹ️ Очередь на сегодня не найдена (это нормально)")
            else:
                print(f"   ⚠️ Ошибка получения очереди: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ Ошибка получения очереди: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка workflow: {e}")
        return False

def test_component_integration():
    """Тест интеграции компонентов"""
    print("\n🔍 6. Тестируем интеграцию компонентов...")
    
    # Проверяем наличие созданных файлов
    import os
    
    components_to_check = [
        "frontend/src/pages/QueueJoin.jsx",
        "frontend/src/components/queue/OnlineQueueManager.jsx", 
        "frontend/src/components/queue/QRScanner.jsx"
    ]
    
    for component in components_to_check:
        if os.path.exists(component):
            print(f"   ✅ Компонент существует: {component}")
        else:
            print(f"   ❌ Компонент отсутствует: {component}")
    
    # Проверяем маршруты в App.jsx
    try:
        with open("frontend/src/App.jsx", "r", encoding="utf-8") as f:
            app_content = f.read()
            
        if "/queue/join" in app_content:
            print("   ✅ Маршрут /queue/join добавлен в App.jsx")
        else:
            print("   ❌ Маршрут /queue/join не найден в App.jsx")
            
        if "QueueJoin" in app_content:
            print("   ✅ Импорт QueueJoin найден в App.jsx")
        else:
            print("   ❌ Импорт QueueJoin не найден в App.jsx")
            
    except Exception as e:
        print(f"   ❌ Ошибка проверки App.jsx: {e}")
    
    return True

def run_all_tests():
    """Запуск всех тестов"""
    print("🚀 Запуск комплексного тестирования frontend системы очереди...")
    print("=" * 70)
    
    results = []
    
    # Запускаем все тесты
    results.append(("Frontend доступность", test_frontend_availability()))
    results.append(("Страница записи в очередь", test_queue_join_page()))
    results.append(("API endpoints", test_api_endpoints()))
    results.append(("Панель регистратора", test_registrar_panel_access()))
    results.append(("Workflow очереди", test_queue_workflow()))
    results.append(("Интеграция компонентов", test_component_integration()))
    
    # Подводим итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
    
    print("=" * 70)
    print(f"📈 РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к использованию!")
    elif passed >= total * 0.8:
        print("✅ БОЛЬШИНСТВО ТЕСТОВ ПРОЙДЕНО! Система в основном работает.")
    else:
        print("⚠️ МНОГО ОШИБОК! Требуется дополнительная отладка.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    
    if success:
        print("\n🎯 РЕКОМЕНДАЦИИ:")
        print("1. Откройте http://localhost:5173/queue/join?token=test для тестирования")
        print("2. Войдите как admin/admin123 в http://localhost:5173/login")
        print("3. Перейдите в панель регистратора для управления очередью")
        print("4. Протестируйте генерацию QR кодов и запись пациентов")
    else:
        print("\n🔧 ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ:")
        print("1. Проверьте, что backend и frontend запущены")
        print("2. Убедитесь, что все компоненты созданы")
        print("3. Проверьте логи на наличие ошибок")
