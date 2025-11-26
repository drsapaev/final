#!/usr/bin/env python3
"""
Проверка группировки услуг в API
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

def check_services_grouping():
    """Проверяем группировку услуг в API"""
    token = get_auth_token()
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    services_url = f"{BASE_URL}/registrar/services"
    
    print(f"\n🔍 Проверяем группировку услуг в API...")
    
    try:
        response = requests.get(services_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        services_by_group = data.get('services_by_group', {})
        
        print(f"📊 Группы услуг: {list(services_by_group.keys())}")
        
        # Проверяем каждую группу
        for group_name, services in services_by_group.items():
            print(f"\n🏷️ ГРУППА '{group_name}' ({len(services)} услуг):")
            
            # Фильтруем только процедуры
            procedure_services = []
            for service in services:
                category = service.get('category_code', '')
                if category in ['P', 'C', 'D_PROC']:
                    procedure_services.append(service)
            
            if procedure_services:
                print(f"  🎯 Процедуры в группе '{group_name}':")
                for service in procedure_services:
                    service_id = service.get('id')
                    service_code = service.get('service_code')
                    category_code = service.get('category_code')
                    name = service.get('name')
                    print(f"    ID {service_id}: {service_code} - {name} (категория: {category_code})")
            else:
                print(f"  ❌ Нет процедур в группе '{group_name}'")
        
        # Проверяем общую статистику процедур
        print(f"\n📊 ОБЩАЯ СТАТИСТИКА ПРОЦЕДУР:")
        print("-" * 40)
        
        all_procedures = []
        for group_name, services in services_by_group.items():
            for service in services:
                category = service.get('category_code', '')
                if category in ['P', 'C', 'D_PROC']:
                    all_procedures.append({
                        'group': group_name,
                        'service': service
                    })
        
        print(f"Всего процедур: {len(all_procedures)}")
        
        # Группируем по категориям
        physio_count = len([p for p in all_procedures if p['service']['category_code'] == 'P'])
        cosmo_count = len([p for p in all_procedures if p['service']['category_code'] == 'C'])
        derm_proc_count = len([p for p in all_procedures if p['service']['category_code'] == 'D_PROC'])
        
        print(f"Физиотерапия (P): {physio_count}")
        print(f"Косметология (C): {cosmo_count}")
        print(f"Дерматологические процедуры (D_PROC): {derm_proc_count}")
        
        # Проверяем распределение по группам
        print(f"\n📋 РАСПРЕДЕЛЕНИЕ ПО ГРУППАМ:")
        print("-" * 40)
        
        for group_name, services in services_by_group.items():
            procedure_count = len([s for s in services if s.get('category_code') in ['P', 'C', 'D_PROC']])
            if procedure_count > 0:
                print(f"  {group_name}: {procedure_count} процедур")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API: {e}")

def check_queue_grouping():
    """Проверяем группировку очередей"""
    token = get_auth_token()
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    queues_url = f"{BASE_URL}/registrar/queues/today"
    
    print(f"\n🔍 Проверяем группировку очередей...")
    
    try:
        response = requests.get(queues_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        queues = data.get('queues', [])
        
        print(f"📊 Найдено очередей: {len(queues)}")
        
        # Проверяем очереди с процедурами
        procedure_queues = []
        for queue in queues:
            specialty = queue.get('specialty', '')
            entries = queue.get('entries', [])
            
            # Проверяем, есть ли в очереди процедуры
            has_procedures = False
            for entry in entries:
                services = entry.get('services', [])
                service_codes = entry.get('service_codes', [])
                
                # Проверяем коды услуг
                for code in service_codes:
                    if (code.startswith('P') and code[1:].isdigit()) or \
                       (code.startswith('C') and code[1:].isdigit()) or \
                       (code.startswith('D_PROC') and code[6:].isdigit()) or \
                       code.startswith('PHYS_') or \
                       code.startswith('COSM_') or \
                       code.startswith('DERM_'):
                        has_procedures = True
                        break
                
                if has_procedures:
                    break
            
            if has_procedures:
                procedure_queues.append({
                    'specialty': specialty,
                    'entries_count': len(entries)
                })
        
        print(f"\n🎯 ОЧЕРЕДИ С ПРОЦЕДУРАМИ:")
        print("-" * 30)
        
        for queue in procedure_queues:
            print(f"  {queue['specialty']}: {queue['entries_count']} записей")
        
        if len(procedure_queues) > 1:
            print(f"\n⚠️ ПРОБЛЕМА: Процедуры разделены на {len(procedure_queues)} очередей!")
            print("Нужно объединить их в одну очередь 'procedures'")
        else:
            print(f"\n✅ Процедуры находятся в одной очереди")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка API: {e}")

if __name__ == "__main__":
    check_services_grouping()
    check_queue_grouping()
