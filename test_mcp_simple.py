"""
Простое тестирование MCP API без авторизации
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_api_docs():
    """Тест доступности API документации"""
    print("🔍 Тестирование API документации...")
    
    try:
        response = requests.get("http://localhost:8000/docs", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API документация доступна")
            print("📖 Откройте http://localhost:8000/docs в браузере")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_openapi_schema():
    """Тест доступности OpenAPI схемы"""
    print("\n🔍 Тестирование OpenAPI схемы...")
    
    try:
        response = requests.get("http://localhost:8000/openapi.json", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            schema = response.json()
            print("✅ OpenAPI схема доступна")
            
            # Проверяем наличие MCP endpoints
            paths = schema.get("paths", {})
            mcp_paths = [path for path in paths.keys() if "mcp" in path.lower()]
            
            print(f"📋 Найдено MCP endpoints: {len(mcp_paths)}")
            for path in mcp_paths[:5]:  # Показываем первые 5
                print(f"  - {path}")
            
            if len(mcp_paths) > 5:
                print(f"  ... и еще {len(mcp_paths) - 5}")
            
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_server_health():
    """Тест общего здоровья сервера"""
    print("\n🔍 Тестирование здоровья сервера...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Сервер работает")
            print(f"  Статус: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_mcp_endpoints_exist():
    """Тест существования MCP endpoints"""
    print("\n🔍 Проверка существования MCP endpoints...")
    
    try:
        response = requests.get("http://localhost:8000/openapi.json", timeout=10)
        
        if response.status_code == 200:
            schema = response.json()
            paths = schema.get("paths", {})
            
            # Список ожидаемых MCP endpoints
            expected_endpoints = [
                "/api/v1/mcp/health",
                "/api/v1/mcp/status", 
                "/api/v1/mcp/metrics",
                "/api/v1/mcp/capabilities",
                "/api/v1/mcp/complaint/analyze",
                "/api/v1/mcp/complaint/validate",
                "/api/v1/mcp/icd10/suggest",
                "/api/v1/mcp/lab/interpret",
                "/api/v1/mcp/imaging/analyze"
            ]
            
            found_endpoints = []
            missing_endpoints = []
            
            for endpoint in expected_endpoints:
                if endpoint in paths:
                    found_endpoints.append(endpoint)
                else:
                    missing_endpoints.append(endpoint)
            
            print(f"✅ Найдено endpoints: {len(found_endpoints)}/{len(expected_endpoints)}")
            
            if found_endpoints:
                print("📋 Доступные MCP endpoints:")
                for endpoint in found_endpoints:
                    print(f"  ✅ {endpoint}")
            
            if missing_endpoints:
                print("❌ Отсутствующие endpoints:")
                for endpoint in missing_endpoints:
                    print(f"  ❌ {endpoint}")
            
            return len(found_endpoints) == len(expected_endpoints)
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_mcp_requires_auth():
    """Тест что MCP endpoints требуют авторизацию"""
    print("\n🔍 Проверка что MCP endpoints требуют авторизацию...")
    
    test_endpoints = [
        "/api/v1/mcp/health",
        "/api/v1/mcp/status",
        "/api/v1/mcp/capabilities"
    ]
    
    auth_required_count = 0
    
    for endpoint in test_endpoints:
        try:
            response = requests.get(f"http://localhost:8000{endpoint}", timeout=10)
            
            if response.status_code == 401:
                print(f"✅ {endpoint}: требует авторизацию (401)")
                auth_required_count += 1
            elif response.status_code == 200:
                print(f"⚠️ {endpoint}: доступен без авторизации (200)")
            else:
                print(f"❓ {endpoint}: неожиданный статус ({response.status_code})")
                
        except Exception as e:
            print(f"❌ {endpoint}: ошибка запроса - {e}")
    
    print(f"\n📊 Результат: {auth_required_count}/{len(test_endpoints)} endpoints требуют авторизацию")
    return auth_required_count == len(test_endpoints)

def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("🚀 ПРОСТОЕ ТЕСТИРОВАНИЕ MCP API")
    print("=" * 60)
    
    tests = [
        ("API документация", test_api_docs),
        ("OpenAPI схема", test_openapi_schema),
        ("Здоровье сервера", test_server_health),
        ("MCP endpoints существуют", test_mcp_endpoints_exist),
        ("MCP требует авторизацию", test_mcp_requires_auth),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ Критическая ошибка в тесте '{test_name}': {str(e)}")
            results[test_name] = False
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    for test_name, success in results.items():
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {test_name}: {'Успешно' if success else 'Ошибка'}")
    
    print("\n" + "-" * 60)
    print(f"Результат: {success_count}/{total_count} тестов пройдено успешно")
    
    if success_count == total_count:
        print("🎉 ВСЕ БАЗОВЫЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n📋 MCP API полностью интегрирован:")
        print("  ✅ Сервер запущен и работает")
        print("  ✅ API документация доступна")
        print("  ✅ MCP endpoints зарегистрированы")
        print("  ✅ Авторизация работает корректно")
        print("\n🌐 Следующие шаги:")
        print("  1. Откройте http://localhost:8000/docs в браузере")
        print("  2. Авторизуйтесь через /api/v1/auth/minimal-login")
        print("  3. Протестируйте MCP endpoints с токеном")
        print("  4. Используйте MCP в медицинских панелях")
    else:
        print(f"⚠️ {total_count - success_count} тестов завершились с ошибками")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
