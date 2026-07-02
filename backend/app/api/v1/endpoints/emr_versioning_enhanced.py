"""
API endpoints для расширенного версионирования EMR
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.emr_versioning_enhanced import emr_versioning_enhanced

router = APIRouter()


@router.get("/{emr_id}/versions/timeline")
async def get_version_timeline(
    emr_id: int,
    limit: int = Query(50, ge=1, le=100, description="Максимальное количество версий"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить временную линию версий EMR"""
    try:
        timeline = await emr_versioning_enhanced.get_version_timeline(
            db=db, emr_id=emr_id, limit=limit
        )

        return {"emr_id": emr_id, "timeline": timeline, "total_versions": len(timeline)}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения временной линии: {str(e)}"
        )


@router.get("/{emr_id}/versions/compare")
async def compare_versions(
    emr_id: int,
    version1_id: int = Query(..., description="ID первой версии"),
    version2_id: int = Query(..., description="ID второй версии"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Сравнить две версии EMR"""
    try:
        comparison = await emr_versioning_enhanced.get_version_comparison(
            db=db, emr_id=emr_id, version1_id=version1_id, version2_id=version2_id
        )

        return comparison

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка сравнения версий: {str(e)}"
        )


@router.post("/{emr_id}/versions/{version_id}/restore")
async def restore_version_with_backup(
    emr_id: int,
    version_id: int,
    reason: Optional[str] = Query(None, description="Причина восстановления"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Восстановить версию EMR с созданием резервной копии"""
    try:
        result = await emr_versioning_enhanced.restore_version_with_backup(
            db=db,
            emr_id=emr_id,
            version_id=version_id,
            restored_by=current_user.id,
            reason=reason,
        )

        return {"message": "Версия успешно восстановлена", "result": result}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка восстановления версии: {str(e)}"
        )


@router.get("/{emr_id}/versions/statistics")
async def get_version_statistics(
    emr_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить статистику версий EMR"""
    try:
        statistics = await emr_versioning_enhanced.get_version_statistics(
            db=db, emr_id=emr_id
        )

        return {"emr_id": emr_id, "statistics": statistics}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статистики: {str(e)}"
        )


@router.post("/{emr_id}/versions/create")
async def create_version_with_analysis(
    emr_id: int,
    version_data: Dict[str, Any],
    change_type: str = Query(..., description="Тип изменения"),
    change_description: Optional[str] = Query(None, description="Описание изменения"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Создать версию EMR с анализом изменений"""
    try:
        # Получаем предыдущую версию для анализа
        from app.crud.emr_template import emr_version

        previous_versions = emr_version.get_by_emr(db, emr_id=emr_id, limit=1)
        previous_version = previous_versions[0] if previous_versions else None

        version = await emr_versioning_enhanced.create_version_with_analysis(
            db=db,
            emr_id=emr_id,
            version_data=version_data,
            change_type=change_type,
            change_description=change_description,
            changed_by=current_user.id,
            previous_version=(
                previous_version.version_data if previous_version else None
            ),
        )

        return {
            "message": "Версия успешно создана",
            "version_id": version.id,
            "version_number": version.version_number,
            "created_at": version.created_at,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания версии: {str(e)}")


@router.get("/{emr_id}/versions/{version_id}/details")
async def get_version_details(
    emr_id: int,
    version_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить детали конкретной версии EMR"""
    try:
        from app.crud.emr_template import emr_version

        version = emr_version.get(db, id=version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Версия не найдена")

        if version.emr_id != emr_id:
            raise HTTPException(
                status_code=400, detail="Версия не принадлежит указанному EMR"
            )

        # Получаем краткое описание данных
        data_summary = await emr_versioning_enhanced._get_data_summary(
            version.version_data
        )

        return {
            "version_id": version.id,
            "emr_id": version.emr_id,
            "version_number": version.version_number,
            "change_type": version.change_type,
            "change_description": version.change_description,
            "changed_by": version.changed_by,
            "created_at": version.created_at,
            "data_summary": data_summary,
            "version_data": version.version_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения деталей версии: {str(e)}"
        )


@router.delete("/{emr_id}/versions/{version_id}")
async def delete_version(
    emr_id: int,
    version_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin")),
) -> Any:
    """Удалить версию EMR (только для администраторов)"""
    try:
        from app.crud.emr_template import emr_version

        version = emr_version.get(db, id=version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Версия не найдена")

        if version.emr_id != emr_id:
            raise HTTPException(
                status_code=400, detail="Версия не принадлежит указанному EMR"
            )

        emr_version.remove(db, id=version_id)

        return {"message": "Версия успешно удалена", "version_id": version_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления версии: {str(e)}")


@router.get("/{emr_id}/versions/export")
async def export_versions(
    emr_id: int,
    format: str = Query("json", description="Формат экспорта: json, csv"),
    include_data: bool = Query(True, description="Включать данные версий"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Экспортировать версии EMR"""
    try:
        from app.crud.emr_template import emr_version

        versions = emr_version.get_by_emr(db, emr_id=emr_id, limit=1000)

        if format == "json":
            export_data = []
            for version in versions:
                version_data = {
                    "id": version.id,
                    "version_number": version.version_number,
                    "change_type": version.change_type,
                    "change_description": version.change_description,
                    "changed_by": version.changed_by,
                    "created_at": version.created_at.isoformat(),
                }

                if include_data:
                    version_data["version_data"] = version.version_data

                export_data.append(version_data)

            return {
                "emr_id": emr_id,
                "format": format,
                "total_versions": len(export_data),
                "data": export_data,
            }

        elif format == "csv":
            # Здесь будет генерация CSV
            return {
                "message": "CSV экспорт будет реализован в следующей версии",
                "emr_id": emr_id,
                "format": format,
            }

        else:
            raise HTTPException(
                status_code=400, detail="Неподдерживаемый формат экспорта"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта версий: {str(e)}")
