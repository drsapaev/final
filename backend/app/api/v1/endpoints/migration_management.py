"""
API endpoints для управления миграциями и совместимостью данных
Доступны только администраторам
"""

from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.migration_management_api_service import MigrationManagementApiService

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class MigrationResult(BaseModel):
    """Результат миграции"""

    success: bool
    migrated_records: int
    errors: list[str]
    integrity_check: Dict[str, Any]


class BackupResult(BaseModel):
    """Результат создания резервной копии"""

    success: bool
    backup_file: Optional[str] = None
    queues_count: Optional[int] = None
    total_entries: Optional[int] = None
    error: Optional[str] = None


class RestoreResult(BaseModel):
    """Результат восстановления"""

    success: bool
    restored_queues: Optional[int] = None
    restored_entries: Optional[int] = None
    error: Optional[str] = None


class CleanupResult(BaseModel):
    """Результат очистки"""

    success: bool
    deleted_queues: Optional[int] = None
    deleted_entries: Optional[int] = None
    cutoff_date: Optional[str] = None
    error: Optional[str] = None


class IntegrityCheckResult(BaseModel):
    """Результат проверки целостности"""

    passed: bool
    checks: Dict[str, Any]
    checked_at: str
    error: Optional[str] = None


# ===================== МИГРАЦИЯ ДАННЫХ =====================


@router.post("/admin/migration/migrate-legacy-data", response_model=MigrationResult)
def migrate_legacy_queue_data(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Мигрирует данные из старых таблиц очередей в новые
    Доступно только администраторам
    """
    try:
        result = MigrationManagementApiService(db).migrate_legacy_queue_data()

        return MigrationResult(
            success=result["success"],
            migrated_records=result["migrated_records"],
            errors=result["errors"],
            integrity_check=result["integrity_check"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка миграции данных: {str(e)}",
        ) from e


# ===================== ПРОВЕРКА ЦЕЛОСТНОСТИ =====================


@router.get("/admin/migration/check-integrity", response_model=IntegrityCheckResult)
def check_data_integrity(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Проверяет целостность данных в таблицах очередей
    Доступно только администраторам
    """
    try:
        result = MigrationManagementApiService(db).check_data_integrity()

        return IntegrityCheckResult(
            passed=result["passed"],
            checks=result["checks"],
            checked_at=result["checked_at"],
            error=result.get("error"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки целостности: {str(e)}",
        ) from e


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


@router.post("/admin/migration/backup-queue-data", response_model=BackupResult)
def backup_queue_data(
    target_date: Optional[str] = Query(None, description="Дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Создает резервную копию данных очередей за указанную дату
    Доступно только администраторам
    """
    try:
        result = MigrationManagementApiService(db).backup_queue_data(target_date)

        return BackupResult(
            success=result["success"],
            backup_file=result.get("backup_file"),
            queues_count=result.get("queues_count"),
            total_entries=result.get("total_entries"),
            error=result.get("error"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания резервной копии: {str(e)}",
        ) from e


# ===================== ВОССТАНОВЛЕНИЕ =====================


@router.post("/admin/migration/restore-queue-data", response_model=RestoreResult)
def restore_queue_data(
    backup_file: str = Query(..., description="Путь к файлу резервной копии"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Восстанавливает данные очередей из резервной копии
    Доступно только администраторам
    """
    try:
        result = MigrationManagementApiService(db).restore_queue_data(backup_file)

        return RestoreResult(
            success=result["success"],
            restored_queues=result.get("restored_queues"),
            restored_entries=result.get("restored_entries"),
            error=result.get("error"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка восстановления данных: {str(e)}",
        ) from e


# ===================== ОЧИСТКА СТАРЫХ ДАННЫХ =====================


@router.post("/admin/migration/cleanup-old-data", response_model=CleanupResult)
def cleanup_old_queue_data(
    days_to_keep: int = Query(
        30, ge=1, le=365, description="Количество дней для хранения"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Очищает старые данные очередей
    Доступно только администраторам
    """
    try:
        result = MigrationManagementApiService(db).cleanup_old_data(days_to_keep)

        return CleanupResult(
            success=result["success"],
            deleted_queues=result.get("deleted_queues"),
            deleted_entries=result.get("deleted_entries"),
            cutoff_date=result.get("cutoff_date"),
            error=result.get("error"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка очистки данных: {str(e)}",
        ) from e


# ===================== СТАТИСТИКА МИГРАЦИЙ =====================


@router.get("/admin/migration/stats")
def get_migration_stats(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получает статистику по миграциям и данным очередей
    Доступно только администраторам
    """
    try:
        return MigrationManagementApiService(db).get_migration_stats()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        ) from e


# ===================== ПРОВЕРКА МИГРАЦИЙ =====================


@router.get("/admin/migration/health")
def check_migration_health(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Проверяет состояние системы миграций
    Доступно только администраторам
    """
    try:
        return MigrationManagementApiService(db).check_migration_health()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки состояния миграций: {str(e)}",
        ) from e
