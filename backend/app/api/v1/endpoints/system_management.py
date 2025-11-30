"""
API endpoints для управления системой (бэкапы и мониторинг)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.core.roles import Roles
from app.models.user import User
from app.services.backup_service import BackupService, get_backup_service
from app.services.monitoring_service import get_monitoring_service, MonitoringService

logger = logging.getLogger(__name__)

router = APIRouter()


# ===================== PYDANTIC MODELS =====================


class BackupRequest(BaseModel):
    """Запрос создания бэкапа"""

    backup_type: str = Field(..., pattern="^(full|database|configuration)$")
    include_files: bool = True
    description: Optional[str] = None


class RestoreRequest(BaseModel):
    """Запрос восстановления из бэкапа"""

    backup_name: str
    components: List[str] = Field(default=["database", "configuration"])
    confirm: bool = False


class BackupResponse(BaseModel):
    """Ответ с информацией о бэкапе"""

    success: bool
    backup_name: Optional[str] = None
    status: Optional[str] = None
    size: Optional[int] = None
    created_at: Optional[str] = None
    error: Optional[str] = None


class MonitoringThresholds(BaseModel):
    """Пороговые значения для мониторинга"""

    cpu_usage: Optional[float] = Field(None, ge=0, le=100)
    memory_usage: Optional[float] = Field(None, ge=0, le=100)
    disk_usage: Optional[float] = Field(None, ge=0, le=100)
    response_time: Optional[float] = Field(None, ge=0)
    error_rate: Optional[float] = Field(None, ge=0, le=100)
    database_connections: Optional[int] = Field(None, ge=0)


# ===================== БЭКАПЫ =====================


@router.post("/backup/create", response_model=BackupResponse)
async def create_backup(
    request: BackupRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Создает бэкап системы"""
    try:
        backup_service = get_backup_service()

        if request.backup_type == "full":
            # Запускаем создание полного бэкапа в фоне
            background_tasks.add_task(
                _create_full_backup_task, backup_service, request.include_files
            )
            return BackupResponse(
                success=True,
                status="started",
                backup_name="full_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
            )

        elif request.backup_type == "database":
            result = backup_service.create_database_backup()
            return BackupResponse(
                success=result.get("status") == "completed",
                backup_name=result.get("name"),
                status=result.get("status"),
                size=result.get("size"),
                created_at=result.get("created_at"),
                error=result.get("error"),
            )

        else:
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип бэкапа")

    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _create_full_backup_task(backup_service: BackupService, include_files: bool):
    """Задача создания полного бэкапа в фоне"""
    try:
        result = backup_service.create_full_backup(include_files)
        logger.info(f"Полный бэкап завершен: {result.get('name', 'unknown')}")
    except Exception as e:
        logger.error(f"Ошибка создания полного бэкапа: {e}")


