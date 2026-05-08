"""
Настройка Gemini API ключа
"""
import os
import secrets
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


def _require_env_write_confirmation():
    if os.getenv("CONFIRM_SETUP_GEMINI_WRITE_ENV") != "1":
        raise RuntimeError(
            "Refusing to create or overwrite backend/.env from setup_gemini_api.py. "
            "Set CONFIRM_SETUP_GEMINI_WRITE_ENV=1 only for an explicit local secret update."
        )


def _read_postgres_database_url():
    database_url = input("DATABASE_URL (PostgreSQL, required): ").strip()
    if not database_url:
        print("DATABASE_URL is required. Create backend/.env manually or rerun this helper.")
        return None

    lowered = database_url.lower()
    if "sqlite" in lowered or not (
        lowered.startswith("postgresql://")
        or lowered.startswith("postgresql+psycopg://")
        or lowered.startswith("postgresql+psycopg2://")
    ):
        print("DATABASE_URL must be a PostgreSQL URL; SQLite is not supported for runtime env files.")
        return None

    return database_url

def setup_gemini_api():
    """Настройка Gemini API"""
    print("🔧 Настройка Gemini API...")
    
    # Проверяем, есть ли уже файл .env
    env_file = "backend/.env"
    
    if os.path.exists(env_file):
        print(f"✅ Файл {env_file} уже существует")
        
        # Читаем существующий файл
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "GEMINI_API_KEY" in content:
            print("✅ GEMINI_API_KEY уже настроен в файле")
        else:
            print("⚠️ GEMINI_API_KEY не найден в файле")
            print("📝 Добавьте строку: GEMINI_API_KEY=ваш_ключ_здесь")
    else:
        print(f"❌ Файл {env_file} не существует")
        print("📝 Создайте файл backend/.env с содержимым:")
        print("   GEMINI_API_KEY=ваш_ключ_здесь")
    
    print(f"\n🔍 Проверка переменных окружения:")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "ваш_ключ_здесь":
        print("✅ GEMINI_API_KEY: настроен (значение скрыто)")
    else:
        print("❌ GEMINI_API_KEY: не настроен")
    
    print(f"\n📋 Инструкция:")
    print(f"1. Получите API ключ: https://makersuite.google.com/app/apikey")
    print(f"2. Создайте файл backend/.env")
    print(f"3. Добавьте строку: GEMINI_API_KEY=AIza...")
    print(f"4. Перезапустите backend сервер")
    
    # Предлагаем создать файл .env
    create_env = input(f"\n❓ Создать файл {env_file}? (y/n): ").lower().strip()
    
    if create_env == 'y':
        api_key = input("🔑 Введите ваш Gemini API ключ: ").strip()
        
        if api_key and api_key.startswith("AIza"):
            database_url = _read_postgres_database_url()
            if not database_url:
                return
            secret_key = secrets.token_urlsafe(48)
            env_content = f"""# AI Provider API Keys
GEMINI_API_KEY={api_key}

# MCP Settings
MCP_ENABLED=true
MCP_LOG_REQUESTS=true
MCP_FALLBACK_TO_DIRECT=true
MCP_REQUEST_TIMEOUT=30
MCP_HEALTH_CHECK_INTERVAL=60
MCP_MAX_BATCH_SIZE=10

# Database
DATABASE_URL={database_url}

# Auth
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:8080","http://127.0.0.1:8080"]
"""
            
            _require_env_write_confirmation()
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            print(f"✅ Файл {env_file} создан с Gemini API ключом")
            print(f"🔄 Перезапустите backend сервер для применения изменений")
        else:
            print("❌ Неверный формат API ключа. Ключ должен начинаться с 'AIza'")
    else:
        print("📝 Создайте файл вручную с содержимым выше")

if __name__ == "__main__":
    setup_gemini_api()
