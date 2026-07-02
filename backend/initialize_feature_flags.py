"""
Скрипт для инициализации предопределенных фича-флагов
"""
import sys
import os

# Добавляем путь к приложению
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.services.feature_flags import initialize_feature_flags

def require_feature_flags_confirmation():
    if os.getenv("CONFIRM_INITIALIZE_FEATURE_FLAGS") != "1":
        raise RuntimeError(
            "Refusing to initialize feature flags. "
            "Set CONFIRM_INITIALIZE_FEATURE_FLAGS=1 only for an explicit feature-flag seed run."
        )


def require_postgres_database_url():
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before initializing feature flags.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError(
            "initialize_feature_flags.py requires PostgreSQL; SQLite is not allowed."
        )


def main():
    """Инициализирует предопределенные фича-флаги"""
    require_feature_flags_confirmation()
    require_postgres_database_url()

    print("🎛️ Инициализация фича-флагов...")
    
    db = SessionLocal()
    try:
        initialize_feature_flags(db)
        print("✅ Фича-флаги успешно инициализированы!")
        
        # Выводим список созданных флагов
        from app.services.feature_flags import PREDEFINED_FLAGS
        print("\n📋 Созданные фича-флаги:")
        for flag in PREDEFINED_FLAGS:
            print(f"  • {flag['key']}: {flag['name']} ({'включен' if flag['enabled'] else 'выключен'})")
            
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return 1
    finally:
        db.close()
    
    return 0

if __name__ == "__main__":
    exit(main())
