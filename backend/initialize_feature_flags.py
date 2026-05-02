"""
Скрипт для инициализации предопределенных фича-флагов
"""
import sys
import os

# Добавляем путь к приложению
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.services.feature_flags import initialize_feature_flags

def main():
    """Инициализирует предопределенные фича-флаги"""
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
