"""
Тест проблемных функций МКБ-10 и интерпретации анализов
"""
import os
import sys
import asyncio
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.ai.ai_manager import get_ai_manager, AIProviderType

async def test_problematic_functions():
    """Тестируем проблемные функции"""
    print("🔍 Тестирование проблемных функций...")

    ai_manager = get_ai_manager()

    # Проверяем доступные провайдеры
    available_providers = ai_manager.get_available_providers()
    print(f"📋 Доступные провайдеры: {available_providers}")

    if "gemini" not in available_providers:
        print("❌ Gemini провайдер не настроен!")
        return

    print("✅ Gemini провайдер настроен")

    # Тест 1: МКБ-10 подсказки
    print(f"\n🔍 ТЕСТ 1: Подсказки МКБ-10")
    symptoms = ["головная боль", "тошнота", "светобоязнь"]
    diagnosis = "Мигрень"

    try:
        result = await ai_manager.suggest_icd10(
            symptoms=symptoms,
            diagnosis=diagnosis,
            provider_type=AIProviderType.GEMINI
        )

        print(f"📝 Симптомы: {symptoms}")
        print(f"📝 Диагноз: {diagnosis}")
        print(f"📊 Результат: {json.dumps(result, ensure_ascii=False, indent=2)}")

        if isinstance(result, list) and len(result) > 0:
            print("✅ МКБ-10 работает корректно")
        else:
            print("❌ МКБ-10 возвращает пустой результат")

    except Exception as e:
        print(f"❌ Ошибка МКБ-10: {e}")
        import traceback
        traceback.print_exc()

    # Тест 2: Интерпретация анализов
    print(f"\n🔍 ТЕСТ 2: Интерпретация анализов")
    lab_results = [
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
    ]

    patient_info = {"age": 45, "gender": "female"}

    try:
        result = await ai_manager.interpret_lab_results(
            results=lab_results,
            patient_info=patient_info,
            provider_type=AIProviderType.GEMINI
        )

        print(f"📝 Анализы: {len(lab_results)} параметров")
        print(f"📝 Пациент: {patient_info}")
        print(f"📊 Результат: {json.dumps(result, ensure_ascii=False, indent=2)}")

        if isinstance(result, dict) and "summary" in result:
            print("✅ Интерпретация анализов работает корректно")
        else:
            print("❌ Интерпретация анализов возвращает некорректный результат")

    except Exception as e:
        print(f"❌ Ошибка интерпретации: {e}")
        import traceback
        traceback.print_exc()

    # Тест 3: Прямой вызов Gemini провайдера
    print(f"\n🔍 ТЕСТ 3: Прямой вызов Gemini провайдера")

    try:
        gemini_provider = ai_manager.get_provider(AIProviderType.GEMINI)

        if gemini_provider:
            print("✅ Gemini провайдер получен")

            # Тестируем МКБ-10 напрямую
            icd_result = await gemini_provider.suggest_icd10(symptoms, diagnosis)
            print(f"📊 Прямой МКБ-10: {json.dumps(icd_result, ensure_ascii=False, indent=2)}")

            # Тестируем анализы напрямую
            lab_result = await gemini_provider.interpret_lab_results(lab_results, patient_info)
            print(f"📊 Прямые анализы: {json.dumps(lab_result, ensure_ascii=False, indent=2)}")
        else:
            print("❌ Gemini провайдер недоступен")

    except Exception as e:
        print(f"❌ Ошибка прямого вызова: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_problematic_functions())
