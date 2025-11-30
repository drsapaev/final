"""
CRUD операции для расширенного управления клиникой
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session

from app.models.clinic import (
    Backup,
    BackupStatus,
    BackupType,
    Branch,
    BranchStatus,
    Equipment,
    EquipmentMaintenance,
    EquipmentStatus,
    EquipmentType,
    License,
    LicenseActivation,
    LicenseStatus,
    LicenseType,
    SystemInfo,
)
from app.schemas.clinic import (
    BackupCreate,
    BackupOut,
    BackupUpdate,
    BranchCreate,
    BranchOut,
    BranchStatsOut,
    BranchUpdate,
    ClinicStatsOut,
    EquipmentCreate,
    EquipmentMaintenanceCreate,
    EquipmentMaintenanceOut,
    EquipmentMaintenanceUpdate,
    EquipmentOut,
    EquipmentUpdate,
    LicenseActivationCreate,
    LicenseActivationOut,
    LicenseActivationUpdate,
    LicenseCreate,
    LicenseOut,
    LicenseUpdate,
    SystemInfoCreate,
    SystemInfoOut,
    SystemInfoUpdate,
)

# ===================== ФИЛИАЛЫ =====================


class CRUDBranch:
    """CRUD операции для филиалов"""

    def create(self, db: Session, *, obj_in: BranchCreate) -> Branch:
        """Создать филиал"""
        db_obj = Branch(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[Branch]:
        """Получить филиал по ID"""
        return db.query(Branch).filter(Branch.id == id).first()

    def get_by_code(self, db: Session, *, code: str) -> Optional[Branch]:
        """Получить филиал по коду"""
        return db.query(Branch).filter(Branch.code == code).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Branch]:
        """Получить список филиалов с фильтрацией"""
        query = db.query(Branch)

        if status:
            query = query.filter(Branch.status == status)

        if search:
            query = query.filter(
                or_(
                    Branch.name.ilike(f"%{search}%"),
                    Branch.address.ilike(f"%{search}%"),
                    Branch.code.ilike(f"%{search}%"),
                )
            )

        return query.offset(skip).limit(limit).all()

    def update(self, db: Session, *, db_obj: Branch, obj_in: BranchUpdate) -> Branch:
        """Обновить филиал"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[Branch]:
        """Удалить филиал"""
        obj = db.query(Branch).filter(Branch.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def get_stats(self, db: Session, *, branch_id: int) -> Optional[BranchStatsOut]:
        """Получить статистику филиала"""
        branch = self.get(db, id=branch_id)
        if not branch:
            return None

        # Подсчет врачей
        doctors_count = (
            db.query(func.count())
            .select_from(Branch)
            .join(Branch.doctors)
            .filter(Branch.id == branch_id)
            .scalar()
            or 0
        )

        # Подсчет оборудования
        equipment_count = (
            db.query(func.count())
            .select_from(Branch)
            .join(Branch.equipment)
            .filter(Branch.id == branch_id)
            .scalar()
            or 0
        )

        # Активное оборудование
        active_equipment = (
            db.query(func.count())
            .select_from(Branch)
            .join(Branch.equipment)
            .filter(
                and_(Branch.id == branch_id, Equipment.status == EquipmentStatus.ACTIVE)
            )
            .scalar()
            or 0
        )

        # Оборудование на обслуживании
        maintenance_due = (
            db.query(func.count())
            .select_from(Branch)
            .join(Branch.equipment)
            .filter(
                and_(
                    Branch.id == branch_id,
                    Equipment.next_maintenance <= datetime.utcnow(),
                )
            )
            .scalar()
            or 0
        )

        # Последнее резервное копирование
        last_backup = (
            db.query(Backup.completed_at)
            .filter(Backup.status == BackupStatus.COMPLETED)
            .order_by(desc(Backup.completed_at))
            .first()
        )

        return BranchStatsOut(
            branch_id=branch.id,
            branch_name=branch.name,
            doctors_count=doctors_count,
            equipment_count=equipment_count,
            active_equipment=active_equipment,
            maintenance_due=maintenance_due,
            last_backup=last_backup[0] if last_backup else None,
            status=branch.status.value,
        )


# ===================== ОБОРУДОВАНИЕ =====================


class CRUDEquipment:
    """CRUD операции для оборудования"""

    def create(self, db: Session, *, obj_in: EquipmentCreate) -> Equipment:
        """Создать оборудование"""
        db_obj = Equipment(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[Equipment]:
        """Получить оборудование по ID"""
        return db.query(Equipment).filter(Equipment.id == id).first()

    def get_by_serial(self, db: Session, *, serial_number: str) -> Optional[Equipment]:
        """Получить оборудование по серийному номеру"""
        return (
            db.query(Equipment).filter(Equipment.serial_number == serial_number).first()
        )

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        branch_id: Optional[int] = None,
        equipment_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Equipment]:
        """Получить список оборудования с фильтрацией"""
        query = db.query(Equipment)

        if branch_id:
            query = query.filter(Equipment.branch_id == branch_id)

        if equipment_type:
            query = query.filter(Equipment.equipment_type == equipment_type)

        if status:
            query = query.filter(Equipment.status == status)

        if search:
            query = query.filter(
                or_(
                    Equipment.name.ilike(f"%{search}%"),
                    Equipment.model.ilike(f"%{search}%"),
                    Equipment.serial_number.ilike(f"%{search}%"),
                )
            )

        return query.offset(skip).limit(limit).all()

    def update(
        self, db: Session, *, db_obj: Equipment, obj_in: EquipmentUpdate
    ) -> Equipment:
        """Обновить оборудование"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[Equipment]:
        """Удалить оборудование"""
        obj = db.query(Equipment).filter(Equipment.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def get_maintenance_due(
        self, db: Session, *, days_ahead: int = 30
    ) -> List[Equipment]:
        """Получить оборудование, требующее обслуживания"""
        due_date = datetime.utcnow() + timedelta(days=days_ahead)
        return (
            db.query(Equipment)
            .filter(
                and_(
                    Equipment.next_maintenance <= due_date,
                    Equipment.status == EquipmentStatus.ACTIVE,
                )
            )
            .all()
        )


# ===================== ОБСЛУЖИВАНИЕ ОБОРУДОВАНИЯ =====================


class CRUDEquipmentMaintenance:
    """CRUD операции для обслуживания оборудования"""

    def create(
        self, db: Session, *, obj_in: EquipmentMaintenanceCreate
    ) -> EquipmentMaintenance:
        """Создать запись обслуживания"""
        db_obj = EquipmentMaintenance(**obj_in.dict())
        db.add(db_obj)

        # Обновляем дату последнего обслуживания в оборудовании
        equipment = (
            db.query(Equipment).filter(Equipment.id == obj_in.equipment_id).first()
        )
        if equipment:
            equipment.last_maintenance = obj_in.maintenance_date
            if obj_in.next_maintenance:
                equipment.next_maintenance = obj_in.next_maintenance

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[EquipmentMaintenance]:
        """Получить запись обслуживания по ID"""
        return (
            db.query(EquipmentMaintenance).filter(EquipmentMaintenance.id == id).first()
        )

    def get_by_equipment(
        self, db: Session, *, equipment_id: int, skip: int = 0, limit: int = 100
    ) -> List[EquipmentMaintenance]:
        """Получить записи обслуживания для оборудования"""
        return (
            db.query(EquipmentMaintenance)
            .filter(EquipmentMaintenance.equipment_id == equipment_id)
            .order_by(desc(EquipmentMaintenance.maintenance_date))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(
        self,
        db: Session,
        *,
        db_obj: EquipmentMaintenance,
        obj_in: EquipmentMaintenanceUpdate,
    ) -> EquipmentMaintenance:
        """Обновить запись обслуживания"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[EquipmentMaintenance]:
        """Удалить запись обслуживания"""
        obj = (
            db.query(EquipmentMaintenance).filter(EquipmentMaintenance.id == id).first()
        )
        if obj:
            db.delete(obj)
            db.commit()
        return obj


# ===================== ЛИЦЕНЗИИ =====================


class CRUDLicense:
    """CRUD операции для лицензий"""

    def create(self, db: Session, *, obj_in: LicenseCreate) -> License:
        """Создать лицензию"""
        db_obj = License(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[License]:
        """Получить лицензию по ID"""
        return db.query(License).filter(License.id == id).first()

    def get_by_key(self, db: Session, *, license_key: str) -> Optional[License]:
        """Получить лицензию по ключу"""
        return db.query(License).filter(License.license_key == license_key).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        license_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[License]:
        """Получить список лицензий с фильтрацией"""
        query = db.query(License)

        if license_type:
            query = query.filter(License.license_type == license_type)

        if status:
            query = query.filter(License.status == status)

        if search:
            query = query.filter(
                or_(
                    License.name.ilike(f"%{search}%"),
                    License.license_key.ilike(f"%{search}%"),
                    License.issued_by.ilike(f"%{search}%"),
                )
            )

        return query.offset(skip).limit(limit).all()

    def update(self, db: Session, *, db_obj: License, obj_in: LicenseUpdate) -> License:
        """Обновить лицензию"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[License]:
        """Удалить лицензию"""
        obj = db.query(License).filter(License.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def get_expiring_soon(self, db: Session, *, days_ahead: int = 30) -> List[License]:
        """Получить лицензии, истекающие в ближайшее время"""
        expiring_date = date.today() + timedelta(days=days_ahead)
        return (
            db.query(License)
            .filter(
                and_(
                    License.expires_date <= expiring_date,
                    License.status == LicenseStatus.ACTIVE,
                )
            )
            .all()
        )


# ===================== АКТИВАЦИИ ЛИЦЕНЗИЙ =====================


class CRUDLicenseActivation:
    """CRUD операции для активаций лицензий"""

    def create(
        self, db: Session, *, obj_in: LicenseActivationCreate
    ) -> LicenseActivation:
        """Создать активацию лицензии"""
        db_obj = LicenseActivation(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[LicenseActivation]:
        """Получить активацию по ID"""
        return db.query(LicenseActivation).filter(LicenseActivation.id == id).first()

    def get_by_license(
        self, db: Session, *, license_id: int, skip: int = 0, limit: int = 100
    ) -> List[LicenseActivation]:
        """Получить активации для лицензии"""
        return (
            db.query(LicenseActivation)
            .filter(LicenseActivation.license_id == license_id)
            .order_by(desc(LicenseActivation.activation_date))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(
        self, db: Session, *, db_obj: LicenseActivation, obj_in: LicenseActivationUpdate
    ) -> LicenseActivation:
        """Обновить активацию"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[LicenseActivation]:
        """Удалить активацию"""
        obj = db.query(LicenseActivation).filter(LicenseActivation.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


class CRUDBackup:
    """CRUD операции для резервного копирования"""

    def create(self, db: Session, *, obj_in: BackupCreate) -> Backup:
        """Создать задачу резервного копирования"""
        db_obj = Backup(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[Backup]:
        """Получить резервную копию по ID"""
        return db.query(Backup).filter(Backup.id == id).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        backup_type: Optional[str] = None,
    ) -> List[Backup]:
        """Получить список резервных копий с фильтрацией"""
        query = db.query(Backup)

        if status:
            query = query.filter(Backup.status == status)

        if backup_type:
            query = query.filter(Backup.backup_type == backup_type)

        return query.order_by(desc(Backup.created_at)).offset(skip).limit(limit).all()

    def update(self, db: Session, *, db_obj: Backup, obj_in: BackupUpdate) -> Backup:
        """Обновить резервную копию"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[Backup]:
        """Удалить резервную копию"""
        obj = db.query(Backup).filter(Backup.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def get_expired(self, db: Session) -> List[Backup]:
        """Получить истекшие резервные копии"""
        return db.query(Backup).filter(Backup.expires_at <= datetime.utcnow()).all()


# ===================== СИСТЕМНАЯ ИНФОРМАЦИЯ =====================


class CRUDSystemInfo:
    """CRUD операции для системной информации"""

    def create(self, db: Session, *, obj_in: SystemInfoCreate) -> SystemInfo:
        """Создать системную информацию"""
        db_obj = SystemInfo(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Optional[SystemInfo]:
        """Получить системную информацию по ID"""
        return db.query(SystemInfo).filter(SystemInfo.id == id).first()

    def get_by_key(self, db: Session, *, key: str) -> Optional[SystemInfo]:
        """Получить системную информацию по ключу"""
        return db.query(SystemInfo).filter(SystemInfo.key == key).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[SystemInfo]:
        """Получить список системной информации"""
        return db.query(SystemInfo).offset(skip).limit(limit).all()

    def update(
        self, db: Session, *, db_obj: SystemInfo, obj_in: SystemInfoUpdate
    ) -> SystemInfo:
        """Обновить системную информацию"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: int) -> Optional[SystemInfo]:
        """Удалить системную информацию"""
        obj = db.query(SystemInfo).filter(SystemInfo.id == id).first()
        if obj:
            db.delete(obj)
            db.commit()
        return obj


# ===================== СТАТИСТИКА =====================


class CRUDClinicStats:
    """CRUD операции для статистики клиники"""

    def get_clinic_stats(self, db: Session) -> ClinicStatsOut:
        """Получить общую статистику клиники"""
        # Филиалы
        total_branches = db.query(func.count(Branch.id)).scalar() or 0
        active_branches = (
            db.query(func.count(Branch.id))
            .filter(Branch.status == BranchStatus.ACTIVE)
            .scalar()
            or 0
        )

        # Врачи
        total_doctors = (
            db.query(func.count()).select_from(Branch).join(Branch.doctors).scalar()
            or 0
        )
        active_doctors = (
            db.query(func.count())
            .select_from(Branch)
            .join(Branch.doctors)
            .filter(Branch.doctors.any())
            .scalar()
            or 0
        )

        # Оборудование
        total_equipment = db.query(func.count(Equipment.id)).scalar() or 0
        active_equipment = (
            db.query(func.count(Equipment.id))
            .filter(Equipment.status == EquipmentStatus.ACTIVE)
            .scalar()
            or 0
        )
        equipment_in_maintenance = (
            db.query(func.count(Equipment.id))
            .filter(Equipment.status == EquipmentStatus.MAINTENANCE)
            .scalar()
            or 0
        )

        # Лицензии
        total_licenses = db.query(func.count(License.id)).scalar() or 0
        active_licenses = (
            db.query(func.count(License.id))
            .filter(License.status == LicenseStatus.ACTIVE)
            .scalar()
            or 0
        )
        expired_licenses = (
            db.query(func.count(License.id))
            .filter(License.status == LicenseStatus.EXPIRED)
            .scalar()
            or 0
        )

        # Резервные копии
        total_backups = db.query(func.count(Backup.id)).scalar() or 0
        recent_backups = (
            db.query(func.count(Backup.id))
            .filter(Backup.created_at >= datetime.utcnow() - timedelta(days=7))
            .scalar()
            or 0
        )

        # Определение состояния системы
        system_health = "healthy"
        if expired_licenses > 0:
            system_health = "warning"
        if (
            equipment_in_maintenance > total_equipment * 0.3
        ):  # Более 30% оборудования на обслуживании
            system_health = "critical"

        return ClinicStatsOut(
            total_branches=total_branches,
            active_branches=active_branches,
            total_doctors=total_doctors,
            active_doctors=active_doctors,
            total_equipment=total_equipment,
            active_equipment=active_equipment,
            equipment_in_maintenance=equipment_in_maintenance,
            total_licenses=total_licenses,
            active_licenses=active_licenses,
            expired_licenses=expired_licenses,
            total_backups=total_backups,
            recent_backups=recent_backups,
            system_health=system_health,
        )


# ===================== ЭКЗЕМПЛЯРЫ =====================

branch = CRUDBranch()
equipment = CRUDEquipment()
equipment_maintenance = CRUDEquipmentMaintenance()
license = CRUDLicense()
license_activation = CRUDLicenseActivation()
backup = CRUDBackup()
system_info = CRUDSystemInfo()
clinic_stats = CRUDClinicStats()
