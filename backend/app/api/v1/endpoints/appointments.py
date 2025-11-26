# app/api/v1/endpoints/appointments.py
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List as TypingList
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.appointment import appointment as appointment_crud
from app.models.setting import Setting
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.services.online_queue import _broadcast  # Добавляем _broadcast
from app.services.online_queue import get_or_create_day, load_stats
from app.models import appointment as appointment_models
from app.services.service_mapping import get_service_code

router = APIRouter(prefix="/appointments", tags=["appointments"])


# Схема для ответа pending-payments
class PendingPaymentResponse(BaseModel):
    id: int
    patient_id: Optional[int]
    patient_name: Optional[str]
    patient_last_name: Optional[str]
    patient_first_name: Optional[str]
    doctor_id: Optional[int]
    department: Optional[str]
    appointment_date: Optional[str]
    appointment_time: Optional[str]
    status: str
    services: TypingList[str]
    services_names: TypingList[str]
    payment_amount: Optional[float]
    created_at: Optional[str]
    record_type: str
    visit_ids: Optional[TypingList[int]] = None


# --- helpers ---------------------------------------------------------------


def _pick_date(date_str: Optional[str], date: Optional[str], d: Optional[str]) -> str:
    """Берём дату из любого из 3х синонимов; если ничего нет — 422."""
    v = date_str or date or d
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
        row = Setting(
            category="queue", key=key, value=value, created_at=now, updated_at=now
        )
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
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить список записей на прием с возможностью фильтрации и пагинации
    """
    from app.models.patient import Patient
    
    appointments = appointment_crud.get_appointments(
        db,
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department=department,
        date_from=date_from,
        date_to=date_to,
    )
    
    # Обогащаем данные именами пациентов и полными наименованиями услуг
    from app.models.service import Service
    
    result = []
    for apt in appointments:
        # Получаем имя пациента
        patient_name = None
        if apt.patient_id:
            patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
            if patient:
                patient_name = patient.short_name()
            else:
                patient_name = f"Пациент #{apt.patient_id}"
        
        # Получаем полные наименования услуг
        services_with_names = []
        if apt.services and isinstance(apt.services, list):
            for service_item in apt.services:
                if isinstance(service_item, str):
                    # Если это код услуги (строка)
                    service = db.query(Service).filter(
                        (Service.code == service_item) | 
                        (Service.service_code == service_item)
                    ).first()
                    if service:
                        services_with_names.append(service.name)
                    else:
                        services_with_names.append(service_item)  # Fallback на код
                elif isinstance(service_item, dict):
                    # Если это объект с данными услуги
                    if 'name' in service_item:
                        services_with_names.append(service_item['name'])
                    elif 'code' in service_item:
                        service = db.query(Service).filter(
                            (Service.code == service_item['code']) | 
                            (Service.service_code == service_item['code'])
                        ).first()
                        if service:
                            services_with_names.append(service.name)
                        else:
                            services_with_names.append(service_item.get('code', 'Услуга'))
                    else:
                        services_with_names.append(str(service_item))
                else:
                    services_with_names.append(str(service_item))
        
        # Создаем Pydantic модель из SQLAlchemy объекта
        apt_schema = appointment_schemas.Appointment.model_validate(apt)
        # Добавляем patient_name и обновленные services через model_dump
        apt_dict = apt_schema.model_dump()
        apt_dict['patient_name'] = patient_name
        if services_with_names:
            apt_dict['services'] = services_with_names  # Заменяем коды на полные наименования
        
        result.append(apt_dict)
    
    return result


@router.post("/", response_model=appointment_schemas.Appointment)
def create_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_in: appointment_schemas.AppointmentCreate,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Создать новую запись на прием
    """
    # Проверяем, не занято ли время у врача
    if appointment_crud.is_time_slot_occupied(
        db,
        doctor_id=appointment_in.doctor_id,
        appointment_date=appointment_in.appointment_date,
        appointment_time=appointment_in.appointment_time,
    ):
        raise HTTPException(
            status_code=400, detail="Это время уже занято у выбранного врача"
        )

    appointment = appointment_crud.create(db=db, obj_in=appointment_in)
    return appointment


