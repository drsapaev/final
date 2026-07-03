#!/usr/bin/env python3
"""
Миграция для добавления расширенных полей в таблицу EMR
"""
import sys
import os

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.db.session import engine
from sqlalchemy import text, inspect


def migrate_emr_table():
    """Добавить недостающие поля в таблицу EMR"""
    print("🔄 МИГРАЦИЯ ТАБЛИЦЫ EMR")
    print("=" * 40)
    
    try:
        inspector = inspect(engine)
        
        # Проверяем, существует ли таблица EMR
        if 'emr' not in inspector.get_table_names():
            print("❌ Таблица EMR не найдена")
            return False
        
        # Получаем текущие колонки
        columns = inspector.get_columns('emr')
        column_names = [col['name'] for col in columns]
        
        print(f"📊 Текущие колонки EMR: {len(column_names)}")
        
        # Поля, которые нужно добавить
        new_fields = {
            'vital_signs': 'TEXT',
            'lab_results': 'TEXT',
            'imaging_results': 'TEXT',
            'medications': 'TEXT',
            'allergies': 'TEXT',
            'family_history': 'TEXT',
            'social_history': 'TEXT',
            'ai_suggestions': 'TEXT',
            'ai_confidence': 'REAL',
            'template_id': 'INTEGER',
            'specialty': 'VARCHAR(100)',
            'updated_at': 'DATETIME',
            'saved_at': 'DATETIME'
        }
        
        with engine.connect() as conn:
            added_fields = []
            
            for field_name, field_type in new_fields.items():
                if field_name not in column_names:
                    try:
                        # Добавляем поле
                        conn.execute(text(f"ALTER TABLE emr ADD COLUMN {field_name} {field_type}"))
                        added_fields.append(field_name)
                        print(f"   ✅ Добавлено поле: {field_name}")
                    except Exception as e:
                        print(f"   ⚠️ Ошибка добавления поля {field_name}: {e}")
                else:
                    print(f"   📋 Поле уже существует: {field_name}")
            
            # Коммитим изменения
            conn.commit()
            
            print(f"\n✅ Миграция завершена")
            print(f"📝 Добавлено полей: {len(added_fields)}")
            
            if added_fields:
                print("🔄 Обновляем существующие записи...")
                
                # Устанавливаем значения по умолчанию для JSON полей
                json_fields = ['vital_signs', 'lab_results', 'imaging_results', 
                              'medications', 'allergies', 'family_history', 
                              'social_history', 'ai_suggestions']
                
                for field in json_fields:
                    if field in added_fields:
                        conn.execute(text(f"UPDATE emr SET {field} = '{{}}' WHERE {field} IS NULL"))  # nosec B608 — one-shot EMR migration script, hardcoded queries
                
                # Устанавливаем ai_confidence по умолчанию
                if 'ai_confidence' in added_fields:
                    conn.execute(text("UPDATE emr SET ai_confidence = 0.0 WHERE ai_confidence IS NULL"))
                
                # Устанавливаем даты
                if 'updated_at' in added_fields:
                    conn.execute(text("UPDATE emr SET updated_at = created_at WHERE updated_at IS NULL"))
                
                if 'saved_at' in added_fields:
                    conn.execute(text("UPDATE emr SET saved_at = created_at WHERE saved_at IS NULL"))
                
                conn.commit()
                print("   ✅ Значения по умолчанию установлены")
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False


if __name__ == "__main__":
    success = migrate_emr_table()
    sys.exit(0 if success else 1)
