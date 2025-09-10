"""
API endpoints для экспорта/импорта EMR
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json
from io import BytesIO

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.emr_export_service import get_emr_export_service, EMRExportService
from app.crud.emr import emr as crud_emr
from app.crud.emr_template import emr_version

router = APIRouter()


@router.get("/formats")
async def get_export_formats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить список поддерживаемых форматов экспорта"""
    try:
        export_service = await get_emr_export_service()
        formats = await export_service.get_export_formats()
        
        return {
            "formats": formats,
            "count": len(formats)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения форматов экспорта: {str(e)}"
        )


@router.get("/{emr_id}/export/json")
async def export_emr_json(
    emr_id: int,
    include_versions: bool = Query(False, description="Включить версии EMR"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт EMR в JSON формате"""
    try:
        # Получаем EMR
        emr = crud_emr.get(db, id=emr_id)
        if not emr:
            raise HTTPException(status_code=404, detail="EMR не найден")
        
        # Получаем версии если нужно
        versions = None
        if include_versions:
            versions = emr_version.get_by_emr(db, emr_id=emr_id, limit=100)
            versions = [version.__dict__ for version in versions]
        
        # Экспортируем в JSON
        export_service = await get_emr_export_service()
        json_data = await export_service.export_emr_to_json(
            emr.__dict__, include_versions, versions
        )
        
        return json_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка экспорта EMR в JSON: {str(e)}"
        )


@router.get("/{emr_id}/export/pdf")
async def export_emr_pdf(
    emr_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт EMR в PDF формате"""
    try:
        # Получаем EMR
        emr = crud_emr.get(db, id=emr_id)
        if not emr:
            raise HTTPException(status_code=404, detail="EMR не найден")
        
        # Экспортируем в PDF
        export_service = await get_emr_export_service()
        pdf_data = await export_service.export_emr_to_pdf(emr.__dict__)
        
        # Возвращаем PDF как поток
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=emr_{emr_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка экспорта EMR в PDF: {str(e)}"
        )


@router.get("/{emr_id}/export/zip")
async def export_emr_zip(
    emr_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт EMR в ZIP архиве"""
    try:
        # Получаем EMR
        emr = crud_emr.get(db, id=emr_id)
        if not emr:
            raise HTTPException(status_code=404, detail="EMR не найден")
        
        # Получаем вложения
        attachments = emr.attachments or []
        
        # Экспортируем в ZIP
        export_service = await get_emr_export_service()
        zip_data = await export_service.export_emr_to_zip(emr.__dict__, attachments)
        
        # Возвращаем ZIP как поток
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=emr_{emr_id}.zip"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка экспорта EMR в ZIP: {str(e)}"
        )


@router.post("/import/json")
async def import_emr_json(
    json_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Импорт EMR из JSON формата"""
    try:
        # Валидируем данные
        export_service = await get_emr_export_service()
        validation_result = await export_service.validate_import_data(json_data)
        
        if not validation_result["is_valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибки валидации: {validation_result['errors']}"
            )
        
        # Импортируем данные
        emr_data = await export_service.import_emr_from_json(json_data)
        
        # Создаем EMR в базе данных
        from app.schemas.emr import EMRCreate
        emr_create = EMRCreate(**emr_data)
        new_emr = crud_emr.create(db, obj_in=emr_create)
        
        return {
            "message": "EMR успешно импортирован",
            "emr_id": new_emr.id,
            "warnings": validation_result.get("warnings", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка импорта EMR: {str(e)}"
        )


@router.post("/import/validate")
async def validate_import_data(
    json_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Валидация данных для импорта EMR"""
    try:
        export_service = await get_emr_export_service()
        validation_result = await export_service.validate_import_data(json_data)
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка валидации импорта: {str(e)}"
        )


@router.get("/{emr_id}/export/health")
async def export_health_check():
    """Проверка здоровья сервиса экспорта"""
    return {
        "status": "ok",
        "export_service": "active",
        "supported_formats": ["json", "pdf", "zip"],
        "features": [
            "export_json",
            "export_pdf", 
            "export_zip",
            "import_json",
            "validate_import"
        ]
    }