@router.get("/pending-payments")
async def get_pending_payments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить объединенный список записей (appointments и visits), ожидающие оплаты
    Группирует visits одного пациента в одну запись
    """
    try:
        from app.models.visit import Visit, VisitService
        from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
        from app.models.service import Service
        from app.models.patient import Patient
        from collections import defaultdict
        
        result = []
        
        # 1. Получаем appointments со статусом pending или без оплаты
        appointments_query = db.query(appointment_models.Appointment).filter(
            appointment_models.Appointment.status.in_(["scheduled", "confirmed", "pending"])
        )
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(appointment_models.Appointment.appointment_date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(appointment_models.Appointment.appointment_date <= to_date)
            except ValueError:
                pass
        
        appointments = appointments_query.order_by(appointment_models.Appointment.created_at.desc()).all()
        
        # Обрабатываем appointments
        for apt in appointments:
            # Проверяем, не оплачен ли уже
            if apt.payment_amount and apt.status == "paid":
                continue
                
            # Получаем имя пациента
            patient_name = None
            patient_last_name = None
            patient_first_name = None
            if apt.patient_id:
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_name = patient.short_name()
                    patient_last_name = patient.last_name
                    patient_first_name = patient.first_name
                else:
                    patient_name = f"Пациент #{apt.patient_id}"
            
            # Получаем коды услуг и полные наименования
            services_codes = []
            services_names = []
            if apt.services and isinstance(apt.services, list):
                for service_code in apt.services:
                    services_codes.append(service_code)
                    service = db.query(Service).filter(Service.code == service_code).first()
                    if service:
                        services_names.append(service.name)
                    else:
                        services_names.append(service_code)
            
            result.append({
                'id': apt.id,
                'patient_id': apt.patient_id,
                'patient_name': patient_name,
                'patient_last_name': patient_last_name,
                'patient_first_name': patient_first_name,
                'doctor_id': apt.doctor_id,
                'department': apt.department,
                'appointment_date': apt.appointment_date.isoformat() if apt.appointment_date else None,
                'appointment_time': apt.appointment_time,
                'status': apt.status,
                'services': services_codes,
                'services_names': services_names,
                'payment_amount': float(apt.payment_amount) if apt.payment_amount else None,
                'created_at': apt.created_at.isoformat() if apt.created_at else None,
                'record_type': 'appointment',
                'visit_ids': []
            })
        
        # 2. Получаем visits без оплаты
        visits_query = db.query(Visit).filter(
            Visit.status.in_(["pending", "confirmed", "scheduled"])
        )
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass
        
        visits = visits_query.order_by(Visit.created_at.desc()).all()
        
        # Группируем visits по patient_id и дате
        visits_by_patient = defaultdict(lambda: {
            'patient_id': None,
            'patient_name': None,
            'patient_last_name': None,
            'patient_first_name': None,
            'doctor_id': None,
            'department': None,
            'appointment_date': None,
            'appointment_time': None,
            'status': 'pending',
            'services': [],
            'services_names': [],
            'payment_amount': None,
            'created_at': None,
            'record_type': 'visit',
            'visit_ids': []
        })
        
        for visit in visits:
            # Проверяем, не оплачен ли уже через PaymentInvoice
            paid_invoices = db.query(PaymentInvoiceVisit).join(PaymentInvoice).filter(
                PaymentInvoiceVisit.visit_id == visit.id,
                PaymentInvoice.status == "paid"
            ).first()
            
            if paid_invoices:
                continue  # Уже оплачен
            
            # Группируем по patient_id и дате (visit_date или created_at.date())
            visit_date = visit.visit_date
            if not visit_date and visit.created_at:
                visit_date = visit.created_at.date()
            
            # Ключ для группировки: patient_id + дата
            group_key = (visit.patient_id, visit_date.isoformat() if visit_date else None)
            
            if group_key not in visits_by_patient:
                # Получаем имя пациента
                patient_name = None
                patient_last_name = None
                patient_first_name = None
                if visit.patient_id:
                    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                    if patient:
                        patient_name = patient.short_name()
                        patient_last_name = patient.last_name
                        patient_first_name = patient.first_name
                
                visits_by_patient[group_key] = {
                    'patient_id': visit.patient_id,
                    'patient_name': patient_name,
                    'patient_last_name': patient_last_name,
                    'patient_first_name': patient_first_name,
                    'doctor_id': visit.doctor_id,
                    'department': visit.department,
                    'appointment_date': visit_date.isoformat() if visit_date else None,
                    'appointment_time': visit.visit_time.strftime('%H:%M') if visit.visit_time and hasattr(visit.visit_time, 'strftime') else (visit.visit_time if visit.visit_time else None),
                    'status': visit.status,
                    'services': [],
                    'services_names': [],
                    'payment_amount': None,
                    'created_at': visit.created_at.isoformat() if visit.created_at else None,
                    'record_type': 'visit',
                    'visit_ids': []
                }
            
            # Добавляем услуги визита
            visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            for vs in visit_services:
                if vs.code and vs.code not in visits_by_patient[group_key]['services']:
                    visits_by_patient[group_key]['services'].append(vs.code)
                    visits_by_patient[group_key]['services_names'].append(vs.name)
            
            visits_by_patient[group_key]['visit_ids'].append(visit.id)
        
        # Добавляем сгруппированные visits в результат
        for group_data in visits_by_patient.values():
            result.append(group_data)
        
        # Применяем пагинацию
        total = len(result)
        result = result[skip:skip + limit]
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения записей: {str(e)}"
        )


@router.get("/{appointment_id}", response_model=appointment_schemas.Appointment)
def get_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
):
    """
    Обновить запись на прием
    """
    appointment = appointment_crud.get_appointment(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем, не занято ли новое время у врача
    if (
        appointment_in.appointment_date
        or appointment_in.appointment_time
        or appointment_in.doctor_id
    ):
        new_date = appointment_in.appointment_date or appointment.appointment_date
        new_time = appointment_in.appointment_time or appointment.appointment_time
        new_doctor_id = appointment_in.doctor_id or appointment.doctor_id

        if appointment_crud.is_time_slot_occupied(
            db,
            doctor_id=new_doctor_id,
            appointment_date=new_date,
            appointment_time=new_time,
            exclude_appointment_id=appointment_id,
        ):
            raise HTTPException(
                status_code=400, detail="Это время уже занято у выбранного врача"
            )

    appointment = appointment_crud.update_appointment(
        db=db, db_obj=appointment, obj_in=appointment_in
    )
    return appointment


@router.delete("/{appointment_id}")
def delete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
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
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить расписание отделения на определенную дату
    """
    schedule = appointment_crud.get_department_schedule(
        db, department=department, date=date
    )
    return schedule


