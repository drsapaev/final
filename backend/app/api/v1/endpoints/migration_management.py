"""
API endpoints для управления миграциями и совместимостью данных
Доступны только администраторам
"""
from datetime import date, datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.migration_service import MigrationService

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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Мигрирует данные из старых таблиц очередей в новые
    Доступно только администраторам
    """
    try:
        migration_service = MigrationService(db)
        result = migration_service.migrate_legacy_queue_data()
        
        return MigrationResult(
            success=result["success"],
            migrated_records=result["migrated_records"],
            errors=result["errors"],
            integrity_check=result["integrity_check"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка миграции данных: {str(e)}"
        )

# ===================== ПРОВЕРКА ЦЕЛОСТНОСТИ =====================

@router.get("/admin/migration/check-integrity", response_model=IntegrityCheckResult)
def check_data_integrity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Проверяет целостность данных в таблицах очередей
    Доступно только администраторам
    """
    try:
        migration_service = MigrationService(db)
        result = migration_service._check_data_integrity()
        
        return IntegrityCheckResult(
            passed=result["passed"],
            checks=result["checks"],
            checked_at=result["checked_at"],
            error=result.get("error")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки целостности: {str(e)}"
        )

# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================

@router.post("/admin/migration/backup-queue-data", response_model=BackupResult)
def backup_queue_data(
    target_date: Optional[str] = Query(None, description="Дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Создает резервную копию данных очередей за указанную дату
    Доступно только администраторам
    """
    try:
        migration_service = MigrationService(db)
        
        # Парсим дату если указана
        parsed_date = None
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD"
                )
        
        result = migration_service.backup_queue_data(parsed_date)
        
        return BackupResult(
            success=result["success"],
            backup_file=result.get("backup_file"),
            queues_count=result.get("queues_count"),
            total_entries=result.get("total_entries"),
            error=result.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания резервной копии: {str(e)}"
        )

# ===================== ВОССТАНОВЛЕНИЕ =====================

@router.post("/admin/migration/restore-queue-data", response_model=RestoreResult)
def restore_queue_data(
    backup_file: str = Query(..., description="Путь к файлу резервной копии"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Восстанавливает данные очередей из резервной копии
    Доступно только администраторам
    """
    try:
        migration_service = MigrationService(db)
        result = migration_service.restore_queue_data(backup_file)
        
        return RestoreResult(
            success=result["success"],
            restored_queues=result.get("restored_queues"),
            restored_entries=result.get("restored_entries"),
            error=result.get("error")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка восстановления данных: {str(e)}"
        )

# ===================== ОЧИСТКА СТАРЫХ ДАННЫХ =====================

@router.post("/admin/migration/cleanup-old-data", response_model=CleanupResult)
def cleanup_old_queue_data(
    days_to_keep: int = Query(30, ge=1, le=365, description="Количество дней для хранения"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Очищает старые данные очередей
    Доступно только администраторам
    """
    try:
        migration_service = MigrationService(db)
        result = migration_service.cleanup_old_data(days_to_keep)
        
        return CleanupResult(
            success=result["success"],
            deleted_queues=result.get("deleted_queues"),
            deleted_entries=result.get("deleted_entries"),
            cutoff_date=result.get("cutoff_date"),
            error=result.get("error")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка очистки данных: {str(e)}"
        )

# ===================== СТАТИСТИКА МИГРАЦИЙ =====================

@router.get("/admin/migration/stats")
def get_migration_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получает статистику по миграциям и данным очередей
    Доступно только администраторам
    """
    try:
        from sqlalchemy import text
        
        # Статистика по очередям
        queue_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_queues,
                COUNT(CASE WHEN active = 1 THEN 1 END) as active_queues,
                COUNT(CASE WHEN opened_at IS NOT NULL THEN 1 END) as opened_queues,
                MIN(day) as earliest_date,
                MAX(day) as latest_date
            FROM daily_queues
        """)).fetchone()
        
        # Статистика по записям в очередях
        entry_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_entries,
                COUNT(CASE WHEN status = 'waiting' THEN 1 END) as waiting_entries,
                COUNT(CASE WHEN status = 'called' THEN 1 END) as called_entries,
                COUNT(CASE WHEN status = 'served' THEN 1 END) as served_entries,
                COUNT(CASE WHEN visit_id IS NOT NULL THEN 1 END) as linked_to_visits,
                COUNT(CASE WHEN source = 'migration' THEN 1 END) as migrated_entries
            FROM queue_entries
        """)).fetchone()
        
        # Статистика по источникам записей
        source_stats = db.execute(text("""
            SELECT 
                source,
                COUNT(*) as count
            FROM queue_entries
            GROUP BY source
            ORDER BY count DESC
        """)).fetchall()
        
        # Статистика по тегам очередей
        tag_stats = db.execute(text("""
            SELECT 
                queue_tag,
                COUNT(*) as queue_count,
                SUM((SELECT COUNT(*) FROM queue_entries WHERE queue_id = daily_queues.id)) as total_entries
            FROM daily_queues
            WHERE queue_tag IS NOT NULL
            GROUP BY queue_tag
            ORDER BY queue_count DESC
        """)).fetchall()
        
        return {
            "queue_statistics": {
                "total_queues": queue_stats.total_queues,
                "active_queues": queue_stats.active_queues,
                "opened_queues": queue_stats.opened_queues,
                "earliest_date": queue_stats.earliest_date,
                "latest_date": queue_stats.latest_date
            },
            "entry_statistics": {
                "total_entries": entry_stats.total_entries,
                "waiting_entries": entry_stats.waiting_entries,
                "called_entries": entry_stats.called_entries,
                "served_entries": entry_stats.served_entries,
                "linked_to_visits": entry_stats.linked_to_visits,
                "migrated_entries": entry_stats.migrated_entries
            },
            "source_distribution": [
                {"source": row.source, "count": row.count}
                for row in source_stats
            ],
            "queue_tag_distribution": [
                {
                    "queue_tag": row.queue_tag,
                    "queue_count": row.queue_count,
                    "total_entries": row.total_entries
                }
                for row in tag_stats
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )

# ===================== ПРОВЕРКА МИГРАЦИЙ =====================

@router.get("/admin/migration/health")
def check_migration_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Проверяет состояние системы миграций
    Доступно только администраторам
    """
    try:
        from sqlalchemy import text
        
        health_checks = {}
        
        # 1. Проверяем существование новых таблиц
        tables_to_check = ['daily_queues', 'queue_entries', 'queue_tokens']
        for table in tables_to_check:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                health_checks[f"table_{table}"] = {
                    "exists": True,
                    "record_count": result.fetchone()[0]
                }
            except Exception as e:
                health_checks[f"table_{table}"] = {
                    "exists": False,
                    "error": str(e)
                }
        
        # 2. Проверяем индексы
        try:
            indexes = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' 
                AND name LIKE 'ix_%queue%'
            """)).fetchall()
            
            health_checks["indexes"] = {
                "count": len(indexes),
                "names": [idx.name for idx in indexes]
            }
        except Exception as e:
            health_checks["indexes"] = {"error": str(e)}
        
        # 3. Проверяем миграции Alembic
        try:
            current_revision = db.execute(text("""
                SELECT version_num FROM alembic_version
            """)).fetchone()
            
            health_checks["alembic"] = {
                "current_revision": current_revision.version_num if current_revision else None
            }
        except Exception as e:
            health_checks["alembic"] = {"error": str(e)}
        
        # Общий статус
        all_healthy = all(
            check.get("exists", True) and "error" not in check
            for check in health_checks.values()
        )
        
        return {
            "healthy": all_healthy,
            "checks": health_checks,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки состояния миграций: {str(e)}"
        )
