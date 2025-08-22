from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import audit as crud

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditOut(BaseModel):
    id: int
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: str


def _row_to_out(r) -> AuditOut:
    # created_at как ISO строка
    created = r.created_at.isoformat() if hasattr(r, "created_at") and r.created_at else ""
    return AuditOut(
        id=r.id,
        action=r.action,
        entity_type=r.entity_type,
        entity_id=r.entity_id,
        actor_user_id=r.actor_user_id,
        payload=r.payload,
        created_at=created,
    )


@router.get("", response_model=List[AuditOut], summary="Список аудита c фильтрами")
async def list_audit(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier")),
    action: Optional[str] = Query(default=None, max_length=64),
    entity_type: Optional[str] = Query(default=None, max_length=64),
    entity_id: Optional[int] = Query(default=None, ge=1),
    actor_user_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows = crud.list_logs(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        limit=limit,
        offset=offset,
    )
    return [_row_to_out(r) for r in rows]