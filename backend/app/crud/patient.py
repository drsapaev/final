from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientUpdate


class CRUDPatient(CRUDBase[Patient, PatientCreate, PatientUpdate]):
    def get_patients(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[Patient]:
        """
        Получить список пациентов с поиском
        """
        query = db.query(self.model)

        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(search_term),
                    self.model.last_name.ilike(search_term),
                    self.model.middle_name.ilike(search_term),
                    self.model.phone.ilike(search_term),
                    self.model.doc_number.ilike(search_term),
                )
            )

        return query.offset(skip).limit(limit).all()

    def get_patient_by_phone(self, db: Session, *, phone: str) -> Optional[Patient]:
        """
        Получить пациента по номеру телефона
        """
        return db.query(self.model).filter(self.model.phone == phone).first()

    def has_active_appointments(self, db: Session, *, patient_id: int) -> bool:
        """
        Проверить, есть ли у пациента активные записи
        """
        from app.models.appointment import Appointment

        today = datetime.now().date()

        active_appointments = (
            db.query(Appointment)
            .filter(
                and_(
                    Appointment.patient_id == patient_id,
                    Appointment.appointment_date >= today,
                    Appointment.status != "cancelled",
                )
            )
            .count()
        )

        return active_appointments > 0

    def get_patient_appointments(
        self, db: Session, *, patient_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получить все записи пациента
        """
        from app.models.appointment import Appointment

        appointments = (
            db.query(Appointment)
            .filter(Appointment.patient_id == patient_id)
            .order_by(Appointment.appointment_date.desc())
            .all()
        )

        return [
            {
                "id": apt.id,
                "appointment_date": apt.appointment_date,
                "appointment_time": apt.appointment_time,
                "department": apt.department,
                "doctor_id": apt.doctor_id,
                "status": apt.status,
                "reason": apt.reason,
            }
            for apt in appointments
        ]


patient = CRUDPatient(Patient)


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===

def get_patient_by_user_id(db: Session, user_id: int) -> Optional[Patient]:
    """Получить пациента по ID пользователя"""
    return db.query(Patient).filter(Patient.user_id == user_id).first()


def create_patient_from_user(db: Session, user: User) -> Patient:
    """Создать профиль пациента из данных пользователя"""
    # Парсим ФИО пользователя
    full_name_parts = user.full_name.split() if user.full_name else ["", "", ""]
    
    patient_data = {
        "user_id": user.id,
        "first_name": full_name_parts[1] if len(full_name_parts) > 1 else "",
        "last_name": full_name_parts[0] if len(full_name_parts) > 0 else "",
        "middle_name": full_name_parts[2] if len(full_name_parts) > 2 else "",
        "phone": user.phone,
        "email": user.email,
        "created_at": datetime.utcnow()
    }
    
    patient = Patient(**patient_data)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    
    return patient
