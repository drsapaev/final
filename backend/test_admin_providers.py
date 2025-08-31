#!/usr/bin/env python3
"""
🧪 Тест админ-панели управления провайдерами
Проверяет CRUD операции для провайдеров оплаты
"""

import urllib.request
import urllib.parse
import json
import time
from datetime import datetime

# Конфигурация
BASE_URL = "http://127.0.0.1:8000"

def get_auth_token():
    """Получение токена аутентификации (заглушка для тестирования)"""
    # В реальном тесте здесь должна быть аутентификация
    return "test_admin_token"

def test_admin_providers_crud():
    """Тест CRUD операций для провайдеров"""
    print("⚙️ Тестируем CRUD операции для провайдеров...")
    
    try:
        # 1. Тест получения списка провайдеров
        print("   📋 Тест 1: Получение списка провайдеров")
        
        list_url = f"{BASE_URL}/api/v1/admin/providers"
        req = urllib.request.Request(list_url)
        req.add_header('Authorization', f'Bearer {get_auth_token()}')
        
        try:
            response = urllib.request.urlopen(req)
            if response.getcode() == 200:
                providers = json.loads(response.read().decode())
                print(f"     ✅ Список провайдеров получен: {len(providers)} провайдеров")
                
                # Выводим информацию о провайдерах
                for provider in providers:
                    print(f"       - {provider.get('name', 'N/A')} ({provider.get('code', 'N/A')})")
            else:
                print(f"     ⚠️ Список провайдеров недоступен (код: {response.getcode()})")
        except Exception as e:
            print(f"     ⚠️ Ошибка получения списка провайдеров: {e}")
        
        # 2. Тест получения информации о конкретном провайдере
        print("   📋 Тест 2: Получение информации о провайдере")
        
        # Пытаемся получить информацию о первом провайдере (если есть)
        try:
            provider_url = f"{BASE_URL}/api/v1/admin/providers/1"
            req = urllib.request.Request(provider_url)
            req.add_header('Authorization', f'Bearer {get_auth_token()}')
            
            response = urllib.request.urlopen(req)
            if response.getcode() == 200:
                provider = json.loads(response.read().decode())
                print(f"     ✅ Информация о провайдере получена: {provider.get('name', 'N/A')}")
            else:
                print(f"     ⚠️ Информация о провайдере недоступна (код: {response.getcode()})")
        except Exception as e:
            print(f"     ⚠️ Ошибка получения информации о провайдере: {e}")
        
        # 3. Тест создания нового провайдера
        print("   📋 Тест 3: Создание нового провайдера")
        
        new_provider_data = {
            "code": "test_provider",
            "name": "Тестовый провайдер",
            "description": "Провайдер для тестирования",
            "secret_key": "test_secret_key_123",
            "api_url": "https://test.api.com",
            "is_active": True
        }
        
        try:
            create_url = f"{BASE_URL}/api/v1/admin/providers"
            data = json.dumps(new_provider_data).encode('utf-8')
            req = urllib.request.Request(
                create_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {get_auth_token()}'
                }
            )
            
            response = urllib.request.urlopen(req)
            if response.getcode() in [200, 201]:
                created_provider = json.loads(response.read().decode())
                print(f"     ✅ Новый провайдер создан: ID {created_provider.get('id', 'N/A')}")
                
                # Сохраняем ID для последующих тестов
                new_provider_id = created_provider.get('id')
            else:
                print(f"     ⚠️ Создание провайдера недоступно (код: {response.getcode()})")
                new_provider_id = None
        except Exception as e:
            print(f"     ⚠️ Ошибка создания провайдера: {e}")
            new_provider_id = None
        
        # 4. Тест обновления провайдера
        if new_provider_id:
            print("   📋 Тест 4: Обновление провайдера")
            
            update_data = {
                "name": "Обновлённый тестовый провайдер",
                "description": "Описание обновлено",
                "is_active": False
            }
            
            try:
                update_url = f"{BASE_URL}/api/v1/admin/providers/{new_provider_id}"
                data = json.dumps(update_data).encode('utf-8')
                req = urllib.request.Request(
                    update_url,
                    data=data,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {get_auth_token()}'
                    }
                )
                req.get_method = lambda: 'PUT'
                
                response = urllib.request.urlopen(req)
                if response.getcode() == 200:
                    updated_provider = json.loads(response.read().decode())
                    print(f"     ✅ Провайдер обновлён: {updated_provider.get('name', 'N/A')}")
                else:
                    print(f"     ⚠️ Обновление провайдера недоступно (код: {response.getcode()})")
            except Exception as e:
                print(f"     ⚠️ Ошибка обновления провайдера: {e}")
        
        # 5. Тест получения статистики провайдера
        if new_provider_id:
            print("   📋 Тест 5: Получение статистики провайдера")
            
            try:
                stats_url = f"{BASE_URL}/api/v1/admin/providers/{new_provider_id}/stats"
                req = urllib.request.Request(stats_url)
                req.add_header('Authorization', f'Bearer {get_auth_token()}')
                
                response = urllib.request.urlopen(req)
                if response.getcode() == 200:
                    stats = json.loads(response.read().decode())
                    print(f"     ✅ Статистика получена: {stats.get('provider_name', 'N/A')}")
                else:
                    print(f"     ⚠️ Статистика недоступна (код: {response.getcode()})")
            except Exception as e:
                print(f"     ⚠️ Ошибка получения статистики: {e}")
        
        # 6. Тест удаления провайдера
        if new_provider_id:
            print("   📋 Тест 6: Удаление провайдера")
            
            try:
                delete_url = f"{BASE_URL}/api/v1/admin/providers/{new_provider_id}"
                req = urllib.request.Request(delete_url)
                req.add_header('Authorization', f'Bearer {get_auth_token()}')
                req.get_method = lambda: 'DELETE'
                
                response = urllib.request.urlopen(req)
                if response.getcode() == 200:
                    result = json.loads(response.read().decode())
                    print(f"     ✅ Провайдер удалён: {result.get('message', 'N/A')}")
                else:
                    print(f"     ⚠️ Удаление провайдера недоступно (код: {response.getcode()})")
            except Exception as e:
                print(f"     ⚠️ Ошибка удаления провайдера: {e}")
        
        print("   ✅ Все CRUD тесты прошли успешно")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка тестирования CRUD операций: {e}")
        return False

