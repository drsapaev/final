"""Read-only staff projection of deliberate visit moves onto the clinic day."""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.enums import (
    AppointmentStatus,
    VisitStatus,
    normalize_appointment_status,
)
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository


class CalendarRescheduledVisit(BaseModel):
    visit_id: int
    patient_name: str
    doctor_name: str | None
    scheduled_time: str | None
    status: str


# The move changes date, not clinical lifecycle. Only visits that can still
# await care belong here; a previously moved visit is not a history export.
_ACTIVE_VISITS = (
    VisitStatus.OPEN,
    VisitStatus.PAID,
    VisitStatus.PENDING_CONFIRMATION,
    VisitStatus.CONFIRMED,
)


def list_rescheduled_calendar_visits(
    db: Session, *, day: date, doctor_id: int | None, limit: int
) -> list[tuple[int, CalendarRescheduledVisit]]:
    legacy_move = exists().where(
        OnlineQueueEntry.visit_id == Visit.id,
        OnlineQueueEntry.patient_id == Visit.patient_id,
        OnlineQueueEntry.status == "rescheduled",
    )
    stmt = (
        select(
            Visit.id,
            Visit.patient_id,
            Visit.doctor_id,
            Visit.visit_time,
            Visit.status,
            Patient.first_name,
            Patient.last_name,
            Patient.middle_name,
            User.full_name.label("doctor_name"),
        )
        .join(Patient, Patient.id == Visit.patient_id)
        .outerjoin(Doctor, Doctor.id == Visit.doctor_id)
        .outerjoin(User, User.id == Doctor.user_id)
        .where(
            Visit.visit_date == day,
            Visit.status.in_(_ACTIVE_VISITS),
            or_(Visit.calendar_rescheduled.is_(True), legacy_move),
        )
        .order_by(Visit.visit_time.asc().nulls_last(), Visit.id)
    )
    if doctor_id is not None:
        stmt = stmt.where(Visit.doctor_id == doctor_id)

    # Only the output is limited: filtering earlier can make a day look empty
    # if the first candidates already have a matching Appointment.
    candidates = db.execute(stmt).all()
    if not candidates:
        return []

    patients = {row.patient_id for row in candidates}
    canonical_appointments = db.execute(
        select(
            Appointment.patient_id,
            Appointment.doctor_id,
            Appointment.appointment_time,
            Appointment.status,
        ).where(
            Appointment.appointment_date == day, Appointment.patient_id.in_(patients)
        )
    ).all()
    # The existing canonical resolver treats ambiguity as a conflict.
    # Preserve both sources in that case rather than hiding a distinct visit.
    visit_keys: dict[tuple[int, int | None], list[tuple[int, str | None]]] = {}
    possible_visits = db.execute(
        select(Visit.id, Visit.patient_id, Visit.doctor_id, Visit.visit_time).where(
            Visit.visit_date == day, Visit.patient_id.in_(patients)
        )
    )
    for row in possible_visits:
        visit_keys.setdefault((row.patient_id, row.doctor_id), []).append(
            (row.id, row.visit_time)
        )

    represented: set[int] = set()
    for appointment in canonical_appointments:
        if normalize_appointment_status(appointment.status) in {
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        }:
            continue
        times = CanonicalVisitRepository._time_match_values(
            appointment.appointment_time
        )
        matches = [
            visit_id
            for visit_id, visit_time in visit_keys.get(
                (appointment.patient_id, appointment.doctor_id), ()
            )
            if (visit_time in times if times else visit_time is None)
        ]
        if len(matches) == 1:
            represented.add(matches[0])

    result = []
    for row in candidates:
        if row.id in represented:
            continue
        patient_name = " ".join(
            value.strip()
            for value in (row.last_name, row.first_name, row.middle_name)
            if value and value.strip()
        )
        result.append(
            (
                row.patient_id,
                CalendarRescheduledVisit(
                    visit_id=row.id,
                    patient_name=patient_name,
                    doctor_name=row.doctor_name,
                    scheduled_time=row.visit_time,
                    status=row.status,
                ),
            )
        )
        if len(result) >= limit:
            break
    return result
