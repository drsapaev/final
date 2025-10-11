#!/usr/bin/env python3
"""
Скрипт для настройки DeepSeek AI - бесплатная альтернатива Gemini
"""
import os
import sys

def setup_deepseek_api():
    print("=" * 60)
    print("🔧 НАСТРОЙКА DEEPSEEK AI")
    print("=" * 60)
    print("\n💡 DeepSeek - это бесплатный AI провайдер с отличным")
    print("   качеством для медицинских задач и БЕЗ блокировок!")
    
    env_path = os.path.join("backend", ".env")
    
    # Проверяем существование файла
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# AI Provider API Keys\n")
        print(f"✅ Файл {env_path} создан")
    
    # Читаем содержимое
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Проверяем наличие ключа DeepSeek
    if "DEEPSEEK_API_KEY=" in content and "DEEPSEEK_API_KEY=sk-" in content:
        print("\n✅ DEEPSEEK_API_KEY уже настроен!")
        for line in content.split("\n"):
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=")[1].strip()
                if key and key != "":
                    print(f"   Текущий ключ: {key[:20]}...")
                    update = input("\n🔄 Обновить ключ? (y/n): ").strip().lower()
                    if update != 'y':
                        print("\n✅ Используем существующий ключ")
                        return
    
    # Запрашиваем новый ключ
    print("\n" + "=" * 60)
    print("📋 ИНСТРУКЦИЯ:")
    print("=" * 60)
    print("1. Откройте https://platform.deepseek.com/api_keys")
    print("2. Зарегистрируйтесь (если еще не сделали)")
    print("3. Нажмите 'Create API Key'")
    print("4. Скопируйте созданный ключ (начинается с sk-...)")
    print("=" * 60)
    
    api_key = input("\n🔑 Введите ваш DEEPSEEK_API_KEY: ").strip()
    
    if not api_key:
        print("\n❌ Ключ не введен. Отмена.")
        return
    
    if not api_key.startswith("sk-"):
        print("\n⚠️  ВНИМАНИЕ: Ключ обычно начинается с 'sk-'")
        confirm = input("   Продолжить все равно? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\n❌ Отмена.")
            return
    
    # Обновляем файл .env
    lines = content.split("\n")
    updated_lines = []
    key_updated = False
    
    for line in lines:
        if line.startswith("DEEPSEEK_API_KEY="):
            updated_lines.append(f"DEEPSEEK_API_KEY={api_key}")
            key_updated = True
        else:
            updated_lines.append(line)
    
    if not key_updated:
        # Добавляем ключ в конец
        if not content.endswith("\n"):
            updated_lines.append("")
        updated_lines.append(f"DEEPSEEK_API_KEY={api_key}")
    
    # Записываем обновленный файл
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_lines))
    
    print("\n" + "=" * 60)
    print("✅ НАСТРОЙКА ЗАВЕРШЕНА")
    print("=" * 60)
    print(f"📁 Файл: {env_path}")
    print(f"🔑 Ключ: {api_key[:20]}...")
    print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Перезапустите backend сервер")
    print("2. Система автоматически будет использовать DeepSeek AI")
    print("3. Протестируйте в HTML тестере")
    print("\n💡 ПРЕИМУЩЕСТВА DEEPSEEK:")
    print("   ✅ Бесплатный API")
    print("   ✅ НЕТ блокировок медицинского контента")
    print("   ✅ Высокое качество ответов")
    print("   ✅ Быстрая обработка")
    print("=" * 60)

if __name__ == "__main__":
    try:
        setup_deepseek_api()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

