from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service import ServiceCatalog


def list_services(
    db: Session,
    *,
    q: Optional[str] = None,
    active: Optional[bool] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[ServiceCatalog]:
    stmt = select(ServiceCatalog)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (ServiceCatalog.name.ilike(like)) | (ServiceCatalog.code.ilike(like))
        )
    if active is not None:
        stmt = stmt.where(ServiceCatalog.active == active)
    stmt = stmt.order_by(ServiceCatalog.name.asc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, service_id: int) -> Optional[ServiceCatalog]:
    return db.get(ServiceCatalog, service_id)


def get_by_code(db: Session, code: str) -> Optional[ServiceCatalog]:
    if not code:
        return None
    stmt = select(ServiceCatalog).where(ServiceCatalog.code == code).limit(1)
    return db.execute(stmt).scalar_one_or_none()
