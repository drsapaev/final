#!/usr/bin/env python3
"""
Тест загрузки DeepSeek API ключа
"""
import os
import sys
from pathlib import Path

# Добавляем путь к backend
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Явно загружаем .env из backend
from dotenv import load_dotenv
env_path = Path(__file__).parent / "backend" / ".env"
print(f"📁 Загрузка .env из: {env_path}")
print(f"📁 Файл существует: {env_path.exists()}")
load_dotenv(env_path)

print("\n" + "=" * 60)
print("🔍 ПРОВЕРКА ЗАГРУЗКИ DEEPSEEK API КЛЮЧА")
print("=" * 60)

print("\n📋 Проверка переменных окружения:")
deepseek_key = os.getenv("DEEPSEEK_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

print(f"  DEEPSEEK_API_KEY: {'✅ ' + deepseek_key[:20] + '...' if deepseek_key else '❌ Не установлен'}")
print(f"  GEMINI_API_KEY: {'✅ ' + gemini_key[:20] + '...' if gemini_key else '❌ Не установлен'}")
print(f"  OPENAI_API_KEY: {'✅ ' + openai_key[:20] + '...' if openai_key else '❌ Не установлен'}")

if deepseek_key:
    print("\n🎉 DeepSeek API ключ успешно загружен!")
    print(f"   Ключ: {deepseek_key[:20]}...")
    
    # Проверяем инициализацию AI Manager
    print("\n📋 Проверка AI Manager:")
    from backend.app.services.ai.ai_manager import get_ai_manager, AIProviderType
    
    ai_manager = get_ai_manager()
    print(f"  Доступные провайдеры: {ai_manager.get_available_providers()}")
    print(f"  Провайдер по умолчанию: {ai_manager.default_provider}")
    
    if AIProviderType.DEEPSEEK in ai_manager.providers:
        print(f"  ✅ DeepSeek провайдер инициализирован!")
        print(f"  ✅ DeepSeek будет использоваться для AI запросов!")
    else:
        print(f"  ❌ DeepSeek провайдер НЕ инициализирован!")
        
else:
    print("\n❌ DeepSeek API ключ НЕ загружен!")
    print("   Проверьте backend/.env файл")

print("=" * 60)

