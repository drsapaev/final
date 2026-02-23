"""
Section Templates API Endpoints

Universal API for doctor's personalized templates across all EMR sections.

Endpoints:
- GET /{section_type} - Get templates for section
- POST /{section_type}/{template_id}/pin - Pin template
- DELETE /{section_type}/{template_id}/pin - Unpin template
- PUT /{section_type}/{template_id} - Update template
- DELETE /{section_type}/{template_id} - Delete template
"""


from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.section_templates import (
    DoctorSectionTemplateResponse,
    DoctorSectionTemplatesListResponse,
    DoctorSectionTemplateUpdate,
    SectionType,
)
from app.models.user import User
from app.services.section_templates_service import DoctorSectionTemplatesService

router = APIRouter(
    prefix="/section-templates",
    tags=["section-templates"],
)


class MessageResponse(BaseModel):
    """Simple message response"""
    success: bool
    message: str


@router.get(
    "/{section_type}",
    response_model=DoctorSectionTemplatesListResponse,
    summary="Get templates for section",
)
async def get_section_templates(
    section_type: str,
    icd10_code: str | None = Query(None, description="ICD-10 code for filtering"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Получить персональные шаблоны врача для секции EMR.

    Если указан icd10_code, возвращает:
    1. Шаблоны для конкретного диагноза
    2. Общие шаблоны (icd10_code IS NULL)

    Сортировка:
    - Закреплённые (📌) вверху
    - По частоте использования
    - По последнему использованию
    """
    # Validate section_type
    try:
        SectionType(section_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section_type. Must be one of: {[s.value for s in SectionType]}"
        )

    service = DoctorSectionTemplatesService(db)
    return await service.get_templates(
        doctor_id=current_user.id,
        section_type=section_type,
        icd10_code=icd10_code,
        limit=limit,
    )


@router.post(
    "/{section_type}/{template_id}/pin",
    response_model=MessageResponse,
    summary="Pin template",
)
async def pin_template(
    section_type: str,
    template_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Закрепить шаблон (📌 Часто использую).

    Лимит: максимум 3 закреплённых на секцию.
    При превышении — автоматически открепляется самый старый.
    """
    service = DoctorSectionTemplatesService(db)
    success, message = await service.pin_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return MessageResponse(success=True, message=message)


@router.delete(
    "/{section_type}/{template_id}/pin",
    response_model=MessageResponse,
    summary="Unpin template",
)
async def unpin_template(
    section_type: str,
    template_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """Открепить шаблон."""
    service = DoctorSectionTemplatesService(db)
    success, message = await service.unpin_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return MessageResponse(success=True, message=message)


@router.put(
    "/{section_type}/{template_id}",
    response_model=DoctorSectionTemplateResponse,
    summary="Update template",
)
async def update_template(
    section_type: str,
    template_id: str,
    body: DoctorSectionTemplateUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Обновить шаблон.

    Режимы:
    - `replace`: обновить текст существующего шаблона
    - `save_as_new`: создать новый шаблон с изменённым текстом
    """
    service = DoctorSectionTemplatesService(db)
    template, message = await service.update_template(
        doctor_id=current_user.id,
        template_id=template_id,
        new_text=body.new_text,
        mode=body.mode,
    )

    if not template:
        raise HTTPException(status_code=400, detail=message)

    return DoctorSectionTemplateResponse(
        id=template.id,
        section_type=template.section_type,
        icd10_code=template.icd10_code,
        template_text=template.template_text,
        usage_count=template.usage_count,
        is_pinned=template.is_pinned,
        last_used_at=template.last_used_at,
        created_at=template.created_at,
    )


@router.delete(
    "/{section_type}/{template_id}",
    response_model=MessageResponse,
    summary="Delete template",
)
async def delete_template(
    section_type: str,
    template_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """Удалить шаблон."""
    service = DoctorSectionTemplatesService(db)
    success, message = await service.delete_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail=message)

    return MessageResponse(success=True, message=message)
