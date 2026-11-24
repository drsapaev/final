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
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.models.section_templates import (
    DoctorSectionTemplateResponse,
    DoctorSectionTemplatesListResponse,
    DoctorSectionTemplateUpdate,
    SectionType,
)
from app.models.user import User
from app.services.section_templates_service import (
    TEMPLATE_REVISION_CONFLICT,
    DoctorSectionTemplatesService,
)

router = APIRouter(
    prefix="/section-templates",
    tags=["section-templates"],
)


class MessageResponse(BaseModel):
    """Simple message response"""
    success: bool
    message: str


class TemplateReviewRequest(BaseModel):
    expected_revision: int = Field(gt=0)
    reviewed: bool = True


@router.post("/{section_type}/{template_id}/review", response_model=DoctorSectionTemplateResponse)
def review_section_template(
    section_type: SectionType,
    template_id: str,
    payload: TemplateReviewRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    service = DoctorSectionTemplatesService(db)
    template = service.review_template(
        current_user.id, section_type.value, template_id, payload.expected_revision, payload.reviewed,
    )
    if template is None:
        raise HTTPException(status_code=409, detail="Template unavailable or version changed")
    return DoctorSectionTemplateResponse.model_validate(template)


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
    db: Session = Depends(deps.get_db),
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
    return service.get_templates(
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
    db: Session = Depends(deps.get_db),
):
    """
    Закрепить шаблон (📌 Часто использую).

    Лимит: максимум 3 закреплённых на секцию.
    При превышении — автоматически открепляется самый старый.
    """
    service = DoctorSectionTemplatesService(db)
    success, message = service.pin_template(
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
    db: Session = Depends(deps.get_db),
):
    """Открепить шаблон."""
    service = DoctorSectionTemplatesService(db)
    success, message = service.unpin_template(
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
    responses={409: {"description": "The selected template revision has changed"}},
)
async def update_template(
    section_type: str,
    template_id: str,
    body: DoctorSectionTemplateUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Обновить шаблон.

    Режимы:
    - `replace`: обновить текст существующего шаблона
    - `save_as_new`: создать новый шаблон с изменённым текстом
    """
    service = DoctorSectionTemplatesService(db)
    template, message = service.update_template(
        doctor_id=current_user.id,
        template_id=template_id,
        new_text=body.new_text,
        mode=body.mode,
        shortcut=body.shortcut,
        expected_revision=body.expected_revision,
    )

    if not template:
        raise HTTPException(
            status_code=409 if message == TEMPLATE_REVISION_CONFLICT else 400,
            detail=message,
        )

    return DoctorSectionTemplateResponse.model_validate(template)


@router.delete(
    "/{section_type}/{template_id}",
    response_model=MessageResponse,
    summary="Delete template",
)
async def delete_template(
    section_type: str,
    template_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Удалить шаблон."""
    service = DoctorSectionTemplatesService(db)
    success, message = service.delete_template(
        doctor_id=current_user.id,
        template_id=template_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail=message)

    return MessageResponse(success=True, message=message)
