from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.crud import (
    appointment as appointment_crud,
    patient as patient_crud,
    service as service_crud,
    visit as visit_crud,
)
from app.models.user import User
from app.schemas.appointment import Appointment, AppointmentCreate
from app.schemas.patient import Patient, PatientUpdate
from app.schemas.service import Service
from app.schemas.visit import Visit, VisitCreate, VisitUpdate, VisitWithServices
from app.services.visit_payment_integration import VisitPaymentIntegrationService

router = APIRouter()


# Мобильные эндпоинты для пациентов
@router.get("/profile", response_model=Patient)
async def get_mobile_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Получение профиля пациента для мобильного приложения"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    patient = patient_crud.get(db, id=current_user.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    return patient


@router.put("/profile", response_model=Patient)
async def update_mobile_profile(
    patient_update: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление профиля пациента через мобильное приложение"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    patient = patient_crud.get(db, id=current_user.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    return patient_crud.update(db, db_obj=patient, obj_in=patient_update)


@router.get("/visits", response_model=List[VisitWithServices])
async def get_mobile_visits(
    status: Optional[str] = Query(None, description="Статус визита"),
    limit: int = Query(20, le=100, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение списка визитов пациента для мобильного приложения"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    visits = visit_crud.get_multi_by_patient(
        db,
        patient_id=current_user.patient_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return visits


@router.get("/visits/{visit_id}", response_model=VisitWithServices)
async def get_mobile_visit(
    visit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение детальной информации о визите"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    visit = visit_crud.get(db, id=visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Визит не найден")

    if visit.patient_id != current_user.patient_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return visit


@router.post("/visits", response_model=Visit)
async def create_mobile_visit(
    visit_create: VisitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создание нового визита через мобильное приложение"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    # Устанавливаем ID пациента из текущего пользователя
    visit_data = visit_create.dict()
    visit_data["patient_id"] = current_user.patient_id

    return visit_crud.create(db, obj_in=VisitCreate(**visit_data))


@router.put("/visits/{visit_id}/reschedule")
async def reschedule_mobile_visit(
    visit_id: int,
    new_date: datetime = Query(..., description="Новая дата визита"),
    notes: Optional[str] = Query(None, description="Заметки о переносе"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Перенос визита через мобильное приложение"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    visit = visit_crud.get(db, id=visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Визит не найден")

    if visit.patient_id != current_user.patient_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Проверяем, что новая дата в будущем
    if new_date <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Новая дата должна быть в будущем")

    # Обновляем визит
    visit_update = VisitUpdate(
        date=new_date,
        notes=f"{visit.notes or ''}\n[Перенесено: {datetime.utcnow().isoformat()}] {notes or ''}",
    )

    updated_visit = visit_crud.update(db, db_obj=visit, obj_in=visit_update)
    return {"message": "Визит успешно перенесён", "visit": updated_visit}


@router.get("/appointments", response_model=List[Appointment])
async def get_mobile_appointments(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Получение списка записей пациента"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    appointments = appointment_crud.get_multi_by_patient(
        db, patient_id=current_user.patient_id
    )
    return appointments


@router.post("/appointments", response_model=Appointment)
async def create_mobile_appointment(
    appointment_create: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создание новой записи через мобильное приложение"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    # Устанавливаем ID пациента из текущего пользователя
    appointment_data = appointment_create.dict()
    appointment_data["patient_id"] = current_user.patient_id

    return appointment_crud.create(db, obj_in=AppointmentCreate(**appointment_data))


@router.get("/services", response_model=List[Service])
async def get_mobile_services(db: Session = Depends(get_db)):
    """Получение списка доступных услуг для мобильного приложения"""
    services = service_crud.get_multi(db)
    return services


@router.get("/payment-status/{visit_id}")
async def get_mobile_payment_status(
    visit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение статуса оплаты визита"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    visit = visit_crud.get(db, id=visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Визит не найден")

    if visit.patient_id != current_user.patient_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Получаем информацию о платеже
    success, message, payment_info = (
        VisitPaymentIntegrationService.get_visit_payment_info(db, visit_id)
    )

    if not success:
        return {"visit_id": visit_id, "payment_status": "unknown", "message": message}

    return {
        "visit_id": visit_id,
        "payment_status": payment_info.get("payment_status", "unknown"),
        "amount": payment_info.get("payment_amount"),
        "currency": payment_info.get("payment_currency"),
        "provider": payment_info.get("payment_provider"),
        "transaction_id": payment_info.get("payment_transaction_id"),
        "processed_at": payment_info.get("payment_processed_at"),
    }


@router.get("/queue-status")
async def get_mobile_queue_status(
    department: str = Query(..., description="Отделение"),
    date: str = Query(..., description="Дата в формате YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение статуса очереди для мобильного приложения"""
    if not current_user.patient_id:
        raise HTTPException(
            status_code=400, detail="Пользователь не связан с пациентом"
        )

    try:
        # Парсим дату
        queue_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    # Получаем статистику очереди
    from app.api.v1.endpoints.online_queue import get_queue_stats

    queue_stats = await get_queue_stats(department=department, date=date, db=db)

    return {
        "department": department,
        "date": date,
        "queue_stats": queue_stats,
        "estimated_wait_time": "15-30 минут",  # Примерное время ожидания
    }


# Публичные эндпоинты (без аутентификации)
@router.get("/public/services", response_model=List[Service])
async def get_public_services(db: Session = Depends(get_db)):
    """Получение списка услуг без аутентификации"""
    services = service_crud.get_multi(db)
    return services


@router.get("/public/health")
async def mobile_health_check():
    """Проверка здоровья мобильного API"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }
