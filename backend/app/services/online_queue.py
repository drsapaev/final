from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.online import OnlineDay  # type: ignore[attr-defined]
from app.models.setting import Setting  # type: ignore[attr-defined]
from app.core.config import settings
import datetime as _dt


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


def _get_str(db: Session, key: str) -> Optional[str]:
    row = (
        db.execute(
            select(Setting).where(Setting.category == "queue", Setting.key == key)
        )
        .scalars()
        .first()
    )
    return (row.value if row and row.value is not None else None)


def _set_str(db: Session, key: str, value: str) -> None:
    row = (
        db.execute(
            select(Setting).where(Setting.category == "queue", Setting.key == key)
        )
        .scalars()
        .first()
    )
    if row:
        row.value = value
    else:
        row = Setting(category="queue", key=key, value=value)
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
    """Отправляем обновление в WebSocket комнату"""
    payload = {
        "type": "queue.update",
        "room": f"{dep}::{d}",
        "timestamp": _dt.datetime.now().isoformat(),
        "stats": {
            "start_number": stats.start_number,
            "last_ticket": stats.last_ticket,
            "waiting": stats.waiting,
            "serving": stats.serving,
            "done": stats.done,
        },
    }
    # room format должен совпадать с ws/queue_ws.py
    print(f"🔔 Broadcasting to room: {dep}::{d}")
    print(f"🔔 Payload: {payload}")
    
    mgr = _ws_manager()
    if mgr:
        try:
            print(f"🔔 WSManager получен: {type(mgr)}")
            print(f"🔔 Комнаты в WSManager: {list(mgr.rooms.keys())}")
            print(f"🔔 Целевая комната: {dep}::{d}")
            
            # broadcast - синхронная функция, не нужно create_task
            mgr.broadcast(f"{dep}::{d}", payload)
            print(f"🔔 Broadcast sent successfully")
        except Exception as e:
            print(f"❌ Broadcast error: {e}")
            import traceback
            traceback.print_exc()
            # не роняем транзакции/запрос, если рассылка не удалась
            pass
    else:
        print(f"⚠️ WSManager not available for broadcast")


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


# --- Business rules for morning online window --------------------------------

def _now_local() -> _dt.datetime:
    # простая локализация по системному времени; для точной TZ можно подключить zoneinfo
    return _dt.datetime.now()


def is_within_morning_window(*, db: Session, department: str, date_str: str) -> bool:
    """
    Окно онлайн-набора: с QUEUE_START_HOUR локального времени и до момента, когда день открыт (opened=accept) в регистратуре.
    В нашей модели OnlineDay.is_open=True означает «утренний набор открыт». После нажатия «Открыть приём» — is_open=False.
    """
    hour_start = int(getattr(settings, "QUEUE_START_HOUR", 7) or 7)
    now = _now_local()
    if now.hour < hour_start:
        return False
    day = get_or_create_day(db, department=department, date_str=date_str)
    return bool(day.is_open)


def can_issue_more_today(*, db: Session, department: str, date_str: str) -> bool:
    max_per_day = int(getattr(settings, "ONLINE_MAX_PER_DAY", 15) or 15)
    stats = load_stats(db, department=department, date_str=date_str)
    # считаем выданные как last_ticket - start_number + 1 (не меньше 0)
    issued = max(0, int(stats.last_ticket) - int(stats.start_number or 1) + 1)
    return issued < max_per_day


def get_existing_ticket_for_identity(
    *, db: Session, department: str, date_str: str, phone: Optional[str], tg_id: Optional[str]
) -> Optional[int]:
    dep = department.strip()
    d = date_str.strip()
    if phone:
        k = _k(dep, d, f"phone::{phone.strip()}")
        v = _get_str(db, k)
        if v:
            try:
                return int(v)
            except Exception:
                pass
    if tg_id:
        k = _k(dep, d, f"tg::{tg_id.strip()}")
        v = _get_str(db, k)
        if v:
            try:
                return int(v)
            except Exception:
                pass
    return None


def remember_identity_ticket(
    *, db: Session, department: str, date_str: str, phone: Optional[str], tg_id: Optional[str], ticket: int
) -> None:
    dep = department.strip()
    d = date_str.strip()
    if phone:
        _set_str(db, _k(dep, d, f"phone::{phone.strip()}"), str(int(ticket)))
    if tg_id:
        _set_str(db, _k(dep, d, f"tg::{tg_id.strip()}"), str(int(ticket)))
