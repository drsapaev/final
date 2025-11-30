"""
CRUD операции для работы с визитами
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.service_mapping import normalize_service_code


def get_visit(db: Session, visit_id: int) -> Optional[Visit]:
    """Получить визит по ID"""
    return db.query(Visit).filter(Visit.id == visit_id).first()


def get_visits_by_patient(
    db: Session, patient_id: int, limit: int = 100, status: Optional[str] = None
) -> List[Visit]:
    """Получить визиты пациента"""
    query = db.query(Visit).filter(Visit.patient_id == patient_id)

    if status:
        query = query.filter(Visit.status == status)

    return query.order_by(desc(Visit.created_at)).limit(limit).all()


def get_visits_by_doctor(
    db: Session,
    doctor_id: int,
    visit_date: Optional[date] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Visit]:
    """Получить визиты врача"""
    query = db.query(Visit).filter(Visit.doctor_id == doctor_id)

    if visit_date:
        query = query.filter(Visit.visit_date == visit_date)

    if status:
        query = query.filter(Visit.status == status)

    return (
        query.order_by(desc(Visit.visit_date), desc(Visit.visit_time))
        .limit(limit)
        .all()
    )


def get_today_visits_by_doctor(db: Session, doctor_id: int) -> List[Visit]:
    """Получить сегодняшние визиты врача"""
    return get_visits_by_doctor(
        db=db, doctor_id=doctor_id, visit_date=date.today(), status="open"
    )


def create_visit(
    db: Session,
    patient_id: int,
    doctor_id: Optional[int] = None,
    visit_date: Optional[date] = None,
    visit_time: Optional[str] = None,
    department: Optional[str] = None,
    discount_mode: str = "none",
    notes: Optional[str] = None,
    services: Optional[List[Dict[str, Any]]] = None,
    # Параметры для side-effects (безопасность при миграции)
    auto_status: bool = True,
    notify: bool = False,
    log: bool = True,
    # Дополнительные поля для совместимости
    status: Optional[str] = None,
    approval_status: Optional[str] = None,
    confirmed_at: Optional[datetime] = None,
    confirmed_by: Optional[str] = None,
) -> Visit:
    """
    Создать новый визит - единая функция для всего проекта.

    Args:
        db: Сессия базы данных
        patient_id: ID пациента
        doctor_id: ID врача (опционально)
        visit_date: Дата визита (по умолчанию сегодня)
        visit_time: Время визита в формате HH:MM
        department: Отделение
        discount_mode: Режим скидки (none|repeat|benefit|all_free)
        notes: Примечания
        services: Список услуг (опционально)
        auto_status: Автоматически устанавливать статус "open" (для обратной совместимости)
        notify: Отправлять уведомления (для будущего использования)
        log: Логировать создание визита (для будущего использования)

    Returns:
        Созданный Visit
    """
    # Нормализуем данные визита
    visit_data = normalize_visit_payload(
        {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "visit_date": visit_date,
            "visit_time": visit_time,
            "department": department,
            "discount_mode": discount_mode,
            "notes": notes,
        }
    )

    # Валидируем время визита
    if not validate_visit_time(visit_data["visit_date"], visit_data.get("visit_time")):
        raise ValueError("Некорректная дата или время визита")

    # Создаем визит
    # ⚠️ ИСПРАВЛЕНИЕ: department - это relationship, нужно использовать department_id
    # Если передан department как строка (key), найдем соответствующий department_id
    department_id_value = None
    if visit_data.get("department"):
        dept_key = visit_data.get("department")
        # Если это число, используем как department_id
        if isinstance(dept_key, int):
            department_id_value = dept_key
        # Если это строка (key), ищем department по key
        elif isinstance(dept_key, str):
            from app.models.department import Department

            dept = db.query(Department).filter(Department.key == dept_key).first()
            if dept:
                department_id_value = dept.id

    visit = Visit(
        patient_id=visit_data["patient_id"],
        doctor_id=visit_data.get("doctor_id"),
        visit_date=visit_data["visit_date"],
        visit_time=visit_data.get("visit_time"),
        department=visit_data.get(
            "department"
        ),  # ✅ ДОБАВЛЕНО: строковое поле department
        department_id=department_id_value,  # ✅ ИСПРАВЛЕНО: используем department_id
        discount_mode=visit_data.get("discount_mode", "none"),
        notes=visit_data.get("notes"),
        status=status or ("open" if auto_status else "pending"),
        approval_status=approval_status,
        confirmed_at=confirmed_at,
        confirmed_by=confirmed_by,
    )

    db.add(visit)
    db.flush()  # Получаем ID визита

    # Добавляем услуги, если переданы
    if services:
        for service_data in services:
            visit_service = VisitService(
                visit_id=visit.id,
                service_id=service_data.get("service_id") or service_data.get("id"),
                qty=service_data.get("quantity", service_data.get("qty", 1)),
                price=service_data.get("price", 0),
                code=(
                    normalize_service_code(service_data.get("code"))
                    if service_data.get("code")
                    else None
                ),
                name=service_data.get("name", ""),
            )
            db.add(visit_service)

    # Логирование
    if log:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            "Создан визит ID=%d для пациента %d, врач=%s, дата=%s, услуг=%d",
            visit.id,
            visit.patient_id,
            visit.doctor_id,
            visit.visit_date,
            len(services) if services else 0,
        )

    # Уведомления (для будущего использования)
    if notify:
        # Здесь можно добавить отправку уведомлений
        pass

    db.commit()
    db.refresh(visit)
    return visit


def update_visit(db: Session, visit_id: int, **kwargs) -> Optional[Visit]:
    """Обновить визит"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        return None

    for key, value in kwargs.items():
        if hasattr(visit, key):
            setattr(visit, key, value)

    db.commit()
    db.refresh(visit)
    return visit


