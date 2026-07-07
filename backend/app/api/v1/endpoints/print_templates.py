"""
API endpoints для управления шаблонами печати
Основа: passport.md стр. 1925-2063, detail.md стр. 3721-3888
"""

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from jinja2 import Environment, TemplateError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import print_config as crud_print
from app.models.user import User
from app.schemas.print_config import (
    PrintJobOut,
    PrintTemplateCreate,
    PrintTemplateOut,
    PrintTemplateUpdate,
)

router = APIRouter()

# Путь к шаблонам
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates" / "print"
MAX_PRINT_TEMPLATE_UPLOAD_BYTES = 5 * 1024 * 1024
PRINT_TEMPLATE_READ_CHUNK_BYTES = 1024 * 1024


def _read_print_template_bounded(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = file.file.read(PRINT_TEMPLATE_READ_CHUNK_BYTES)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > MAX_PRINT_TEMPLATE_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Print template upload is too large "
                    f"(maximum {MAX_PRINT_TEMPLATE_UPLOAD_BYTES // 1024 // 1024} MB)"
                ),
            )
        chunks.append(chunk)

    return b"".join(chunks)


def _safe_template_type(value: str) -> str:
    if value == "ticket":
        return "ticket"
    if value == "prescription":
        return "prescription"
    if value == "medical_certificate":
        return "medical_certificate"
    if value == "payment_receipt":
        return "payment_receipt"
    if value == "lab_results":
        return "lab_results"
    if value == "appointment_reminder":
        return "appointment_reminder"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid template_type",
    )


def _safe_template_language(value: str) -> str:
    if value == "ru":
        return "ru"
    if value == "uz":
        return "uz"
    if value == "en":
        return "en"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid language",
    )


def _template_filename(template_type: str, language: str | None = None) -> str:
    safe_template_type = _safe_template_type(template_type)
    if language is None:
        return f"{safe_template_type}.j2"

    safe_language = _safe_template_language(language)
    return f"{safe_template_type}_{safe_language}.j2"


def _template_path(filename: str) -> Path:
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template path",
        )

    root = TEMPLATES_DIR.resolve()
    candidate = (TEMPLATES_DIR / safe_filename).resolve()
    if candidate.parent != root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template path",
        )
    return candidate

# ===================== УПРАВЛЕНИЕ ШАБЛОНАМИ =====================


@router.get("/templates", response_model=list[PrintTemplateOut])
def get_print_templates(
    template_type: str | None = None,
    language: str | None = None,
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
            detail="Internal server error",
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
            env = Environment(autoescape=True)
            env.from_string(template_data.template_content)
        except TemplateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Internal server error",
            )

        template = crud_print.create_print_template(db, template_data)

        return template

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/templates/types")
def get_template_types(
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    return _print_template_types_payload()


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
                env = Environment(autoescape=True)
                env.from_string(template_data.template_content)
            except TemplateError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Internal server error",
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
            detail="Internal server error",
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
        filename = _template_filename(template_type, language)
        file_path = _template_path(filename)

        # Сохраняем файл
        content = _read_print_template_bounded(file)

        # Валидируем шаблон
        try:
            env = Environment(autoescape=True)
            env.from_string(content.decode('utf-8'))
        except TemplateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Internal server error",
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
            detail="Internal server error",
        )


# ===================== ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР =====================


@router.post("/templates/{template_id}/preview")
def preview_template(
    template_id: int,
    preview_data: dict[str, Any],
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
        env = Environment(autoescape=True)
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
            detail="Internal server error",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
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
        filename = _template_filename(template_type, language)
        file_path = _template_path(filename)

        # Если файл не найден, пробуем базовый шаблон
        if not file_path.exists():
            filename = _template_filename(template_type)
            file_path = _template_path(filename)

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Стандартный шаблон '{template_type}' не найден",
            )

        with open(file_path, encoding='utf-8') as f:
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
            detail="Internal server error",
        )


def _print_template_types_payload():
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


@router.get("/jobs", response_model=list[PrintJobOut])
def get_print_jobs(
    status_filter: str | None = None,
    document_type: str | None = None,
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
            detail="Internal server error",
        )