@router.get("/backup/list")
async def list_backups(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает список всех бэкапов"""
    try:
        backup_service = get_backup_service()
        backups = backup_service.list_backups()

        return {"success": True, "backups": backups, "total_count": len(backups)}

    except Exception as e:
        logger.error(f"Ошибка получения списка бэкапов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backup/{backup_name}")
async def get_backup_info(
    backup_name: str,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает информацию о конкретном бэкапе"""
    try:
        backup_service = get_backup_service()
        backup_info = backup_service.get_backup_info(backup_name)

        if not backup_info:
            raise HTTPException(status_code=404, detail="Бэкап не найден")

        return {"success": True, "backup": backup_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о бэкапе: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backup/{backup_name}/restore")
async def restore_backup(
    backup_name: str,
    request: RestoreRequest,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Восстанавливает систему из бэкапа"""
    try:
        if not request.confirm:
            raise HTTPException(
                status_code=400,
                detail="Для восстановления требуется подтверждение (confirm=true)",
            )

        backup_service = get_backup_service()
        result = backup_service.restore_backup(backup_name, request.components)

        return {
            "success": result.get("success", False),
            "message": (
                "Восстановление завершено"
                if result.get("success")
                else "Ошибка восстановления"
            ),
            "details": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка восстановления бэкапа: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/backup/{backup_name}")
async def delete_backup(
    backup_name: str,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Удаляет бэкап"""
    try:
        backup_service = get_backup_service()
        result = backup_service.delete_backup(backup_name)

        return result

    except Exception as e:
        logger.error(f"Ошибка удаления бэкапа: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== МОНИТОРИНГ =====================


@router.get("/monitoring/health")
async def get_system_health(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает общее состояние системы"""
    try:
        monitoring_service = get_monitoring_service()
        health = monitoring_service.check_health()

        return health

    except Exception as e:
        logger.error(f"Ошибка проверки состояния системы: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/metrics/system")
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает системные метрики"""
    try:
        monitoring_service = get_monitoring_service()
        metrics = monitoring_service.get_system_metrics()

        return {"success": True, "metrics": metrics}

    except Exception as e:
        logger.error(f"Ошибка получения системных метрик: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/metrics/application")
async def get_application_metrics(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает метрики приложения"""
    try:
        monitoring_service = get_monitoring_service()
        metrics = monitoring_service.get_application_metrics()

        return {"success": True, "metrics": metrics}

    except Exception as e:
        logger.error(f"Ошибка получения метрик приложения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/metrics/history")
async def get_metrics_history(
    hours: int = Query(24, ge=1, le=168, description="Количество часов истории"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает историю метрик"""
    try:
        monitoring_service = get_monitoring_service()
        history = monitoring_service.get_metrics_history(hours)

        return {
            "success": True,
            "history": history,
            "period_hours": hours,
            "data_points": len(history),
        }

    except Exception as e:
        logger.error(f"Ошибка получения истории метрик: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/metrics/summary")
async def get_metrics_summary(
    hours: int = Query(24, ge=1, le=168, description="Количество часов для анализа"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает сводку метрик за период"""
    try:
        monitoring_service = get_monitoring_service()
        summary = monitoring_service.get_metrics_summary(hours)

        return {"success": True, "summary": summary}

    except Exception as e:
        logger.error(f"Ошибка получения сводки метрик: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/alerts")
async def get_alerts(
    severity: Optional[str] = Query(None, pattern="^(critical|warning|info)$"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Получает список алертов"""
    try:
        monitoring_service = get_monitoring_service()
        alerts = monitoring_service.get_alerts(severity, limit)

        return {
            "success": True,
            "alerts": alerts,
            "total_count": len(alerts),
            "severity_filter": severity,
        }

    except Exception as e:
        logger.error(f"Ошибка получения алертов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/thresholds")
async def get_monitoring_thresholds(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Получает пороговые значения мониторинга"""
    try:
        monitoring_service = get_monitoring_service()
        thresholds = monitoring_service.get_thresholds()

        return {"success": True, "thresholds": thresholds}

    except Exception as e:
        logger.error(f"Ошибка получения порогов мониторинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/monitoring/thresholds")
async def update_monitoring_thresholds(
    thresholds: MonitoringThresholds,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Обновляет пороговые значения мониторинга"""
    try:
        monitoring_service = get_monitoring_service()

        # Фильтруем только заданные значения
        new_thresholds = {k: v for k, v in thresholds.dict().items() if v is not None}

        result = monitoring_service.update_thresholds(new_thresholds)

        return result

    except Exception as e:
        logger.error(f"Ошибка обновления порогов мониторинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== УТИЛИТЫ =====================


@router.post("/monitoring/collect")
async def collect_metrics_now(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Принудительно собирает метрики сейчас"""
    try:
        monitoring_service = get_monitoring_service()
        monitoring_service.collect_metrics()

        return {
            "success": True,
            "message": "Метрики собраны",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка сбора метрик: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/status")
async def get_system_status(current_user: User = Depends(get_current_user)):
    """Получает краткий статус системы (доступно всем авторизованным пользователям)"""
    try:
        monitoring_service = get_monitoring_service()

        # Получаем только базовую информацию
        system_metrics = monitoring_service.get_system_metrics()
        health = monitoring_service.check_health()

        return {
            "status": health.get("overall_status", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "basic_info": {
                "cpu_usage": system_metrics.get("cpu", {}).get("usage_percent", 0),
                "memory_usage": system_metrics.get("memory", {}).get(
                    "usage_percent", 0
                ),
                "disk_usage": system_metrics.get("disk", {}).get("usage_percent", 0),
            },
            "alerts_count": len(health.get("alerts", [])),
        }

    except Exception as e:
        logger.error(f"Ошибка получения статуса системы: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }
