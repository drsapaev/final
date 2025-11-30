"""
CRUD операции для лабораторных результатов
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.lab import LabOrder, LabResult
from app.schemas.lab import LabResultCreate, LabResultUpdate


def get_lab_result(db: Session, result_id: int) -> Optional[LabResult]:
    """Получить лабораторный результат по ID"""
    return db.query(LabResult).filter(LabResult.id == result_id).first()


def get_lab_results_by_order(db: Session, order_id: int) -> List[LabResult]:
    """Получить все результаты по заказу"""
    return db.query(LabResult).filter(LabResult.order_id == order_id).all()


def get_lab_results_by_patient(
    db: Session,
    patient_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[LabResult]:
    """Получить результаты пациента"""
    query = db.query(LabResult).join(LabOrder).filter(LabOrder.patient_id == patient_id)

    if date_from:
        query = query.filter(LabResult.created_at >= date_from)
    if date_to:
        query = query.filter(LabResult.created_at <= date_to)

    return query.all()


def create_lab_result(db: Session, result_data: LabResultCreate) -> LabResult:
    """Создать новый лабораторный результат"""
    db_result = LabResult(**result_data.dict())
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def update_lab_result(
    db: Session, result_id: int, result_data: LabResultUpdate
) -> Optional[LabResult]:
    """Обновить лабораторный результат"""
    db_result = get_lab_result(db, result_id)
    if not db_result:
        return None

    for field, value in result_data.dict(exclude_unset=True).items():
        setattr(db_result, field, value)

    db.commit()
    db.refresh(db_result)
    return db_result


def delete_lab_result(db: Session, result_id: int) -> bool:
    """Удалить лабораторный результат"""
    db_result = get_lab_result(db, result_id)
    if not db_result:
        return False

    db.delete(db_result)
    db.commit()
    return True


def get_abnormal_results(
    db: Session,
    patient_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[LabResult]:
    """Получить аномальные результаты"""
    query = db.query(LabResult).filter(LabResult.abnormal == True)

    if patient_id:
        query = query.join(LabOrder).filter(LabOrder.patient_id == patient_id)

    if date_from:
        query = query.filter(LabResult.created_at >= date_from)
    if date_to:
        query = query.filter(LabResult.created_at <= date_to)

    return query.all()


def get_results_by_test_code(
    db: Session, test_code: str, patient_id: Optional[int] = None
) -> List[LabResult]:
    """Получить результаты по коду теста"""
    query = db.query(LabResult).filter(LabResult.test_code == test_code)

    if patient_id:
        query = query.join(LabOrder).filter(LabOrder.patient_id == patient_id)

    return query.all()
