from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.schedule import ScheduleTemplate
from app.models.user import User


def list_schedules(
    db: Session,
    *,
    department: Optional[str] = None,
    doctor_id: Optional[int] = None,
    weekday: Optional[int] = None,
    active: Optional[bool] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[ScheduleTemplate]:
    stmt = select(ScheduleTemplate)
    if department:
        stmt = stmt.where(ScheduleTemplate.department == department)
    if doctor_id:
        stmt = stmt.where(ScheduleTemplate.doctor_id == doctor_id)
    if weekday is not None:
        stmt = stmt.where(ScheduleTemplate.weekday == weekday)
    if active is not None:
        stmt = stmt.where(ScheduleTemplate.active == active)
    stmt = (
        stmt.order_by(
            ScheduleTemplate.department.nulls_last(),
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
    department: Optional[str],
    doctor_id: Optional[int],
    weekday: int,
    start_time: str,
    end_time: str,
    room: Optional[str],
    capacity_per_hour: Optional[int],
    active: bool,
) -> ScheduleTemplate:
    row = ScheduleTemplate(
        department=(department or None),
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
    department: Optional[str] = None,
    doctor_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить расписание на неделю
    """
    weekly_schedule = []

    for i in range(7):
        current_date = start_date + timedelta(days=i)
        weekday = current_date.weekday()

        # Получаем шаблоны расписания для этого дня недели
        stmt = select(ScheduleTemplate).where(
            and_(ScheduleTemplate.weekday == weekday, ScheduleTemplate.active == True)
        )

        if department:
            stmt = stmt.where(ScheduleTemplate.department == department)
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
                Appointment.department == department
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
                    "department": t.department,
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
                    "department": a.department,
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
    department: Optional[str] = None,
    doctor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить расписание на конкретный день
    """
    weekday = target_date.weekday()

    # Получаем шаблоны расписания
    stmt = select(ScheduleTemplate).where(
        and_(ScheduleTemplate.weekday == weekday, ScheduleTemplate.active == True)
    )

    if department:
        stmt = stmt.where(ScheduleTemplate.department == department)
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
            Appointment.department == department
        )
    if doctor_id:
        appointments_stmt = appointments_stmt.where(Appointment.doctor_id == doctor_id)

    appointments = list(db.execute(appointments_stmt).scalars().all())

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "weekday": weekday,
        "weekday_name": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][weekday],
        "templates": [
            {
                "id": t.id,
                "department": t.department,
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
                "department": a.department,
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
    doctor_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить доступные слоты времени для записи
    """
    weekday = target_date.weekday()

    # Получаем шаблоны расписания для этого дня
    stmt = select(ScheduleTemplate).where(
        and_(
            ScheduleTemplate.weekday == weekday,
            ScheduleTemplate.active == True,
            ScheduleTemplate.department == department,
        )
    )

    if doctor_id:
        stmt = stmt.where(ScheduleTemplate.doctor_id == doctor_id)

    templates = list(db.execute(stmt).scalars().all())

    # Получаем существующие записи
    appointments_stmt = select(Appointment).where(
        and_(
            Appointment.appointment_date == target_date,
            Appointment.department == department,
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
                        "department": template.department,
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
    department: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Получить список врачей, сгруппированных по отделениям
    """
    # Получаем уникальные отделения
    dept_stmt = (
        select(ScheduleTemplate.department)
        .distinct()
        .where(ScheduleTemplate.active == True)
    )
    departments = [r[0] for r in db.execute(dept_stmt).all() if r[0]]

    result = []

    for dept in departments:
        if department and dept != department:
            continue

        # Получаем врачей для этого отделения
        doctors_stmt = (
            select(ScheduleTemplate.doctor_id)
            .distinct()
            .where(
                and_(
                    ScheduleTemplate.department == dept,
                    ScheduleTemplate.active == True,
                    ScheduleTemplate.doctor_id.isnot(None),
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


def get_departments(db: Session) -> List[Dict[str, Any]]:
    """
    Получить список всех отделений с расписанием
    """
    # Получаем уникальные отделения
    dept_stmt = (
        select(ScheduleTemplate.department)
        .distinct()
        .where(ScheduleTemplate.active == True)
    )
    departments = [r[0] for r in db.execute(dept_stmt).all() if r[0]]

    result = []

    for dept in departments:
        # Подсчитываем количество активных шаблонов для отделения
        count_stmt = select(func.count(ScheduleTemplate.id)).where(
            and_(ScheduleTemplate.department == dept, ScheduleTemplate.active == True)
        )
        template_count = db.execute(count_stmt).scalar()

        dept_info = {
            "department": dept,
            "template_count": template_count,
            "active": True,
        }
        result.append(dept_info)

    return result
