#!/usr/bin/env python3
"""
Скрипт для добавления новых полей в таблицы appointments и patients
для поддержки улучшенной таблицы регистратора.

Добавляемые поля:
- appointments.visit_type (paid/repeat/free)
- appointments.payment_type (cash/card/online) 
- appointments.services (JSON список услуг)
- patients.address уже есть в модели

Запуск: python add_registrar_fields.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.config import settings

def add_registrar_fields():
    """Добавляет новые поля для регистратора"""
    db = SessionLocal()
    
    try:
        print("🔧 Добавление новых полей для регистратора...")
        
        # Проверяем и добавляем поля в таблицу appointments
        print("📋 Обновление таблицы appointments...")
        
        # Добавляем visit_type
        try:
            db.execute(text("""
                ALTER TABLE appointments 
                ADD COLUMN visit_type VARCHAR(16) DEFAULT 'paid'
            """))
            print("✅ Добавлено поле visit_type")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("ℹ️  Поле visit_type уже существует")
            else:
                print(f"❌ Ошибка добавления visit_type: {e}")
        
        # Добавляем payment_type
        try:
            db.execute(text("""
                ALTER TABLE appointments 
                ADD COLUMN payment_type VARCHAR(16) DEFAULT 'cash'
            """))
            print("✅ Добавлено поле payment_type")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("ℹ️  Поле payment_type уже существует")
            else:
                print(f"❌ Ошибка добавления payment_type: {e}")
        
        # Добавляем services (JSON)
        try:
            db.execute(text("""
                ALTER TABLE appointments 
                ADD COLUMN services JSON
            """))
            print("✅ Добавлено поле services")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("ℹ️  Поле services уже существует")
            else:
                print(f"❌ Ошибка добавления services: {e}")
        
        # Проверяем поле address в таблице patients (SQLite синтаксис)
        print("👤 Проверка таблицы patients...")
        try:
            result = db.execute(text("""
                PRAGMA table_info(patients)
            """)).fetchall()
            
            address_exists = any(col[1] == 'address' for col in result)
            
            if address_exists:
                print("ℹ️  Поле address в таблице patients уже существует")
            else:
                db.execute(text("""
                    ALTER TABLE patients 
                    ADD COLUMN address VARCHAR(512)
                """))
                print("✅ Добавлено поле address в таблицу patients")
        except Exception as e:
            print(f"❌ Ошибка с полем address: {e}")
        
        # Коммитим изменения
        db.commit()
        print("🎉 Все изменения успешно применены!")
        
        # Показываем структуру таблиц (SQLite синтаксис)
        print("\n📊 Текущая структура таблицы appointments:")
        result = db.execute(text("""
            PRAGMA table_info(appointments)
        """)).fetchall()
        
        for row in result:
            print(f"  - {row[1]}: {row[2]} {'NULL' if row[3] == 0 else 'NOT NULL'} {f'DEFAULT {row[4]}' if row[4] else ''}")
        
        print("\n👤 Структура таблицы patients:")
        result = db.execute(text("""
            PRAGMA table_info(patients)
        """)).fetchall()
        
        for row in result:
            if row[1] in ['address', 'last_name', 'first_name', 'phone']:  # Показываем только ключевые поля
                print(f"  - {row[1]}: {row[2]} {'NULL' if row[3] == 0 else 'NOT NULL'}")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Запуск миграции полей регистратора...")
    print(f"📡 База данных: {settings.DATABASE_URL}")
    
    try:
        add_registrar_fields()
        print("\n✅ Миграция завершена успешно!")
        print("\n📝 Следующие шаги:")
        print("1. Перезапустите backend сервер")
        print("2. Проверьте работу таблицы в регистратуре")
        print("3. Новые записи будут содержать все поля")
    except Exception as e:
        print(f"\n❌ Миграция не удалась: {e}")
        sys.exit(1)
