from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.online import OnlineDay  # type: ignore[attr-defined]
from app.models.setting import Setting  # type: ignore[attr-defined]


# ЛЕНИВЫЙ импорт менеджера WS, чтобы избежать циклов импорта при старте приложения
def _ws_manager():
    try:
        from app.ws.queue_ws import ws_manager  # импорт только в момент использования
        return ws_manager
    except Exception:
        return None


@dataclass
class DayStats:
    department: str
    date_str: str
    is_open: bool
    start_number: Optional[int]
    last_ticket: int
    waiting: int
    serving: int
    done: int


# --- helpers for key/value counters stored in settings (category="queue") ---

def _k(dep: str, date_str: str, name: str) -> str:
    return f"{dep.strip()}::{date_str.strip()}::{name}"


def _get_int(db: Session, key: str, default: int = 0) -> int:
    row = (
        db.execute(
            select(Setting).where(Setting.category == "queue", Setting.key == key)
        )
        .scalars()
        .first()
    )
    if not row or row.value is None:
        return default
    try:
        return int(str(row.value).strip())
    except Exception:
        return default


def _set_int(db: Session, key: str, value: int) -> None:
    row = (
        db.execute(
            select(Setting).where(Setting.category == "queue", Setting.key == key)
        )
        .scalars()
        .first()
    )
    if row:
        row.value = str(int(value))
    else:
        row = Setting(category="queue", key=key, value=str(int(value)))
        db.add(row)


def get_or_create_day(
    db: Session,
    *,
    department: str,
    date_str: str,
    start_number: Optional[int] = None,
    open_flag: Optional[bool] = None,
) -> OnlineDay:
    dep = department.strip()
    d = date_str.strip()
    row = (
        db.execute(
            select(OnlineDay).where(OnlineDay.department == dep, OnlineDay.date_str == d)
        )
        .scalars()
        .first()
    )
    if not row:
        row = OnlineDay(
            department=dep,
            date_str=d,
            start_number=start_number or 1,
            is_open=bool(open_flag if open_flag is not None else True),
        )
        db.add(row)
        db.flush()
    changed = False
    if start_number is not None and row.start_number != start_number:
        row.start_number = start_number
        changed = True
    if open_flag is not None and row.is_open != bool(open_flag):
        row.is_open = bool(open_flag)
        changed = True
    if changed:
        db.flush()
    return row


def load_stats(db: Session, *, department: str, date_str: str) -> DayStats:
    dep = department.strip()
    d = date_str.strip()
    day = get_or_create_day(db, department=dep, date_str=d)
    last_ticket = _get_int(db, _k(dep, d, "last_ticket"), (day.start_number or 1) - 1)
    waiting = _get_int(db, _k(dep, d, "waiting"), 0)
    serving = _get_int(db, _k(dep, d, "serving"), 0)
    done = _get_int(db, _k(dep, d, "done"), 0)
    return DayStats(
        department=dep,
        date_str=d,
        is_open=bool(day.is_open),
        start_number=day.start_number,
        last_ticket=int(last_ticket),
        waiting=int(waiting),
        serving=int(serving),
        done=int(done),
    )


def _broadcast(dep: str, d: str, stats: DayStats) -> None:
    payload = {
        "type": "queue.update",
        "room": f"{dep}::{d}",
        "payload": {
            "department": stats.department,
            "date_str": stats.date_str,
            "is_open": stats.is_open,
            "start_number": stats.start_number,
            "last_ticket": stats.last_ticket,
            "waiting": stats.waiting,
            "serving": stats.serving,
            "done": stats.done,
        },
    }
    # room format должен совпадать с ws/queue_ws.py
    mgr = _ws_manager()
    if mgr:
        try:
            asyncio.create_task(mgr.broadcast(f"{dep}::{d}", payload))
        except Exception:
            # не роняем транзакции/запрос, если рассылка не удалась
            pass


def issue_next_ticket(db: Session, *, department: str, date_str: str) -> tuple[int, DayStats]:
    dep = department.strip()
    d = date_str.strip()
    day = get_or_create_day(db, department=dep, date_str=d)

    last_ticket = _get_int(db, _k(dep, d, "last_ticket"), (day.start_number or 1) - 1)
    # следующий номер
    next_ticket = max(last_ticket, (day.start_number or 1) - 1) + 1
    _set_int(db, _k(dep, d, "last_ticket"), next_ticket)

    waiting = _get_int(db, _k(dep, d, "waiting"), 0) + 1
    _set_int(db, _k(dep, d, "waiting"), waiting)

    # serving/done не меняем
    db.flush()
    db.commit()

    stats = load_stats(db, department=dep, date_str=d)
    _broadcast(dep, d, stats)
    return next_ticket, stats
