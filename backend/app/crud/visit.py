from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.orm import Session


def _visits(db: Session) -> Table:
    md = MetaData()
    return Table("visits", md, autoload_with=db.get_bind())


def _vservices(db: Session) -> Table:
    md = MetaData()
    return Table("visit_services", md, autoload_with=db.get_bind())


def create_visit(
    db: Session,
    *,
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    t = _visits(db)
    row = (
        db.execute(
            t.insert()
            .values(
                patient_id=patient_id, doctor_id=doctor_id, status="open", notes=notes
            )
            .returning(t)
        )
        .mappings()
        .first()
    )
    db.commit()
    assert row is not None
    return dict(row)


def get_visit(db: Session, visit_id: int) -> Optional[dict]:
    t = _visits(db)
    row = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    return dict(row) if row else None


def set_status(db: Session, visit_id: int, status_new: str) -> Optional[dict]:
    if status_new not in {"open", "in_progress", "closed", "canceled"}:
        raise ValueError("invalid status")
    t = _visits(db)
    values = {"status": status_new}
    now = datetime.utcnow()
    if status_new == "in_progress":
        values["started_at"] = now
    if status_new in {"closed", "canceled"}:
        values["finished_at"] = now
    row = (
        db.execute(t.update().where(t.c.id == visit_id).values(**values).returning(t))
        .mappings()
        .first()
    )
    if not row:
        return None
    db.commit()
    return dict(row)


def list_services(db: Session, visit_id: int) -> List[dict]:
    s = _vservices(db)
    rows = (
        db.execute(select(s).where(s.c.visit_id == visit_id).order_by(s.c.id.asc()))
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def add_service(
    db: Session,
    *,
    visit_id: int,
    code: Optional[str],
    name: str,
    price: float,
    qty: int = 1,
) -> dict:
    s = _vservices(db)
    row = (
        db.execute(
            s.insert()
            .values(visit_id=visit_id, code=code, name=name, price=price, qty=qty)
            .returning(s)
        )
        .mappings()
        .first()
    )
    db.commit()
    assert row is not None
    return dict(row)
