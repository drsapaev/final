# app/api/v1/endpoints/appointments.py
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.online_queue import load_stats, _broadcast  # Добавляем _broadcast
from app.models.setting import Setting
from app.services.online_queue import get_or_create_day
from app.crud.appointment import appointment as appointment_crud
from app.schemas import appointment as appointment_schemas
from app.models.user import User

router = APIRouter(prefix="/appointments", tags=["appointments"])


# --- helpers ---------------------------------------------------------------

def _pick_date(date_str: Optional[str], date: Optional[str], d: Optional[str]) -> str:
    """Берём дату из любого из 3х синонимов; если ничего нет — 422."""
    v = (date_str or date or d)
    if not v:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date is required (use ?date_str=YYYY-MM-DD or ?date=... or ?d=...)",
        )
    return v


def _upsert_queue_setting(db: Session, key: str, value: str) -> None:
    """Простой upsert в таблицу settings (category='queue'). Гарантируем created_at/updated_at."""
    now = datetime.utcnow()
    row = (
        db.query(Setting)
        .filter(Setting.category == "queue", Setting.key == key)
        .with_for_update(read=True)
        .first()
    )
    if row:
        row.value = value
        row.updated_at = now
    else:
        row = Setting(category="queue", key=key, value=value, created_at=now, updated_at=now)
        db.add(row)
    # коммит делать в вызывающей функции (у нас — сразу после двух апдейтов)


# --- endpoints -------------------------------------------------------------

@router.get("/", response_model=List[appointment_schemas.Appointment])
def list_appointments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None, description="Фильтр по ID пациента"),
    doctor_id: Optional[int] = Query(None, description="Фильтр по ID врача"),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Получить список записей на прием с возможностью фильтрации и пагинации
    """
    appointments = appointment_crud.get_appointments(
        db, 
        skip=skip, 
        limit=limit,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department=department,
        date_from=date_from,
        date_to=date_to
    )
    return appointments

@router.post("/", response_model=appointment_schemas.Appointment)
def create_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_in: appointment_schemas.AppointmentCreate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Создать новую запись на прием
    """
    # Проверяем, не занято ли время у врача
    if appointment_crud.is_time_slot_occupied(
        db, 
        doctor_id=appointment_in.doctor_id,
        appointment_date=appointment_in.appointment_date,
        appointment_time=appointment_in.appointment_time
    ):
        raise HTTPException(
            status_code=400,
            detail="Это время уже занято у выбранного врача"
        )
    
    appointment = appointment_crud.create_appointment(db=db, appointment=appointment_in)
    return appointment

@router.get("/{appointment_id}", response_model=appointment_schemas.Appointment)
def get_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Получить запись на прием по ID
    """
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return appointment

@router.put("/{appointment_id}", response_model=appointment_schemas.Appointment)
def update_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    appointment_in: appointment_schemas.AppointmentUpdate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Обновить запись на прием
    """
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    # Проверяем, не занято ли новое время у врача
    if (appointment_in.appointment_date or appointment_in.appointment_time or appointment_in.doctor_id):
        new_date = appointment_in.appointment_date or appointment.appointment_date
        new_time = appointment_in.appointment_time or appointment.appointment_time
        new_doctor_id = appointment_in.doctor_id or appointment.doctor_id
        
        if appointment_crud.is_time_slot_occupied(
            db, 
            doctor_id=new_doctor_id,
            appointment_date=new_date,
            appointment_time=new_time,
            exclude_appointment_id=appointment_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Это время уже занято у выбранного врача"
            )
    
    appointment = appointment_crud.update_appointment(db=db, db_obj=appointment, obj_in=appointment_in)
    return appointment

@router.delete("/{appointment_id}")
def delete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Отменить запись на прием
    """
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    appointment_crud.delete_appointment(db=db, id=appointment_id)
    return {"message": "Запись успешно отменена"}

@router.get("/doctor/{doctor_id}/schedule")
def get_doctor_schedule(
    *,
    db: Session = Depends(deps.get_db),
    doctor_id: int,
    date: str = Query(..., description="Дата (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Получить расписание врача на определенную дату
    """
    schedule = appointment_crud.get_doctor_schedule(db, doctor_id=doctor_id, date=date)
    return schedule

