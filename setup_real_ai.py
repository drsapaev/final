#!/usr/bin/env python3
"""
Скрипт для настройки реального AI провайдера (Gemini)
"""
import os
import sys

def setup_gemini_api():
    print("=" * 60)
    print("🔧 НАСТРОЙКА GEMINI AI ПРОВАЙДЕРА")
    print("=" * 60)
    
    env_path = os.path.join("backend", ".env")
    
    # Проверяем существование файла
    if not os.path.exists(env_path):
        print(f"\n📝 Создаем файл {env_path}...")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# AI Provider API Keys\n")
            f.write("GEMINI_API_KEY=\n")
            f.write("\n# Other settings\n")
        print(f"✅ Файл {env_path} создан")
    else:
        print(f"✅ Файл {env_path} уже существует")
    
    # Читаем содержимое
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Проверяем наличие ключа
    if "GEMINI_API_KEY=" in content:
        if "GEMINI_API_KEY=AIza" in content:
            print("\n✅ GEMINI_API_KEY уже настроен!")
            
            # Показываем текущий ключ (частично)
            for line in content.split("\n"):
                if line.startswith("GEMINI_API_KEY="):
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
    print("1. Откройте https://aistudio.google.com/app/apikey")
    print("2. Войдите в Google аккаунт")
    print("3. Нажмите 'Create API Key' или 'Get API key'")
    print("4. Скопируйте созданный ключ (начинается с AIza...)")
    print("=" * 60)
    
    api_key = input("\n🔑 Введите ваш GEMINI_API_KEY: ").strip()
    
    if not api_key:
        print("\n❌ Ключ не введен. Отмена.")
        return
    
    if not api_key.startswith("AIza"):
        print("\n⚠️  ВНИМАНИЕ: Ключ должен начинаться с 'AIza'")
        confirm = input("   Продолжить все равно? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\n❌ Отмена.")
            return
    
    # Обновляем файл .env
    lines = content.split("\n")
    updated_lines = []
    key_updated = False
    
    for line in lines:
        if line.startswith("GEMINI_API_KEY="):
            updated_lines.append(f"GEMINI_API_KEY={api_key}")
            key_updated = True
        else:
            updated_lines.append(line)
    
    if not key_updated:
        # Добавляем ключ в конец
        updated_lines.append(f"\nGEMINI_API_KEY={api_key}")
    
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
    print("2. Система автоматически переключится на Gemini AI")
    print("3. Протестируйте в HTML тестере")
    print("=" * 60)
    
    # Предлагаем перезапустить сервер
    restart = input("\n🔄 Перезапустить backend сервер сейчас? (y/n): ").strip().lower()
    if restart == 'y':
        print("\n⏳ Останавливаем текущий сервер...")
        os.system("taskkill /F /IM python.exe /T >nul 2>&1")
        
        print("⏳ Запускаем новый сервер...")
        print("   Откройте новый терминал и запустите:")
        print("   cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 18000")
        print("\n✅ Готово!")

if __name__ == "__main__":
    try:
        setup_gemini_api()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