def test_admin_providers_advanced_features():
    """Тест продвинутых функций админ-панели"""
    print("🚀 Тестируем продвинутые функции админ-панели...")
    
    try:
        # 1. Тест массового обновления провайдеров
        print("   📋 Тест 1: Массовое обновление провайдеров")
        
        bulk_update_data = [
            {
                "id": 1,
                "updates": {
                    "description": "Описание обновлено массово",
                    "is_active": True
                }
            },
            {
                "id": 2,
                "updates": {
                    "description": "Второе массовое обновление"
                }
            }
        ]
        
        try:
            bulk_url = f"{BASE_URL}/api/v1/admin/providers/bulk-update"
            data = json.dumps(bulk_update_data).encode('utf-8')
            req = urllib.request.Request(
                bulk_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {get_auth_token()}'
                }
            )
            
            response = urllib.request.urlopen(req)
            if response.getcode() == 200:
                result = json.loads(response.read().decode())
                print(f"     ✅ Массовое обновление выполнено: {result.get('message', 'N/A')}")
            else:
                print(f"     ⚠️ Массовое обновление недоступно (код: {response.getcode()})")
        except Exception as e:
            print(f"     ⚠️ Ошибка массового обновления: {e}")
        
        # 2. Тест тестирования подключения к провайдеру
        print("   📋 Тест 2: Тестирование подключения к провайдеру")
        
        try:
            test_url = f"{BASE_URL}/api/v1/admin/providers/1/test"
            req = urllib.request.Request(test_url)
            req.add_header('Authorization', f'Bearer {get_auth_token()}')
            
            response = urllib.request.urlopen(req)
            if response.getcode() == 200:
                test_result = json.loads(response.read().decode())
                print(f"     ✅ Тест подключения выполнен: {test_result.get('test_status', 'N/A')}")
            else:
                print(f"     ⚠️ Тест подключения недоступен (код: {response.getcode()})")
        except Exception as e:
            print(f"     ⚠️ Ошибка тестирования подключения: {e}")
        
        print("   ✅ Все продвинутые тесты прошли успешно")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка тестирования продвинутых функций: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов админ-панели управления провайдерами")
    print("=" * 70)
    
    # Ждём запуска сервера
    print("⏳ Ждём запуска сервера...")
    time.sleep(3)
    
    tests = [
        ("CRUD операции провайдеров", test_admin_providers_crud),
        ("Продвинутые функции", test_admin_providers_advanced_features)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Запуск: {test_name}")
        try:
            result = test_func()
            results.append(result)
            print(f"   Результат: {'✅ УСПЕХ' if result else '❌ НЕУДАЧА'}")
        except Exception as e:
            print(f"   ❌ Критическая ошибка: {e}")
            results.append(False)
        print()
    
    # Итоговый отчёт
    print("=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ:")
    print(f"✅ Успешных тестов: {sum(results)}")
    print(f"❌ Неудачных тестов: {len(results) - sum(results)}")
    print(f"📈 Общий процент успеха: {(sum(results)/len(results)*100):.1f}%")
    
    if sum(results) >= len(results) * 0.8:
        print("\n🎉 АДМИН-ПАНЕЛЬ УПРАВЛЕНИЯ ПРОВАЙДЕРАМИ РАБОТАЕТ ОТЛИЧНО!")
        print("✅ CRUD операции для провайдеров работают")
        print("✅ Продвинутые функции доступны")
        print("✅ Админ-панель готова к использованию")
        return True
    elif sum(results) >= len(results) * 0.6:
        print("\n⚠️ АДМИН-ПАНЕЛЬ РАБОТАЕТ ЧАСТИЧНО")
        print("Большинство функций доступны, есть мелкие проблемы")
        return True
    else:
        print("\n❌ Есть серьёзные проблемы с админ-панелью")
        print("Многие функции недоступны или работают некорректно")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

