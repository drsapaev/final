#!/usr/bin/env python3
"""
Диагностика проблемы с аналитикой
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_analytics():
    print("🔍 ДИАГНОСТИКА АНАЛИТИКИ")
    print("=========================")
    
    # 1. Логинимся как admin
    print("1. Логинимся как admin...")
    login_data = {"username": "admin", "password": "admin123"}
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    
    if response.status_code != 200:
        print(f"   ❌ Ошибка логина: {response.status_code} - {response.text}")
        return
    
    token = response.json().get("access_token")
    print(f"   ✅ Логин успешен, токен: {token[:20]}...")
    
    # 2. Тестируем быструю статистику
    print("\n2. Тестируем быструю статистику...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/analytics/quick-stats", headers=headers)
    
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Быстрая статистика работает")
        print(f"   Данные: {response.json()}")
    else:
        print(f"   ❌ Ошибка быстрой статистики: {response.text}")
        
        # Попробуем получить детали ошибки
        try:
            error_detail = response.json()
            print(f"   Детали ошибки: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Текст ошибки: {response.text}")
    
    # 3. Тестируем дашборд
    print("\n3. Тестируем дашборд...")
    response = requests.get(f"{BASE_URL}/analytics/dashboard", headers=headers)
    
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Дашборд работает")
        print(f"   Данные: {response.json()}")
    else:
        print(f"   ❌ Ошибка дашборда: {response.text}")

if __name__ == "__main__":
    test_analytics()
