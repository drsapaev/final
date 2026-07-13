from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.orm import Session


def _dq(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("daily_queues", md, autoload_with=db.get_bind())


def _qe(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("queue_entries", md, autoload_with=db.get_bind())


def get_daily_by_date_department(
    db: Session, *, d: date, department: str
) -> dict | None:
    t = _dq(db)
    row = (
        db.execute(select(t).where(and_(t.c.date == d, t.c.department == department)))
        .mappings()
        .first()
    )
    return dict(row) if row else None


def ensure_daily_queue(
    db: Session, *, d: date, department: str, start_number: int | None = None
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
    db: Session, *, daily_queue_id: int, patient_id: int | None = None
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
                created_at=datetime.now(UTC),
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
    window_no: str | None = None,
) -> dict | None:
    """Установить статус: waiting|serving|done|skipped."""
    qe_t = _qe(db)
    values: dict[str, object] = {"status": status}
    now = datetime.now(UTC)
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


def get_entry_by_id(db: Session, entry_id: int) -> dict | None:
    qe_t = _qe(db)
    row = db.execute(select(qe_t).where(qe_t.c.id == entry_id)).mappings().first()
    return dict(row) if row else None


def stats_for_daily(db: Session, *, daily_queue_id: int) -> tuple[int, int, int, int]:
    """Возвращает (last_ticket, waiting, serving, done).

    PR-1: rewritten to use ORM models (the legacy ``Table``-autoload version
    was broken — ``MetaData(bind=...)`` is unsupported in SQLAlchemy 2.x
    and the ``daily_queues`` table has no ``last_ticket`` column; derive
    ``last_ticket`` as ``MAX(OnlineQueueEntry.number)`` instead).
    """
    from app.models.online_queue import OnlineQueueEntry

    last_ticket = (
        db.execute(
            select(func.max(OnlineQueueEntry.number)).where(
                OnlineQueueEntry.queue_id == daily_queue_id
            )
        ).scalar_one()
        or 0
    )

    q = (
        select(OnlineQueueEntry.status, func.count())
        .where(OnlineQueueEntry.queue_id == daily_queue_id)
        .group_by(OnlineQueueEntry.status)
    )
    counts = {row[0]: int(row[1]) for row in db.execute(q).all()}
    return (
        int(last_ticket),
        counts.get("waiting", 0),
        counts.get("serving", 0) + counts.get("in_service", 0) + counts.get("called", 0),
        counts.get("done", 0) + counts.get("served", 0) + counts.get("skipped", 0),
    )


# === PR-1: Mobile API wrappers (ORM-based) ===

from app.models.online_queue import DailyQueue, OnlineQueueEntry


def get_daily_queues(
    db: Session,
    *,
    day: date | None = None,
    active_only: bool = False,
) -> list[DailyQueue]:
    """Return DailyQueue ORM rows filtered by ``day`` and/or ``active`` flag.

    Switching to the ORM (vs the legacy Table-autoload helpers above) is what
    makes the mobile_api_extended.py attribute accesses work — the raw-dict
    helpers return dicts whose attribute access silently fails with 500.
    """
    stmt = select(DailyQueue)
    if day is not None:
        stmt = stmt.where(DailyQueue.day == day)
    if active_only:
        stmt = stmt.where(DailyQueue.active == True)  # noqa: E712
    stmt = stmt.order_by(DailyQueue.id.asc())
    return list(db.execute(stmt).scalars().all())


def get_daily_queue(
    db: Session,
    *,
    queue_id: int,
) -> DailyQueue | None:
    """Return a single DailyQueue ORM row by id."""
    return db.get(DailyQueue, queue_id)


def get_patient_queue_positions(
    db: Session,
    *,
    patient_id: int,
) -> list[OnlineQueueEntry]:
    """Return all active OnlineQueueEntry rows for a patient (ORM objects).

    Ordered by creation time desc so the most recent position comes first.
    """
    stmt = (
        select(OnlineQueueEntry)
        .where(
            OnlineQueueEntry.patient_id == patient_id,
            OnlineQueueEntry.status.in_(["waiting", "called", "in_service", "diagnostics"]),
        )
        .order_by(OnlineQueueEntry.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
