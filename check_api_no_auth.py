#!/usr/bin/env python3
"""
Проверка API услуг без аутентификации
"""

import json
import os

import requests

BASE_URL = "http://localhost:18000/api/v1"
REGISTRAR_PASSWORD_ENV = "QA_REGISTRAR_PASSWORD"
REGISTRAR_PASSWORD = os.environ.get(REGISTRAR_PASSWORD_ENV, "").strip()
if not REGISTRAR_PASSWORD:
    raise SystemExit(f"Set {REGISTRAR_PASSWORD_ENV} before running this smoke script.")

def check_services_without_auth():
    """Проверяем API услуг без аутентификации"""
    url = f"{BASE_URL}/registrar/services"
    
    print(f"🔍 Проверяем API без аутентификации: {url}")
    
    try:
        response = requests.get(url)
        print(f"📊 Статус: {response.status_code}")
        
        if response.status_code == 200:
            services = response.json()
            print(f"✅ Успешно! Количество услуг: {len(services)}")
            
            # Проверяем процедуры
            procedure_categories = ['P', 'C', 'D_PROC']
            procedure_services = [s for s in services if s.get('category_code') in procedure_categories]
            
            print(f"\n🎯 ПРОЦЕДУРЫ ({len(procedure_services)} услуг):")
            for service in procedure_services:
                code = service.get('service_code', 'Без кода')
                name = service.get('name', 'Без названия')
                category = service.get('category_code', 'Без категории')
                print(f"  {code} - {name} (категория: {category})")
                
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"Ответ: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка подключения: {e}")

def check_minimal_login():
    """Проверяем минимальную аутентификацию"""
    login_url = f"{BASE_URL}/auth/minimal-login"
    
    print(f"\n🔐 Проверяем минимальную аутентификацию: {login_url}")
    
    credentials = {
        "username": "registrar",
        "password": REGISTRAR_PASSWORD
    }
    
    try:
        response = requests.post(login_url, json=credentials)
        print(f"📊 Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Успешно! Токен: {data.get('access_token', 'Нет токена')[:30]}...")
            
            # Теперь проверяем услуги с токеном
            token = data.get('access_token')
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                services_url = f"{BASE_URL}/registrar/services"
                
                print(f"\n🔍 Проверяем услуги с токеном...")
                services_response = requests.get(services_url, headers=headers)
                
                if services_response.status_code == 200:
                    data = services_response.json()
                    print(f"✅ Данные получены: {data}")
                    
                    # Проверяем структуру ответа
                    if isinstance(data, dict):
                        services_by_group = data.get('services_by_group', {})
                        categories = data.get('categories', [])
                        total_services = data.get('total_services', 0)
                        
                        print(f"\n📊 СТРУКТУРА ОТВЕТА:")
                        print(f"  services_by_group: {len(services_by_group)} групп")
                        print(f"  categories: {len(categories)} категорий")
                        print(f"  total_services: {total_services}")
                        
                        # Выводим все группы услуг
                        print(f"\n📋 ГРУППЫ УСЛУГ:")
                        for group_name, services in services_by_group.items():
                            print(f"  {group_name}: {len(services)} услуг")
                            for service in services:
                                if isinstance(service, dict):
                                    code = service.get('service_code', 'Без кода')
                                    name = service.get('name', 'Без названия')
                                    category = service.get('category_code', 'Без категории')
                                    print(f"    {code} - {name} (категория: {category})")
                        
                        # Проверяем процедуры
                        procedure_categories = ['P', 'C', 'D_PROC']
                        procedure_services = []
                        
                        for group_name, services in services_by_group.items():
                            for service in services:
                                if isinstance(service, dict) and service.get('category_code') in procedure_categories:
                                    procedure_services.append(service)
                        
                        print(f"\n🎯 ПРОЦЕДУРЫ ({len(procedure_services)} услуг):")
                        for service in procedure_services:
                            code = service.get('service_code', 'Без кода')
                            name = service.get('name', 'Без названия')
                            category = service.get('category_code', 'Без категории')
                            print(f"  {code} - {name} (категория: {category})")
                    else:
                        print(f"❌ Неожиданный формат данных: {type(data)}")
                else:
                    print(f"❌ Ошибка при получении услуг: {services_response.status_code}")
                    print(f"Ответ: {services_response.text}")
        else:
            print(f"❌ Ошибка аутентификации: {response.status_code}")
            print(f"Ответ: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    check_services_without_auth()
    check_minimal_login()
