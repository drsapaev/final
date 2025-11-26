#!/usr/bin/env python3
"""
Создание таблицы для версий EMR
"""
import sys
import os

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.db.session import engine
from app.models.emr_version import EMRVersion
from app.db.base import Base


def create_emr_versions_table():
    """Создать таблицу для версий EMR"""
    print("🔄 СОЗДАНИЕ ТАБЛИЦЫ EMR_VERSIONS")
    print("=" * 40)
    
    try:
        # Создаем таблицу
        Base.metadata.create_all(bind=engine, tables=[EMRVersion.__table__])
        print("✅ Таблица emr_versions создана успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания таблицы: {e}")
        return False


if __name__ == "__main__":
    success = create_emr_versions_table()
    sys.exit(0 if success else 1)
