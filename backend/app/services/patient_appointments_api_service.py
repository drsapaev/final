"""Service layer for patient appointment endpoints."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.user import User
from app.repositories.patient_appointments_api_repository import (
    PatientAppointmentsApiRepository,
)


class PatientAppointmentsApiService:
    """Handles business operations for patient appointment APIs."""

    def __init__(
        self,
        db: Session,
        repository: PatientAppointmentsApiRepository | None = None,
    ):
        self.repository = repository or PatientAppointmentsApiRepository(db)

    def get_patient_for_user(self, user: User):
        return self.repository.get_patient_by_user_id(user.id)

    def list_appointments(
        self,
        *,
        patient_id: int,
        status_filter: str | None,
        include_past: bool,
    ):
        return self.repository.list_appointments(
            patient_id=patient_id,
            status_filter=status_filter,
            include_past=include_past,
            today=date.today(),
        )

    def get_appointment_for_patient(self, *, appointment_id: int, patient_id: int):
        return self.repository.get_appointment_for_patient(
            appointment_id=appointment_id,
            patient_id=patient_id,
        )

    def get_doctor_name(self, doctor_id: int | None) -> str:
        if not doctor_id:
            return "Врач не назначен"

        doctor = self.repository.get_doctor(doctor_id)
        if not doctor:
            return f"Врач #{doctor_id}"

        if doctor.user_id:
            user = self.repository.get_user(doctor.user_id)
            if user:
                return user.full_name or user.username

        return f"Врач #{doctor_id}"

    @staticmethod
    def default_end_date(*, start_date: date) -> date:
        return start_date + timedelta(days=7)

    def list_available_slots(
        self,
        *,
        appointment: Appointment,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        doctor_name = "Врач"
        schedules = []

        if appointment.doctor_id:
            doctor_name = self.get_doctor_name(appointment.doctor_id)
            schedules = self.repository.list_active_schedules(appointment.doctor_id)

        booked_slots = set()
        if appointment.doctor_id:
            existing_appointments = self.repository.list_booked_appointments(
                doctor_id=appointment.doctor_id,
                start_date=start_date,
                end_date=end_date,
            )
            for existing in existing_appointments:
                booked_slots.add(f"{existing.appointment_date}_{existing.appointment_time}")

        slots: list[dict[str, Any]] = []
        current_date = start_date

        while current_date <= end_date:
            weekday = current_date.weekday()
            day_schedule = next(
                (
                    schedule
                    for schedule in schedules
                    if schedule.weekday == weekday and schedule.active
                ),
                None,
            )

            if day_schedule and day_schedule.start_time and day_schedule.end_time:
                start_hour = (
                    day_schedule.start_time.hour
                    if hasattr(day_schedule.start_time, "hour")
                    else 9
                )
                end_hour = (
                    day_schedule.end_time.hour
                    if hasattr(day_schedule.end_time, "hour")
                    else 18
                )
                for hour in range(start_hour, end_hour):
                    self._append_slot_if_free(
                        slots=slots,
                        booked_slots=booked_slots,
                        slot_date=current_date,
                        time_str=f"{hour:02d}:00",
                        doctor_id=appointment.doctor_id or 0,
                        doctor_name=doctor_name,
                    )
            elif not schedules and weekday < 6:
                for hour in [9, 10, 11, 14, 15, 16]:
                    self._append_slot_if_free(
                        slots=slots,
                        booked_slots=booked_slots,
                        slot_date=current_date,
                        time_str=f"{hour:02d}:00",
                        doctor_id=appointment.doctor_id or 0,
                        doctor_name=doctor_name,
                    )

            current_date += timedelta(days=1)

        return slots

    @staticmethod
    def _append_slot_if_free(
        *,
        slots: list[dict[str, Any]],
        booked_slots: set[str],
        slot_date: date,
        time_str: str,
        doctor_id: int,
        doctor_name: str,
    ) -> None:
        slot_key = f"{slot_date}_{time_str}"
        if slot_key in booked_slots:
            return
        slots.append(
            {
                "date": str(slot_date),
                "time": time_str,
                "doctor_id": doctor_id,
                "doctor_name": doctor_name,
            }
        )

    def cancel_appointment(self, appointment: Appointment) -> None:
        appointment.status = "cancelled"
        appointment.updated_at = datetime.now()
        self.repository.commit()

    def reschedule_appointment(
        self,
        *,
        appointment: Appointment,
        new_date: date,
        new_time: str,
    ) -> None:
        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        appointment.updated_at = datetime.now()
        self.repository.commit()

    def list_done_lab_results(self, *, patient_id: int, limit: int):
        return self.repository.list_done_lab_results(patient_id=patient_id, limit=limit)

    def rollback(self) -> None:
        self.repository.rollback()
