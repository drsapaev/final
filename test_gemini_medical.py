"""
Тест Gemini API для медицинских задач
"""
import os
import sys
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.ai.ai_manager import get_ai_manager, AIProviderType

async def test_gemini_medical():
    """Тестируем Gemini API для медицинских задач"""
    print("🧪 Тестирование Gemini API для медицинских задач...")
    
    ai_manager = get_ai_manager()
    
    # Проверяем доступные провайдеры
    available_providers = ai_manager.get_available_providers()
    print(f"📋 Доступные провайдеры: {available_providers}")
    
    if "gemini" not in available_providers:
        print("❌ Gemini провайдер не настроен!")
        print("🔧 Запустите: python setup_gemini_api.py")
        return
    
    print("✅ Gemini провайдер настроен")
    
    # Тестируем анализ жалоб
    test_complaints = [
        "Сильная головная боль и головокружение в течение последних 24 часов",
        "Острая боль в груди, отдающая в левую руку, сопровождающаяся одышкой",
        "Появились новые высыпания на коже, сопровождающиеся зудом и покраснением"
    ]
    
    for i, complaint in enumerate(test_complaints, 1):
        print(f"\n🔍 Тест {i}: Анализ жалобы")
        print(f"📝 Жалоба: {complaint}")
        
        try:
            # Получаем Gemini провайдер
            gemini_provider = ai_manager.get_provider(AIProviderType.GEMINI)
            
            if gemini_provider:
                # Тестируем анализ жалоб
                result = await gemini_provider.analyze_complaint(
                    complaint=complaint,
                    patient_info={"age": 45, "gender": "female"}
                )
                
                print(f"✅ Результат анализа:")
                print(f"   Предварительный диагноз: {result.get('preliminary_diagnosis', 'N/A')}")
                print(f"   Срочность: {result.get('urgency_level', 'N/A')}")
                print(f"   Рекомендации: {result.get('recommendations', 'N/A')}")
            else:
                print("❌ Gemini провайдер недоступен")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # Тестируем подсказки МКБ-10
    print(f"\n🔍 Тест: Подсказки МКБ-10")
    symptoms = ["головная боль", "тошнота", "светобоязнь"]
    
    try:
        gemini_provider = ai_manager.get_provider(AIProviderType.GEMINI)
        
        if gemini_provider:
            result = await gemini_provider.suggest_icd10(
                symptoms=symptoms,
                diagnosis="Мигрень"
            )
            
            print(f"✅ Результат МКБ-10:")
            print(f"   Предложенные коды: {result.get('suggested_codes', 'N/A')}")
            print(f"   Уверенность: {result.get('confidence', 'N/A')}")
        else:
            print("❌ Gemini провайдер недоступен")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini_medical())
