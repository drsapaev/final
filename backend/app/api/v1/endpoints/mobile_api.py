"""
Мобильные API endpoints для PWA
"""

import gzip
import json
from datetime import datetime, UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud import (
    appointment as crud_appointment,
)
from app.crud import (
    lab as crud_lab,
)
from app.crud import (
    notification as crud_notification,
)
from app.crud import (
    patient as crud_patient,
)
from app.crud import (
    user as crud_user,
)
from app.crud.patient import get_patient_by_user_id
from app.db.session import get_db
from app.services.notification_platform_service import get_notification_platform_service
from app.schemas.mobile import (
    AppointmentUpcomingOut,
    BookAppointmentRequest,
    LabResultOut,
    MobileAppointmentDetailOut,
    MobileLoginRequest,
    MobileLoginResponse,
    MobileQuickStats,
    PatientProfileOut,
)
from app.services.mobile_api_service import MobileApiService
from app.services.notifications import notification_sender_service

router = APIRouter()


# Функция для сжатия JSON ответов (будет использоваться в endpoints)
def compress_json_response(data: dict) -> Response:
    """Сжимает JSON ответ если он большой"""
    json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')

    if len(json_data) > 1024:  # Сжимаем только большие ответы
        compressed_data = gzip.compress(json_data)
        return Response(
            content=compressed_data,
            media_type="application/json",
            headers={
                "Content-Encoding": "gzip",
                "Content-Length": str(len(compressed_data)),
            },
        )
    else:
        return JSONResponse(content=data)


def _get_mobile_notification_rows(
    db: Session,
    *,
    user_id: int,
    patient_id: int | None,
    limit: int,
    offset: int,
) -> list[dict]:
    """Fetch notifications via the canonical notification platform.

    Previously this queried the legacy NotificationHistory table directly.
    Now uses notification_platform_service.get_inbox() which reads from
    NotificationEvent/NotificationDelivery (the canonical platform tables).
    """
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []

    platform = get_notification_platform_service(db)
    result = platform.get_inbox(
        current_user=user,
        status="all",
        limit=limit,
    )
    # NOTIF-REAUDIT-28 P0-1: get_inbox returns "items" key, not "deliveries".
    # Раньше всегда возвращался пустой список — мобильное приложение не
    # показывало уведомления.
    items = result.get("items", [])
    # Apply offset manually since get_inbox uses cursor-based pagination
    return items[offset:offset + limit] if items else []


