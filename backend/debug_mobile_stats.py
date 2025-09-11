#!/usr/bin/env python3
"""
Диагностика проблемы с мобильной статистикой
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_mobile_stats():
    print("🔍 ДИАГНОСТИКА МОБИЛЬНОЙ СТАТИСТИКИ")
    print("=====================================")
    
    # 1. Логинимся как admin
    print("1. Логинимся как admin...")
    login_data = {"username": "admin", "password": "admin123"}
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    
    if response.status_code != 200:
        print(f"   ❌ Ошибка логина: {response.status_code} - {response.text}")
        return
    
    token = response.json().get("access_token")
    print(f"   ✅ Логин успешен, токен: {token[:20]}...")
    
    # 2. Тестируем мобильную статистику
    print("\n2. Тестируем мобильную статистику...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/mobile/stats", headers=headers)
    
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Мобильная статистика работает")
        print(f"   Данные: {response.json()}")
    else:
        print(f"   ❌ Ошибка мобильной статистики: {response.text}")
        
        # Попробуем получить детали ошибки
        try:
            error_detail = response.json()
            print(f"   Детали ошибки: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Текст ошибки: {response.text}")

if __name__ == "__main__":
    test_mobile_stats()
