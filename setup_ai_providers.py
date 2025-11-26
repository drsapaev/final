"""
Настройка AI провайдеров для получения реальных результатов
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.services.ai.ai_manager import get_ai_manager, AIProviderType

def setup_ai_providers():
    """Настройка AI провайдеров"""
    print("🔧 Настройка AI провайдеров для получения реальных результатов...")
    
    ai_manager = get_ai_manager()
    
    print(f"\n📋 Текущие провайдеры:")
    available_providers = ai_manager.get_available_providers()
    print(f"  Доступные: {available_providers}")
    print(f"  По умолчанию: {ai_manager.default_provider}")
    
    print(f"\n🔑 Проверка API ключей:")
    env_keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY")
    }
    
    for key_name, key_value in env_keys.items():
        if key_value and key_value != "your_openai_api_key_here":
            print(f"  ✅ {key_name}: {'*' * 8}...{key_value[-4:]}")
        else:
            print(f"  ❌ {key_name}: не настроен")
    
    print(f"\n📝 Инструкции для настройки:")
    print(f"1. Получите API ключи:")
    print(f"   - OpenAI: https://platform.openai.com/api-keys")
    print(f"   - Google Gemini: https://makersuite.google.com/app/apikey")
    print(f"   - DeepSeek: https://platform.deepseek.com/api_keys")
    print(f"")
    print(f"2. Создайте файл backend/.env с ключами:")
    print(f"   OPENAI_API_KEY=sk-your-key-here")
    print(f"   GEMINI_API_KEY=your-gemini-key-here")
    print(f"   DEEPSEEK_API_KEY=your-deepseek-key-here")
    print(f"")
    print(f"3. Перезапустите backend сервер")
    
    if not available_providers or available_providers == ["mock"]:
        print(f"\n⚠️  ВНИМАНИЕ: Используется только Mock провайдер!")
        print(f"   Для получения реальных результатов настройте API ключи.")
    else:
        print(f"\n✅ Настроены реальные AI провайдеры: {available_providers}")

if __name__ == "__main__":
    setup_ai_providers()
