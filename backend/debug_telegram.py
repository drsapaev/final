#!/usr/bin/env python3
"""
Диагностика проблем с Telegram
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_telegram():
    print("🔍 ДИАГНОСТИКА TELEGRAM")
    print("========================")
    
    # 1. Логинимся как admin
    print("1. Логинимся как admin...")
    login_data = {"username": "admin", "password": "admin123"}
    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    
    if response.status_code != 200:
        print(f"   ❌ Ошибка логина: {response.status_code} - {response.text}")
        return
    
    token = response.json().get("access_token")
    print(f"   ✅ Логин успешен, токен: {token[:20]}...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Тестируем Telegram endpoints
    telegram_endpoints = [
        "/telegram/bot-status",
        "/telegram/config",
        "/telegram/users",
        "/telegram/messages",
        "/telegram/send-message",
        "/telegram/webhook",
        "/telegram/setup"
    ]
    
    working_endpoints = []
    broken_endpoints = []
    
    for endpoint in telegram_endpoints:
        print(f"\n2. Тестируем {endpoint}...")
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
            print(f"   Статус: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ {endpoint} работает")
                working_endpoints.append(endpoint)
            else:
                print(f"   ❌ {endpoint} ошибка: {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Детали: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
                except:
                    print(f"   Текст: {response.text[:200]}...")
                broken_endpoints.append(endpoint)
                
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ {endpoint} - ConnectionError: {e}")
            broken_endpoints.append(endpoint)
        except requests.exceptions.Timeout as e:
            print(f"   ❌ {endpoint} - Timeout: {e}")
            broken_endpoints.append(endpoint)
        except Exception as e:
            print(f"   ❌ {endpoint} - Exception: {e}")
            broken_endpoints.append(endpoint)
    
    # 3. Итоговый отчет
    print(f"\n📱 ИТОГОВЫЙ ОТЧЕТ TELEGRAM")
    print("=" * 40)
    print(f"✅ Работают: {len(working_endpoints)}/{len(telegram_endpoints)}")
    print(f"❌ Не работают: {len(broken_endpoints)}/{len(telegram_endpoints)}")
    
    if working_endpoints:
        print(f"\n✅ Работающие endpoints:")
        for ep in working_endpoints:
            print(f"   - {ep}")
    
    if broken_endpoints:
        print(f"\n❌ Сломанные endpoints:")
        for ep in broken_endpoints:
            print(f"   - {ep}")

if __name__ == "__main__":
    test_telegram()
