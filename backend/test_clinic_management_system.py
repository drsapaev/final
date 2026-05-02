#!/usr/bin/env python3
"""
Тестирование системы управления клиникой
"""
import sys
import os
from datetime import datetime, date, timedelta

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_clinic_management_system():
    """Тестирует систему управления клиникой"""
    print("🏥 ТЕСТИРОВАНИЕ СИСТЕМЫ УПРАВЛЕНИЯ КЛИНИКОЙ")
    print("=" * 60)
    
    try:
        from app.db.session import SessionLocal
        from app.services.clinic_management_service import (
            branch_management, equipment_management, license_management,
            backup_management, system_info_service, clinic_management
        )
        from app.schemas.clinic import (
            BranchCreate, EquipmentCreate, LicenseCreate, BackupCreate,
            SystemInfoCreate
        )
        
        db = SessionLocal()
        
        try:
            print("1️⃣ Тест создания филиала...")
            import time
            timestamp = int(time.time())
            branch_data = BranchCreate(
                name=f"Тестовый филиал {timestamp}",
                code=f"TEST{timestamp}",
                address="Тестовый адрес",
                phone="+998901234567",
                email="test@clinic.com",
                status="active",
                timezone="Asia/Tashkent",
                capacity=50
            )
            branch = branch_management.create_branch(db=db, branch_data=branch_data)
            print(f"✅ Филиал создан: {branch.name} (ID: {branch.id})")
            
            print("\n2️⃣ Тест создания оборудования...")
            equipment_data = EquipmentCreate(
                name=f"Тестовое оборудование {timestamp}",
                model="Test Model 2024",
                serial_number=f"TEST{timestamp}",
                equipment_type="medical",
                branch_id=branch.id,
                cabinet="101",
                status="active",
                cost=100000.00,
                supplier="Test Supplier"
            )
            equipment = equipment_management.create_equipment(db=db, equipment_data=equipment_data)
            print(f"✅ Оборудование создано: {equipment.name} (ID: {equipment.id})")
            
            print("\n3️⃣ Тест создания лицензии...")
            license_data = LicenseCreate(
                name=f"Тестовая лицензия {timestamp}",
                license_type="software",
                license_key=f"TEST-LICENSE-KEY-{timestamp}",
                status="active",
                issued_by="Test Company",
                issued_date=date(2024, 1, 1),
                expires_date=date(2025, 1, 1),
                cost=50000.00,
                features=["basic", "advanced"],
                restrictions=["single_user"]
            )
            license = license_management.create_license(db=db, license_data=license_data)
            print(f"✅ Лицензия создана: {license.name} (ID: {license.id})")
            
            print("\n4️⃣ Тест создания резервной копии...")
            backup_data = BackupCreate(
                name=f"Тестовая резервная копия {timestamp}",
                backup_type="full",
                status="pending",
                retention_days=30
            )
            backup = backup_management.create_backup_task(db=db, backup_data=backup_data)
            print(f"✅ Резервная копия создана: {backup.name} (ID: {backup.id})")
            
            print("\n5️⃣ Тест системной информации...")
            system_info = system_info_service.set_system_info(
                db=db, 
                key="test_key", 
                value={"test": "value"}, 
                description="Тестовая системная информация"
            )
            print(f"✅ Системная информация установлена: {system_info.key}")
            
            print("\n6️⃣ Тест статистики клиники...")
            stats = clinic_management.get_clinic_stats(db=db)
            print(f"✅ Статистика получена:")
            print(f"   - Филиалов: {stats.total_branches}")
            print(f"   - Оборудования: {stats.total_equipment}")
            print(f"   - Лицензий: {stats.total_licenses}")
            print(f"   - Резервных копий: {stats.total_backups}")
            print(f"   - Состояние системы: {stats.system_health}")
            
            print("\n7️⃣ Тест состояния системы...")
            health = clinic_management.get_system_health(db=db)
            print(f"✅ Состояние системы: {health['status']}")
            if health['warnings']:
                print(f"   ⚠️ Предупреждения: {', '.join(health['warnings'])}")
            else:
                print("   ✅ Предупреждений нет")
            
            print("\n8️⃣ Тест инициализации данных...")
            init_results = clinic_management.initialize_default_data(db=db)
            print(f"✅ Инициализация завершена:")
            for key, value in init_results.items():
                print(f"   - {key}: {value}")
            
            print("\n9️⃣ Тест получения списков...")
            branches = branch_management.get_branches(db=db, limit=10)
            equipment_list = equipment_management.get_equipment_list(db=db, limit=10)
            licenses = license_management.get_licenses(db=db, limit=10)
            backups = backup_management.get_backups(db=db, limit=10)
            
            print(f"✅ Списки получены:")
            print(f"   - Филиалов: {len(branches)}")
            print(f"   - Оборудования: {len(equipment_list)}")
            print(f"   - Лицензий: {len(licenses)}")
            print(f"   - Резервных копий: {len(backups)}")
            
            print("\n🔟 Тест поиска и фильтрации...")
            # Поиск филиалов
            search_branches = branch_management.get_branches(db=db, search="Тест", limit=10)
            print(f"✅ Поиск филиалов: найдено {len(search_branches)}")
            
            # Фильтрация оборудования
            active_equipment = equipment_management.get_equipment_list(db=db, status="active", limit=10)
            print(f"✅ Активное оборудование: {len(active_equipment)}")
            
            # Фильтрация лицензий
            active_licenses = license_management.get_licenses(db=db, status="active", limit=10)
            print(f"✅ Активные лицензии: {len(active_licenses)}")
            
            print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            print("=" * 60)
            print("✅ Создание филиалов - ПРОЙДЕН")
            print("✅ Создание оборудования - ПРОЙДЕН")
            print("✅ Создание лицензий - ПРОЙДЕН")
            print("✅ Создание резервных копий - ПРОЙДЕН")
            print("✅ Системная информация - ПРОЙДЕН")
            print("✅ Статистика клиники - ПРОЙДЕН")
            print("✅ Состояние системы - ПРОЙДЕН")
            print("✅ Инициализация данных - ПРОЙДЕН")
            print("✅ Получение списков - ПРОЙДЕН")
            print("✅ Поиск и фильтрация - ПРОЙДЕН")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка тестирования: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_clinic_management_system()
    sys.exit(0 if success else 1)
