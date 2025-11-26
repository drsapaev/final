"""
Тест форматирования результатов в HTML тестере
"""
import requests
import json

def test_html_tester_formatting():
    """Тестируем форматирование результатов"""
    print("🔍 Тестирование форматирования результатов...")
    
    base_url = "http://localhost:8000/api/v1"
    
    # Получаем токен
    try:
        auth_response = requests.post(
            f"{base_url}/auth/minimal-login",
            json={"username": "mcp_test", "password": "test123"},
            headers={"Content-Type": "application/json"}
        )
        
        if auth_response.status_code != 200:
            print(f"❌ Ошибка авторизации: {auth_response.status_code}")
            return
        
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        print("✅ Токен получен")
        
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    # Тест интерпретации анализов
    print(f"\n🔍 ТЕСТ: Интерпретация анализов")
    
    lab_data = {
        "results": [
            {
                "name": "Гемоглобин",
                "value": "120",
                "unit": "г/л",
                "reference": "120-160"
            },
            {
                "name": "Лейкоциты",
                "value": "15.2",
                "unit": "×10⁹/л",
                "reference": "4.0-9.0"
            },
            {
                "name": "СОЭ",
                "value": "25",
                "unit": "мм/ч",
                "reference": "2-15"
            }
        ],
        "patient_age": 45,
        "patient_gender": "female",
        "include_recommendations": True
    }
    
    try:
        response = requests.post(
            f"{base_url}/mcp/lab/interpret",
            json=lab_data,
            headers=headers
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Проверяем структуру данных
            print(f"\n📊 Структура ответа:")
            print(f"  - status: {data.get('status')}")
            print(f"  - data.status: {data.get('data', {}).get('status')}")
            print(f"  - data.ai_interpretation: {'есть' if data.get('data', {}).get('ai_interpretation') else 'нет'}")
            
            if data.get('data', {}).get('ai_interpretation'):
                ai = data['data']['ai_interpretation']
                print(f"\n🤖 AI интерпретация:")
                print(f"  - summary: {ai.get('summary')}")
                print(f"  - abnormal_values: {len(ai.get('abnormal_values', []))} шт.")
                print(f"  - possible_conditions: {len(ai.get('possible_conditions', []))} шт.")
                print(f"  - recommendations: {len(ai.get('recommendations', []))} шт.")
                
                # Показываем форматированный результат
                print(f"\n📋 ФОРМАТИРОВАННЫЙ РЕЗУЛЬТАТ:")
                print(f"✅ Интерпретация анализов выполнена!")
                print(f"")
                print(f"📊 {ai.get('summary')}")
                print(f"")
                
                if ai.get('abnormal_values'):
                    print(f"⚠️ Отклонения от нормы:")
                    for i, item in enumerate(ai['abnormal_values'], 1):
                        print(f"{i}. {item['parameter']}: {item['value']}")
                        print(f"   {item['interpretation']}")
                        print(f"   Клиническое значение: {item['clinical_significance']}")
                        print(f"")
                
                if ai.get('possible_conditions'):
                    print(f"🔍 Возможные состояния:")
                    for i, condition in enumerate(ai['possible_conditions'], 1):
                        print(f"{i}. {condition}")
                    print(f"")
                
                if ai.get('recommendations'):
                    print(f"💡 Рекомендации:")
                    for i, rec in enumerate(ai['recommendations'], 1):
                        print(f"{i}. {rec}")
                    print(f"")
                
                print(f"🚨 Срочная консультация: {'Требуется' if ai.get('urgency') == 'да' else 'Не требуется'}")
                
            else:
                print(f"❌ AI интерпретация отсутствует в ответе")
                print(f"Полный ответ: {json.dumps(data, ensure_ascii=False, indent=2)}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")

if __name__ == "__main__":
    test_html_tester_formatting()