@router.post("/mobile/auth/login", response_model=MobileLoginResponse)
async def mobile_login(credentials: MobileLoginRequest, db: Session = Depends(get_db)):
    """
    Мобильная аутентификация

    Поддерживает:
    - Вход по номеру телефона и паролю
    - Вход через Telegram ID
    - Регистрация нового пользователя
    """
    try:
        # Поиск пользователя по телефону или Telegram ID
        user = None
        patient = None

        if credentials.phone:
            patient = crud_patient.get_patient_by_phone(db, phone=credentials.phone)
            user = patient.user if patient and patient.user else None
        elif credentials.telegram_id:
            raise HTTPException(
                status_code=400, detail="Telegram login requires a verified link"
            )

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not credentials.password or not user.hashed_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not crud_user.verify_password(credentials.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Генерируем токен
        access_token = crud_user.create_access_token(data={"sub": user.username})

        # Обновляем токен устройства
        if credentials.device_token:
            MobileApiService(db).update_user_device_token(
                user=user,
                device_token=credentials.device_token,
            )

        return MobileLoginResponse(
            access_token=access_token,
            expires_in=3600,  # 1 час
            user={
                "id": user.id,
                "username": user.username,
                "phone": patient.phone if patient else None,
                "role": user.role,
                "is_active": user.is_active,
            },
            permissions=crud_user.get_user_permissions(user),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/patients/me", response_model=PatientProfileOut)
async def get_mobile_patient_profile(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """Профиль пациента для мобильного приложения"""
    try:
        # Получаем профиль пациента
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Получаем статистику
        upcoming_appointments = crud_appointment.count_upcoming_appointments(
            db, patient_id=patient.id
        )

        total_visits = crud_appointment.count_patient_visits(db, patient_id=patient.id)

        last_visit = crud_appointment.get_last_visit(db, patient_id=patient.id)

        return PatientProfileOut(
            id=patient.id,
            fio=patient.fio,
            phone=patient.phone,
            birth_year=patient.birth_year,
            address=patient.address,
            telegram_id=patient.telegram_id,
            created_at=patient.created_at,
            last_visit=last_visit.appointment_date if last_visit else None,
            total_visits=total_visits,
            upcoming_appointments=upcoming_appointments,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/appointments/upcoming", response_model=list[AppointmentUpcomingOut])
async def get_upcoming_appointments(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """Предстоящие записи пациента"""
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        appointments = crud_appointment.get_upcoming_appointments(
            db, patient_id=patient.id, limit=limit, offset=offset
        )

        result = []
        for appointment in appointments:
            services = [service.service.title for service in appointment.services]  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use

            result.append(
                AppointmentUpcomingOut(
                    id=appointment.id,
                    doctor_name=appointment.doctor.name,
                    specialty=appointment.doctor.specialty or "Врач",
                    appointment_date=appointment.appointment_date,
                    status=appointment.status,
                    clinic_address="Главный филиал",
                )
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/appointments/{appointment_id}", response_model=MobileAppointmentDetailOut)
async def get_appointment_detail(
    appointment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Детальная информация о записи"""
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        appointment = crud_appointment.get_appointment(
            db, appointment_id=appointment_id
        )

        if not appointment or appointment.patient_id != patient.id:
            raise HTTPException(status_code=404, detail="Запись не найдена")

        services = []
        for service in appointment.services:
            services.append(
                {
                    "id": service.service_id,
                    "title": service.service.title,
                    "price": service.price,
                    "quantity": service.quantity,
                }
            )

        return MobileAppointmentDetailOut(
            id=appointment.id,
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            doctor_name=appointment.doctor.name,
            specialty=appointment.doctor.specialty or "Врач",
            appointment_date=appointment.appointment_date,
            status=appointment.status,
            complaint=appointment.complaint,
            diagnosis=appointment.diagnosis,
            total_cost=appointment.total_cost,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/appointments/book", response_model=AppointmentUpcomingOut)
async def book_mobile_appointment(
    request: BookAppointmentRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Запись к врачу через мобильное приложение"""
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Создаем запись
        appointment_data = {
            "patient_id": patient.id,
            "doctor_id": request.doctor_id,
            "appointment_date": datetime.fromisoformat(request.preferred_date),
            "complaint": request.complaint,
            "notes": request.notes,
            "status": "scheduled",
            "source": "mobile",
        }

        appointment = crud_appointment.create_appointment(db, appointment_data)

        # Добавляем услуги
        if request.services:
            for service_id in request.services:
                crud_appointment.add_appointment_service(
                    db, appointment_id=appointment.id, service_id=service_id
                )

        # Получаем информацию о враче
        doctor = crud_user.get_user(db, user_id=request.doctor_id)

        # Отправляем уведомление
        # Используем notification_sender_service
        await notification_sender_service.send_appointment_confirmation(db, appointment.id)

        return AppointmentUpcomingOut(
            id=appointment.id,
            doctor_name=doctor.name,
            specialty=doctor.specialty or "Врач",
            appointment_date=appointment.appointment_date,
            status=appointment.status,
            clinic_address="Главный филиал",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/lab/results", response_model=list[LabResultOut])
async def get_lab_results(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Результаты анализов пациента"""
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        results = crud_lab.get_patient_lab_results(
            db, patient_id=patient.id, limit=limit, offset=offset
        )

        return [
            LabResultOut(
                id=result.id,
                test_name=result.test_name,
                result_value=result.result,
                reference_range=result.normal_range,
                unit=result.unit,
                result_date=result.test_date,
                status=result.status,
                notes=result.doctor_notes,
            )
            for result in results
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/stats", response_model=MobileQuickStats)
async def get_mobile_quick_stats(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """Быстрая статистика для мобильного приложения"""
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        # Получаем статистику
        from app.crud.appointment import (
            count_patient_visits,
            count_upcoming_appointments,
            get_last_visit,
        )
        from app.crud.payment import count_pending_payments, get_patient_total_spent

        total_appointments = count_patient_visits(db, patient_id=patient.id)
        upcoming_appointments = count_upcoming_appointments(db, patient_id=patient.id)
        completed_appointments = (
            total_appointments - upcoming_appointments
        )  # Вычисляем как разность

        total_spent = get_patient_total_spent(db, patient_id=patient.id)
        last_visit = get_last_visit(db, patient_id=patient.id)
        favorite_doctor = None  # Пока не реализовано
        pending_payments = count_pending_payments(db, patient_id=patient.id)

        return MobileQuickStats(
            total_appointments=total_appointments,
            upcoming_appointments=upcoming_appointments,
            completed_appointments=completed_appointments,
            total_spent=total_spent,
            last_visit=last_visit.appointment_date if last_visit else None,
            favorite_doctor=favorite_doctor.name if favorite_doctor else None,
            pending_payments=pending_payments,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/notifications", response_model=list[dict])
async def get_mobile_notifications(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """История уведомлений для мобильного приложения"""
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)
        notifications = _get_mobile_notification_rows(
            db,
            user_id=current_user.id,
            patient_id=patient.id if patient else None,
            limit=limit,
            offset=offset,
        )

        return [
            {
                "id": notif.get("delivery_id"),
                "title": notif.get("event_title", ""),
                "message": notif.get("event_message", ""),
                "type": notif.get("event_type", ""),
                "data": notif.get("event_payload_snapshot", {}) or {},
                "sent_at": notif.get("delivery_created_at"),
                "read": notif.get("delivery_read_at") is not None,
            }
            for notif in notifications
        ]

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/notifications/{notification_id}/read", response_model=dict[str, Any])
async def mark_notification_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отметить уведомление как прочитанное"""
    try:
        # NOTIF-REAUDIT-28 P0-2: используем await (раньше run_until_complete
        # внутри async-эндпоинта падал с RuntimeError). mark_read ожидает
        # delivery_id: str, а не int.
        platform = get_notification_platform_service(db)
        try:
            await platform.mark_read(
                current_user=current_user,
                delivery_id=str(notification_id),
            )
        except PermissionError:
            raise HTTPException(status_code=404, detail="Уведомление не найдено")

        return {"message": "Уведомление отмечено как прочитанное"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/health", response_model=dict[str, Any])
async def mobile_health_check():
    """Проверка здоровья мобильного API"""
    return {
        "status": "ok",
        "mobile_api": "active",
        "timestamp": datetime.now(UTC),
        "version": "1.0.0",
    }


@router.post("/notifications/test-push", response_model=dict[str, Any])
async def test_push_notification(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """Тестирование push-уведомлений"""
    try:
        # Отправляем тестовое уведомление
        success = await notification_sender_service.send_push(
            user_id=current_user.id,
            title="Тестовое уведомление",
            message="Это тестовое push-уведомление от мобильного API",
            data={"test": "true", "timestamp": datetime.now(UTC).isoformat()},
            db=db
        )

        if success:
            return {
                "status": "success",
                "message": "Тестовое уведомление отправлено",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        else:
            return {
                "status": "error",
                "message": "Не удалось отправить тестовое уведомление",
                "timestamp": datetime.now(UTC).isoformat(),
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )
