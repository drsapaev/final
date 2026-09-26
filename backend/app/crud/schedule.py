from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.roles import DOCTOR_ROLE_SPELLINGS
from app.core.specialties import INCOMPLETE_DOCTOR_SPECIALTY
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.schedule import ScheduleTemplate
from app.models.user import User


def _resolve_department_id(db: Session, department: str | None) -> int | None:
    """Round-9 (codex P2, PR #3340): department filters arrive as the canonical
    `Department.key` STRING while both `schedule_templates` and `appointments`
    store the FK `department_id`. The previous `Model.department == key`
    comparisons used the RELATIONSHIP attribute — SQLAlchemy compiled them
    against the id column with a string value (`department_id = 'cardio'`),
    which never matches on SQLite and errors on Postgres (`integer = varchar`).
    Unknown keys resolve to None — the caller answers an empty selection
    (exact-key semantics, the same contract the template filters always had)."""
    if not department:
        return None
    return db.scalar(select(Department.id).where(Department.key == department))


# ---------------------------------------------------------------------------
# Review round 3 (owner P2, #3402): READ-side schedule/department consistency.
#
# The CREATE boundary validates department activity and doctor eligibility
# under row locks, but a row lock cannot outlive its transaction: an admin
# deactivation committed AFTER a template was created must be reflected by
# the READS, otherwise the schedule keeps advertising slots the booking
# contract would refuse (their own PG pin leaves ScheduleTemplate.active=True
# behind a deactivated department). The advertising surfaces therefore
# exclude templates whose Department is inactive or whose Doctor is
# ineligible — WITHOUT touching the template rows (deactivation must stay
# reversible: reactivating the department brings the slots back).
#
# Deliberately NOT filtered (management views, staff-only routes):
# list_schedules, get_weekly_schedule, get_daily_schedule — admins must
# still SEE templates of a deactivated department to manage/re-enable them.
# ---------------------------------------------------------------------------


def _eligible_doctor_clause():
    """SQL filter: template's Doctor (if any) must be booking-eligible.

    SQL mirror of ``ensure_doctor_eligible_for_appointment()`` (the booking
    contract's SSOT): active Doctor, completed specialty (not blank / not
    the "general" placeholder), existing active owner account carrying a
    doctor-family role. doctor_id IS NULL (department-wide template) has no
    doctor to validate — mirrors the helper's None short-circuit."""
    return or_(
        ScheduleTemplate.doctor_id.is_(None),
        ScheduleTemplate.doctor_id.in_(
            select(Doctor.id).where(
                Doctor.active.is_(True),
                # is_doctor_profile_incomplete(): blank or placeholder
                # specialty is INCOMPLETE (Codex round-9 P2).
                Doctor.specialty.isnot(None),
                func.trim(Doctor.specialty) != "",
                func.trim(Doctor.specialty) != INCOMPLETE_DOCTOR_SPECIALTY,
                Doctor.user_id.isnot(None),
                User.id == Doctor.user_id,
                User.is_active.is_(True),
                # is_doctor_role_spelling(): normalize = strip + lower.
                func.lower(func.trim(User.role)).in_(DOCTOR_ROLE_SPELLINGS),
            )
        ),
    )


def list_schedules(
    db: Session,
    *,
    department: str | None = None,
    doctor_id: int | None = None,
    weekday: int | None = None,
    active: bool | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[ScheduleTemplate]:
    stmt = select(ScheduleTemplate)
    if department:
        dept_id = _resolve_department_id(db, department)
        if dept_id is None:
            # Unknown department key: exact-key semantics — nothing matches.
            return []
        stmt = stmt.where(ScheduleTemplate.department_id == dept_id)
    if doctor_id:
        stmt = stmt.where(ScheduleTemplate.doctor_id == doctor_id)
    if weekday is not None:
        stmt = stmt.where(ScheduleTemplate.weekday == weekday)
    if active is not None:
        stmt = stmt.where(ScheduleTemplate.active == active)
    stmt = (
        stmt.order_by(
            # department_id/doctor_id are real columns; .department is a
            # relationship and ordering by it 500s (Sentry PYTHON-FASTAPI-M)
            ScheduleTemplate.department_id.nulls_last(),
            ScheduleTemplate.doctor_id.nulls_last(),
            ScheduleTemplate.weekday.asc(),
            ScheduleTemplate.start_time.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


def create_schedule(
    db: Session,
    *,
    department: str | None,
    doctor_id: int | None,
    weekday: int,
    start_time: str,
    end_time: str,
    room: str | None,
    capacity_per_hour: int | None,
    active: bool,
) -> ScheduleTemplate:
    row = ScheduleTemplate(
        # Round-9 (codex P2, PR #3340): `department` arrives as the canonical
        # KEY string — persist its FK id (assigning a string to the
        # relationship attribute never produced a department-backed row).
        department_id=_resolve_department_id(db, department or None),
        doctor_id=(doctor_id or None),
        weekday=int(weekday),
        start_time=start_time,
        end_time=end_time,
        room=(room or None),
        capacity_per_hour=(capacity_per_hour or None),
        active=bool(active),
    )
    db.add(row)
    db.flush()
    return row


def delete_schedule(db: Session, *, id_: int) -> bool:
    row = db.get(ScheduleTemplate, id_)
    if not row:
        return False
    db.delete(row)
    db.flush()
    return True


# Новые функции для интеграции с панелью регистратора


def get_weekly_schedule(
    db: Session,
    *,
    start_date: date,
    department: str | None = None,
    doctor_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить расписание на неделю
    """
    weekly_schedule = []
    # Round-9 (codex P2, PR #3340): the department filter is a KEY string —
    # resolve it ONCE per read; an unknown key answers an empty week
    # (exact-key semantics, the same contract the template filters had).
    dept_id = _resolve_department_id(db, department)
    department_filtered = bool(department)

    for i in range(7):
        current_date = start_date + timedelta(days=i)
        weekday = current_date.weekday()

        if department_filtered and dept_id is None:
            weekly_schedule.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "weekday": weekday,
                    "weekday_name": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][weekday],
                    "templates": [],
                    "appointments": [],
                }
            )
            continue

        # Получаем шаблоны расписания для этого дня недели
        stmt = select(ScheduleTemplate).where(
            and_(ScheduleTemplate.weekday == weekday, ScheduleTemplate.active)
        )

        if department:
            stmt = stmt.where(ScheduleTemplate.department_id == dept_id)
        if doctor_id:
            stmt = stmt.where(ScheduleTemplate.doctor_id == doctor_id)

        templates = list(db.execute(stmt).scalars().all())

        # Получаем существующие записи на этот день
        appointments_stmt = select(Appointment).where(
            and_(
                Appointment.appointment_date == current_date,
                Appointment.status != "cancelled",
            )
        )

        if department:
            appointments_stmt = appointments_stmt.where(
                Appointment.department_id == dept_id
            )
        if doctor_id:
            appointments_stmt = appointments_stmt.where(
                Appointment.doctor_id == doctor_id
            )

        appointments = list(db.execute(appointments_stmt).scalars().all())

        daily_schedule = {
            "date": current_date.strftime("%Y-%m-%d"),
            "weekday": weekday,
            "weekday_name": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][weekday],
            "templates": [
                {
                    "id": t.id,
                    # Round-9 (codex P2): the KEY string these payloads
                    # historically promised — never the Department object.
                    "department": getattr(t.department, "key", None),
                    "doctor_id": t.doctor_id,
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                    "room": t.room,
                    "capacity_per_hour": t.capacity_per_hour,
                }
                for t in templates
            ],
            "appointments": [
                {
                    "id": a.id,
                    "patient_id": a.patient_id,
                    "doctor_id": a.doctor_id,
                    # Round-9 (codex P2): `department_key` accessor — a
                    # department-backed row must not leak the ORM object.
                    "department": a.department_key,
                    "appointment_time": a.appointment_time,
                    "status": a.status,
                }
                for a in appointments
            ],
        }

        weekly_schedule.append(daily_schedule)

    return weekly_schedule


def get_daily_schedule(
    db: Session,
    *,
    target_date: date,
    department: str | None = None,
    doctor_id: int | None = None,
) -> dict[str, Any]:
    """
    Получить расписание на конкретный день
    """
    weekday = target_date.weekday()

    # Round-9 (codex P2, PR #3340): resolve the KEY-string filter once; an
    # unknown key answers an empty day (exact-key semantics).
    dept_id = _resolve_department_id(db, department)
    if department and dept_id is None:
        templates, appointments = [], []
    else:
        # Получаем шаблоны расписания
        stmt = select(ScheduleTemplate).where(
            and_(ScheduleTemplate.weekday == weekday, ScheduleTemplate.active)
        )

        if department:
            stmt = stmt.where(ScheduleTemplate.department_id == dept_id)
        if doctor_id:
            stmt = stmt.where(ScheduleTemplate.doctor_id == doctor_id)

        templates = list(db.execute(stmt).scalars().all())

        # Получаем существующие записи
        appointments_stmt = select(Appointment).where(
            and_(
                Appointment.appointment_date == target_date,
                Appointment.status != "cancelled",
            )
        )

        if department:
            appointments_stmt = appointments_stmt.where(
                Appointment.department_id == dept_id
            )
        if doctor_id:
            appointments_stmt = appointments_stmt.where(
                Appointment.doctor_id == doctor_id
            )

        appointments = list(db.execute(appointments_stmt).scalars().all())

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "weekday": weekday,
        "weekday_name": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][weekday],
        "templates": [
            {
                "id": t.id,
                # Round-9 (codex P2): the KEY string, never the Department object.
                "department": getattr(t.department, "key", None),
                "doctor_id": t.doctor_id,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "room": t.room,
                "capacity_per_hour": t.capacity_per_hour,
            }
            for t in templates
        ],
        "appointments": [
            {
                "id": a.id,
                "patient_id": a.patient_id,
                "doctor_id": a.doctor_id,
                # Round-9 (codex P2): `department_key` — no ORM-object leak.
                "department": a.department_key,
                "appointment_time": a.appointment_time,
                "status": a.status,
            }
            for a in appointments
        ],
    }


def get_available_slots(
    db: Session,
    *,
    target_date: date,
    department: str,
    doctor_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить доступные слоты времени для записи
    """
    weekday = target_date.weekday()

    # Round-9 (codex P2, PR #3340): the department filter is a KEY string —
    # match the FK ids; an unknown key answers no slots (exact-key).
    dept_id = _resolve_department_id(db, department)
    if dept_id is None:
        return []

    # Review round 3 (owner P2): the resolved department must STILL be
    # active — a template created before an admin deactivation must not
    # keep advertising slots the booking boundary would refuse. A column
    # select (not db.get) deliberately bypasses the identity map, the same
    # stale-snapshot class the booking lock's populate_existing() fixed.
    dept_active = db.scalar(
        select(Department.active).where(Department.id == dept_id)
    )
    if dept_active is not True:
        return []

    # Получаем шаблоны расписания для этого дня (+ doctor leg: a template
    # pinned to an ineligible doctor must not advertise bookable slots).
    stmt = select(ScheduleTemplate).where(
        and_(
            ScheduleTemplate.weekday == weekday,
            ScheduleTemplate.active,
            ScheduleTemplate.department_id == dept_id,
            _eligible_doctor_clause(),
        )
    )

    if doctor_id:
        stmt = stmt.where(ScheduleTemplate.doctor_id == doctor_id)

    templates = list(db.execute(stmt).scalars().all())

    # Получаем существующие записи
    appointments_stmt = select(Appointment).where(
        and_(
            Appointment.appointment_date == target_date,
            Appointment.department_id == dept_id,
            Appointment.status != "cancelled",
        )
    )

    if doctor_id:
        appointments_stmt = appointments_stmt.where(Appointment.doctor_id == doctor_id)

    appointments = list(db.execute(appointments_stmt).scalars().all())

    available_slots = []

    for template in templates:
        start_time = datetime.strptime(template.start_time, "%H:%M").time()
        end_time = datetime.strptime(template.end_time, "%H:%M").time()

        # Генерируем слоты по часам
        current_time = start_time
        while current_time < end_time:
            slot_time = current_time.strftime("%H:%M")

            # Проверяем, не занят ли этот слот
            slot_appointments = [
                a
                for a in appointments
                if a.appointment_time == slot_time
                and (not doctor_id or a.doctor_id == doctor_id)
            ]

            # Проверяем вместимость
            max_capacity = template.capacity_per_hour or 1
            current_capacity = len(slot_appointments)

            if current_capacity < max_capacity:
                available_slots.append(
                    {
                        "time": slot_time,
                        # Round-9 (codex P2): the KEY string, never the object.
                        "department": getattr(template.department, "key", None),
                        "doctor_id": template.doctor_id,
                        "room": template.room,
                        "available_capacity": max_capacity - current_capacity,
                        "total_capacity": max_capacity,
                    }
                )

            # Переходим к следующему часу
            current_time = datetime.combine(date.today(), current_time) + timedelta(
                hours=1
            )
            current_time = current_time.time()

    return available_slots


def get_doctors_by_department(
    db: Session,
    *,
    department: str | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список врачей, сгруппированных по отделениям
    """
    # Получаем уникальные отделения (обновлено для CI/CD)
    # Round-9 (codex P2, PR #3340): select the FK id column — selecting the
    # relationship attribute yielded raw department_id INTs that were then
    # compared against (and returned as) the KEY string the payload promises.
    dept_stmt = (
        select(ScheduleTemplate.department_id).distinct().where(ScheduleTemplate.active)
    )
    dept_ids = [r[0] for r in db.execute(dept_stmt).all() if r[0]]
    # Review round 3 (owner P2): only still-ACTIVE departments are
    # advertised — an inactive department's templates must not surface it
    # (the listing is derived from active templates, which outlive a
    # deactivation).
    dept_rows = (
        db.query(Department)
        .filter(Department.id.in_(dept_ids), Department.active.is_(True))
        .all()
        if dept_ids
        else []
    )
    key_by_id = {int(row.id): row.key for row in dept_rows}

    # The optional filter arrives as the canonical KEY string — resolve it
    # to the id it must match.
    filtered_id = _resolve_department_id(db, department)
    if department and filtered_id is None:
        return []

    result = []

    for dept_id in dept_ids:
        dept = key_by_id.get(int(dept_id))
        if dept is None:
            continue
        if department and int(dept_id) != int(filtered_id):
            continue

        # Получаем врачей для этого отделения (+ review round 3: only
        # booking-eligible doctors are advertised).
        doctors_stmt = (
            select(ScheduleTemplate.doctor_id)
            .distinct()
            .where(
                and_(
                    ScheduleTemplate.department_id == int(dept_id),
                    ScheduleTemplate.active,
                    ScheduleTemplate.doctor_id.isnot(None),
                    _eligible_doctor_clause(),
                )
            )
        )
        doctor_ids = [r[0] for r in db.execute(doctors_stmt).all() if r[0]]

        dept_info = {
            "department": dept,
            "doctors": [
                {
                    "id": doc_id,
                    "name": f"Врач #{doc_id}",  # В будущем можно подключить таблицу пользователей
                }
                for doc_id in doctor_ids
            ],
        }
        result.append(dept_info)

    return result


def get_departments(db: Session) -> list[dict[str, Any]]:
    """
    Получить список всех отделений с расписанием
    """
    # Round-9 (codex P2, PR #3340): distinct FK ids + one key lookup — the
    # payload's `department` field is the KEY string, not the raw id the
    # relationship selection used to produce.
    dept_stmt = (
        select(ScheduleTemplate.department_id).distinct().where(ScheduleTemplate.active)
    )
    dept_ids = [r[0] for r in db.execute(dept_stmt).all() if r[0]]
    # Review round 3 (owner P2): same active-department rule as
    # get_doctors_by_department — templates outliving a deactivation must
    # not advertise the department they belonged to.
    dept_rows = (
        db.query(Department)
        .filter(Department.id.in_(dept_ids), Department.active.is_(True))
        .all()
        if dept_ids
        else []
    )
    key_by_id = {int(row.id): row.key for row in dept_rows}

    result = []

    for dept_id in dept_ids:
        dept = key_by_id.get(int(dept_id))
        if dept is None:
            continue
        # Подсчитываем количество активных шаблонов для отделения
        count_stmt = select(func.count(ScheduleTemplate.id)).where(
            and_(
                ScheduleTemplate.department_id == int(dept_id),
                ScheduleTemplate.active,
            )
        )
        template_count = db.execute(count_stmt).scalar()

        dept_info = {
            "department": dept,
            "template_count": template_count,
            "active": True,
        }
        result.append(dept_info)

    return result
