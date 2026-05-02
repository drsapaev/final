#!/usr/bin/env python3
"""
Миграция для добавления поля notes в таблицу lab_results
"""
import sys
import os

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.db.session import engine
from sqlalchemy import text, inspect


def migrate_lab_results_table():
    """Добавить поле notes в таблицу lab_results"""
    print("🔄 МИГРАЦИЯ ТАБЛИЦЫ LAB_RESULTS")
    print("=" * 40)
    
    try:
        inspector = inspect(engine)
        
        # Проверяем, существует ли таблица lab_results
        if 'lab_results' not in inspector.get_table_names():
            print("❌ Таблица lab_results не найдена")
            return False
        
        # Получаем текущие колонки
        columns = inspector.get_columns('lab_results')
        column_names = [col['name'] for col in columns]
        
        print(f"📊 Текущие колонки lab_results: {len(column_names)}")
        
        with engine.connect() as conn:
            if 'notes' not in column_names:
                try:
                    # Добавляем поле notes
                    conn.execute(text("ALTER TABLE lab_results ADD COLUMN notes VARCHAR(1000)"))
                    conn.commit()
                    print("   ✅ Добавлено поле: notes")
                except Exception as e:
                    print(f"   ⚠️ Ошибка добавления поля notes: {e}")
                    return False
            else:
                print("   📋 Поле notes уже существует")
            
            print("✅ Миграция завершена")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False


if __name__ == "__main__":
    success = migrate_lab_results_table()
    sys.exit(0 if success else 1)
