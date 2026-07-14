"""
Тест AI провайдеров из backend директории
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Меняем рабочую директорию на backend
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.ai.ai_manager import get_ai_manager, AIProviderType
from app.core.config import get_settings

def test_ai_providers_from_backend():
    """Тестируем AI провайдеры из backend директории"""
    print("🔧 Тестирование AI провайдеров из backend директории...")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"📁 Файл .env: {os.path.exists('.env')}")

    # Проверяем настройки
    settings = get_settings()
    print(f"\n📋 Настройки из config.py:")
    print(f"  - OPENAI_API_KEY: {'есть' if settings.OPENAI_API_KEY else 'нет'}")
    print(f"  - GEMINI_API_KEY: {'есть' if settings.GEMINI_API_KEY else 'нет'}")
    print(f"  - DEEPSEEK_API_KEY: {'есть' if settings.DEEPSEEK_API_KEY else 'нет'}")

    # Проверяем переменные окружения
    print(f"\n🔑 Переменные окружения:")
    print(f"  - OPENAI_API_KEY: {'есть' if os.getenv('OPENAI_API_KEY') else 'нет'}")
    print(f"  - GEMINI_API_KEY: {'есть' if os.getenv('GEMINI_API_KEY') else 'нет'}")
    print(f"  - DEEPSEEK_API_KEY: {'есть' if os.getenv('DEEPSEEK_API_KEY') else 'нет'}")

    # Проверяем AI менеджер
    ai_manager = get_ai_manager()
    available_providers = ai_manager.get_available_providers()
    print(f"\n📋 Доступные провайдеры: {available_providers}")
    print(f"📋 Default провайдер: {ai_manager.default_provider}")

    if "gemini" in available_providers:
        print("✅ Gemini провайдер настроен!")
    else:
        print("❌ Gemini провайдер не настроен")

if __name__ == "__main__":
    test_ai_providers_from_backend()
