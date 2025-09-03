from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import service as crud

router = APIRouter(prefix="/services", tags=["services"])


class ServiceOut(BaseModel):
    id: int
    code: Optional[str] = None
    name: str
    price: float | None = None
    currency: str | None = None
    active: bool = True


def _row_to_out(r) -> ServiceOut:
    price = None
    try:
        price = float(r.price) if r.price is not None else None
    except Exception:
        price = None
    return ServiceOut(
        id=r.id,
        code=r.code,
        name=r.name,
        price=price,
        currency=r.currency,
        active=bool(r.active),
    )


@router.get("", response_model=List[ServiceOut], summary="Каталог услуг")
async def list_services(
    db: Session = Depends(get_db),
    user=Depends(
        require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")
    ),
    q: Optional[str] = Query(default=None, max_length=120),
    active: Optional[bool] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows = crud.list_services(db, q=q, active=active, limit=limit, offset=offset)
    return [_row_to_out(r) for r in rows]
