from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import setting as crud
from app.schemas.setting import SettingRowOut, SettingUpsertIn  # type: ignore[attr-defined]

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=List[SettingRowOut], summary="Список настроек")
async def list_settings(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")),
    category: Optional[str] = Query(default=None, max_length=64),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    rows = crud.list_settings(db, category=category, limit=limit, offset=offset)
    return [SettingRowOut(category=r.category, key=r.key, value=r.value) for r in rows]


@router.put("/{category}/{key}", response_model=SettingRowOut, summary="Создать/обновить настройку")
async def upsert_setting(
    payload: SettingUpsertIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
    category: str = Path(..., min_length=1, max_length=64),
    key: str = Path(..., min_length=1, max_length=128),
):
    if payload.category != category or payload.key != key:
        raise HTTPException(status_code=400, detail="Category/key mismatch")
    row = crud.upsert_setting(db, category=category, key=key, value=payload.value)
    return SettingRowOut(category=row.category, key=row.key, value=row.value)


@router.delete("/{category}/{key}", summary="Удалить настройку")
async def delete_setting(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
    category: str = Path(..., min_length=1, max_length=64),
    key: str = Path(..., min_length=1, max_length=128),
):
    ok = crud.delete_setting(db, category=category, key=key)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}