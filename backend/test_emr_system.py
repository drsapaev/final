"""
Тестовый скрипт для проверки EMR системы
"""
import requests
import json
from datetime import datetime

# Базовый URL API
BASE_URL = "http://localhost:8000/api/v1"

def test_emr_endpoints():
    """Тестирование EMR endpoints"""
    print("🧪 ТЕСТИРОВАНИЕ EMR СИСТЕМЫ")
    print("=" * 50)
    
    # Тест 1: Проверка доступности endpoints
    print("\n1️⃣ Проверка доступности EMR endpoints...")
    
    endpoints_to_test = [
        "/emr/templates",
        "/emr/templates/default/load",
        "/health"
    ]
    
    for endpoint in endpoints_to_test:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            print(f"✅ {endpoint}: {response.status_code}")
            if response.status_code == 200:
                print(f"   Ответ: {response.json()}")
            elif response.status_code == 401:
                print(f"   Требуется аутентификация (ожидаемо)")
            else:
                print(f"   Ошибка: {response.text}")
        except Exception as e:
            print(f"❌ {endpoint}: Ошибка - {e}")
    
    # Тест 2: Проверка структуры API
    print("\n2️⃣ Проверка структуры API...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ Swagger документация доступна")
        else:
            print(f"❌ Swagger недоступен: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка доступа к Swagger: {e}")
    
    # Тест 3: Проверка схем данных
    print("\n3️⃣ Проверка схем данных...")
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            openapi_data = response.json()
            emr_paths = [path for path in openapi_data.get("paths", {}).keys() if "/emr/" in path]
            print(f"✅ Найдено {len(emr_paths)} EMR endpoints:")
            for path in emr_paths:
                print(f"   - {path}")
        else:
            print(f"❌ OpenAPI недоступен: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка доступа к OpenAPI: {e}")
    
    print("\n🎯 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")

def test_emr_templates_structure():
    """Тестирование структуры шаблонов EMR"""
    print("\n📋 ТЕСТИРОВАНИЕ СТРУКТУРЫ ШАБЛОНОВ")
    print("=" * 50)
    
    # Импортируем сервис шаблонов
    try:
        from app.services.emr_templates import EMRTemplateService
        
        # Получаем предустановленные шаблоны
        templates = EMRTemplateService.get_default_templates()
        print(f"✅ Загружено {len(templates)} предустановленных шаблонов:")
        
        for i, template in enumerate(templates, 1):
            print(f"\n{i}. {template['template_name']}")
            print(f"   Специализация: {template['specialty']}")
            print(f"   Описание: {template['description']}")
            print(f"   Секций: {len(template['sections'])}")
            
            # Показываем секции
            for section in template['sections']:
                print(f"     - {section['section_title']} ({len(section['fields'])} полей)")
        
        print("\n✅ Структура шаблонов корректна!")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки шаблонов: {e}")

def test_emr_models():
    """Тестирование моделей EMR"""
    print("\n🗄️ ТЕСТИРОВАНИЕ МОДЕЛЕЙ EMR")
    print("=" * 50)
    
    try:
        from app.models.emr_template import EMRTemplate, EMRVersion
        from app.schemas.emr_template import EMRTemplateCreate, EMRTemplateOut
        
        print("✅ Модели EMR загружены успешно:")
        print(f"   - EMRTemplate: {EMRTemplate.__tablename__}")
        print(f"   - EMRVersion: {EMRVersion.__tablename__}")
        print(f"   - EMRTemplateCreate: {EMRTemplateCreate.__name__}")
        print(f"   - EMRTemplateOut: {EMRTemplateOut.__name__}")
        
        # Тестируем создание схемы
        test_template_data = {
            "name": "Тестовый шаблон",
            "description": "Тестовое описание",
            "specialty": "general",
            "template_structure": {"test": "data"},
            "is_active": True,
            "is_public": True
        }
        
        template_schema = EMRTemplateCreate(**test_template_data)
        print(f"✅ Схема EMRTemplateCreate работает корректно")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки моделей: {e}")

if __name__ == "__main__":
    print("🏥 ТЕСТИРОВАНИЕ EMR СИСТЕМЫ")
    print("=" * 60)
    
    # Запускаем тесты
    test_emr_endpoints()
    test_emr_templates_structure()
    test_emr_models()
    
    print("\n🎉 ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
