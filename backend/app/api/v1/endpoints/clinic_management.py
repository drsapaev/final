"""
API endpoints для управления клиникой
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.user import User
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
from app.services.clinic_management_service import (
    backup_management,
    branch_management,
    clinic_management,
    equipment_management,
    license_management,
    system_info_service,
)

router = APIRouter()

# ===================== ФИЛИАЛЫ =====================


@router.post("/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
def create_branch(
    *,
    db: Session = Depends(get_db),
    branch_data: BranchCreate,
    current_user: User = Depends(require_admin),
):
    """Создать филиал"""
    try:
        return branch_management.create_branch(db=db, branch_data=branch_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка создания филиала: {str(e)}",
        )


@router.get("/branches", response_model=List[BranchOut])
def get_branches(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    search: Optional[str] = Query(
        None, description="Поиск по названию, адресу или коду"
    ),
    current_user: User = Depends(require_admin),
):
    """Получить список филиалов"""
    return branch_management.get_branches(
        db=db, skip=skip, limit=limit, status=status, search=search
    )


@router.get("/branches/{branch_id}", response_model=BranchOut)
def get_branch(
    *,
    db: Session = Depends(get_db),
    branch_id: int,
    current_user: User = Depends(require_admin),
):
    """Получить филиал по ID"""
    branch = branch_management.get_branch(db=db, branch_id=branch_id)
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Филиал не найден"
        )
    return branch


@router.put("/branches/{branch_id}", response_model=BranchOut)
def update_branch(
    *,
    db: Session = Depends(get_db),
    branch_id: int,
    branch_data: BranchUpdate,
    current_user: User = Depends(require_admin),
):
    """Обновить филиал"""
    branch = branch_management.update_branch(
        db=db, branch_id=branch_id, branch_data=branch_data
    )
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Филиал не найден"
        )
    return branch


@router.delete("/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    *,
    db: Session = Depends(get_db),
    branch_id: int,
    current_user: User = Depends(require_admin),
):
    """Удалить филиал"""
    success = branch_management.delete_branch(db=db, branch_id=branch_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Филиал не найден"
        )


@router.get("/branches/{branch_id}/stats", response_model=BranchStatsOut)
def get_branch_stats(
    *,
    db: Session = Depends(get_db),
    branch_id: int,
    current_user: User = Depends(require_admin),
):
    """Получить статистику филиала"""
    stats = branch_management.get_branch_stats(db=db, branch_id=branch_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Филиал не найден"
        )
    return stats


# ===================== ОБОРУДОВАНИЕ =====================


@router.post(
    "/equipment", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED
)
def create_equipment(
    *,
    db: Session = Depends(get_db),
    equipment_data: EquipmentCreate,
    current_user: User = Depends(require_admin),
):
    """Создать оборудование"""
    try:
        return equipment_management.create_equipment(
            db=db, equipment_data=equipment_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка создания оборудования: {str(e)}",
        )


@router.get("/equipment", response_model=List[EquipmentOut])
def get_equipment(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    branch_id: Optional[int] = Query(None, description="Фильтр по филиалу"),
    equipment_type: Optional[str] = Query(None, description="Фильтр по типу"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    search: Optional[str] = Query(
        None, description="Поиск по названию, модели или серийному номеру"
    ),
    current_user: User = Depends(require_admin),
):
    """Получить список оборудования"""
    return equipment_management.get_equipment_list(
        db=db,
        skip=skip,
        limit=limit,
        branch_id=branch_id,
        equipment_type=equipment_type,
        status=status,
        search=search,
    )


@router.get("/equipment/{equipment_id}", response_model=EquipmentOut)
def get_equipment_by_id(
    *,
    db: Session = Depends(get_db),
    equipment_id: int,
    current_user: User = Depends(require_admin),
):
    """Получить оборудование по ID"""
    equipment = equipment_management.get_equipment(db=db, equipment_id=equipment_id)
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено"
        )
    return equipment


@router.put("/equipment/{equipment_id}", response_model=EquipmentOut)
def update_equipment(
    *,
    db: Session = Depends(get_db),
    equipment_id: int,
    equipment_data: EquipmentUpdate,
    current_user: User = Depends(require_admin),
):
    """Обновить оборудование"""
    equipment = equipment_management.update_equipment(
        db=db, equipment_id=equipment_id, equipment_data=equipment_data
    )
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено"
        )
    return equipment


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(
    *,
    db: Session = Depends(get_db),
    equipment_id: int,
    current_user: User = Depends(require_admin),
):
    """Удалить оборудование"""
    success = equipment_management.delete_equipment(db=db, equipment_id=equipment_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено"
        )


@router.get("/equipment/maintenance/due", response_model=List[EquipmentOut])
def get_maintenance_due(
    *,
    db: Session = Depends(get_db),
    days_ahead: int = Query(
        30, ge=1, le=365, description="Количество дней вперед для проверки"
    ),
    current_user: User = Depends(require_admin),
):
    """Получить оборудование, требующее обслуживания"""
    return equipment_management.get_maintenance_due(db=db, days_ahead=days_ahead)


@router.post(
    "/equipment/{equipment_id}/maintenance",
    response_model=EquipmentMaintenanceOut,
    status_code=status.HTTP_201_CREATED,
)
def schedule_maintenance(
    *,
    db: Session = Depends(get_db),
    equipment_id: int,
    maintenance_data: EquipmentMaintenanceCreate,
    current_user: User = Depends(require_admin),
):
    """Запланировать обслуживание оборудования"""
    maintenance_data.equipment_id = equipment_id
    try:
        return equipment_management.schedule_maintenance(
            db=db, equipment_id=equipment_id, maintenance_data=maintenance_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка планирования обслуживания: {str(e)}",
        )


@router.get(
    "/equipment/{equipment_id}/maintenance",
    response_model=List[EquipmentMaintenanceOut],
)
def get_maintenance_history(
    *,
    db: Session = Depends(get_db),
    equipment_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
):
    """Получить историю обслуживания оборудования"""
    return equipment_management.get_maintenance_history(
        db=db, equipment_id=equipment_id, skip=skip, limit=limit
    )


# ===================== ЛИЦЕНЗИИ =====================


@router.post(
    "/licenses", response_model=LicenseOut, status_code=status.HTTP_201_CREATED
)
def create_license(
    *,
    db: Session = Depends(get_db),
    license_data: LicenseCreate,
    current_user: User = Depends(require_admin),
):
    """Создать лицензию"""
    try:
        return license_management.create_license(db=db, license_data=license_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка создания лицензии: {str(e)}",
        )


@router.get("/licenses", response_model=List[LicenseOut])
def get_licenses(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    license_type: Optional[str] = Query(None, description="Фильтр по типу лицензии"),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    search: Optional[str] = Query(
        None, description="Поиск по названию, ключу или издателю"
    ),
    current_user: User = Depends(require_admin),
):
    """Получить список лицензий"""
    return license_management.get_licenses(
        db=db,
        skip=skip,
        limit=limit,
        license_type=license_type,
        status=status,
        search=search,
    )


@router.get("/licenses/{license_id}", response_model=LicenseOut)
def get_license(
    *,
    db: Session = Depends(get_db),
    license_id: int,
    current_user: User = Depends(require_admin),
):
    """Получить лицензию по ID"""
    license = license_management.get_license(db=db, license_id=license_id)
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Лицензия не найдена"
        )
    return license


@router.put("/licenses/{license_id}", response_model=LicenseOut)
def update_license(
    *,
    db: Session = Depends(get_db),
    license_id: int,
    license_data: LicenseUpdate,
    current_user: User = Depends(require_admin),
):
    """Обновить лицензию"""
    license = license_management.update_license(
        db=db, license_id=license_id, license_data=license_data
    )
    if not license:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Лицензия не найдена"
        )
    return license


@router.delete("/licenses/{license_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_license(
    *,
    db: Session = Depends(get_db),
    license_id: int,
    current_user: User = Depends(require_admin),
):
    """Удалить лицензию"""
    success = license_management.delete_license(db=db, license_id=license_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Лицензия не найдена"
        )


@router.get("/licenses/expiring", response_model=List[LicenseOut])
def get_expiring_licenses(
    *,
    db: Session = Depends(get_db),
    days_ahead: int = Query(
        30, ge=1, le=365, description="Количество дней вперед для проверки"
    ),
    current_user: User = Depends(require_admin),
):
    """Получить лицензии, истекающие в ближайшее время"""
    return license_management.get_expiring_licenses(db=db, days_ahead=days_ahead)


@router.post(
    "/licenses/{license_id}/activate",
    response_model=LicenseActivationOut,
    status_code=status.HTTP_201_CREATED,
)
def activate_license(
    *,
    db: Session = Depends(get_db),
    license_id: int,
    activation_data: LicenseActivationCreate,
    current_user: User = Depends(require_admin),
):
    """Активировать лицензию"""
    try:
        return license_management.activate_license(
            db=db, license_id=license_id, activation_data=activation_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка активации лицензии: {str(e)}",
        )


@router.get(
    "/licenses/{license_id}/activations", response_model=List[LicenseActivationOut]
)
def get_license_activations(
    *,
    db: Session = Depends(get_db),
    license_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
):
    """Получить активации лицензии"""
    return license_management.get_license_activations(
        db=db, license_id=license_id, skip=skip, limit=limit
    )


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


@router.post("/backups", response_model=BackupOut, status_code=status.HTTP_201_CREATED)
def create_backup(
    *,
    db: Session = Depends(get_db),
    backup_data: BackupCreate,
    current_user: User = Depends(require_admin),
):
    """Создать задачу резервного копирования"""
    try:
        return backup_management.create_backup_task(db=db, backup_data=backup_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка создания резервной копии: {str(e)}",
        )


@router.get("/backups", response_model=List[BackupOut])
def get_backups(
    *,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    backup_type: Optional[str] = Query(None, description="Фильтр по типу"),
    current_user: User = Depends(require_admin),
):
    """Получить список резервных копий"""
    return backup_management.get_backups(
        db=db, skip=skip, limit=limit, status=status, backup_type=backup_type
    )


@router.get("/backups/{backup_id}", response_model=BackupOut)
def get_backup(
    *,
    db: Session = Depends(get_db),
    backup_id: int,
    current_user: User = Depends(require_admin),
):
    """Получить резервную копию по ID"""
    backup = backup_management.get_backup(db=db, backup_id=backup_id)
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Резервная копия не найдена"
        )
    return backup


@router.put("/backups/{backup_id}", response_model=BackupOut)
def update_backup(
    *,
    db: Session = Depends(get_db),
    backup_id: int,
    backup_data: BackupUpdate,
    current_user: User = Depends(require_admin),
):
    """Обновить резервную копию"""
    backup = backup_management.update_backup(
        db=db, backup_id=backup_id, backup_data=backup_data
    )
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Резервная копия не найдена"
        )
    return backup


@router.delete("/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backup(
    *,
    db: Session = Depends(get_db),
    backup_id: int,
    current_user: User = Depends(require_admin),
):
    """Удалить резервную копию"""
    success = backup_management.delete_backup(db=db, backup_id=backup_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Резервная копия не найдена"
        )


@router.post("/backups/cleanup", response_model=Dict[str, int])
def cleanup_expired_backups(
    *, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    """Очистить истекшие резервные копии"""
    count = backup_management.cleanup_expired_backups(db=db)
    return {"cleaned_count": count}


@router.post(
    "/backups/full", response_model=BackupOut, status_code=status.HTTP_201_CREATED
)
def create_full_backup(
    *,
    db: Session = Depends(get_db),
    backup_name: str = Query(..., description="Название резервной копии"),
    current_user: User = Depends(require_admin),
):
    """Создать полную резервную копию"""
    return backup_management.create_full_backup(db=db, backup_name=backup_name)


@router.post(
    "/backups/incremental",
    response_model=BackupOut,
    status_code=status.HTTP_201_CREATED,
)
def create_incremental_backup(
    *,
    db: Session = Depends(get_db),
    backup_name: str = Query(..., description="Название резервной копии"),
    current_user: User = Depends(require_admin),
):
    """Создать инкрементальную резервную копию"""
    return backup_management.create_incremental_backup(db=db, backup_name=backup_name)


# ===================== СИСТЕМНАЯ ИНФОРМАЦИЯ =====================


@router.get("/system/info/{key}", response_model=SystemInfoOut)
def get_system_info(
    *,
    db: Session = Depends(get_db),
    key: str,
    current_user: User = Depends(require_admin),
):
    """Получить системную информацию по ключу"""
    info = system_info_service.get_system_info(db=db, key=key)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Системная информация не найдена",
        )
    return info


@router.put("/system/info/{key}", response_model=SystemInfoOut)
def set_system_info(
    *,
    db: Session = Depends(get_db),
    key: str,
    value: Dict[str, Any],
    description: Optional[str] = None,
    current_user: User = Depends(require_admin),
):
    """Установить системную информацию"""
    return system_info_service.set_system_info(
        db=db, key=key, value=value, description=description
    )


@router.get("/system/info", response_model=Dict[str, Any])
def get_all_system_info(
    *, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    """Получить всю системную информацию"""
    return system_info_service.get_all_system_info(db=db)


# ===================== СТАТИСТИКА И ОТЧЕТЫ =====================


@router.get("/stats", response_model=ClinicStatsOut)
def get_clinic_stats(
    *, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    """Получить статистику клиники"""
    return clinic_management.get_clinic_stats(db=db)


@router.get("/health", response_model=Dict[str, Any])
def get_system_health(
    *, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    """Получить состояние системы"""
    return clinic_management.get_system_health(db=db)


@router.post("/initialize", response_model=Dict[str, Any])
def initialize_clinic_data(
    *, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    """Инициализировать данные клиники по умолчанию"""
    return clinic_management.initialize_default_data(db=db)
