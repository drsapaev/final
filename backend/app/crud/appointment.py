from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.appointment import Appointment
from app.models.enums import (
    AppointmentStatus,
    can_transition_status,
    normalize_appointment_status,
)
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


class CRUDAppointment(CRUDBase[Appointment, AppointmentCreate, AppointmentUpdate]):
    def get_appointments(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        department: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Appointment]:
        """
        Получить список записей с фильтрацией
        """
        query = db.query(self.model)

        if patient_id:
            query = query.filter(self.model.patient_id == patient_id)

        if doctor_id:
            query = query.filter(self.model.doctor_id == doctor_id)

        if department:
            query = query.filter(self.model.department == department)

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(self.model.appointment_date >= from_date)
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(self.model.appointment_date <= to_date)
            except ValueError:
                pass

        return (
            query.order_by(self.model.appointment_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def is_time_slot_occupied(
        self,
        db: Session,
        *,
        doctor_id: int,
        appointment_date: Union[str, date],
        appointment_time: str,
        exclude_appointment_id: Optional[int] = None,
    ) -> bool:
        """
        Проверить, занято ли время у врача
        """
        if isinstance(appointment_date, str):
            try:
                appointment_date = datetime.strptime(
                    appointment_date, "%Y-%m-%d"
                ).date()
            except ValueError:
                return False

        query = db.query(self.model).filter(
            and_(
                self.model.doctor_id == doctor_id,
                self.model.appointment_date == appointment_date,
                self.model.appointment_time == appointment_time,
                self.model.status != "cancelled",
            )
        )

        if exclude_appointment_id:
            query = query.filter(self.model.id != exclude_appointment_id)

        return query.first() is not None

    def get_doctor_schedule(
        self, db: Session, *, doctor_id: int, date: str
    ) -> List[Dict[str, Any]]:
        """
        Получить расписание врача на определенную дату
        """
        try:
            schedule_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return []

        appointments = (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doctor_id == doctor_id,
                    self.model.appointment_date == schedule_date,
                    self.model.status != "cancelled",
                )
            )
            .order_by(self.model.appointment_time)
            .all()
        )

        return [
            {
                "id": apt.id,
                "appointment_time": apt.appointment_time,
                "patient_id": apt.patient_id,
                "department": apt.department,
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ]

    def get_department_schedule(
        self, db: Session, *, department: str, date: str
    ) -> List[Dict[str, Any]]:
        """
        Получить расписание отделения на определенную дату
        """
        try:
            schedule_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return []

        appointments = (
            db.query(self.model)
            .filter(
                and_(
                    self.model.department == department,
                    self.model.appointment_date == schedule_date,
                    self.model.status != "cancelled",
                )
            )
            .order_by(self.model.appointment_time)
            .all()
        )

        return [
            {
                "id": apt.id,
                "appointment_time": apt.appointment_time,
                "patient_id": apt.patient_id,
                "doctor_id": apt.doctor_id,
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ]

    def get_upcoming_appointments(
        self, db: Session, *, patient_id: int, limit: int = 10
    ) -> List[Appointment]:
        """
        Получить предстоящие записи пациента
        """
        today = datetime.now().date()

        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.patient_id == patient_id,
                    self.model.appointment_date >= today,
                    self.model.status != "cancelled",
                )
            )
            .order_by(self.model.appointment_date, self.model.appointment_time)
            .limit(limit)
            .all()
        )

    def update_status(
        self,
        db: Session,
        *,
        appointment_id: int,
        new_status: str,
        validate_transition: bool = True,
    ) -> Optional[Appointment]:
        """
        Обновить статус записи с валидацией перехода
        """
        appointment = (
            db.query(self.model).filter(self.model.id == appointment_id).first()
        )
        if not appointment:
            return None

        current_status = normalize_appointment_status(appointment.status)
        new_status_normalized = normalize_appointment_status(new_status)

        if validate_transition and not can_transition_status(
            current_status, new_status_normalized
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый переход статуса: {current_status} -> {new_status_normalized}",
            )

        appointment.status = new_status_normalized
        appointment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(appointment)
        return appointment

    def start_visit(self, db: Session, *, appointment_id: int) -> Optional[Appointment]:
        """
        Начать прием (переход paid -> in_visit)
        """
        return self.update_status(
            db, appointment_id=appointment_id, new_status=AppointmentStatus.IN_VISIT
        )

    def complete_visit(
        self, db: Session, *, appointment_id: int
    ) -> Optional[Appointment]:
        """
        Завершить прием (переход in_visit -> completed)
        """
        return self.update_status(
            db, appointment_id=appointment_id, new_status=AppointmentStatus.COMPLETED
        )

    def mark_paid(self, db: Session, *, appointment_id: int) -> Optional[Appointment]:
        """
        Отметить как оплаченное (переход pending -> paid)
        """
        return self.update_status(
            db, appointment_id=appointment_id, new_status=AppointmentStatus.PAID
        )

    def cancel_appointment(
        self, db: Session, *, appointment_id: int
    ) -> Optional[Appointment]:
        """
        Отменить запись
        """
        return self.update_status(
            db, appointment_id=appointment_id, new_status=AppointmentStatus.CANCELLED
        )

    def mark_no_show(
        self, db: Session, *, appointment_id: int
    ) -> Optional[Appointment]:
        """
        Отметить как неявку
        """
        return self.update_status(
            db, appointment_id=appointment_id, new_status=AppointmentStatus.NO_SHOW
        )

    def get_by_status(
        self, db: Session, *, status: str, skip: int = 0, limit: int = 100
    ) -> List[Appointment]:
        """
        Получить записи по статусу
        """
        normalized_status = normalize_appointment_status(status)
        return (
            db.query(self.model)
            .filter(self.model.status == normalized_status)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_paid_appointments(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Appointment]:
        """
        Получить оплаченные записи для отправки к врачу
        """
        return self.get_by_status(
            db, status=AppointmentStatus.PAID, skip=skip, limit=limit
        )

    def get_active_visits(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Appointment]:
        """
        Получить активные приемы (in_visit)
        """
        return self.get_by_status(
            db, status=AppointmentStatus.IN_VISIT, skip=skip, limit=limit
        )


appointment = CRUDAppointment(Appointment)


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===

def count_upcoming_appointments(db: Session, patient_id: int) -> int:
    """Подсчитать предстоящие записи пациента"""
    from datetime import datetime
    
    today = datetime.now().date()
    return (
        db.query(Appointment)
        .filter(
            and_(
                Appointment.patient_id == patient_id,
                Appointment.appointment_date >= today,
                Appointment.status.in_(["planned", "confirmed", "paid"])
            )
        )
        .count()
    )


def count_patient_visits(db: Session, patient_id: int) -> int:
    """Подсчитать количество визитов пациента"""
    return (
        db.query(Appointment)
        .filter(
            and_(
                Appointment.patient_id == patient_id,
                Appointment.status.in_(["completed", "in_visit"])
            )
        )
        .count()
    )


def get_last_visit(db: Session, patient_id: int) -> Optional[Appointment]:
    """Получить последний визит пациента"""
    return (
        db.query(Appointment)
        .filter(
            and_(
                Appointment.patient_id == patient_id,
                Appointment.status.in_(["completed", "in_visit"])
            )
        )
        .order_by(Appointment.appointment_date.desc())
        .first()
    )


def get_upcoming_appointments(db: Session, patient_id: int, limit: int = 10) -> List[Appointment]:
    """Получить предстоящие записи пациента"""
    from datetime import datetime
    
    today = datetime.now().date()
    return (
        db.query(Appointment)
        .filter(
            and_(
                Appointment.patient_id == patient_id,
                Appointment.appointment_date >= today,
                Appointment.status.in_(["planned", "confirmed", "paid"])
            )
        )
        .order_by(Appointment.appointment_date.asc())
        .limit(limit)
        .all()
    )


def get_appointment(db: Session, appointment_id: int) -> Optional[Appointment]:
    """Получить запись по ID"""
    return db.query(Appointment).filter(Appointment.id == appointment_id).first()


def create_appointment(db: Session, appointment_data: dict) -> Appointment:
    """Создать новую запись"""
    appointment = Appointment(**appointment_data)
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def add_appointment_service(db: Session, appointment_id: int, service_id: int) -> bool:
    """Добавить услугу к записи"""
    try:
        # Здесь должна быть логика добавления услуги к записи
        # Пока что просто возвращаем True
        return True
    except Exception:
        return False
