#!/usr/bin/env python3
"""
Быстрый тест исправлений
"""
import requests

def quick_test_fixes():
    """Быстрый тест исправлений"""
    print("🔧 БЫСТРЫЙ ТЕСТ ИСПРАВЛЕНИЙ")
    print("=" * 40)
    
    # Получаем токен
    try:
        auth_response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if auth_response.status_code != 200:
            print(f"❌ Ошибка аутентификации: {auth_response.status_code}")
            return
        
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Токен получен")
        
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    # Тестируем исправленные endpoints
    test_endpoints = [
        ("/api/v1/mobile/stats", "Mobile Stats"),
        ("/api/v1/telegram/bot-status", "Telegram Status"),
        ("/api/v1/analytics/quick-stats", "Analytics Quick Stats"),
        ("/api/v1/analytics/dashboard", "Analytics Dashboard")
    ]
    
    results = {"passed": 0, "total": 0}
    
    for endpoint, name in test_endpoints:
        print(f"\n🔍 Тестируем {name}...")
        try:
            response = requests.get(f"http://localhost:8000{endpoint}", headers=headers, timeout=5)
            
            if response.status_code == 200:
                print(f"   ✅ {name}: Работает!")
                results["passed"] += 1
            elif response.status_code == 500:
                print(f"   ❌ {name}: 500 Internal Server Error")
                try:
                    error_detail = response.json()
                    print(f"   Детали: {error_detail.get('detail', 'Нет деталей')[:100]}...")
                except:
                    print(f"   Текст: {response.text[:100]}...")
            else:
                print(f"   ⚠️ {name}: Статус {response.status_code}")
            
            results["total"] += 1
            
        except Exception as e:
            print(f"   ❌ {name}: Ошибка {e}")
            results["total"] += 1
    
    # Результаты
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"   ✅ Успешно: {results['passed']}/{results['total']}")
    print(f"   📈 Процент: {(results['passed']/results['total']*100):.1f}%")
    
    if results['passed'] == results['total']:
        print("🎉 ВСЕ ИСПРАВЛЕНИЯ РАБОТАЮТ!")
    elif results['passed'] > results['total'] // 2:
        print("⚠️ БОЛЬШИНСТВО ИСПРАВЛЕНИЙ РАБОТАЕТ")
    else:
        print("❌ НУЖНЫ ДОПОЛНИТЕЛЬНЫЕ ИСПРАВЛЕНИЯ")

if __name__ == "__main__":
    quick_test_fixes()
