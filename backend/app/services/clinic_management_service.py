"""
Сервисы для управления клиникой
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import os
import shutil
import zipfile
import json

from app.crud.clinic_management import (
    branch, equipment, equipment_maintenance, license, license_activation,
    backup, system_info, clinic_stats
)
from app.schemas.clinic import (
    BranchCreate, BranchUpdate, BranchOut,
    EquipmentCreate, EquipmentUpdate, EquipmentOut,
    EquipmentMaintenanceCreate, EquipmentMaintenanceUpdate, EquipmentMaintenanceOut,
    LicenseCreate, LicenseUpdate, LicenseOut,
    LicenseActivationCreate, LicenseActivationUpdate, LicenseActivationOut,
    BackupCreate, BackupUpdate, BackupOut,
    SystemInfoCreate, SystemInfoUpdate, SystemInfoOut,
    ClinicStatsOut, BranchStatsOut
)


class BranchManagementService:
    """Сервис управления филиалами"""
    
    def create_branch(self, db: Session, branch_data: BranchCreate) -> BranchOut:
        """Создать филиал"""
        db_branch = branch.create(db=db, obj_in=branch_data)
        return BranchOut.from_orm(db_branch)
    
    def get_branch(self, db: Session, branch_id: int) -> Optional[BranchOut]:
        """Получить филиал"""
        db_branch = branch.get(db=db, id=branch_id)
        if not db_branch:
            return None
        return BranchOut.from_orm(db_branch)
    
    def get_branches(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[BranchOut]:
        """Получить список филиалов"""
        db_branches = branch.get_multi(
            db=db, skip=skip, limit=limit, status=status, search=search
        )
        return [BranchOut.from_orm(b) for b in db_branches]
    
    def update_branch(self, db: Session, branch_id: int, branch_data: BranchUpdate) -> Optional[BranchOut]:
        """Обновить филиал"""
        db_branch = branch.get(db=db, id=branch_id)
        if not db_branch:
            return None
        
        updated_branch = branch.update(db=db, db_obj=db_branch, obj_in=branch_data)
        return BranchOut.from_orm(updated_branch)
    
    def delete_branch(self, db: Session, branch_id: int) -> bool:
        """Удалить филиал"""
        db_branch = branch.delete(db=db, id=branch_id)
        return db_branch is not None
    
    def get_branch_stats(self, db: Session, branch_id: int) -> Optional[BranchStatsOut]:
        """Получить статистику филиала"""
        return branch.get_stats(db=db, branch_id=branch_id)


class EquipmentManagementService:
    """Сервис управления оборудованием"""
    
    def create_equipment(self, db: Session, equipment_data: EquipmentCreate) -> EquipmentOut:
        """Создать оборудование"""
        db_equipment = equipment.create(db=db, obj_in=equipment_data)
        return EquipmentOut.from_orm(db_equipment)
    
    def get_equipment(self, db: Session, equipment_id: int) -> Optional[EquipmentOut]:
        """Получить оборудование"""
        db_equipment = equipment.get(db=db, id=equipment_id)
        if not db_equipment:
            return None
        return EquipmentOut.from_orm(db_equipment)
    
    def get_equipment_list(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        branch_id: Optional[int] = None,
        equipment_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[EquipmentOut]:
        """Получить список оборудования"""
        db_equipment = equipment.get_multi(
            db=db, skip=skip, limit=limit, branch_id=branch_id,
            equipment_type=equipment_type, status=status, search=search
        )
        return [EquipmentOut.from_orm(e) for e in db_equipment]
    
    def update_equipment(self, db: Session, equipment_id: int, equipment_data: EquipmentUpdate) -> Optional[EquipmentOut]:
        """Обновить оборудование"""
        db_equipment = equipment.get(db=db, id=equipment_id)
        if not db_equipment:
            return None
        
        updated_equipment = equipment.update(db=db, db_obj=db_equipment, obj_in=equipment_data)
        return EquipmentOut.from_orm(updated_equipment)
    
    def delete_equipment(self, db: Session, equipment_id: int) -> bool:
        """Удалить оборудование"""
        db_equipment = equipment.delete(db=db, id=equipment_id)
        return db_equipment is not None
    
    def get_maintenance_due(self, db: Session, days_ahead: int = 30) -> List[EquipmentOut]:
        """Получить оборудование, требующее обслуживания"""
        db_equipment = equipment.get_maintenance_due(db=db, days_ahead=days_ahead)
        return [EquipmentOut.from_orm(e) for e in db_equipment]
    
    def schedule_maintenance(
        self, 
        db: Session, 
        equipment_id: int, 
        maintenance_data: EquipmentMaintenanceCreate
    ) -> EquipmentMaintenanceOut:
        """Запланировать обслуживание"""
        db_maintenance = equipment_maintenance.create(db=db, obj_in=maintenance_data)
        return EquipmentMaintenanceOut.from_orm(db_maintenance)
    
    def get_maintenance_history(
        self, 
        db: Session, 
        equipment_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[EquipmentMaintenanceOut]:
        """Получить историю обслуживания"""
        db_maintenance = equipment_maintenance.get_by_equipment(
            db=db, equipment_id=equipment_id, skip=skip, limit=limit
        )
        return [EquipmentMaintenanceOut.from_orm(m) for m in db_maintenance]


class LicenseManagementService:
    """Сервис управления лицензиями"""
    
    def create_license(self, db: Session, license_data: LicenseCreate) -> LicenseOut:
        """Создать лицензию"""
        db_license = license.create(db=db, obj_in=license_data)
        return LicenseOut.from_orm(db_license)
    
    def get_license(self, db: Session, license_id: int) -> Optional[LicenseOut]:
        """Получить лицензию"""
        db_license = license.get(db=db, id=license_id)
        if not db_license:
            return None
        return LicenseOut.from_orm(db_license)
    
    def get_licenses(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        license_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[LicenseOut]:
        """Получить список лицензий"""
        db_licenses = license.get_multi(
            db=db, skip=skip, limit=limit, license_type=license_type,
            status=status, search=search
        )
        return [LicenseOut.from_orm(l) for l in db_licenses]
    
    def update_license(self, db: Session, license_id: int, license_data: LicenseUpdate) -> Optional[LicenseOut]:
        """Обновить лицензию"""
        db_license = license.get(db=db, id=license_id)
        if not db_license:
            return None
        
        updated_license = license.update(db=db, db_obj=db_license, obj_in=license_data)
        return LicenseOut.from_orm(updated_license)
    
    def delete_license(self, db: Session, license_id: int) -> bool:
        """Удалить лицензию"""
        db_license = license.delete(db=db, id=license_id)
        return db_license is not None
    
    def get_expiring_licenses(self, db: Session, days_ahead: int = 30) -> List[LicenseOut]:
        """Получить лицензии, истекающие в ближайшее время"""
        db_licenses = license.get_expiring_soon(db=db, days_ahead=days_ahead)
        return [LicenseOut.from_orm(l) for l in db_licenses]
    
    def activate_license(
        self, 
        db: Session, 
        license_id: int, 
        activation_data: LicenseActivationCreate
    ) -> LicenseActivationOut:
        """Активировать лицензию"""
        activation_data.license_id = license_id
        db_activation = license_activation.create(db=db, obj_in=activation_data)
        return LicenseActivationOut.from_orm(db_activation)
    
    def get_license_activations(
        self, 
        db: Session, 
        license_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[LicenseActivationOut]:
        """Получить активации лицензии"""
        db_activations = license_activation.get_by_license(
            db=db, license_id=license_id, skip=skip, limit=limit
        )
        return [LicenseActivationOut.from_orm(a) for a in db_activations]


class BackupManagementService:
    """Сервис управления резервным копированием"""
    
    def create_backup_task(self, db: Session, backup_data: BackupCreate) -> BackupOut:
        """Создать задачу резервного копирования"""
        db_backup = backup.create(db=db, obj_in=backup_data)
        return BackupOut.from_orm(db_backup)
    
    def get_backup(self, db: Session, backup_id: int) -> Optional[BackupOut]:
        """Получить резервную копию"""
        db_backup = backup.get(db=db, id=backup_id)
        if not db_backup:
            return None
        return BackupOut.from_orm(db_backup)
    
    def get_backups(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None,
        backup_type: Optional[str] = None
    ) -> List[BackupOut]:
        """Получить список резервных копий"""
        db_backups = backup.get_multi(
            db=db, skip=skip, limit=limit, status=status, backup_type=backup_type
        )
        return [BackupOut.from_orm(b) for b in db_backups]
    
    def update_backup(self, db: Session, backup_id: int, backup_data: BackupUpdate) -> Optional[BackupOut]:
        """Обновить резервную копию"""
        db_backup = backup.get(db=db, id=backup_id)
        if not db_backup:
            return None
        
        updated_backup = backup.update(db=db, db_obj=db_backup, obj_in=backup_data)
        return BackupOut.from_orm(updated_backup)
    
    def delete_backup(self, db: Session, backup_id: int) -> bool:
        """Удалить резервную копию"""
        db_backup = backup.delete(db=db, id=backup_id)
        return db_backup is not None
    
    def cleanup_expired_backups(self, db: Session) -> int:
        """Очистить истекшие резервные копии"""
        expired_backups = backup.get_expired(db=db)
        count = 0
        
        for db_backup in expired_backups:
            # Удаляем файл, если он существует
            if db_backup.file_path and os.path.exists(db_backup.file_path):
                try:
                    os.remove(db_backup.file_path)
                except OSError:
                    pass  # Игнорируем ошибки удаления файла
            
            # Удаляем запись из БД
            backup.delete(db=db, id=db_backup.id)
            count += 1
        
        return count
    
    def create_full_backup(self, db: Session, backup_name: str) -> BackupOut:
        """Создать полную резервную копию"""
        backup_data = BackupCreate(
            name=backup_name,
            backup_type="full",
            status="pending",
            retention_days=30
        )
        return self.create_backup_task(db=db, backup_data=backup_data)
    
    def create_incremental_backup(self, db: Session, backup_name: str) -> BackupOut:
        """Создать инкрементальную резервную копию"""
        backup_data = BackupCreate(
            name=backup_name,
            backup_type="incremental",
            status="pending",
            retention_days=7
        )
        return self.create_backup_task(db=db, backup_data=backup_data)


class SystemInfoService:
    """Сервис системной информации"""
    
    def get_system_info(self, db: Session, key: str) -> Optional[SystemInfoOut]:
        """Получить системную информацию по ключу"""
        db_info = system_info.get_by_key(db=db, key=key)
        if not db_info:
            return None
        return SystemInfoOut.from_orm(db_info)
    
    def set_system_info(self, db: Session, key: str, value: Dict[str, Any], description: Optional[str] = None) -> SystemInfoOut:
        """Установить системную информацию"""
        existing = system_info.get_by_key(db=db, key=key)
        
        if existing:
            update_data = SystemInfoUpdate(value=value, description=description)
            updated_info = system_info.update(db=db, db_obj=existing, obj_in=update_data)
            return SystemInfoOut.from_orm(updated_info)
        else:
            create_data = SystemInfoCreate(key=key, value=value, description=description)
            new_info = system_info.create(db=db, obj_in=create_data)
            return SystemInfoOut.from_orm(new_info)
    
    def get_all_system_info(self, db: Session) -> Dict[str, Any]:
        """Получить всю системную информацию"""
        db_infos = system_info.get_multi(db=db, skip=0, limit=1000)
        return {info.key: info.value for info in db_infos}


class ClinicManagementService:
    """Основной сервис управления клиникой"""
    
    def __init__(self):
        self.branch_service = BranchManagementService()
        self.equipment_service = EquipmentManagementService()
        self.license_service = LicenseManagementService()
        self.backup_service = BackupManagementService()
        self.system_info_service = SystemInfoService()
    
    def get_clinic_stats(self, db: Session) -> ClinicStatsOut:
        """Получить общую статистику клиники"""
        return clinic_stats.get_clinic_stats(db=db)
    
    def get_system_health(self, db: Session) -> Dict[str, Any]:
        """Получить состояние системы"""
        stats = self.get_clinic_stats(db=db)
        
        # Получаем предупреждения
        warnings = []
        
        if stats.expired_licenses > 0:
            warnings.append(f"Истекло лицензий: {stats.expired_licenses}")
        
        if stats.equipment_in_maintenance > stats.total_equipment * 0.2:
            warnings.append(f"Много оборудования на обслуживании: {stats.equipment_in_maintenance}")
        
        if stats.recent_backups == 0:
            warnings.append("Нет недавних резервных копий")
        
        return {
            "status": stats.system_health,
            "warnings": warnings,
            "stats": stats.dict()
        }
    
    def initialize_default_data(self, db: Session) -> Dict[str, Any]:
        """Инициализировать данные по умолчанию"""
        results = {}
        
        # Создаем главный филиал, если его нет
        main_branch = branch.get_by_code(db=db, code="MAIN")
        if not main_branch:
            branch_data = BranchCreate(
                name="Главный филиал",
                code="MAIN",
                address="Основной адрес клиники",
                status="active",
                timezone="Asia/Tashkent",
                capacity=100
            )
            main_branch = self.branch_service.create_branch(db=db, branch_data=branch_data)
            results["main_branch"] = "Создан главный филиал"
        
        # Создаем базовую системную информацию
        system_data = {
            "clinic_name": "Programma Clinic",
            "version": "1.0.0",
            "timezone": "Asia/Tashkent",
            "maintenance_mode": False
        }
        
        for key, value in system_data.items():
            self.system_info_service.set_system_info(
                db=db, key=key, value={"value": value}, 
                description=f"Системная информация: {key}"
            )
        
        results["system_info"] = "Инициализирована системная информация"
        
        return results


# ===================== ЭКЗЕМПЛЯРЫ =====================

branch_management = BranchManagementService()
equipment_management = EquipmentManagementService()
license_management = LicenseManagementService()
backup_management = BackupManagementService()
system_info_service = SystemInfoService()
clinic_management = ClinicManagementService()
