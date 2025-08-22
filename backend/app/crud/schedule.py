from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import ScheduleTemplate  # type: ignore[attr-defined]


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
    stmt = stmt.order_by(
        ScheduleTemplate.department.nulls_last(),
        ScheduleTemplate.doctor_id.nulls_last(),
        ScheduleTemplate.weekday.asc(),
        ScheduleTemplate.start_time.asc(),
    ).limit(limit).offset(offset)
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