"""
Тест доступных моделей Gemini API с загрузкой .env
"""
import google.generativeai as genai
import os
from dotenv import load_dotenv

def test_gemini_models():
    """Тестируем доступные модели Gemini"""
    print("🔍 Тестирование доступных моделей Gemini API...")

    # Загружаем .env файл
    load_dotenv('.env')

    # Получаем API ключ
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY не найден в .env файле")
        return

    print("✅ API ключ найден: [REDACTED]")

    # Настраиваем Gemini
    genai.configure(api_key=api_key)

    try:
        # Получаем список доступных моделей
        print("\n📋 Получение списка доступных моделей...")
        models = genai.list_models()

        # Конвертируем в список
        models_list = list(models)
        print(f"✅ Найдено моделей: {len(models_list)}")

        gemini_models = []
        all_models = []
        for model in models_list:
            all_models.append(model.name)
            if 'gemini' in model.name.lower():
                gemini_models.append(model.name)
                print(f"  - {model.name}")

        if not gemini_models:
            print("❌ Модели Gemini не найдены")
            print(f"\n📋 Все доступные модели ({len(all_models)}):")
            for model_name in all_models[:10]:  # Показываем первые 10
                print(f"  - {model_name}")
            if len(all_models) > 10:
                print(f"  ... и еще {len(all_models) - 10} моделей")
            return

        # Тестируем каждую модель
        print(f"\n🧪 Тестирование {len(gemini_models)} моделей Gemini...")

        working_model = None
        for model_name in gemini_models:
            try:
                print(f"\n🔍 Тестирование модели: {model_name}")
                model = genai.GenerativeModel(model_name)

                # Простой тест генерации
                response = model.generate_content("Привет! Как дела?")
                print(f"  ✅ Модель работает: {response.text[:50]}...")

                # Если модель работает, используем её
                working_model = model_name
                print(f"  🎯 Рабочая модель найдена: {model_name}")
                break

            except Exception as e:
                print(f"  ❌ Ошибка: {str(e)}")

        if working_model:
            print(f"\n🎉 Рекомендуемая модель для использования: {working_model}")
        else:
            print("\n❌ Ни одна модель не работает")

    except Exception as e:
        print(f"❌ Ошибка при получении моделей: {str(e)}")

if __name__ == "__main__":
    test_gemini_models()