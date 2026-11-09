"""Persistence queries for public booking requests."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
)


def _future_or_unknown_time(value: str | None, after_time: time) -> bool:
    if not isinstance(value, str):
        return True
    for time_format in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, time_format).time() > after_time
        except ValueError:
            continue
    return True


class PublicBookingRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def has_appointment_link(self, *, appointment_id: int) -> bool:
        return (
            self.db.query(PublicBookingRequest.id)
            .filter(PublicBookingRequest.appointment_id == appointment_id)
            .first()
            is not None
        )

    def lock_settings(self, key: str) -> ClinicSettings | None:
        return (
            self.db.query(ClinicSettings)
            .filter(ClinicSettings.key == key)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def lock_patient_for_booking(self, *, patient_id: int) -> Patient | None:
        """Serialize patient quotas without blocking foreign-key key shares."""
        return (
            self.db.query(Patient)
            .filter(Patient.id == patient_id)
            .populate_existing()
            # SQLAlchemy renders FOR NO KEY UPDATE for PostgreSQL.
            .with_for_update(key_share=True)
            .first()
        )

    def create(self, request: PublicBookingRequest) -> PublicBookingRequest:
        self.db.add(request)
        self.db.flush()
        return request

    def has_active_request_for_slot(
        self,
        *,
        patient_id: int,
        service_id: int,
        doctor_id: int,
        appointment_date: date,
        appointment_time: time,
        excluding_request_id: UUID | None = None,
    ) -> bool:
        query = self.db.query(PublicBookingRequest.id).filter(
            PublicBookingRequest.patient_id == patient_id,
            PublicBookingRequest.service_id == service_id,
            PublicBookingRequest.doctor_id == doctor_id,
            PublicBookingRequest.appointment_date == appointment_date,
            PublicBookingRequest.appointment_time == appointment_time,
            PublicBookingRequest.status.in_(("pending", "needs_new_time")),
        )
        if excluding_request_id is not None:
            query = query.filter(PublicBookingRequest.id != excluding_request_id)
        return query.first() is not None

    def count_patient_booking_creations_since(
        self, *, patient_id: int, created_since: datetime
    ) -> int:
        linked_request = (
            self.db.query(PublicBookingRequest.id)
            .filter(PublicBookingRequest.appointment_id == Appointment.id)
            .exists()
        )
        request_count = int(
            self.db.query(func.count(PublicBookingRequest.id))
            .filter(
                PublicBookingRequest.patient_id == patient_id,
                PublicBookingRequest.created_at >= created_since,
            )
            .scalar()
            or 0
        )
        appointment_count = int(
            self.db.query(func.count(Appointment.id))
            .filter(
                Appointment.patient_id == patient_id,
                Appointment.created_at >= created_since,
                ~linked_request,
            )
            .scalar()
            or 0
        )
        return request_count + appointment_count

    def count_active_future_appointments(
        self, *, patient_id: int, from_date: date, after_time: time
    ) -> int:
        """Count nonterminal appointments whose local start is in the future.

        Unknown statuses normalize to pending in the appointment lifecycle.
        A missing or invalid time on today's appointment is counted as active.
        """
        active_status = Appointment.status.notin_(
            (
                AppointmentStatus.COMPLETED.value,
                AppointmentStatus.CANCELLED.value,
                AppointmentStatus.NO_SHOW.value,
            )
        )
        # A single statement avoids mixing snapshots if a visit is rescheduled.
        appointments = self.db.query(
            Appointment.appointment_date, Appointment.appointment_time
        ).filter(
            Appointment.patient_id == patient_id,
            Appointment.appointment_date >= from_date,
            active_status,
        )
        return sum(
            appointment_date > from_date
            or _future_or_unknown_time(appointment_time, after_time)
            for appointment_date, appointment_time in appointments
        )

    def get_event_by_idempotency_key_hash(
        self, key_hash: str
    ) -> PublicBookingRequestEvent | None:
        return (
            self.db.query(PublicBookingRequestEvent)
            .options(
                joinedload(PublicBookingRequestEvent.request).options(
                    joinedload(PublicBookingRequest.service),
                    joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                    selectinload(PublicBookingRequest.events),
                ),
            )
            .filter(PublicBookingRequestEvent.idempotency_key_hash == key_hash)
            .first()
        )

    def get_for_patient(
        self, *, request_id: UUID, patient_id: int, lock: bool = False
    ) -> PublicBookingRequest | None:
        query = (
            self.db.query(PublicBookingRequest)
            .options(
                joinedload(PublicBookingRequest.service),
                joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                selectinload(PublicBookingRequest.events),
            )
            .filter(
                PublicBookingRequest.id == request_id,
                PublicBookingRequest.patient_id == patient_id,
            )
        )
        if lock:
            query = query.populate_existing().with_for_update(of=PublicBookingRequest)
        return query.first()

    def list_for_patient(
        self, *, patient_id: int, limit: int = 100, offset: int = 0
    ) -> list[PublicBookingRequest]:
        return list(
            self.db.query(PublicBookingRequest)
            .options(
                joinedload(PublicBookingRequest.service),
                joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                selectinload(PublicBookingRequest.events),
            )
            .filter(PublicBookingRequest.patient_id == patient_id)
            .order_by(PublicBookingRequest.created_at.desc(), PublicBookingRequest.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_for_staff(
        self, *, request_id: UUID, lock: bool = False
    ) -> PublicBookingRequest | None:
        query = (
            self.db.query(PublicBookingRequest)
            .options(
                joinedload(PublicBookingRequest.patient),
                joinedload(PublicBookingRequest.service),
                joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                selectinload(PublicBookingRequest.events),
            )
            .filter(PublicBookingRequest.id == request_id)
        )
        if lock:
            query = query.populate_existing().with_for_update(of=PublicBookingRequest)
        return query.first()

    def list_for_staff(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[PublicBookingRequest]:
        query = self.db.query(PublicBookingRequest).options(
            joinedload(PublicBookingRequest.patient),
            joinedload(PublicBookingRequest.service),
            joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
            selectinload(PublicBookingRequest.events),
        )
        if status is not None:
            query = query.filter(PublicBookingRequest.status == status)
        return list(
            query.order_by(
                PublicBookingRequest.created_at.asc(), PublicBookingRequest.id
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
