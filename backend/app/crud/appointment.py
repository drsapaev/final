from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.crud.base import CRUDBase
from app.models.appointment import Appointment
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from datetime import datetime, date

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
        date_to: Optional[str] = None
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
        
        return query.order_by(self.model.appointment_date.desc()).offset(skip).limit(limit).all()
    
    def is_time_slot_occupied(
        self,
        db: Session,
        *,
        doctor_id: int,
        appointment_date: Union[str, date],
        appointment_time: str,
        exclude_appointment_id: Optional[int] = None
    ) -> bool:
        """
        Проверить, занято ли время у врача
        """
        if isinstance(appointment_date, str):
            try:
                appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
            except ValueError:
                return False
        
        query = db.query(self.model).filter(
            and_(
                self.model.doctor_id == doctor_id,
                self.model.appointment_date == appointment_date,
                self.model.appointment_time == appointment_time,
                self.model.status != "cancelled"
            )
        )
        
        if exclude_appointment_id:
            query = query.filter(self.model.id != exclude_appointment_id)
        
        return query.first() is not None
    
    def get_doctor_schedule(
        self,
        db: Session,
        *,
        doctor_id: int,
        date: str
    ) -> List[Dict[str, Any]]:
        """
        Получить расписание врача на определенную дату
        """
        try:
            schedule_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return []
        
        appointments = db.query(self.model).filter(
            and_(
                self.model.doctor_id == doctor_id,
                self.model.appointment_date == schedule_date,
                self.model.status != "cancelled"
            )
        ).order_by(self.model.appointment_time).all()
        
        return [
            {
                "id": apt.id,
                "appointment_time": apt.appointment_time,
                "patient_id": apt.patient_id,
                "department": apt.department,
                "status": apt.status,
                "reason": apt.reason
            }
            for apt in appointments
        ]
    
    def get_department_schedule(
        self,
        db: Session,
        *,
        department: str,
        date: str
    ) -> List[Dict[str, Any]]:
        """
        Получить расписание отделения на определенную дату
        """
        try:
            schedule_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return []
        
        appointments = db.query(self.model).filter(
            and_(
                self.model.department == department,
                self.model.appointment_date == schedule_date,
                self.model.status != "cancelled"
            )
        ).order_by(self.model.appointment_time).all()
        
        return [
            {
                "id": apt.id,
                "appointment_time": apt.appointment_time,
                "patient_id": apt.patient_id,
                "doctor_id": apt.doctor_id,
                "status": apt.status,
                "reason": apt.reason
            }
            for apt in appointments
        ]
    
    def get_upcoming_appointments(
        self,
        db: Session,
        *,
        patient_id: int,
        limit: int = 10
    ) -> List[Appointment]:
        """
        Получить предстоящие записи пациента
        """
        today = datetime.now().date()
        
        return db.query(self.model).filter(
            and_(
                self.model.patient_id == patient_id,
                self.model.appointment_date >= today,
                self.model.status != "cancelled"
            )
        ).order_by(self.model.appointment_date, self.model.appointment_time).limit(limit).all()

appointment = CRUDAppointment(Appointment)