def complete_visit(
    db: Session, visit_id: int, medical_data: Optional[Dict[str, Any]] = None
) -> Optional[Visit]:
    """Завершить визит"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        return None

    visit.status = "closed"

    if medical_data:
        # Добавляем медицинские данные в заметки
        notes = visit.notes or ""

        if "diagnosis" in medical_data:
            notes += f"\nДиагноз: {medical_data['diagnosis']}"
        if "treatment" in medical_data:
            notes += f"\nЛечение: {medical_data['treatment']}"
        if "recommendations" in medical_data:
            notes += f"\nРекомендации: {medical_data['recommendations']}"
        if "next_visit" in medical_data:
            notes += f"\nСледующий визит: {medical_data['next_visit']}"

        visit.notes = notes

    visit.notes = (
        visit.notes or ""
    ) + f"\nПрием завершен в {datetime.now().strftime('%H:%M')}"

    db.commit()
    db.refresh(visit)
    return visit


def cancel_visit(
    db: Session, visit_id: int, reason: Optional[str] = None
) -> Optional[Visit]:
    """Отменить визит"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()

    if not visit:
        return None

    visit.status = "canceled"

    if reason:
        visit.notes = (visit.notes or "") + f"\nОтменен: {reason}"

    db.commit()
    db.refresh(visit)
    return visit


def get_visit_services(db: Session, visit_id: int) -> List[VisitService]:
    """Получить услуги визита"""
    return db.query(VisitService).filter(VisitService.visit_id == visit_id).all()


def add_visit_service(
    db: Session,
    visit_id: int,
    service_id: int,
    quantity: int = 1,
    custom_price: Optional[float] = None,
) -> VisitService:
    """Добавить услугу к визиту"""
    # Получаем цену услуги
    service = db.query(Service).filter(Service.id == service_id).first()
    price = (
        custom_price if custom_price is not None else (service.price if service else 0)
    )

    # Получаем и нормализуем код услуги
    service_code = None
    if service and hasattr(service, 'code') and service.code:
        service_code = normalize_service_code(service.code)
    elif service and hasattr(service, 'service_code') and service.service_code:
        service_code = normalize_service_code(service.service_code)

    visit_service = VisitService(
        visit_id=visit_id,
        service_id=service_id,
        quantity=quantity,
        price=price,
        custom_price=custom_price,
        code=service_code,
        name=service.name if service else "",
    )

    db.add(visit_service)
    db.commit()
    db.refresh(visit_service)
    return visit_service


def remove_visit_service(db: Session, visit_service_id: int) -> bool:
    """Удалить услугу из визита"""
    visit_service = (
        db.query(VisitService).filter(VisitService.id == visit_service_id).first()
    )

    if not visit_service:
        return False

    db.delete(visit_service)
    db.commit()
    return True


def get_visits_by_date_range(
    db: Session,
    date_from: date,
    date_to: date,
    doctor_id: Optional[int] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Visit]:
    """Получить визиты за период"""
    query = db.query(Visit).filter(
        and_(Visit.visit_date >= date_from, Visit.visit_date <= date_to)
    )

    if doctor_id:
        query = query.filter(Visit.doctor_id == doctor_id)

    if department:
        query = query.filter(Visit.department == department)

    if status:
        query = query.filter(Visit.status == status)

    return query.order_by(desc(Visit.visit_date), desc(Visit.visit_time)).all()


