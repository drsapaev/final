"""
API endpoints для управления шаблонами печати
Основа: passport.md стр. 1925-2063, detail.md стр. 3721-3888
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from jinja2 import Environment, FileSystemLoader, TemplateError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import print_config as crud_print
from app.models.print_config import PrinterConfig, PrintJob, PrintTemplate
from app.models.user import User
from app.schemas.print_config import (
    PrintJobCreate,
    PrintJobOut,
    PrintTemplateCreate,
    PrintTemplateOut,
    PrintTemplateUpdate,
)

router = APIRouter()

# Путь к шаблонам
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "print"

# ===================== УПРАВЛЕНИЕ ШАБЛОНАМИ =====================


@router.get("/templates", response_model=List[PrintTemplateOut])
def get_print_templates(
    template_type: Optional[str] = None,
    language: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить список шаблонов печати
    """
    try:
        templates = crud_print.get_print_templates(
            db, template_type=template_type, language=language, active_only=active_only
        )

        return templates

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения шаблонов: {str(e)}",
        )


@router.post("/templates", response_model=PrintTemplateOut)
def create_print_template(
    template_data: PrintTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Создать новый шаблон печати
    """
    try:
        # Проверяем что принтер существует
        printer = crud_print.get_printer_config(db, template_data.printer_id)
        if not printer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Принтер не найден"
            )

        # Валидируем шаблон Jinja2
        try:
            env = Environment()
            env.from_string(template_data.template_content)
        except TemplateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка в шаблоне Jinja2: {str(e)}",
            )

        template = crud_print.create_print_template(db, template_data)

        return template

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания шаблона: {str(e)}",
        )


@router.get("/templates/{template_id}", response_model=PrintTemplateOut)
def get_print_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить шаблон печати по ID
    """
    template = crud_print.get_print_template(db, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден"
        )

    return template


@router.put("/templates/{template_id}", response_model=PrintTemplateOut)
def update_print_template(
    template_id: int,
    template_data: PrintTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Обновить шаблон печати
    """
    try:
        template = crud_print.get_print_template(db, template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден"
            )

        # Валидируем новый шаблон если он обновляется
        if template_data.template_content:
            try:
                env = Environment()
                env.from_string(template_data.template_content)
            except TemplateError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ошибка в шаблоне Jinja2: {str(e)}",
                )

        updated_template = crud_print.update_print_template(
            db, template_id, template_data
        )

        return updated_template

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления шаблона: {str(e)}",
        )


@router.delete("/templates/{template_id}")
def delete_print_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Удалить шаблон печати
    """
    template = crud_print.get_print_template(db, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден"
        )

    crud_print.delete_print_template(db, template_id)

    return {"message": "Шаблон удален"}


# ===================== ЗАГРУЗКА ФАЙЛОВ ШАБЛОНОВ =====================


@router.post("/templates/upload/{template_type}")
def upload_template_file(
    template_type: str,
    file: UploadFile = File(...),
    language: str = "ru",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Загрузить файл шаблона
    """
    try:
        # Проверяем тип файла
        if not file.filename.endswith(('.j2', '.jinja2', '.html')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Поддерживаются только файлы .j2, .jinja2, .html",
            )

        # Создаем директорию если не существует
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

        # Формируем имя файла
        filename = f"{template_type}_{language}.j2"
        file_path = TEMPLATES_DIR / filename

        # Сохраняем файл
        content = file.file.read()

        # Валидируем шаблон
        try:
            env = Environment()
            env.from_string(content.decode('utf-8'))
        except TemplateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка в шаблоне Jinja2: {str(e)}",
            )

        with open(file_path, 'wb') as f:
            f.write(content)

        return {
            "message": "Шаблон загружен успешно",
            "filename": filename,
            "path": str(file_path),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки шаблона: {str(e)}",
        )


# ===================== ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР =====================


@router.post("/templates/{template_id}/preview")
def preview_template(
    template_id: int,
    preview_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Предварительный просмотр шаблона с тестовыми данными
    """
    try:
        template = crud_print.get_print_template(db, template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон не найден"
            )

        # Рендерим шаблон с тестовыми данными
        env = Environment()
        jinja_template = env.from_string(template.template_content)

        rendered_content = jinja_template.render(**preview_data)

        return {
            "template_id": template_id,
            "template_name": template.name,
            "rendered_content": rendered_content,
            "template_type": template.template_type,
        }

    except TemplateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка рендеринга шаблона: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка предварительного просмотра: {str(e)}",
        )


# ===================== СТАНДАРТНЫЕ ШАБЛОНЫ =====================


@router.get("/templates/default/{template_type}")
def get_default_template(
    template_type: str,
    language: str = "ru",
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить стандартный шаблон по типу
    """
    try:
        filename = f"{template_type}_{language}.j2"
        file_path = TEMPLATES_DIR / filename

        # Если файл не найден, пробуем базовый шаблон
        if not file_path.exists():
            filename = f"{template_type}.j2"
            file_path = TEMPLATES_DIR / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Стандартный шаблон '{template_type}' не найден",
            )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            "template_type": template_type,
            "language": language,
            "filename": filename,
            "content": content,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения стандартного шаблона: {str(e)}",
        )


@router.get("/templates/types")
def get_template_types(
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """
    Получить список доступных типов шаблонов
    """
    return {
        "template_types": [
            {
                "code": "ticket",
                "name": "Талон очереди",
                "description": "Талон для пациентов в очереди",
                "formats": ["ESC/POS"],
            },
            {
                "code": "prescription",
                "name": "Рецепт",
                "description": "Медицинский рецепт",
                "formats": ["A5", "A4"],
            },
            {
                "code": "medical_certificate",
                "name": "Медицинская справка",
                "description": "Справка о состоянии здоровья",
                "formats": ["A4"],
            },
            {
                "code": "payment_receipt",
                "name": "Чек об оплате",
                "description": "Чек за медицинские услуги",
                "formats": ["ESC/POS", "A5"],
            },
            {
                "code": "lab_results",
                "name": "Результаты анализов",
                "description": "Лабораторные исследования",
                "formats": ["A4"],
            },
            {
                "code": "appointment_reminder",
                "name": "Напоминание о записи",
                "description": "Талон-напоминание",
                "formats": ["ESC/POS"],
            },
        ],
        "formats": [
            {
                "code": "ESC/POS",
                "name": "ESC/POS (Термопринтер)",
                "description": "58мм термопринтер",
                "paper_width": 58,
            },
            {
                "code": "A5",
                "name": "A5 (148×210мм)",
                "description": "Лазерный принтер A5",
                "paper_width": 148,
                "paper_height": 210,
            },
            {
                "code": "A4",
                "name": "A4 (210×297мм)",
                "description": "Лазерный принтер A4",
                "paper_width": 210,
                "paper_height": 297,
            },
        ],
    }


# ===================== ЗАДАНИЯ ПЕЧАТИ =====================


@router.get("/jobs", response_model=List[PrintJobOut])
def get_print_jobs(
    status_filter: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить список заданий печати
    """
    try:
        jobs = crud_print.get_print_jobs(
            db, status_filter=status_filter, document_type=document_type, limit=limit
        )

        return jobs

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения заданий печати: {str(e)}",
        )
