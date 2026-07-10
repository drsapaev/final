from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service import Service, ServiceCatalog


def list_services(
    db: Session,
    *,
    q: str | None = None,
    active: bool | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Service]:
    stmt = select(Service)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Service.name.ilike(like)) | (Service.code.ilike(like)))
    if active is not None:
        stmt = stmt.where(Service.active == active)
    stmt = stmt.order_by(Service.name.asc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def get_by_id(db: Session, service_id: int) -> Service | None:
    return db.get(Service, service_id)


def get_by_code(db: Session, code: str) -> Service | None:
    if not code:
        return None
    stmt = select(Service).where(Service.code == code).limit(1)
    return db.execute(stmt).scalar_one_or_none()


# Для обратной совместимости со старым ServiceCatalog
def list_service_catalog(
    db: Session,
    *,
    q: str | None = None,
    active: bool | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[ServiceCatalog]:
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


# === PR-1: Mobile API wrappers ===

from sqlalchemy import func as _func
from sqlalchemy.orm import Session as _Session

from app.models.clinic import ServiceCategory


def search_services(
    db: _Session,
    *,
    category: str | None = None,
    name: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    limit: int = 20,
) -> list[Service]:
    """Search services by category id/name and/or name + price range.

    ``category`` may be either an int (ServiceCategory.id) or a string
    (matched against ServiceCategory.code/name_ru). For PR-1 we keep the
    signature loose to preserve the endpoint contract.
    """
    stmt = select(Service)
    if name:
        like = f"%{name}%"
        stmt = stmt.where((Service.name.ilike(like)) | (Service.code.ilike(like)))
    if category is not None:
        # Resolve to a category id if a string name/code was provided.
        cat_id: int | None = None
        if isinstance(category, int):
            cat_id = category
        else:
            cat_stmt = select(ServiceCategory).where(
                (ServiceCategory.code == category)
                | (ServiceCategory.name_ru == category)
            )
            cat = db.execute(cat_stmt).scalar_one_or_none()
            cat_id = cat.id if cat is not None else None
        if cat_id is not None:
            stmt = stmt.where(Service.category_id == cat_id)
    if price_min is not None:
        stmt = stmt.where(Service.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Service.price <= price_max)
    stmt = stmt.where(Service.active == True).order_by(Service.name.asc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_service_doctors_count(db: _Session, service_id: int) -> int:
    """PR-1: Service has a single doctor via ``doctor_id`` — return 1 or 0."""
    svc = db.get(Service, service_id)
    if svc is None:
        return 0
    return 1 if svc.doctor_id else 0


def count_services_in_category(db: _Session, category_id: int) -> int:
    """Count active services in a category by ``category_id``."""
    stmt = (
        select(_func.count())
        .select_from(Service)
        .where(Service.category_id == category_id, Service.active == True)
    )
    return int(db.execute(stmt).scalar_one() or 0)


def get_category_avg_price(db: _Session, category_id: int) -> float:
    """Return average ``Service.price`` for a category, or 0.0 if no services."""
    stmt = (
        select(_func.avg(Service.price))
        .where(Service.category_id == category_id, Service.active == True)
    )
    result = db.execute(stmt).scalar_one()
    if result is None:
        return 0.0
    return float(result)
