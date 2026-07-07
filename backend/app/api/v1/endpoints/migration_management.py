"""
API endpoints для управления миграциями и совместимостью данных
Доступны только администраторам
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit_helper import log_action
from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.migration_management_api_service import MigrationManagementApiService

# ADM-AUDIT-28 P0-4: production env guard for destructive migrations.
router = APIRouter()


def _ensure_not_production(operation: str):
    """Block destructive migration operations in production."""
    from app.core.config import settings
    env = str(getattr(settings, "ENV", "") or "").lower()
    if env in ("prod", "production"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Destructive migration operation '{operation}' is blocked in production. "
            "Use a staging environment or manual DBA procedure.",
        )

# ===================== МОДЕЛИ ДАННЫХ =====================


class MigrationResult(BaseModel):
    """Результат миграции"""

    success: bool
    migrated_records: int
    errors: list[str]
    integrity_check: dict[str, Any]


class BackupResult(BaseModel):
    """Результат создания резервной копии"""

    success: bool
    backup_file: str | None = None
    queues_count: int | None = None
    total_entries: int | None = None
    error: str | None = None


class RestoreResult(BaseModel):
    """Результат восстановления"""

    success: bool
    restored_queues: int | None = None
    restored_entries: int | None = None
    error: str | None = None


class CleanupResult(BaseModel):
    """Результат очистки"""

    success: bool
    deleted_queues: int | None = None
    deleted_entries: int | None = None
    cutoff_date: str | None = None
    error: str | None = None


class IntegrityCheckResult(BaseModel):
    """Результат проверки целостности"""

    passed: bool
    checks: dict[str, Any]
    checked_at: str
    error: str | None = None


class EMRCutoverBackfillResult(BaseModel):
    """Результат backfill миграции legacy EMR в canonical v2."""

    success: bool
    dry_run: bool
    processed: int
    migrated: int
    skipped: int
    failed: int
    rebound_prescriptions: int
    rebound_files: int
    errors: list[dict[str, Any]]
    generated_at: str
    verification: dict[str, Any] | None = None


class EMRCutoverVerificationResult(BaseModel):
    """Verification summary for EMR v2 hard cutover."""

    passed: bool
    checks: dict[str, Any]
    generated_at: str


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
            detail="Internal server error",
        ) from e


@router.post(
    "/admin/migration/emr-cutover/backfill",
    response_model=EMRCutoverBackfillResult,
)
def migrate_legacy_emr_cutover(
    dry_run: bool = Query(False, description="Только проверить, без записи изменений"),
    limit: int | None = Query(None, ge=1, le=10000, description="Лимит legacy EMR для одного прогона"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Запускает ledger-driven миграцию legacy EMR -> canonical EMR v2."""
    try:
        result = MigrationManagementApiService(db).migrate_legacy_emr_data(
            dry_run=dry_run,
            limit=limit,
        )
        return EMRCutoverBackfillResult(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/admin/migration/emr-cutover/verification",
    response_model=EMRCutoverVerificationResult,
)
def verify_emr_cutover(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Проверяет инварианты hard-cutover для EMR v2."""
    try:
        result = MigrationManagementApiService(db).verify_emr_cutover()
        return EMRCutoverVerificationResult(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
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
            detail="Internal server error",
        ) from e


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


@router.post("/admin/migration/backup-queue-data", response_model=BackupResult)
def backup_queue_data(
    target_date: str | None = Query(None, description="Дата в формате YYYY-MM-DD"),
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
            detail="Internal server error",
        ) from e


# ===================== ВОССТАНОВЛЕНИЕ =====================


@router.post("/admin/migration/restore-queue-data", response_model=RestoreResult)
def restore_queue_data(
    backup_file: str = Query(
        ...,
        min_length=1,
        description="Путь к файлу резервной копии",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Восстанавливает данные очередей из резервной копии
    Доступно только администраторам
    """
    try:
        result = MigrationManagementApiService(db).restore_queue_data(backup_file)

        if not result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка восстановления данных: {result.get('error', 'Неизвестная ошибка')}",
            )

        return RestoreResult(
            success=result["success"],
            restored_queues=result.get("restored_queues"),
            restored_entries=result.get("restored_entries"),
            error=result.get("error"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
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
            detail="Internal server error",
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
            detail="Internal server error",
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
            detail="Internal server error",
        ) from e
