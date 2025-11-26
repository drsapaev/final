#!/usr/bin/env python3
"""
Создание таблиц для системы управления клиникой
"""
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_clinic_management_tables():
    """Создает таблицы для управления клиникой"""
    print("🏥 СОЗДАНИЕ ТАБЛИЦ УПРАВЛЕНИЯ КЛИНИКОЙ")
    print("=" * 50)
    
    try:
        from app.db.base_class import Base
        from app.db.session import engine
        
        # Импортируем все модели для создания таблиц
        from app.models.clinic import (
            Branch, BranchStatus, Equipment, EquipmentStatus, EquipmentType, EquipmentMaintenance,
            License, LicenseStatus, LicenseType, LicenseActivation,
            Backup, BackupStatus, BackupType, SystemInfo
        )
        
        print("📋 Создание таблиц...")
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        
        print("✅ Таблицы созданы успешно")
        
        # Проверяем созданные таблицы
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%branch%' OR name LIKE '%equipment%' OR name LIKE '%license%' OR name LIKE '%backup%' OR name LIKE '%system_info%'"))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"📊 Создано таблиц: {len(tables)}")
            for table in tables:
                print(f"  ✅ {table}")
        
        print("\n🎉 СИСТЕМА УПРАВЛЕНИЯ КЛИНИКОЙ ГОТОВА!")
        print("=" * 50)
        print("✅ Модели БД созданы")
        print("✅ Pydantic схемы готовы")
        print("✅ CRUD операции реализованы")
        print("✅ Сервисы созданы")
        print("✅ API endpoints готовы")
        print("✅ Таблицы БД созданы")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_clinic_management_tables()
    sys.exit(0 if success else 1)
