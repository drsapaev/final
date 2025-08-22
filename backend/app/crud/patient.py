from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import MetaData, Table, and_, asc, desc, select
from sqlalchemy.orm import Session


def _patients(db: Session) -> Table:
    md = MetaData(bind=db.get_bind())
    return Table("patients", md, autoload_with=db.get_bind())


def get_patient_by_id(db: Session, patient_id: int) -> Optional[dict]:
    t = _patients(db)
    row = db.execute(select(t).where(t.c.id == patient_id)).mappings().first()
    return dict(row) if row else None


def search_patients(
    db: Session,
    *,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "-id",
) -> List[dict]:
    t = _patients(db)
    stmt = select(t)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (t.c.first_name.ilike(like))
            | (t.c.last_name.ilike(like))
            | (t.c.middle_name.ilike(like))
            | (t.c.phone.ilike(like))
            | (t.c.doc_number.ilike(like))
        )

    # sort
    if sort.startswith("-"):
        col = sort[1:]
        direction = desc
    else:
        col = sort
        direction = asc
    if col not in t.c:
        col = "id"

    stmt = stmt.order_by(direction(t.c[col])).limit(limit).offset(offset)
    rows = db.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


def create_patient(
    db: Session,
    *,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    birth_date: Optional[str] = None,  # YYYY-MM-DD
    gender: Optional[str] = None,
    phone: Optional[str] = None,
    doc_type: Optional[str] = None,
    doc_number: Optional[str] = None,
    address: Optional[str] = None,
) -> dict:
    t = _patients(db)
    row = (
        db.execute(
            t.insert()
            .values(
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                birth_date=birth_date,
                gender=gender,
                phone=phone,
                doc_type=doc_type,
                doc_number=doc_number,
                address=address,
            )
            .returning(t)
        )
        .mappings()
        .first()
    )
    db.commit()
    assert row is not None
    return dict(row)


def update_patient(db: Session, patient_id: int, values: Dict[str, Any]) -> Optional[dict]:
    t = _patients(db)
    clean = {k: v for k, v in values.items() if v is not None}
    row = (
        db.execute(t.update().where(t.c.id == patient_id).values(**clean).returning(t))
        .mappings()
        .first()
    )
    if not row:
        return None
    db.commit()
    return dict(row)


def delete_patient(db: Session, patient_id: int) -> bool:
    t = _patients(db)
    res = db.execute(t.delete().where(t.c.id == patient_id))
    db.commit()
    return (res.rowcount or 0) > 0