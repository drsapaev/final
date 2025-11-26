"""
API endpoints для шаблонов EMR
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.emr_template import (
    EMRTemplateCreate,
    EMRTemplateUpdate,
    EMRTemplateOut,
    EMRVersionOut,
    EMRTemplateStructure
)
from app.crud.emr_template import emr_template, emr_version
from app.services.emr_templates import EMRTemplateService

router = APIRouter()


@router.get("/templates", response_model=List[EMRTemplateOut])
async def get_emr_templates(
    specialty: Optional[str] = Query(None, description="Фильтр по специализации"),
    is_public: Optional[bool] = Query(None, description="Только публичные шаблоны"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить список шаблонов EMR"""
    try:
        if is_public:
            templates = emr_template.get_public_templates(db, specialty=specialty)
        elif specialty:
            templates = emr_template.get_by_specialty(db, specialty=specialty)
        else:
            templates = emr_template.get_multi(db)
        
        return templates
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения шаблонов: {str(e)}"
        )


@router.get("/templates/user", response_model=List[EMRTemplateOut])
async def get_user_templates(
    specialty: Optional[str] = Query(None, description="Фильтр по специализации"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить шаблоны пользователя"""
    try:
        templates = emr_template.get_user_templates(
            db, user_id=current_user.id, specialty=specialty
        )
        return templates
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения пользовательских шаблонов: {str(e)}"
        )


@router.post("/templates", response_model=EMRTemplateOut)
async def create_emr_template(
    template_data: EMRTemplateCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Создать новый шаблон EMR"""
    try:
        template_data.created_by = current_user.id
        template = emr_template.create(db, obj_in=template_data)
        return template
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка создания шаблона: {str(e)}"
        )


@router.post("/templates/from-structure", response_model=EMRTemplateOut)
async def create_template_from_structure(
    structure: EMRTemplateStructure,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Создать шаблон из структуры"""
    try:
        template = emr_template.create_from_structure(
            db, structure=structure.dict(), created_by=current_user.id
        )
        return template
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка создания шаблона из структуры: {str(e)}"
        )


@router.get("/templates/{template_id}", response_model=EMRTemplateOut)
async def get_emr_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить шаблон EMR по ID"""
    try:
        template = emr_template.get(db, id=template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        return template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения шаблона: {str(e)}"
        )


@router.put("/templates/{template_id}", response_model=EMRTemplateOut)
async def update_emr_template(
    template_id: int,
    template_update: EMRTemplateUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Обновить шаблон EMR"""
    try:
        template = emr_template.get(db, id=template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        
        # Проверяем права доступа
        if template.created_by != current_user.id and not current_user.role == "Admin":
            raise HTTPException(status_code=403, detail="Нет прав для редактирования")
        
        updated_template = emr_template.update(db, db_obj=template, obj_in=template_update)
        return updated_template
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обновления шаблона: {str(e)}"
        )


@router.post("/templates/{template_id}/clone", response_model=EMRTemplateOut)
async def clone_emr_template(
    template_id: int,
    new_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Клонировать шаблон EMR"""
    try:
        cloned_template = emr_template.clone_template(
            db, template_id=template_id, new_name=new_name, created_by=current_user.id
        )
        return cloned_template
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка клонирования шаблона: {str(e)}"
        )


@router.delete("/templates/{template_id}")
async def delete_emr_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Удалить шаблон EMR"""
    try:
        template = emr_template.get(db, id=template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        
        # Проверяем права доступа
        if template.created_by != current_user.id and not current_user.role == "Admin":
            raise HTTPException(status_code=403, detail="Нет прав для удаления")
        
        emr_template.remove(db, id=template_id)
        return {"message": "Шаблон успешно удален"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления шаблона: {str(e)}"
        )


@router.get("/templates/default/load")
async def load_default_templates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Загрузить предустановленные шаблоны"""
    try:
        if current_user.role != "Admin":
            raise HTTPException(status_code=403, detail="Только администраторы могут загружать шаблоны")
        
        default_templates = EMRTemplateService.get_default_templates()
        created_templates = []
        
        for template_structure in default_templates:
            template_data = EMRTemplateService.create_template_from_structure(template_structure)
            template_data["created_by"] = current_user.id
            template = emr_template.create(db, obj_in=EMRTemplateCreate(**template_data))
            created_templates.append(template)
        
        return {
            "message": f"Загружено {len(created_templates)} шаблонов",
            "templates": created_templates
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка загрузки шаблонов: {str(e)}"
        )


@router.get("/emr/{emr_id}/versions", response_model=List[EMRVersionOut])
async def get_emr_versions(
    emr_id: int,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить версии EMR"""
    try:
        versions = emr_version.get_by_emr(db, emr_id=emr_id, limit=limit)
        return versions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения версий: {str(e)}"
        )


@router.post("/emr/{emr_id}/versions/{version_id}/restore")
async def restore_emr_version(
    emr_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Восстановить версию EMR"""
    try:
        restored_version = emr_version.restore_version(
            db, version_id=version_id, restored_by=current_user.id
        )
        if not restored_version:
            raise HTTPException(status_code=404, detail="Версия не найдена")
        
        return {
            "message": "Версия успешно восстановлена",
            "version": restored_version
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка восстановления версии: {str(e)}"
        )
