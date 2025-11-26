#!/usr/bin/env python3
"""
Проверка данных записей из API
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "registrar"
PASSWORD = "registrar123"

def get_auth_token():
    """Получаем токен аутентификации"""
    login_url = f"{BASE_URL}/auth/minimal-login"
    credentials = {
        "username": USERNAME,
        "password": PASSWORD
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

def check_appointments_data():
    """Проверяем данные записей из API"""
    token = get_auth_token()
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Проверяем записи
    print(f"\n🔍 Проверяем записи из API...")
    queues_url = f"{BASE_URL}/registrar/queues/today"
    
    try:
        response = requests.get(queues_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Статус: {response.status_code}")
        
        # Анализируем структуру данных
        if 'queues' in data:
            print(f"📊 Найдено очередей: {len(data['queues'])}")
            
            for queue in data['queues']:
                specialty = queue.get('specialty', 'unknown')
                entries = queue.get('entries', [])
                print(f"\n🏷️ Очередь '{specialty}': {len(entries)} записей")
                
                for i, entry in enumerate(entries[:3]):  # Показываем первые 3 записи
                    print(f"  Запись {i+1}:")
                    print(f"    ID: {entry.get('id')}")
                    print(f"    Пациент: {entry.get('patient_fio')}")
                    print(f"    Услуги (ID): {entry.get('services', [])}")
                    print(f"    Коды услуг: {entry.get('service_codes', [])}")
                    print(f"    Статус: {entry.get('status')}")
                    
                    # Проверяем, есть ли процедуры
                    services = entry.get('services', [])
                    if services:
                        print(f"    🔍 Анализ услуг:")
                        for service_id in services:
                            print(f"      ID {service_id}: нужно проверить в базе данных")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Детали ошибки: {e.response.text}")

def check_services_mapping():
    """Проверяем маппинг услуг"""
    print(f"\n🔍 Проверяем маппинг услуг...")
    
    # Проверяем услуги из API
    token = get_auth_token()
    if not token:
        return
        
    headers = {"Authorization": f"Bearer {token}"}
    services_url = f"{BASE_URL}/registrar/services"
    
    try:
        response = requests.get(services_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        services_by_group = data.get('services_by_group', {})
        
        print(f"📊 Группы услуг: {list(services_by_group.keys())}")
        
        # Проверяем процедуры
        procedures_group = services_by_group.get('procedures', [])
        print(f"\n🎯 Процедуры ({len(procedures_group)} услуг):")
        
        for service in procedures_group:
            service_id = service.get('id')
            service_code = service.get('service_code')
            category_code = service.get('category_code')
            name = service.get('name')
            print(f"  ID {service_id}: {service_code} - {name} (категория: {category_code})")
        
        # Проверяем дерматологию
        derma_group = services_by_group.get('dermatology', [])
        print(f"\n👨‍⚕️ Дерматология ({len(derma_group)} услуг):")
        
        for service in derma_group:
            service_id = service.get('id')
            service_code = service.get('service_code')
            category_code = service.get('category_code')
            name = service.get('name')
            print(f"  ID {service_id}: {service_code} - {name} (категория: {category_code})")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API: {e}")

if __name__ == "__main__":
    check_appointments_data()
    check_services_mapping()
