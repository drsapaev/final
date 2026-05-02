#!/usr/bin/env python3
"""
Скрипт для проверки загруженных API ключей
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.core.config import settings

def check_api_keys():
    print("=" * 60)
    print("🔍 ПРОВЕРКА API КЛЮЧЕЙ")
    print("=" * 60)
    
    print("\n📋 Проверка переменных окружения:")
    print(f"  OPENAI_API_KEY: {'✅ Установлен' if os.getenv('OPENAI_API_KEY') else '❌ Не установлен'}")
    print(f"  GEMINI_API_KEY: {'✅ Установлен' if os.getenv('GEMINI_API_KEY') else '❌ Не установлен'}")
    print(f"  DEEPSEEK_API_KEY: {'✅ Установлен' if os.getenv('DEEPSEEK_API_KEY') else '❌ Не установлен'}")
    
    print("\n📋 Проверка настроек приложения:")
    print(f"  settings.OPENAI_API_KEY: {'✅ Установлен' if getattr(settings, 'OPENAI_API_KEY', None) else '❌ Не установлен'}")
    print(f"  settings.GEMINI_API_KEY: {'✅ Установлен' if getattr(settings, 'GEMINI_API_KEY', None) else '❌ Не установлен'}")
    print(f"  settings.DEEPSEEK_API_KEY: {'✅ Установлен' if getattr(settings, 'DEEPSEEK_API_KEY', None) else '❌ Не установлен'}")
    
    print("\n📋 Значения ключей (первые 20 символов):")
    if os.getenv('OPENAI_API_KEY'):
        print(f"  OPENAI: {os.getenv('OPENAI_API_KEY')[:20]}...")
    if os.getenv('GEMINI_API_KEY'):
        print(f"  GEMINI: {os.getenv('GEMINI_API_KEY')[:20]}...")
    if os.getenv('DEEPSEEK_API_KEY'):
        print(f"  DEEPSEEK: {os.getenv('DEEPSEEK_API_KEY')[:20]}...")
    
    print("\n📋 Значения из settings:")
    if getattr(settings, 'OPENAI_API_KEY', None):
        print(f"  OPENAI: {getattr(settings, 'OPENAI_API_KEY')[:20]}...")
    if getattr(settings, 'GEMINI_API_KEY', None):
        print(f"  GEMINI: {getattr(settings, 'GEMINI_API_KEY')[:20]}...")
    if getattr(settings, 'DEEPSEEK_API_KEY', None):
        print(f"  DEEPSEEK: {getattr(settings, 'DEEPSEEK_API_KEY')[:20]}...")
    
    print("\n📁 Проверка файла .env:")
    env_path = os.path.join("backend", ".env")
    if os.path.exists(env_path):
        print(f"  ✅ Файл {env_path} существует")
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"  {'✅' if 'OPENAI_API_KEY=' in content else '❌'} OPENAI_API_KEY в файле")
            print(f"  {'✅' if 'GEMINI_API_KEY=' in content else '❌'} GEMINI_API_KEY в файле")
            print(f"  {'✅' if 'DEEPSEEK_API_KEY=' in content else '❌'} DEEPSEEK_API_KEY в файле")
    else:
        print(f"  ❌ Файл {env_path} не найден")
    
    print("=" * 60)

if __name__ == "__main__":
    try:
        check_api_keys()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

