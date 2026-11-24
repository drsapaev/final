from __future__ import annotations

from datetime import datetime

from sqlalchemy import MetaData, Table, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.lab import (
    FINAL_INSTANCE_STATUSES,
    LabOrder,
    LabReportInstance,
    LabReportValue,
    LabResult,
)


def _orders(db: Session) -> Table:
    # PR-3: SQLAlchemy 2.x removed MetaData(bind=...) — use autoload only.
    md = MetaData()
    return Table("lab_orders", md, autoload_with=db.get_bind())


def _results(db: Session) -> Table:
    md = MetaData()
    return Table("lab_results", md, autoload_with=db.get_bind())


def create_order(
    db: Session,
    *,
    visit_id: int | None = None,
    patient_id: int | None = None,
    notes: str | None = None,
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


def set_order_status(db: Session, order_id: int, status_new: str) -> dict | None:
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


def add_results(db: Session, order_id: int, items: list[dict]) -> list[dict]:
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


def list_results(db: Session, order_id: int) -> list[dict]:
    r = _results(db)
    rows = (
        db.execute(select(r).where(r.c.order_id == order_id).order_by(r.c.id.asc()))
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


def get_patient_lab_results(
    db: Session,
    patient_id: int,
    limit: int | None = 50,
    offset: int = 0,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_observation: bool = False,
) -> list[dict]:
    """Read patient results and the exact released evaluation behind each projection."""
    r = LabResult.__table__
    source = LabReportInstance.__table__
    result_date = func.coalesce(source.c.finalized_at, r.c.created_at)
    date_filters = []
    if date_from is not None:
        date_filters.append(result_date >= date_from)
    if date_to is not None:
        date_filters.append(result_date <= date_to)
    rows = db.execute(
        patient_lab_results_statement(patient_id, include_observation=include_observation)
        .where(*date_filters)
        .order_by(r.c.id.desc())
        .offset(offset)
        .limit(limit)
    ).mappings().all()
    return [dict(row) for row in rows]


def patient_lab_results_statement(patient_id: int, *, include_observation: bool = False):
    """Select exact released projections and genuine unlinked legacy results."""
    r = LabResult.__table__
    o = LabOrder.__table__
    source = LabReportInstance.__table__
    root = source.alias("lab_result_root")
    value = LabReportValue.__table__
    released_statuses = sorted(FINAL_INSTANCE_STATUSES)
    observation = (
        (value.c.result_payload, value.c.value_numeric) if include_observation else ()
    )

    return (
        select(
            r,
            source.c.finalized_at.label("released_at"),
            source.c.supersedes_instance_id,
            value.c.evaluation_snapshot,
            value.c.resolved_reference_text,
            *observation,
        )
        .join(o, r.c.order_id == o.c.id)
        .outerjoin(
            source,
            and_(
                source.c.id == r.c.source_instance_id,
                source.c.patient_id == o.c.patient_id,
                source.c.order_id == o.c.id,
                source.c.status.in_(released_statuses),
            ),
        )
        .outerjoin(
            root,
            and_(
                root.c.id == r.c.source_root_instance_id,
                root.c.patient_id == o.c.patient_id,
                root.c.order_id == o.c.id,
                root.c.supersedes_instance_id.is_(None),
                root.c.status.in_(released_statuses),
            ),
        )
        .outerjoin(
            value,
            and_(
                value.c.instance_id == source.c.id,
                value.c.field_key == r.c.test_code,
            ),
        )
        .where(
            o.c.patient_id == patient_id,
            or_(
                and_(
                    r.c.source_instance_id.is_(None),
                    r.c.source_root_instance_id.is_(None),
                ),
                and_(source.c.id.is_not(None), root.c.id.is_not(None)),
            ),
        )
    )
