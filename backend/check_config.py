#!/usr/bin/env python3
"""
Скрипт для проверки загруженных настроек из .env
"""
import os
import sys
from pathlib import Path

# Добавляем путь к приложению
sys.path.append(str(Path(__file__).parent))

def check_env_file():
    """Проверяет наличие и содержимое .env файла"""
    print("🔍 Проверка файла .env")
    print("=" * 50)
    
    env_path = Path(".env")
    if env_path.exists():
        print("✅ Файл .env найден")
        
        # Читаем содержимое
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        non_empty_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
        
        print(f"📊 Найдено {len(non_empty_lines)} настроек")
        print()
        
        # Показываем основные настройки
        important_settings = [
            'ENV', 'APP_NAME', 'APP_VERSION', 'API_V1_STR',
            'DATABASE_URL', 'SECRET_KEY', 'ALGORITHM', 'ACCESS_TOKEN_EXPIRE_MINUTES',
            'CORS_ALLOW_ALL', 'CORS_ORIGINS', 'TIMEZONE', 'QUEUE_START_HOUR',
            'PDF_FOOTER_ENABLED', 'PRINTER_TYPE', 'REQUIRE_LICENSE'
        ]
        
        print("🔧 Основные настройки:")
        for setting in important_settings:
            for line in lines:
                if line.startswith(f"{setting}="):
                    value = line.split('=', 1)[1].strip()
                    if setting == 'SECRET_KEY' and len(value) > 20:
                        value = value[:20] + "..."
                    print(f"  {setting}: {value}")
                    break
            else:
                print(f"  {setting}: ❌ не найдено")
        
        print()
        print("🔧 Дополнительные настройки:")
        for line in lines:
            if line.strip() and not line.strip().startswith('#') and '=' in line:
                key = line.split('=')[0].strip()
                if key not in important_settings:
                    value = line.split('=', 1)[1].strip()
                    if 'KEY' in key.upper() or 'TOKEN' in key.upper() or 'SECRET' in key.upper():
                        value = value[:10] + "..." if len(value) > 10 else "***"
                    print(f"  {key}: {value}")
        
    else:
        print("❌ Файл .env не найден")
        return False
    
    return True

def check_app_config():
    """Проверяет настройки, загруженные приложением"""
    print("\n🚀 Проверка настроек приложения")
    print("=" * 50)
    
    try:
        from app.core.config import get_settings
        settings = get_settings()
        
        print("✅ Настройки успешно загружены")
        print()
        
        # Основные настройки
        print("📋 Основные параметры:")
        print(f"  ENV: {settings.ENV}")
        print(f"  APP_NAME: {settings.APP_NAME}")
        print(f"  APP_VERSION: {settings.APP_VERSION}")
        print(f"  API_V1_STR: {settings.API_V1_STR}")
        print()
        
        # База данных
        print("🗄️ База данных:")
        print(f"  DATABASE_URL: {settings.DATABASE_URL}")
        print()
        
        # Аутентификация
        print("🔐 Аутентификация:")
        print(f"  SECRET_KEY: {settings.SECRET_KEY[:20]}...")
        print(f"  ALGORITHM: {settings.ALGORITHM}")
        print(f"  ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
        print()
        
        # CORS
        print("🌐 CORS:")
        print(f"  CORS_ALLOW_ALL: {getattr(settings, 'CORS_ALLOW_ALL', 'не установлено')}")
        print(f"  CORS_ORIGINS: {settings.BACKEND_CORS_ORIGINS}")
        print()
        
        # Время и очередь
        print("⏰ Время и очередь:")
        print(f"  TIMEZONE: {settings.TIMEZONE}")
        print(f"  QUEUE_START_HOUR: {settings.QUEUE_START_HOUR}")
        print(f"  ONLINE_MAX_PER_DAY: {settings.ONLINE_MAX_PER_DAY}")
        print()
        
        # PDF и печать
        print("📄 PDF и печать:")
        print(f"  PDF_FOOTER_ENABLED: {settings.PDF_FOOTER_ENABLED}")
        print(f"  CLINIC_LOGO_PATH: {settings.CLINIC_LOGO_PATH}")
        print()
        
        # Принтер
        print("🖨️ Принтер:")
        print(f"  PRINTER_TYPE: {settings.PRINTER_TYPE}")
        print(f"  PRINTER_NET_HOST: {settings.PRINTER_NET_HOST}")
        print(f"  PRINTER_NET_PORT: {settings.PRINTER_NET_PORT}")
        print()
        
        # Лицензирование
        print("📜 Лицензирование:")
        print(f"  REQUIRE_LICENSE: {getattr(settings, 'REQUIRE_LICENSE', 'не установлено')}")
        print(f"  LICENSE_ALLOW_HEALTH: {getattr(settings, 'LICENSE_ALLOW_HEALTH', 'не установлено')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        return False

def check_environment_variables():
    """Проверяет переменные окружения системы"""
    print("\n🌍 Проверка переменных окружения системы")
    print("=" * 50)
    
    env_vars = [
        'ENV', 'APP_NAME', 'DATABASE_URL', 'SECRET_KEY', 
        'CORS_ORIGINS', 'TIMEZONE', 'FIREBASE_PROJECT_ID'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if 'KEY' in var or 'SECRET' in var:
                value = value[:10] + "..." if len(value) > 10 else "***"
            print(f"  {var}: {value}")
        else:
            print(f"  {var}: ❌ не установлено")

def main():
    """Основная функция"""
    print("🔧 Проверка конфигурации системы клиники")
    print("=" * 60)
    
    # Проверяем .env файл
    env_ok = check_env_file()
    
    if env_ok:
        # Проверяем настройки приложения
        app_ok = check_app_config()
        
        # Проверяем переменные окружения
        check_environment_variables()
        
        print("\n" + "=" * 60)
        if app_ok:
            print("✅ Все настройки загружены корректно!")
            print("🚀 Система готова к работе")
        else:
            print("⚠️ Есть проблемы с загрузкой настроек")
    else:
        print("❌ Файл .env не найден. Запустите setup_env.py")

if __name__ == "__main__":
    main()