# Сохраняем существующие endpoints для совместимости
@router.post(
    "/open-day", name="open_day", dependencies=[Depends(deps.require_roles("Admin"))]
)
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
        print("🔔 Attempting to import _broadcast...")
        print("🔔 _broadcast imported successfully")
        print(f"🔔 Calling _broadcast({department}, {date_str}, stats)")
        print(f"🔔 Stats object: {stats}")
        print(f"🔔 Stats type: {type(stats)}")
        _broadcast(department, date_str, stats)
        print("🔔 _broadcast called successfully")
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


@router.post(
    "/close", name="close_day", dependencies=[Depends(deps.require_roles("Admin"))]
)
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


@router.get("/pending-payments")
async def get_pending_payments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить объединенный список записей (appointments и visits), ожидающие оплаты
    Группирует visits одного пациента в одну запись
    """
    try:
        from app.models.visit import Visit, VisitService
        from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
        from app.models.service import Service
        from app.models.patient import Patient
        from collections import defaultdict
        
        result = []
        
        # 1. Получаем appointments со статусом pending или без оплаты
        appointments_query = db.query(appointment_models.Appointment).filter(
            appointment_models.Appointment.status.in_(["scheduled", "confirmed", "pending"])
        )
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(appointment_models.Appointment.appointment_date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(appointment_models.Appointment.appointment_date <= to_date)
            except ValueError:
                pass
        
        appointments = appointments_query.order_by(appointment_models.Appointment.created_at.desc()).all()
        
        # Обрабатываем appointments
        for apt in appointments:
            # Проверяем, не оплачен ли уже
            if apt.payment_amount and apt.status == "paid":
                continue
                
            # Получаем имя пациента
            patient_name = None
            patient_last_name = None
            patient_first_name = None
            if apt.patient_id:
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_name = patient.short_name()
                    patient_last_name = patient.last_name
                    patient_first_name = patient.first_name
                else:
                    patient_name = f"Пациент #{apt.patient_id}"
            
            # Получаем коды услуг и полные наименования
            services_codes = []
            services_names = []
            if apt.services and isinstance(apt.services, list):
                for service_item in apt.services:
                    if isinstance(service_item, str):
                        service = db.query(Service).filter(
                            (Service.code == service_item) | 
                            (Service.service_code == service_item)
                        ).first()
                        if service:
                            # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                            service_code = get_service_code(service.id, db) or service.code or service_item
                            services_codes.append(service_code)
                            services_names.append(service.name)
                        else:
                            services_codes.append(service_item)
                            services_names.append(service_item)
                    elif isinstance(service_item, dict):
                        code = service_item.get('code') or service_item.get('service_code') or str(service_item)
                        if 'name' in service_item:
                            services_codes.append(code)
                            services_names.append(service_item['name'])
                        elif 'code' in service_item:
                            service = db.query(Service).filter(
                                (Service.code == service_item['code']) | 
                                (Service.service_code == service_item['code'])
                            ).first()
                            if service:
                                # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                                service_code = get_service_code(service.id, db) or service.code or service_item['code']
                                services_codes.append(service_code)
                                services_names.append(service.name)
                            else:
                                services_codes.append(code)
                                services_names.append(code)
                        else:
                            services_codes.append(str(service_item))
                            services_names.append(str(service_item))
                    else:
                        services_codes.append(str(service_item))
                        services_names.append(str(service_item))
            
            apt_dict = {
                "id": int(apt.id),
                "patient_id": int(apt.patient_id) if apt.patient_id else None,
                "patient_name": str(patient_name) if patient_name else None,
                "patient_last_name": str(patient_last_name) if patient_last_name else None,
                "patient_first_name": str(patient_first_name) if patient_first_name else None,
                "doctor_id": int(apt.doctor_id) if apt.doctor_id else None,
                "department": str(apt.department) if apt.department else None,
                "appointment_date": apt.appointment_date.isoformat() if apt.appointment_date else None,
                "appointment_time": str(apt.appointment_time) if apt.appointment_time else None,
                "status": str(apt.status),
                "services": [str(s) for s in services_codes] if services_codes else [],
                "services_names": [str(s) for s in services_names] if services_names else [],
                "payment_amount": float(apt.payment_amount) if apt.payment_amount else None,
                "created_at": apt.created_at.isoformat() if apt.created_at else None,
                "record_type": "appointment",
                "visit_ids": []  # Для appointments visit_ids всегда пустой
            }
            result.append(apt_dict)
        
        # 2. Получаем visits, ожидающие оплаты
        visits_query = db.query(Visit).filter(
            Visit.discount_mode != "all_free"  # Не бесплатные
        )
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass
        
        visits = visits_query.order_by(Visit.created_at.desc()).all()
        
        # Группируем visits по patient_id и visit_date (или created_at в один день)
        visits_by_patient = defaultdict(lambda: {
            'visits': [],
            'patient_id': None,
            'patient_name': None,
            'patient_last_name': None,
            'patient_first_name': None,
            'visit_date': None,
            'created_at': None,
            'services_codes': [],
            'services_names': [],
            'total_amount': 0,
            'visit_ids': []
        })
        
        for visit in visits:
            # Проверяем, не оплачен ли уже через PaymentInvoice
            paid_invoices = db.query(PaymentInvoiceVisit).join(PaymentInvoice).filter(
                PaymentInvoiceVisit.visit_id == visit.id,
                PaymentInvoice.status == "paid"
            ).first()
            
            if paid_invoices:
                continue  # Уже оплачен
            
            # Группируем по patient_id и дате (visit_date или created_at.date())
            visit_date = visit.visit_date
            if not visit_date and visit.created_at:
                visit_date = visit.created_at.date()
            
            # Ключ для группировки: patient_id + дата
            group_key = (visit.patient_id, visit_date.isoformat() if visit_date else None)
            
            if group_key not in visits_by_patient:
                # Получаем данные пациента (один раз для группы)
                patient_name = None
                patient_last_name = None
                patient_first_name = None
                if visit.patient_id:
                    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                    if patient:
                        patient_name = patient.short_name()
                        patient_last_name = patient.last_name
                        patient_first_name = patient.first_name
                    else:
                        patient_name = f"Пациент #{visit.patient_id}"
                
                visits_by_patient[group_key] = {
                    'visits': [],
                    'patient_id': visit.patient_id,
                    'patient_name': patient_name,
                    'patient_last_name': patient_last_name,
                    'patient_first_name': patient_first_name,
                    'visit_date': visit_date,
                    'created_at': visit.created_at,
                    'services_codes': [],
                    'services_names': [],
                    'total_amount': 0,
                    'visit_ids': []
                }
            
            visits_by_patient[group_key]['visits'].append(visit)
            visits_by_patient[group_key]['visit_ids'].append(visit.id)
            # Обновляем created_at на самый ранний
            if visit.created_at and (not visits_by_patient[group_key]['created_at'] or 
                                     visit.created_at < visits_by_patient[group_key]['created_at']):
                visits_by_patient[group_key]['created_at'] = visit.created_at
        
        # Обрабатываем сгруппированные visits
        for group_key, group_data in visits_by_patient.items():
            # Собираем все услуги из всех visits группы
            all_services_codes = []
            all_services_names = []
            total_amount = 0
            
            for visit in group_data['visits']:
                # Получаем услуги визита
                visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
                
                for vs in visit_services:
                    # Получаем код услуги (приоритет: service_code из Service)
                    service_code = vs.code
                    if not service_code:
                        service = db.query(Service).filter(Service.id == vs.service_id).first()
                        if service:
                            # Используем service_code (D01, K01, etc.) или code как fallback
                            # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                            service_code = get_service_code(vs.service_id, db) or service.code or f"S{vs.service_id}"
                    
                    service_name = vs.name
                    if not service_name:
                        service = db.query(Service).filter(Service.id == vs.service_id).first()
                        if service:
                            service_name = service.name
                        else:
                            service_name = f"Услуга #{vs.service_id}"
                    
                    # Добавляем код и наименование (избегаем дубликатов)
                    if service_code not in all_services_codes:
                        all_services_codes.append(service_code or f"S{vs.service_id}")
                        all_services_names.append(service_name)
                    
                    # Суммируем стоимость
                    if vs.price:
                        total_amount += float(vs.price) * vs.qty
            
            # Создаем одну запись для группы visits
            # Проверяем, что visit_ids не пустой перед вызовом min()
            if not group_data['visit_ids']:
                continue  # Пропускаем группы без visits
            
            visit_dict = {
                "id": int(min(group_data['visit_ids']) + 20000),  # Используем минимальный ID из группы
                "patient_id": int(group_data['patient_id']) if group_data['patient_id'] else None,
                "patient_name": str(group_data['patient_name']) if group_data['patient_name'] else None,
                "patient_last_name": str(group_data['patient_last_name']) if group_data['patient_last_name'] else None,
                "patient_first_name": str(group_data['patient_first_name']) if group_data['patient_first_name'] else None,
                "doctor_id": None,  # Может быть разным для разных visits
                "department": None,  # Может быть разным
                "appointment_date": group_data['visit_date'].isoformat() if group_data['visit_date'] else None,
                "appointment_time": None,  # Может быть разным
                "status": "pending",
                "services": [str(s) for s in all_services_codes] if all_services_codes else [],
                "services_names": [str(s) for s in all_services_names] if all_services_names else [],
                "payment_amount": float(total_amount) if total_amount > 0 else None,
                "created_at": group_data['created_at'].isoformat() if group_data['created_at'] else None,
                "record_type": "visit",
                "visit_ids": [int(vid) for vid in group_data['visit_ids']] if group_data['visit_ids'] else []  # Сохраняем все ID для обработки оплаты
            }
            result.append(visit_dict)
        
        # Сортируем по дате создания
        result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        # Применяем пагинацию
        paginated_result = result[skip:skip + limit]
        
        # Убеждаемся, что все данные JSON-совместимы
        json_result = []
        for item in paginated_result:
            json_item = {}
            for key, value in item.items():
                if value is None:
                    json_item[key] = None
                elif isinstance(value, (str, int, float, bool)):
                    json_item[key] = value
                elif isinstance(value, list):
                    json_item[key] = [str(v) if not isinstance(v, (str, int, float, bool)) else v for v in value]
                else:
                    json_item[key] = str(value)
            json_result.append(json_item)
        
        return json_result
    
    except Exception as e:
        import logging
        logging.error(f"Error in get_pending_payments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении записей, ожидающих оплаты: {str(e)}"
        )
