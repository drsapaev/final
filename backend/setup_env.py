#!/usr/bin/env python3
"""
Скрипт для создания базового .env файла
"""
import os
import secrets

def create_env_file():
    """Создает базовый .env файл с безопасными настройками"""
    
    # Генерируем безопасный SECRET_KEY
    secret_key = secrets.token_urlsafe(32)
    
    env_content = f"""# ===========================================
# КЛИНИКА - ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ===========================================

# --- ОСНОВНЫЕ НАСТРОЙКИ ---
ENV=dev
APP_NAME=Clinic Manager
APP_VERSION=0.9.0
API_V1_STR=/api/v1

# --- БАЗА ДАННЫХ ---
DATABASE_URL=sqlite:///./clinic.db

# --- АУТЕНТИФИКАЦИЯ ---
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# --- CORS ---
CORS_ALLOW_ALL=0
CORS_ORIGINS=http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173

# --- ВРЕМЯ И ОЧЕРЕДЬ ---
TIMEZONE=Asia/Tashkent
QUEUE_START_HOUR=7
ONLINE_MAX_PER_DAY=15

# --- PDF И ПЕЧАТЬ ---
PDF_FOOTER_ENABLED=1
CLINIC_LOGO_PATH=

# --- ПРИНТЕР (ESC/POS) ---
PRINTER_TYPE=none
PRINTER_NET_HOST=
PRINTER_NET_PORT=
PRINTER_USB_VID=
PRINTER_USB_PID=

# --- ЛИЦЕНЗИРОВАНИЕ ---
REQUIRE_LICENSE=0
LICENSE_ALLOW_HEALTH=1

# --- FIREBASE (PUSH УВЕДОМЛЕНИЯ) ---
# Раскомментируйте и настройте для реальных push-уведомлений
# FIREBASE_PROJECT_ID=your-project-id
# FIREBASE_PRIVATE_KEY_ID=your-key-id
# FIREBASE_PRIVATE_KEY=your-private-key
# FIREBASE_CLIENT_EMAIL=your-client-email
# FIREBASE_CLIENT_ID=your-client-id
# FIREBASE_CLIENT_CERT_URL=your-cert-url

# --- TELEGRAM (УВЕДОМЛЕНИЯ) ---
# Раскомментируйте для интеграции с Telegram
# TELEGRAM_BOT_TOKEN=your-bot-token
# TELEGRAM_CHAT_ID=your-chat-id

# --- ПЛАТЕЖИ ---
# Раскомментируйте для интеграции с платежными системами
# PAYME_MERCHANT_ID=your-merchant-id
# PAYME_SECRET_KEY=your-secret-key
# PAYME_TEST_MODE=1
"""

    # Проверяем, существует ли уже .env
    if os.path.exists('.env'):
        print("⚠️  Файл .env уже существует!")
        response = input("Перезаписать? (y/N): ").lower().strip()
        if response != 'y':
            print("❌ Отменено")
            return False
    
    # Создаем .env файл
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print("✅ Файл .env создан успешно!")
        print(f"🔑 SECRET_KEY сгенерирован: {secret_key[:20]}...")
        print("\n📋 Следующие шаги:")
        print("1. Перезапустите backend")
        print("2. При необходимости добавьте дополнительные настройки")
        print("3. Для продакшена смените SECRET_KEY")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания .env: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Настройка переменных окружения для клиники")
    print("=" * 50)
    create_env_file()
