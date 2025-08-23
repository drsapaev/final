from __future__ import annotations

from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import qrcode

from app.api.deps import get_db, get_current_user, require_roles
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


@router.post("/open", dependencies=[Depends(require_roles("Admin"))])
def open_day(
    department: str = Query(...),
    date_str: str = Query(...),
    start_number: int = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # create or open the day using the existing service and return a typed response
    day = get_or_create_day(db=db, department=department.strip(), date_str=date_str.strip(), start_number=start_number)
    return OpenOut(
        ok=True,
        department=day.department,
        date_str=day.date_str,
        start_number=getattr(day, "start_number", None),
        is_open=bool(getattr(day, "is_open", False)),
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