"""
API endpoints для экспорта и импорта EMR данных
"""

import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.emr import EMRBase, EMRUpdate
from app.services.emr_export_service import EMRExportService

router = APIRouter()


@router.get("/formats")
async def get_export_formats(current_user: User = Depends(get_current_user)):
    """Получить список поддерживаемых форматов экспорта"""
    try:
        export_service = EMRExportService()
        formats = await export_service.get_export_formats()

        return {
            "success": True,
            "formats": formats,
            "message": "Список форматов экспорта получен",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения форматов: {str(e)}"
        )


@router.get("/formats/import")
async def get_import_formats(current_user: User = Depends(get_current_user)):
    """Получить список поддерживаемых форматов импорта"""
    try:
        export_service = EMRExportService()
        formats = await export_service.get_import_formats()

        return {
            "success": True,
            "formats": formats,
            "message": "Список форматов импорта получен",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения форматов: {str(e)}"
        )


@router.post("/export/json")
async def export_emr_to_json(
    emr_data: dict,
    include_versions: bool = Query(False, description="Включить версии EMR"),
    include_templates: bool = Query(False, description="Включить шаблоны"),
    include_attachments: bool = Query(False, description="Включить вложения"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в JSON формат"""
    try:
        export_service = EMRExportService()

        json_data = await export_service.export_emr_to_json(
            emr_data=emr_data,
            include_versions=include_versions,
            include_templates=include_templates,
            include_attachments=include_attachments,
        )

        return {
            "success": True,
            "data": json_data,
            "message": "EMR успешно экспортирован в JSON",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта в JSON: {str(e)}")


@router.post("/export/xml")
async def export_emr_to_xml(
    emr_data: dict,
    include_versions: bool = Query(False, description="Включить версии EMR"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в XML формат"""
    try:
        export_service = EMRExportService()

        xml_data = await export_service.export_emr_to_xml(
            emr_data=emr_data, include_versions=include_versions
        )

        return Response(
            content=xml_data,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=emr_export.xml"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта в XML: {str(e)}")


@router.post("/export/csv")
async def export_emr_to_csv(
    emr_data: dict,
    fields: Optional[List[str]] = Query(None, description="Поля для экспорта"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в CSV формат"""
    try:
        export_service = EMRExportService()

        csv_data = await export_service.export_emr_to_csv(
            emr_data=emr_data, fields=fields
        )

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=emr_export.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта в CSV: {str(e)}")


@router.post("/export/zip")
async def export_emr_to_zip(
    emr_data: dict,
    include_attachments: bool = Query(True, description="Включить вложения"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в ZIP архив"""
    try:
        export_service = EMRExportService()

        zip_data = await export_service.export_emr_to_zip(
            emr_data=emr_data, include_attachments=include_attachments
        )

        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=emr_export.zip"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта в ZIP: {str(e)}")


@router.post("/import/json")
async def import_emr_from_json(
    json_data: dict, current_user: User = Depends(get_current_user)
):
    """Импорт EMR из JSON формата"""
    try:
        export_service = EMRExportService()

        emr_data = await export_service.import_emr_from_json(json_data)

        return {
            "success": True,
            "data": emr_data,
            "message": "EMR успешно импортирован из JSON",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка импорта из JSON: {str(e)}")


@router.post("/import/xml")
async def import_emr_from_xml(
    xml_data: str, current_user: User = Depends(get_current_user)
):
    """Импорт EMR из XML формата"""
    try:
        export_service = EMRExportService()

        emr_data = await export_service.import_emr_from_xml(xml_data)

        return {
            "success": True,
            "data": emr_data,
            "message": "EMR успешно импортирован из XML",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка импорта из XML: {str(e)}")


@router.post("/import/zip")
async def import_emr_from_zip(
    zip_data: bytes, current_user: User = Depends(get_current_user)
):
    """Импорт EMR из ZIP архива"""
    try:
        export_service = EMRExportService()

        emr_data = await export_service.import_emr_from_zip(zip_data)

        return {
            "success": True,
            "data": emr_data,
            "message": "EMR успешно импортирован из ZIP",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка импорта из ZIP: {str(e)}")


@router.post("/validate")
async def validate_import_data(
    data: dict,
    format_type: str = Query("json", description="Тип формата данных"),
    current_user: User = Depends(get_current_user),
):
    """Валидация импортируемых данных"""
    try:
        export_service = EMRExportService()

        validation_result = await export_service.validate_import_data(
            data=data, format_type=format_type
        )

        return {
            "success": True,
            "validation": validation_result,
            "message": "Валидация данных выполнена",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка валидации: {str(e)}")


@router.post("/estimate-size")
async def estimate_export_size(
    emr_data: dict,
    format_type: str = Query("json", description="Тип формата экспорта"),
    current_user: User = Depends(get_current_user),
):
    """Оценить размер экспортируемых данных"""
    try:
        export_service = EMRExportService()

        size_info = await export_service.estimate_export_size(
            emr_data=emr_data, format_type=format_type
        )

        return {
            "success": True,
            "size_info": size_info,
            "message": "Размер экспорта оценен",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка оценки размера: {str(e)}")


@router.get("/templates/export")
async def get_export_templates(current_user: User = Depends(get_current_user)):
    """Получить шаблоны для экспорта EMR"""
    try:
        templates = {
            "json": {
                "description": "JSON формат с полной структурой данных",
                "fields": [
                    "patient_id",
                    "doctor_id",
                    "complaints",
                    "diagnosis",
                    "icd10",
                ],
                "example": {
                    "patient_id": 1,
                    "doctor_id": 1,
                    "complaints": "боль в груди",
                    "diagnosis": "стенокардия",
                    "icd10": "I20.9",
                },
            },
            "xml": {
                "description": "XML формат для интеграции с внешними системами",
                "structure": "emr_export > emr_data > fields",
                "example": "<?xml version=\"1.0\"?><emr_export><emr_data><patient_id>1</patient_id></emr_data></emr_export>",
            },
            "csv": {
                "description": "CSV формат для анализа в Excel",
                "fields": ["patient_id", "doctor_id", "complaints", "diagnosis"],
                "separator": ",",
            },
            "zip": {
                "description": "ZIP архив с данными и вложениями",
                "contents": [
                    "emr_data.json",
                    "emr_data.xml",
                    "emr_data.csv",
                    "attachments/",
                ],
            },
        }

        return {
            "success": True,
            "templates": templates,
            "message": "Шаблоны экспорта получены",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения шаблонов: {str(e)}"
        )


@router.get("/statistics")
async def get_export_statistics(current_user: User = Depends(get_current_user)):
    """Получить статистику экспорта/импорта"""
    try:
        # Здесь можно добавить логику для получения статистики из базы данных
        statistics = {
            "total_exports": 0,
            "total_imports": 0,
            "formats_usage": {"json": 0, "xml": 0, "csv": 0, "zip": 0},
            "last_export": None,
            "last_import": None,
            "success_rate": 100.0,
        }

        return {
            "success": True,
            "statistics": statistics,
            "message": "Статистика экспорта/импорта получена",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статистики: {str(e)}"
        )
