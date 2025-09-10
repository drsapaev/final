from __future__ import annotations

from typing import List, Optional

from sqlalchemy import MetaData, select, Table
from sqlalchemy.orm import Session


def _orders(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("lab_orders", md, autoload_with=db.get_bind())


def _results(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("lab_results", md, autoload_with=db.get_bind())


def create_order(
    db: Session,
    *,
    visit_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    t = _orders(db)
    row = (
        db.execute(
            t.insert()
            .values(
                visit_id=visit_id, patient_id=patient_id, status="ordered", notes=notes
            )
            .returning(t)
        )
        .mappings()
        .first()
    )
    db.commit()
    assert row is not None
    return dict(row)


def set_order_status(db: Session, order_id: int, status_new: str) -> Optional[dict]:
    if status_new not in {"ordered", "in_progress", "done", "canceled"}:
        raise ValueError("invalid status")
    t = _orders(db)
    row = (
        db.execute(
            t.update().where(t.c.id == order_id).values(status=status_new).returning(t)
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    db.commit()
    return dict(row)


def add_results(db: Session, order_id: int, items: List[dict]) -> List[dict]:
    r = _results(db)
    created: list[dict] = []
    for it in items:
        row = (
            db.execute(
                r.insert()
                .values(
                    order_id=order_id,
                    test_code=it.get("test_code"),
                    test_name=it["test_name"],
                    value=it.get("value"),
                    unit=it.get("unit"),
                    ref_range=it.get("ref_range"),
                    abnormal=bool(it.get("abnormal", False)),
                )
                .returning(r)
            )
            .mappings()
            .first()
        )
        assert row is not None
        created.append(dict(row))
    db.commit()
    return created


def list_results(db: Session, order_id: int) -> List[dict]:
    r = _results(db)
    rows = (
        db.execute(select(r).where(r.c.order_id == order_id).order_by(r.c.id.asc()))
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===

def get_patient_lab_results(db: Session, patient_id: int, limit: int = 50) -> List[dict]:
    """Получить результаты анализов пациента"""
    r = _results(db)
    o = _orders(db)
    
    # Получаем результаты через заказы пациента
    rows = (
        db.execute(
            select(r, o)
            .join(o, r.c.order_id == o.c.id)
            .where(o.c.patient_id == patient_id)
            .order_by(r.c.id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    
    return [dict(row) for row in rows]
