"""
CRUD операции для системы печати
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.print_config import PrinterConfig, PrintJob, PrintTemplate
from app.schemas.print_config import (
    PrinterConfigCreate,
    PrinterConfigUpdate,
    PrintJobCreate,
    PrintJobUpdate,
    PrintTemplateCreate,
    PrintTemplateUpdate,
)

# ===================== ПРИНТЕРЫ =====================


def get_printer_config(db: Session, printer_id: int) -> Optional[PrinterConfig]:
    """Получить конфигурацию принтера по ID"""
    return db.query(PrinterConfig).filter(PrinterConfig.id == printer_id).first()


def get_printer_by_name(db: Session, name: str) -> Optional[PrinterConfig]:
    """Получить принтер по имени"""
    return db.query(PrinterConfig).filter(PrinterConfig.name == name).first()


def get_printer_configs(
    db: Session, skip: int = 0, limit: int = 100, active_only: bool = False
) -> List[PrinterConfig]:
    """Получить список принтеров"""
    query = db.query(PrinterConfig)

    if active_only:
        query = query.filter(PrinterConfig.active == True)

    return query.offset(skip).limit(limit).all()


def create_printer_config(
    db: Session, printer_data: PrinterConfigCreate
) -> PrinterConfig:
    """Создать конфигурацию принтера"""
    db_printer = PrinterConfig(**printer_data.dict())
    db.add(db_printer)
    db.commit()
    db.refresh(db_printer)
    return db_printer


def update_printer_config(
    db: Session, printer_id: int, printer_data: PrinterConfigUpdate
) -> Optional[PrinterConfig]:
    """Обновить конфигурацию принтера"""
    db_printer = get_printer_config(db, printer_id)
    if not db_printer:
        return None

    update_data = printer_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_printer, field, value)

    db.commit()
    db.refresh(db_printer)
    return db_printer


def delete_printer_config(db: Session, printer_id: int) -> bool:
    """Удалить конфигурацию принтера"""
    db_printer = get_printer_config(db, printer_id)
    if not db_printer:
        return False

    db.delete(db_printer)
    db.commit()
    return True


def get_default_printer_for_type(
    db: Session, document_type: str
) -> Optional[PrinterConfig]:
    """Получить принтер по умолчанию для типа документа"""
    # Пока возвращаем первый активный принтер
    # В будущем можно добавить логику сопоставления типов документов и принтеров
    return (
        db.query(PrinterConfig)
        .filter(and_(PrinterConfig.active == True, PrinterConfig.is_default == True))
        .first()
    )


# ===================== ШАБЛОНЫ =====================


def get_print_template(db: Session, template_id: int) -> Optional[PrintTemplate]:
    """Получить шаблон по ID"""
    return db.query(PrintTemplate).filter(PrintTemplate.id == template_id).first()


def get_print_templates(
    db: Session,
    template_type: Optional[str] = None,
    language: Optional[str] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> List[PrintTemplate]:
    """Получить список шаблонов"""
    query = db.query(PrintTemplate)

    if template_type:
        query = query.filter(PrintTemplate.template_type == template_type)

    if language:
        query = query.filter(PrintTemplate.language == language)

    if active_only:
        query = query.filter(PrintTemplate.active == True)

    return query.offset(skip).limit(limit).all()


def create_print_template(
    db: Session, template_data: PrintTemplateCreate
) -> PrintTemplate:
    """Создать шаблон печати"""
    db_template = PrintTemplate(**template_data.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


def update_print_template(
    db: Session, template_id: int, template_data: PrintTemplateUpdate
) -> Optional[PrintTemplate]:
    """Обновить шаблон печати"""
    db_template = get_print_template(db, template_id)
    if not db_template:
        return None

    update_data = template_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_template, field, value)

    db.commit()
    db.refresh(db_template)
    return db_template


def delete_print_template(db: Session, template_id: int) -> bool:
    """Удалить шаблон печати"""
    db_template = get_print_template(db, template_id)
    if not db_template:
        return False

    db.delete(db_template)
    db.commit()
    return True


def get_template_by_type_and_printer(
    db: Session, template_type: str, printer_id: int
) -> Optional[PrintTemplate]:
    """Получить шаблон по типу и принтеру"""
    # Сначала ищем шаблон для конкретного принтера
    template = (
        db.query(PrintTemplate)
        .filter(
            and_(
                PrintTemplate.template_type == template_type,
                PrintTemplate.printer_id == printer_id,
                PrintTemplate.active == True,
            )
        )
        .first()
    )

    # Если не найден, ищем любой активный шаблон этого типа
    if not template:
        template = (
            db.query(PrintTemplate)
            .filter(
                and_(
                    PrintTemplate.template_type == template_type,
                    PrintTemplate.active == True,
                )
            )
            .first()
        )

    return template


# ===================== ЗАДАНИЯ ПЕЧАТИ =====================


def get_print_job(db: Session, job_id: int) -> Optional[PrintJob]:
    """Получить задание печати по ID"""
    return db.query(PrintJob).filter(PrintJob.id == job_id).first()


def get_print_jobs(
    db: Session,
    status_filter: Optional[str] = None,
    document_type: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[PrintJob]:
    """Получить список заданий печати"""
    query = db.query(PrintJob)

    if status_filter:
        query = query.filter(PrintJob.status == status_filter)

    if document_type:
        query = query.filter(PrintJob.document_type == document_type)

    if user_id:
        query = query.filter(PrintJob.user_id == user_id)

    return query.order_by(PrintJob.created_at.desc()).offset(skip).limit(limit).all()


def create_print_job(db: Session, job_data: Dict[str, Any]) -> PrintJob:
    """Создать задание печати"""
    db_job = PrintJob(**job_data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def update_print_job(
    db: Session, job_id: int, job_data: Dict[str, Any]
) -> Optional[PrintJob]:
    """Обновить задание печати"""
    db_job = get_print_job(db, job_id)
    if not db_job:
        return None

    for field, value in job_data.items():
        if hasattr(db_job, field):
            setattr(db_job, field, value)

    db.commit()
    db.refresh(db_job)
    return db_job
