"""Repository helpers for patient appointment endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor, Schedule
from app.models.lab import LabOrder
from app.models.patient import Patient
from app.models.user import User


class PatientAppointmentsApiRepository:
    """Encapsulates ORM queries used by patient appointment APIs."""

    def __init__(self, db: Session):
        self.db = db

    def get_patient_by_user_id(self, user_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.user_id == user_id).first()

    def list_appointments(
        self,
        *,
        patient_id: int,
        status_filter: str | None,
        include_past: bool,
        today: date,
    ) -> list[Appointment]:
        query = self.db.query(Appointment).filter(Appointment.patient_id == patient_id)
        if status_filter:
            query = query.filter(Appointment.status == status_filter)
        if not include_past:
            query = query.filter(Appointment.appointment_date >= today)
        return query.order_by(Appointment.appointment_date, Appointment.appointment_time).all()

    def get_appointment_for_patient(
        self,
        *,
        appointment_id: int,
        patient_id: int,
    ) -> Appointment | None:
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.id == appointment_id,
                Appointment.patient_id == patient_id,
            )
            .first()
        )

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def list_active_schedules(self, doctor_id: int) -> list[Schedule]:
        return (
            self.db.query(Schedule)
            .filter(
                Schedule.doctor_id == doctor_id,
                Schedule.active.is_(True),
            )
            .all()
        )

    def list_booked_appointments(
        self,
        *,
        doctor_id: int,
        start_date: date,
        end_date: date,
    ) -> list[Appointment]:
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date >= start_date,
                Appointment.appointment_date <= end_date,
                Appointment.status.notin_(["cancelled"]),
            )
            .all()
        )

    def list_done_lab_results(self, *, patient_id: int, limit: int) -> list[LabOrder]:
        return (
            self.db.query(LabOrder)
            .filter(
                LabOrder.patient_id == patient_id,
                LabOrder.status == "done",
            )
            .order_by(desc(LabOrder.created_at))
            .limit(limit)
            .all()
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
