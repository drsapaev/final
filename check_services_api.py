#!/usr/bin/env python3
"""
Проверка API эндпоинта /registrar/services
"""

import requests
import json

BASE_URL = "http://localhost:18000/api/v1"
USERNAME = "registrar"
PASSWORD = "registrar123"

def get_auth_token():
    """Получаем токен аутентификации"""
    login_url = f"{BASE_URL}/auth/login"
    credentials = {
        "username": USERNAME,
        "password": PASSWORD,
        "remember_me": False
    }
    try:
        response = requests.post(login_url, json=credentials)
        response.raise_for_status()
        token = response.json().get("access_token")
        if token:
            print(f"✅ Токен получен: {token[:30]}...")
            return token
        else:
            print("❌ Не удалось получить токен")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при получении токена: {e}")
        return None

def check_services_api():
    """Проверяем API эндпоинт услуг"""
    token = get_auth_token()
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/registrar/services"
    
    print(f"\n🔍 Проверяем API: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        services = response.json()
        print(f"✅ Статус: {response.status_code}")
        print(f"📊 Количество услуг: {len(services)}")
        
        print(f"\n📋 ВСЕ УСЛУГИ:")
        print("-" * 50)
        
        # Группируем по категориям
        categories = {}
        for service in services:
            category = service.get('category_code', 'Без категории')
            if category not in categories:
                categories[category] = []
            categories[category].append(service)
        
        for category, service_list in categories.items():
            print(f"\n🏷️ КАТЕГОРИЯ '{category}' ({len(service_list)} услуг):")
            for service in service_list:
                code = service.get('service_code', 'Без кода')
                name = service.get('name', 'Без названия')
                print(f"  {code} - {name}")
        
        # Проверяем конкретно процедуры
        print(f"\n🎯 ПРОВЕРКА ПРОЦЕДУР:")
        print("-" * 30)
        
        procedure_categories = ['P', 'C', 'D_PROC']
        procedure_services = [s for s in services if s.get('category_code') in procedure_categories]
        
        print(f"📊 Найдено процедур: {len(procedure_services)}")
        
        for service in procedure_services:
            code = service.get('service_code', 'Без кода')
            name = service.get('name', 'Без названия')
            category = service.get('category_code', 'Без категории')
            print(f"  {code} - {name} (категория: {category})")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Детали ошибки: {e.response.text}")

if __name__ == "__main__":
    check_services_api()
