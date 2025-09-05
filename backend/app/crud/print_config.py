"""
CRUD операции для системы печати
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from datetime import datetime, timedelta

from app.models.print_config import PrinterConfig, PrintTemplate, PrintJob
from app.schemas.print_config import (
    PrinterConfigCreate, PrinterConfigUpdate,
    PrintTemplateCreate, PrintTemplateUpdate
)


# ===================== ПРИНТЕРЫ =====================

def get_printers(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    active_only: bool = False,
    printer_type: Optional[str] = None
) -> List[PrinterConfig]:
    """Получить список принтеров"""
    query = db.query(PrinterConfig)
    
    if active_only:
        query = query.filter(PrinterConfig.active == True)
    if printer_type:
        query = query.filter(PrinterConfig.printer_type == printer_type)
    
    return query.offset(skip).limit(limit).all()


def get_printer_by_id(db: Session, printer_id: int) -> Optional[PrinterConfig]:
    """Получить принтер по ID"""
    return db.query(PrinterConfig).filter(PrinterConfig.id == printer_id).first()


def get_printer_by_name(db: Session, name: str) -> Optional[PrinterConfig]:
    """Получить принтер по имени"""
    return db.query(PrinterConfig).filter(PrinterConfig.name == name).first()


def get_default_printer(db: Session, printer_type: Optional[str] = None) -> Optional[PrinterConfig]:
    """Получить принтер по умолчанию"""
    query = db.query(PrinterConfig).filter(
        and_(PrinterConfig.is_default == True, PrinterConfig.active == True)
    )
    
    if printer_type:
        query = query.filter(PrinterConfig.printer_type == printer_type)
    
    return query.first()


def create_printer(db: Session, printer: PrinterConfigCreate) -> PrinterConfig:
    """Создать принтер"""
    # Если это первый активный принтер данного типа, делаем его по умолчанию
    if printer.active and not get_default_printer(db, printer.printer_type):
        printer.is_default = True
    
    # Если делаем принтер по умолчанию, убираем флаг у других того же типа
    if printer.is_default:
        db.query(PrinterConfig).filter(
            and_(
                PrinterConfig.printer_type == printer.printer_type,
                PrinterConfig.is_default == True
            )
        ).update({"is_default": False})
    
    db_printer = PrinterConfig(**printer.model_dump())
    db.add(db_printer)
    db.commit()
    db.refresh(db_printer)
    return db_printer


def update_printer(db: Session, printer_id: int, printer: PrinterConfigUpdate) -> Optional[PrinterConfig]:
    """Обновить принтер"""
    db_printer = get_printer_by_id(db, printer_id)
    if not db_printer:
        return None
    
    update_data = printer.model_dump(exclude_unset=True)
    
    # Если делаем принтер по умолчанию, убираем флаг у других того же типа
    if update_data.get("is_default"):
        db.query(PrinterConfig).filter(
            and_(
                PrinterConfig.printer_type == db_printer.printer_type,
                PrinterConfig.id != printer_id
            )
        ).update({"is_default": False})
    
    for field, value in update_data.items():
        setattr(db_printer, field, value)
    
    db.commit()
    db.refresh(db_printer)
    return db_printer


def delete_printer(db: Session, printer_id: int) -> bool:
    """Удалить принтер"""
    db_printer = get_printer_by_id(db, printer_id)
    if not db_printer:
        return False
    
    # Если это принтер по умолчанию, назначаем другой
    if db_printer.is_default:
        other_printer = db.query(PrinterConfig).filter(
            and_(
                PrinterConfig.printer_type == db_printer.printer_type,
                PrinterConfig.id != printer_id,
                PrinterConfig.active == True
            )
        ).first()
        if other_printer:
            other_printer.is_default = True
    
    db_printer.active = False
    db.commit()
    return True


# ===================== ШАБЛОНЫ ПЕЧАТИ =====================

def get_print_templates(
    db: Session,
    printer_id: Optional[int] = None,
    template_type: Optional[str] = None,
    language: str = "ru",
    active_only: bool = True
) -> List[PrintTemplate]:
    """Получить шаблоны печати"""
    query = db.query(PrintTemplate)
    
    if printer_id:
        query = query.filter(PrintTemplate.printer_id == printer_id)
    if template_type:
        query = query.filter(PrintTemplate.template_type == template_type)
    if language:
        query = query.filter(PrintTemplate.language == language)
    if active_only:
        query = query.filter(PrintTemplate.active == True)
    
    return query.all()


def get_print_template_by_id(db: Session, template_id: int) -> Optional[PrintTemplate]:
    """Получить шаблон по ID"""
    return db.query(PrintTemplate).filter(PrintTemplate.id == template_id).first()


def create_print_template(db: Session, template: PrintTemplateCreate) -> PrintTemplate:
    """Создать шаблон печати"""
    db_template = PrintTemplate(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


def update_print_template(
    db: Session, 
    template_id: int, 
    template: PrintTemplateUpdate
) -> Optional[PrintTemplate]:
    """Обновить шаблон печати"""
    db_template = get_print_template_by_id(db, template_id)
    if not db_template:
        return None
    
    for field, value in template.model_dump(exclude_unset=True).items():
        setattr(db_template, field, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template


def delete_print_template(db: Session, template_id: int) -> bool:
    """Удалить шаблон печати"""
    db_template = get_print_template_by_id(db, template_id)
    if not db_template:
        return False
    
    db_template.active = False
    db.commit()
    return True


# ===================== ЗАДАНИЯ ПЕЧАТИ =====================

def create_print_job(
    db: Session,
    user_id: Optional[int],
    printer_id: int,
    document_type: str,
    print_data: Dict[str, Any],
    template_id: Optional[int] = None,
    document_id: Optional[str] = None
) -> PrintJob:
    """Создать задание печати"""
    job = PrintJob(
        user_id=user_id,
        printer_id=printer_id,
        template_id=template_id,
        document_type=document_type,
        document_id=document_id,
        print_data=print_data,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_print_job_status(
    db: Session,
    job_id: int,
    status: str,
    error_message: Optional[str] = None
) -> Optional[PrintJob]:
    """Обновить статус задания печати"""
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        return None
    
    job.status = status
    if error_message:
        job.error_message = error_message
    if status in ["completed", "failed"]:
        job.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(job)
    return job


def get_print_jobs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    printer_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> List[PrintJob]:
    """Получить задания печати"""
    query = db.query(PrintJob)
    
    if status:
        query = query.filter(PrintJob.status == status)
    if printer_id:
        query = query.filter(PrintJob.printer_id == printer_id)
    if user_id:
        query = query.filter(PrintJob.user_id == user_id)
    
    return query.order_by(desc(PrintJob.created_at)).offset(skip).limit(limit).all()


# ===================== СТАТИСТИКА =====================

def get_print_stats(
    db: Session,
    days_back: int = 30,
    printer_id: Optional[int] = None
) -> Dict[str, Any]:
    """Получить статистику печати"""
    start_date = datetime.utcnow() - timedelta(days=days_back)
    
    query = db.query(PrintJob).filter(PrintJob.created_at >= start_date)
    
    if printer_id:
        query = query.filter(PrintJob.printer_id == printer_id)
    
    jobs = query.all()
    
    total_jobs = len(jobs)
    successful_jobs = len([j for j in jobs if j.status == "completed"])
    failed_jobs = len([j for j in jobs if j.status == "failed"])
    pending_jobs = len([j for j in jobs if j.status == "pending"])
    
    # Статистика по типам документов
    by_document_type = {}
    for job in jobs:
        doc_type = job.document_type
        if doc_type not in by_document_type:
            by_document_type[doc_type] = {"total": 0, "successful": 0, "failed": 0}
        
        by_document_type[doc_type]["total"] += 1
        if job.status == "completed":
            by_document_type[doc_type]["successful"] += 1
        elif job.status == "failed":
            by_document_type[doc_type]["failed"] += 1
    
    # Статистика по принтерам
    by_printer = {}
    for job in jobs:
        printer_name = job.printer.name if job.printer else "unknown"
        if printer_name not in by_printer:
            by_printer[printer_name] = {"total": 0, "successful": 0, "failed": 0}
        
        by_printer[printer_name]["total"] += 1
        if job.status == "completed":
            by_printer[printer_name]["successful"] += 1
        elif job.status == "failed":
            by_printer[printer_name]["failed"] += 1
    
    return {
        "total_jobs": total_jobs,
        "successful_jobs": successful_jobs,
        "failed_jobs": failed_jobs,
        "pending_jobs": pending_jobs,
        "by_document_type": by_document_type,
        "by_printer": by_printer,
        "period_start": start_date,
        "period_end": datetime.utcnow()
    }


# ===================== НАСТРОЙКИ СИСТЕМЫ =====================

def get_print_system_settings(db: Session) -> Dict[str, Any]:
    """Получить настройки системы печати"""
    from app.crud.clinic import get_settings_by_category
    
    print_settings = get_settings_by_category(db, "print")
    
    result = {
        "enabled": True,
        "default_language": "ru",
        "auto_print_tickets": True,
        "auto_print_receipts": True,
        "print_quality": "normal",
        "color_printing": False,
        "backup_failed_jobs": True,
        "retry_failed_jobs": True,
        "max_retries": 3
    }
    
    # Применяем сохраненные настройки
    for setting in print_settings:
        if setting.key in result:
            result[setting.key] = setting.value
    
    return result


def update_print_system_settings(db: Session, settings: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Обновить настройки системы печати"""
    from app.crud.clinic import update_settings_batch
    
    # Сохраняем настройки в категории "print"
    update_settings_batch(db, "print", settings, user_id)
    
    return get_print_system_settings(db)
