from __future__ import annotations

from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import qrcode

from app.api.deps import get_db, require_roles
from app.services.online_queue import DayStats, get_or_create_day, load_stats

router = APIRouter(prefix="/appointments", tags=["appointments"])


class OpenIn(BaseModel):
    department: str = Field(min_length=1, max_length=64)
    date: str = Field(min_length=8, max_length=16, description="YYYY-MM-DD")
    start_number: Optional[int] = Field(default=None, ge=1)


class OpenOut(BaseModel):
    ok: bool
    department: str
    date_str: str
    start_number: Optional[int] = None
    is_open: bool


@router.post("/open", response_model=OpenOut, summary="Открыть день онлайн-очереди")
async def open_day(
    payload: OpenIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar")),
):
    row = get_or_create_day(
        db,
        department=payload.department.strip(),
        date_str=payload.date.strip(),
        start_number=payload.start_number,
        open_flag=True,
    )
    return OpenOut(
        ok=True,
        department=row.department,
        date_str=row.date_str,
        start_number=row.start_number,
        is_open=row.is_open,
    )


class StatsOut(BaseModel):
    department: str
    date_str: str
    is_open: bool
    start_number: Optional[int] = None
    last_ticket: int
    waiting: int
    serving: int
    done: int


@router.get("/stats", response_model=StatsOut, summary="Статус дня онлайн-очереди")
async def stats(
    department: str = Query(..., min_length=1, max_length=64),
    date_: str = Query(..., min_length=8, max_length=16, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")),
):
    s: DayStats = load_stats(db, department=department.strip(), date_str=date_.strip())
    return StatsOut(
        department=s.department,
        date_str=s.date_str,
        is_open=s.is_open,
        start_number=s.start_number,
        last_ticket=s.last_ticket,
        waiting=s.waiting,
        serving=s.serving,
        done=s.done,
    )


@router.get("/qrcode", summary="QR PNG на публичную форму/ссылку", response_class=Response)
async def qrcode_png(
    department: str = Query(..., min_length=1, max_length=64),
    date_: str = Query(..., min_length=8, max_length=16),
):
    content = f"queue://open?department={department.strip()}&date={date_.strip()}"
    img = qrcode.make(content)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")