def get_visit_statistics(
    db: Session,
    doctor_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    """Получить статистику визитов"""
    query = db.query(Visit)

    if doctor_id:
        query = query.filter(Visit.doctor_id == doctor_id)

    if date_from:
        query = query.filter(Visit.visit_date >= date_from)

    if date_to:
        query = query.filter(Visit.visit_date <= date_to)

    total_visits = query.count()
    completed_visits = query.filter(Visit.status == "closed").count()
    canceled_visits = query.filter(Visit.status == "canceled").count()
    open_visits = query.filter(Visit.status == "open").count()

    return {
        "total_visits": total_visits,
        "completed_visits": completed_visits,
        "canceled_visits": canceled_visits,
        "open_visits": open_visits,
        "completion_rate": round(
            (completed_visits / total_visits * 100) if total_visits > 0 else 0, 2
        ),
    }


def find_or_create_today_visit(
    db: Session, patient_id: int, doctor_id: int, department: Optional[str] = None
) -> Visit:
    """Найти или создать визит на сегодня"""
    # Ищем открытый визит на сегодня
    visit = (
        db.query(Visit)
        .filter(
            and_(
                Visit.patient_id == patient_id,
                Visit.visit_date == date.today(),
                Visit.status == "open",
            )
        )
        .first()
    )

    if not visit:
        # Создаем новый визит
        visit = create_visit(
            db=db,
            patient_id=patient_id,
            doctor_id=doctor_id,
            visit_date=date.today(),
            visit_time=datetime.now().strftime("%H:%M"),
            department=department,
        )

    return visit


# ===================== ЕДИНЫЕ ФУНКЦИИ - SINGLE SOURCE OF TRUTH =====================


def normalize_visit_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализация данных визита - единая функция для всего проекта.

    Приводит данные визита к единому формату, устанавливает значения по умолчанию.

    Args:
        payload: Словарь с данными визита

    Returns:
        Нормализованный словарь с данными визита
    """
    normalized = {}

    # Обязательные поля
    if "patient_id" not in payload:
        raise ValueError("patient_id обязателен для создания визита")
    normalized["patient_id"] = payload["patient_id"]

    # Опциональные поля с значениями по умолчанию
    normalized["doctor_id"] = payload.get("doctor_id")
    normalized["visit_date"] = payload.get("visit_date") or date.today()
    normalized["visit_time"] = payload.get("visit_time")
    normalized["department"] = payload.get("department")
    normalized["discount_mode"] = payload.get("discount_mode", "none")
    normalized["notes"] = payload.get("notes")

    # Дополнительные поля (если есть)
    if "status" in payload:
        normalized["status"] = payload["status"]
    if "approval_status" in payload:
        normalized["approval_status"] = payload["approval_status"]
    if "confirmation_token" in payload:
        normalized["confirmation_token"] = payload["confirmation_token"]

    return normalized


def validate_visit_time(visit_date: date, visit_time: Optional[str] = None) -> bool:
    """
    Валидация даты и времени визита.

    Args:
        visit_date: Дата визита
        visit_time: Время визита в формате HH:MM (опционально)

    Returns:
        True если дата и время валидны, False если нет
    """
    if not visit_date:
        return False

    today = date.today()

    # Дата не должна быть слишком старой (более 1 года назад)
    min_date = date(today.year - 1, 1, 1)
    if visit_date < min_date:
        return False

    # Дата не должна быть слишком далекой в будущем (более 1 года вперед)
    max_date = date(today.year + 1, 12, 31)
    if visit_date > max_date:
        return False

    # Валидация времени (если указано)
    if visit_time:
        try:
            # Проверяем формат HH:MM
            parts = visit_time.split(":")
            if len(parts) != 2:
                return False

            hour = int(parts[0])
            minute = int(parts[1])

            if hour < 0 or hour > 23:
                return False
            if minute < 0 or minute > 59:
                return False
        except (ValueError, AttributeError):
            return False

    return True


def get_visit_history(db: Session, patient_id: int, limit: int = 100) -> List[Visit]:
    """
    Получить историю визитов пациента - единая функция для всего проекта.

    Args:
        db: Сессия базы данных
        patient_id: ID пациента
        limit: Максимальное количество визитов

    Returns:
        Список визитов пациента, отсортированный по дате (от новых к старым)
    """
    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(desc(Visit.visit_date), desc(Visit.created_at))
        .limit(limit)
        .all()
    )