@router.get("/department/{department}/schedule")
def get_department_schedule(
    *,
    db: Session = Depends(deps.get_db),
    department: str,
    date: str = Query(..., description="Дата (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Получить расписание отделения на определенную дату
    """
    schedule = appointment_crud.get_department_schedule(db, department=department, date=date)
    return schedule

# Сохраняем существующие endpoints для совместимости
@router.post("/open-day", name="open_day", dependencies=[Depends(deps.require_roles("Admin"))])
def open_day(
    department: str = Query(..., description="Например ENT"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    start_number: int = Query(..., ge=0),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),  # просто чтобы токен проверился
):
    """
    Открывает день для онлайн-очереди:
    - queue::{dep}::{date}::open = 1
    - queue::{dep}::{date}::start_number = {start_number}
    (last_ticket не трогаем; будет устанавливаться по мере выдачи талонов)
    """
    key_prefix = f"{department}::{date_str}"

    _upsert_queue_setting(db, f"{key_prefix}::open", "1")
    _upsert_queue_setting(db, f"{key_prefix}::start_number", str(start_number))
    db.commit()

    # вернём понятный ответ + сводку
    stats = load_stats(db, department=department, date_str=date_str)
    # Отправляем broadcast в WebSocket
    try:
        print(f"🔔 Attempting to import _broadcast...")
        print(f"🔔 _broadcast imported successfully")
        print(f"🔔 Calling _broadcast({department}, {date_str}, stats)")
        print(f"🔔 Stats object: {stats}")
        print(f"🔔 Stats type: {type(stats)}")
        _broadcast(department, date_str, stats)
        print(f"🔔 _broadcast called successfully")
    except Exception as e:
        # Не роняем запрос, если broadcast не удался
        print(f"⚠️ Broadcast error in open_day: {e}")
        import traceback
        traceback.print_exc()
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "start_number": start_number,
        "is_open": True,
        "last_ticket": getattr(stats, "last_ticket", None),
        "waiting": getattr(stats, "waiting", None),
        "serving": getattr(stats, "serving", None),
        "done": getattr(stats, "done", None),
    }


@router.get("/stats", name="stats")
def stats(
    department: str = Query(...),
    # принимаем все варианты имени даты; внутри нормализуем к одной строке
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    eff_date = _pick_date(date_str, date, d)
    s = load_stats(db, department=department, date_str=eff_date)
    # load_stats обычно возвращает dataclass DayStats — распакуем атрибуты
    return {
        "department": department,
        "date_str": eff_date,
        "is_open": getattr(s, "is_open", False),
        "start_number": getattr(s, "start_number", 0),
        "last_ticket": getattr(s, "last_ticket", 0),
        "waiting": getattr(s, "waiting", 0),
        "serving": getattr(s, "serving", 0),
        "done": getattr(s, "done", 0),
    }


@router.post("/close", name="close_day", dependencies=[Depends(deps.require_roles("Admin"))])
def close_day(
    department: str = Query(..., description="Например ENT"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Закрывает утренний онлайн-набор (кнопка «Открыть приём сейчас»).
    Фактически выставляет OnlineDay.is_open = False для department+date.
    """
    get_or_create_day(db, department=department, date_str=date_str, open_flag=False)
    db.commit()
    s = load_stats(db, department=department, date_str=date_str)
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "is_open": s.is_open,
        "start_number": s.start_number,
        "last_ticket": s.last_ticket,
        "waiting": s.waiting,
        "serving": s.serving,
        "done": s.done,
    }


@router.get("/qrcode", name="qrcode_png")
def qrcode_png(
    department: str = Query(...),
    date_str: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    d: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_user),
):
    """
    Маршрут-заглушка: возвращаем данные для фронта, где уже рисуется QR
    (если у тебя есть реальная генерация PNG — просто замени реализацию тут).
    """
    eff_date = _pick_date(date_str, date, d)
    payload = f"{department}::{eff_date}"
    return {"format": "text", "data": payload}
