"""
CRUD операции для работы с визитами
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.models.user import User


def get_visit(db: Session, visit_id: int) -> Optional[Visit]:
    """Получить визит по ID"""
    return db.query(Visit).filter(Visit.id == visit_id).first()


def get_visits_by_patient(
    db: Session, 
    patient_id: int, 
    limit: int = 100,
    status: Optional[str] = None
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
    limit: int = 100
) -> List[Visit]:
    """Получить визиты врача"""
    query = db.query(Visit).filter(Visit.doctor_id == doctor_id)
    
    if visit_date:
        query = query.filter(Visit.visit_date == visit_date)
    
    if status:
        query = query.filter(Visit.status == status)
    
    return query.order_by(desc(Visit.visit_date), desc(Visit.visit_time)).limit(limit).all()


def get_today_visits_by_doctor(db: Session, doctor_id: int) -> List[Visit]:
    """Получить сегодняшние визиты врача"""
    return get_visits_by_doctor(
        db=db,
        doctor_id=doctor_id,
        visit_date=date.today(),
        status="open"
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
    services: Optional[List[Dict[str, Any]]] = None
) -> Visit:
    """Создать новый визит"""
    visit = Visit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        visit_date=visit_date or date.today(),
        visit_time=visit_time,
        department=department,
        discount_mode=discount_mode,
        notes=notes,
        status="open"
    )
    
    db.add(visit)
    db.flush()  # Получаем ID визита
    
    # Добавляем услуги, если переданы
    if services:
        for service_data in services:
            visit_service = VisitService(
                visit_id=visit.id,
                service_id=service_data["service_id"],
                quantity=service_data.get("quantity", 1),
                price=service_data.get("price", 0),
                custom_price=service_data.get("custom_price")
            )
            db.add(visit_service)
    
    db.commit()
    db.refresh(visit)
    return visit


def update_visit(
    db: Session,
    visit_id: int,
    **kwargs
) -> Optional[Visit]:
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
    db: Session,
    visit_id: int,
    medical_data: Optional[Dict[str, Any]] = None
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
    
    visit.notes = (visit.notes or "") + f"\nПрием завершен в {datetime.now().strftime('%H:%M')}"
    
    db.commit()
    db.refresh(visit)
    return visit


def cancel_visit(db: Session, visit_id: int, reason: Optional[str] = None) -> Optional[Visit]:
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
    custom_price: Optional[float] = None
) -> VisitService:
    """Добавить услугу к визиту"""
    # Получаем цену услуги
    service = db.query(Service).filter(Service.id == service_id).first()
    price = custom_price if custom_price is not None else (service.price if service else 0)
    
    visit_service = VisitService(
        visit_id=visit_id,
        service_id=service_id,
        quantity=quantity,
        price=price,
        custom_price=custom_price
    )
    
    db.add(visit_service)
    db.commit()
    db.refresh(visit_service)
    return visit_service


def remove_visit_service(db: Session, visit_service_id: int) -> bool:
    """Удалить услугу из визита"""
    visit_service = db.query(VisitService).filter(VisitService.id == visit_service_id).first()
    
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
    status: Optional[str] = None
) -> List[Visit]:
    """Получить визиты за период"""
    query = db.query(Visit).filter(
        and_(
            Visit.visit_date >= date_from,
            Visit.visit_date <= date_to
        )
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
    date_to: Optional[date] = None
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
        "completion_rate": round((completed_visits / total_visits * 100) if total_visits > 0 else 0, 2)
    }


def find_or_create_today_visit(
    db: Session,
    patient_id: int,
    doctor_id: int,
    department: Optional[str] = None
) -> Visit:
    """Найти или создать визит на сегодня"""
    # Ищем открытый визит на сегодня
    visit = db.query(Visit).filter(
        and_(
            Visit.patient_id == patient_id,
            Visit.visit_date == date.today(),
            Visit.status == "open"
        )
    ).first()
    
    if not visit:
        # Создаем новый визит
        visit = create_visit(
            db=db,
            patient_id=patient_id,
            doctor_id=doctor_id,
            visit_date=date.today(),
            visit_time=datetime.now().strftime("%H:%M"),
            department=department
        )
    
    return visit