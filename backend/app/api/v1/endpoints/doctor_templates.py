"""
Doctor Treatment Templates API - персональная клиническая память врача

Endpoints для получения и управления шаблонами лечения,
основанными на реальной практике врача.

Принцип: AI = индекс + сортировка, НЕ генерация
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.doctor_templates_service import DoctorTemplatesService
from app.models.doctor_templates import (
    DoctorTreatmentTemplatesListResponse,
    DoctorTreatmentTemplateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/doctor-templates", tags=["Doctor Templates"])


@router.get(
    "/treatment",
    response_model=DoctorTreatmentTemplatesListResponse,
    summary="Получить шаблоны лечения по диагнозу",
)
async def get_treatment_templates(
    icd10: str = Query(..., description="Код МКБ-10"),
    limit: int = Query(5, ge=1, le=20, description="Максимум шаблонов"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить персональные шаблоны лечения врача по коду МКБ-10.
    
    Возвращает шаблоны, основанные на прошлых подписанных EMR врача,
    отсортированные по частоте использования (usage_count DESC).
    
    Пример ответа:
    ```json
    {
        "source": "doctor_history",
        "icd10_code": "I10",
        "templates": [
            {
                "id": "...",
                "treatment_text": "Эналаприл 10 мг 2 раза в день",
                "usage_count": 12,
                "last_used_at": "2025-01-10T..."
            }
        ],
        "total": 1
    }
    ```
    """
    service = DoctorTemplatesService(db)
    return await service.get_templates_by_diagnosis(
        doctor_id=current_user.id,
        icd10_code=icd10.strip().upper(),
        limit=limit,
    )


@router.delete(
    "/treatment/{template_id}",
    summary="Удалить шаблон лечения",
)
async def delete_treatment_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Удалить свой шаблон лечения.
    
    Врач может удалить только свои шаблоны.
    """
    service = DoctorTemplatesService(db)
    deleted = await service.delete_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"status": "deleted", "id": template_id}


@router.get(
    "/all",
    response_model=list[DoctorTreatmentTemplateResponse],
    summary="Получить все шаблоны врача",
)
async def get_all_templates(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить все шаблоны лечения врача (для админ панели).
    """
    service = DoctorTemplatesService(db)
    return await service.get_all_templates_for_doctor(
        doctor_id=current_user.id,
        limit=limit,
    )


# ============== Pin/Unpin Endpoints ==============

@router.post(
    "/treatment/{template_id}/pin",
    summary="📌 Закрепить шаблон",
)
async def pin_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Закрепить шаблон (📌 Часто использую).
    
    Max 3 закреплённых на диагноз.
    При превышении лимита - автоматически открепляет самый старый.
    """
    service = DoctorTemplatesService(db)
    pinned = await service.pin_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )
    
    if not pinned:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"status": "pinned", "id": template_id}


@router.delete(
    "/treatment/{template_id}/pin",
    summary="Открепить шаблон",
)
async def unpin_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Открепить шаблон.
    """
    service = DoctorTemplatesService(db)
    unpinned = await service.unpin_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )
    
    if not unpinned:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"status": "unpinned", "id": template_id}


# ============== Edit Template Endpoint ==============

from pydantic import BaseModel as PydanticBaseModel

class UpdateTemplateRequest(PydanticBaseModel):
    treatment_text: str
    mode: str = "replace"  # "replace" | "save_as_new"


@router.put(
    "/treatment/{template_id}",
    summary="✏️ Редактировать шаблон",
)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Редактировать шаблон лечения.
    
    Modes:
    - "replace": Обновить текст существующего шаблона
    - "save_as_new": Создать новый шаблон с новым текстом
    """
    if request.mode not in ("replace", "save_as_new"):
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'replace' or 'save_as_new'")
    
    service = DoctorTemplatesService(db)
    result = await service.update_template(
        doctor_id=current_user.id,
        template_id=template_id,
        new_text=request.treatment_text,
        mode=request.mode,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Template not found or update failed")
    
    return {
        "status": "updated" if request.mode == "replace" else "created",
        "id": result.id,
        "mode": request.mode,
    }

