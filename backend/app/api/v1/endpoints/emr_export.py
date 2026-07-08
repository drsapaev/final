"""
API endpoints для экспорта и импорта EMR данных

P0-7 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `emr_data: dict`, `json_data: dict`,
and `data: dict` with no validation, allowing PHI schema drift, memory
abuse via oversized payloads, and potential deserialization attacks.
Replaced with typed Pydantic request models from app.schemas.emr_export
that enforce required core fields, size caps, and reject dangerous keys.
"""

import logging
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.deps import get_current_user

# EMR-AUDIT-28 P0-4: весь роутер требует Admin/Doctor role.
# Раньше использовал get_current_user без role check — Patient мог
# вызывать export и получать произвольный EMR data как downloadable file.
from app.api.deps import require_roles as _require_emr_export_roles
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.emr_export import (
    EMRExportDataRequest,
    EMRImportJsonRequest,
    EMRValidateDataRequest,
)
from app.services.emr_export_service import EMRExportService

router = APIRouter(dependencies=[Depends(_require_emr_export_roles("Admin", "Doctor"))])
logger = logging.getLogger(__name__)

EMR_EXPORT_PUBLIC_ERROR = "Internal server error"


def _raise_emr_export_internal_error(operation: str, exc: Exception) -> NoReturn:
    logger.warning(
        "EMR export endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail=EMR_EXPORT_PUBLIC_ERROR) from exc


@router.get("/formats", response_model=dict[str, Any])
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
        _raise_emr_export_internal_error("get_export_formats", e)


@router.get("/formats/import", response_model=dict[str, Any])
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
        _raise_emr_export_internal_error("get_import_formats", e)


@router.post("/export/json", response_model=dict[str, Any])
@limiter.limit("5/minute")  # P1-1: rate limit (export)
async def export_emr_to_json(request: Request,
    body: EMRExportDataRequest,
    include_versions: bool = Query(False, description="Включить версии EMR"),
    include_templates: bool = Query(False, description="Включить шаблоны"),
    include_attachments: bool = Query(False, description="Включить вложения"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в JSON формат"""
    try:
        export_service = EMRExportService()

        json_data = await export_service.export_emr_to_json(
            emr_data=body.model_dump(exclude_none=True),
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
        _raise_emr_export_internal_error("export_emr_to_json", e)


@router.post("/export/xml", response_model=dict[str, Any])
async def export_emr_to_xml(
    body: EMRExportDataRequest,
    include_versions: bool = Query(False, description="Включить версии EMR"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в XML формат"""
    try:
        export_service = EMRExportService()

        xml_data = await export_service.export_emr_to_xml(
            emr_data=body.model_dump(exclude_none=True),
            include_versions=include_versions,
        )

        return Response(
            content=xml_data,
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=emr_export.xml"},
        )
    except Exception as e:
        _raise_emr_export_internal_error("export_emr_to_xml", e)


@router.post("/export/csv", response_model=dict[str, Any])
async def export_emr_to_csv(
    body: EMRExportDataRequest,
    fields: list[str] | None = Query(None, description="Поля для экспорта"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в CSV формат"""
    try:
        export_service = EMRExportService()

        csv_data = await export_service.export_emr_to_csv(
            emr_data=body.model_dump(exclude_none=True),
            fields=fields,
        )

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=emr_export.csv"},
        )
    except Exception as e:
        _raise_emr_export_internal_error("export_emr_to_csv", e)


@router.post("/export/zip", response_model=dict[str, Any])
async def export_emr_to_zip(
    body: EMRExportDataRequest,
    include_attachments: bool = Query(True, description="Включить вложения"),
    current_user: User = Depends(get_current_user),
):
    """Экспорт EMR в ZIP архив"""
    try:
        export_service = EMRExportService()

        zip_data = await export_service.export_emr_to_zip(
            emr_data=body.model_dump(exclude_none=True),
            include_attachments=include_attachments,
        )

        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=emr_export.zip"},
        )
    except Exception as e:
        _raise_emr_export_internal_error("export_emr_to_zip", e)


@router.post("/import/json", response_model=dict[str, Any])
async def import_emr_from_json(
    body: EMRImportJsonRequest,
    current_user: User = Depends(get_current_user),
):
    """Импорт EMR из JSON формата"""
    try:
        export_service = EMRExportService()

        emr_data = await export_service.import_emr_from_json(
            body.model_dump(exclude_none=True)
        )

        return {
            "success": True,
            "data": emr_data,
            "message": "EMR успешно импортирован из JSON",
        }
    except Exception as e:
        _raise_emr_export_internal_error("import_emr_from_json", e)


@router.post("/import/xml", response_model=dict[str, Any])
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
        _raise_emr_export_internal_error("import_emr_from_xml", e)


@router.post("/import/zip", response_model=dict[str, Any])
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
        _raise_emr_export_internal_error("import_emr_from_zip", e)


@router.post("/validate", response_model=dict[str, Any])
async def validate_import_data(
    body: EMRValidateDataRequest,
    format_type: str = Query("json", description="Тип формата данных"),
    current_user: User = Depends(get_current_user),
):
    """Валидация импортируемых данных"""
    try:
        export_service = EMRExportService()

        validation_result = await export_service.validate_import_data(
            data=body.model_dump(exclude_none=True),
            format_type=format_type,
        )

        return {
            "success": True,
            "validation": validation_result,
            "message": "Валидация данных выполнена",
        }
    except Exception as e:
        _raise_emr_export_internal_error("validate_import_data", e)


@router.post("/estimate-size", response_model=dict[str, Any])
async def estimate_export_size(
    body: EMRExportDataRequest,
    format_type: str = Query("json", description="Тип формата экспорта"),
    current_user: User = Depends(get_current_user),
):
    """Оценить размер экспортируемых данных"""
    try:
        export_service = EMRExportService()

        size_info = await export_service.estimate_export_size(
            emr_data=body.model_dump(exclude_none=True),
            format_type=format_type,
        )

        return {
            "success": True,
            "size_info": size_info,
            "message": "Размер экспорта оценен",
        }
    except Exception as e:
        _raise_emr_export_internal_error("estimate_export_size", e)


@router.get("/templates/export", response_model=dict[str, Any])
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
        _raise_emr_export_internal_error("get_export_templates", e)


@router.get("/statistics", response_model=dict[str, Any])
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
        _raise_emr_export_internal_error("get_export_statistics", e)
