from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import and_, func, MetaData, select, Table
from sqlalchemy.orm import Session


def _dq(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("daily_queues", md, autoload_with=db.get_bind())


def _qe(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("queue_entries", md, autoload_with=db.get_bind())


def get_daily_by_date_department(
    db: Session, *, d: date, department: str
) -> Optional[dict]:
    t = _dq(db)
    row = (
        db.execute(select(t).where(and_(t.c.date == d, t.c.department == department)))
        .mappings()
        .first()
    )
    return dict(row) if row else None


def ensure_daily_queue(
    db: Session, *, d: date, department: str, start_number: Optional[int] = None
) -> dict:
    """Вернёт существующую дневную очередь или создаст новую."""
    existing = get_daily_by_date_department(db, d=d, department=department)
    if existing:
        return existing
    t = _dq(db)
    row = (
        db.execute(
            t.insert()
            .values(date=d, department=department, last_ticket=int(start_number or 0))
            .returning(t)
        )
        .mappings()
        .first()
    )
    db.commit()
    assert row is not None
    return dict(row)


def next_ticket_and_insert_entry(
    db: Session, *, daily_queue_id: int, patient_id: Optional[int] = None
) -> dict:
    """Инкрементирует last_ticket и создаёт запись в очереди."""
    dq_t, qe_t = _dq(db), _qe(db)

    # Получим текущий last_ticket
    dq_row = (
        db.execute(select(dq_t.c.last_ticket).where(dq_t.c.id == daily_queue_id))
        .mappings()
        .first()
        or {}
    )
    current_last = int(dq_row.get("last_ticket", 0) or 0)
    new_no = current_last + 1

    db.execute(
        dq_t.update().where(dq_t.c.id == daily_queue_id).values(last_ticket=new_no)
    )
    created = (
        db.execute(
            qe_t.insert()
            .values(
                daily_queue_id=daily_queue_id,
                patient_id=patient_id,
                ticket_number=new_no,
                status="waiting",
                created_at=datetime.utcnow(),
            )
            .returning(qe_t)
        )
        .mappings()
        .first()
    )
    db.commit()
    assert created is not None
    return dict(created)


def set_entry_status(
    db: Session,
    *,
    entry_id: int,
    status: str,
    window_no: Optional[str] = None,
) -> Optional[dict]:
    """Установить статус: waiting|serving|done|skipped."""
    qe_t = _qe(db)
    values: Dict[str, object] = {"status": status}
    now = datetime.utcnow()
    if status == "serving":
        values["started_at"] = now
        if window_no is not None:
            values["window_no"] = window_no
    if status in {"done", "skipped"}:
        values["finished_at"] = now
    row = (
        db.execute(
            qe_t.update().where(qe_t.c.id == entry_id).values(**values).returning(qe_t)
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    db.commit()
    return dict(row)


def get_entry_by_id(db: Session, entry_id: int) -> Optional[dict]:
    qe_t = _qe(db)
    row = db.execute(select(qe_t).where(qe_t.c.id == entry_id)).mappings().first()
    return dict(row) if row else None


def stats_for_daily(db: Session, *, daily_queue_id: int) -> Tuple[int, int, int, int]:
    """Возвращает (last_ticket, waiting, serving, done)."""
    dq_t, qe_t = _dq(db), _qe(db)

    last_ticket = (
        db.execute(
            select(dq_t.c.last_ticket).where(dq_t.c.id == daily_queue_id)
        ).scalar_one_or_none()
        or 0
    )

    q = (
        select(qe_t.c.status, func.count())
        .where(qe_t.c.daily_queue_id == daily_queue_id)
        .group_by(qe_t.c.status)
    )
    counts = {row[0]: int(row[1]) for row in db.execute(q).all()}
    return (
        int(last_ticket),
        counts.get("waiting", 0),
        counts.get("serving", 0),
        counts.get("done", 0),
    )
