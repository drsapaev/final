"""
Мобильные API endpoints для PWA
"""

import gzip

# PR-3: import the modules directly (not via app.crud.__init__ which
# re-exports the CRUDAppointment *instance* named `appointment` and shadows
# the module of the same name). Using importlib avoids the shadowing.
import importlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.endpoints._error_logging import log_endpoint_error  # PR-7

crud_appointment = importlib.import_module("app.crud.appointment")
crud_lab = importlib.import_module("app.crud.lab")
crud_user = importlib.import_module("app.crud.user")
# patient is special: app/crud/__init__.py exports `patient = CRUDPatient(...)`
# via `from .patient import *`. `from app.crud import patient` returns the
# *instance* (which has methods like get_patient_by_phone). Module-level
# functions like get_patient_by_user_id live on the module itself.
# Use the instance for method calls, import the module functions directly.
from app.core.config import settings  # PR-29: needed for real expires_in
from app.crud import patient as crud_patient  # CRUDPatient instance (for methods)
from app.crud.patient import get_patient_by_user_id
from app.db.session import get_db
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
from app.services.notification_platform_service import get_notification_platform_service
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


@router.post("/auth/login", response_model=MobileLoginResponse)
def mobile_login(credentials: MobileLoginRequest, db: Session = Depends(get_db)):
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
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/refresh")
def mobile_refresh_token(
    refresh_token: str = Query(..., description="Refresh token issued at login"),
    db: Session = Depends(get_db),
):
    """PR-33: Mobile-friendly refresh endpoint.

    Wraps the same authentication_service.refresh_access_token logic as
    /authentication/refresh, but lives under /mobile/ for a consistent
    mobile API surface. Returns BOTH access_token and refresh_token
    because the service implements refresh-token rotation (RFC 6749 §10.4):
    each refresh issues a NEW refresh token and revokes the old one.
    """
    try:
        from app.services.authentication_service import get_authentication_service

        service = get_authentication_service()
        result = service.refresh_access_token(db, refresh_token)

        if not result.get("success"):
            raise HTTPException(
                status_code=401,
                detail=result.get("message", "Invalid refresh token"),
            )

        return {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token") or refresh_token,
            "token_type": result.get("token_type", "bearer"),
            "expires_in": result.get("expires_in", settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        }

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/patients/me", response_model=PatientProfileOut)
def get_mobile_patient_profile(
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
            fio=patient.short_name(),
            phone=patient.phone or "",
            birth_year=patient.birth_date.year if patient.birth_date else None,
            address=patient.address,
            telegram_id=None,  # PR-3: telegram_id is on User/onboarding tables, not Patient
            created_at=patient.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error('GET /patients/me failed: %s\n%s', e, traceback.format_exc())
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/appointments/upcoming", response_model=list[AppointmentUpcomingOut])
def get_upcoming_appointments(
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
            # PR-3: appointment.doctor is a Doctor, name lives on Doctor.user.full_name
            doctor = appointment.doctor
            doctor_name = "Врач"
            specialty = "Врач"
            if doctor is not None:
                specialty = doctor.specialty or "Врач"
                if doctor.user is not None:
                    doctor_name = doctor.user.full_name or doctor.user.username or "Врач"

            result.append(
                AppointmentUpcomingOut(
                    id=appointment.id,
                    doctor_name=doctor_name,
                    specialty=specialty,
                    appointment_date=appointment.appointment_date,
                    status=appointment.status,
                    clinic_address="Главный филиал",
                )
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error('GET /appointments/upcoming failed: %s\n%s', e, traceback.format_exc())
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/appointments/{appointment_id}", response_model=MobileAppointmentDetailOut)
def get_appointment_detail(
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

        # PR-3: appointment.services is a JSON list[str], not a relationship.
        # appointment.doctor is now a relationship (added in this PR).
        # Doctor name lives on doctor.user.full_name.
        doctor = appointment.doctor
        doctor_name = "Врач"
        specialty = "Врач"
        if doctor is not None:
            specialty = doctor.specialty or "Врач"
            if doctor.user is not None:
                doctor_name = doctor.user.full_name or doctor.user.username or "Врач"

        # complaint / diagnosis / total_cost are not real Appointment columns
        # — return None rather than crash. (Mobile schema marks them optional.)
        return MobileAppointmentDetailOut(
            id=appointment.id,
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id or 0,
            doctor_name=doctor_name,
            specialty=specialty,
            appointment_date=appointment.appointment_date,
            status=appointment.status,
            complaint=getattr(appointment, "complaint", None),
            diagnosis=getattr(appointment, "diagnosis", None),
            total_cost=getattr(appointment, "total_cost", None),
            created_at=appointment.created_at,
            updated_at=appointment.updated_at or appointment.created_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
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

        # PR-3: doctor lives in the doctors table, not users. Use clinic CRUD.
        from app.crud import clinic as crud_clinic
        doctor = crud_clinic.get_doctor_by_id(db, doctor_id=request.doctor_id)
        doctor_name = "Врач"
        specialty = "Врач"
        if doctor is not None:
            specialty = doctor.specialty or "Врач"
            if doctor.user is not None:
                doctor_name = doctor.user.full_name or doctor.user.username or "Врач"

        # Отправляем уведомление
        # Используем notification_sender_service
        try:
            await notification_sender_service.send_appointment_confirmation(db, appointment.id)
        except Exception:
            pass  # Don't fail booking if notification fails

        return AppointmentUpcomingOut(
            id=appointment.id,
            doctor_name=doctor_name,
            specialty=specialty,
            appointment_date=appointment.appointment_date,
            status=appointment.status,
            clinic_address="Главный филиал",
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/lab/results", response_model=list[LabResultOut])
def get_lab_results(
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

        # PR-3: get_patient_lab_results returns list[dict] (Core Table autoload),
        # not ORM objects. Field names also differ from the schema — adapt.
        return [
            LabResultOut(
                id=result["id"] if "id" in result else result.get("lab_results_id", 0),
                test_name=result.get("test_name") or "",
                result_value=result.get("value") or "",
                reference_range=result.get("ref_range") or "",
                unit=result.get("unit") or "",
                result_date=result.get("created_at") or datetime.utcnow(),
                status="abnormal" if result.get("abnormal") else "normal",
                notes=result.get("notes"),
            )
            for result in results
        ]

    except HTTPException:
        raise
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).error('GET /lab/results failed: %s\n%s', e, traceback.format_exc())
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/stats", response_model=MobileQuickStats)
def get_mobile_quick_stats(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """Быстрая статистика для мобильного приложения.

    PR-32 (High-39): Consolidated 5+ separate queries into 2 aggregate queries:
    1. Single aggregate over appointments table: COUNT(completed), COUNT(upcoming),
       MAX(appointment_date) for last_visit — replaces count_patient_visits,
       count_upcoming_appointments, get_last_visit.
    2. Single JOIN+SUM over payments+appointments — replaces get_patient_total_spent
       (which had its own N+1: 1 query for visits + 1 per visit for payments).
    Only count_pending_payments remains separate (different filter criteria).
    """
    try:
        patient = get_patient_by_user_id(db, user_id=current_user.id)

        if not patient:
            raise HTTPException(status_code=404, detail="Профиль пациента не найден")

        from datetime import datetime

        from sqlalchemy import case, func

        from app.crud.payment import count_pending_payments
        from app.models.appointment import Appointment
        from app.models.payment import Payment

        today = datetime.now().date()

        # Single aggregate query: completed count, upcoming count, last visit date.
        # Replaces count_patient_visits + count_upcoming_appointments + get_last_visit.
        completed_status_set = ["completed", "in_visit"]
        upcoming_status_set = ["planned", "confirmed", "paid"]

        stats_row = (
            db.query(
                func.count(
                    case(
                        (Appointment.status.in_(completed_status_set), Appointment.id),
                    )
                ).label("completed_count"),
                func.count(
                    case(
                        (
                            and_(
                                Appointment.status.in_(upcoming_status_set),
                                Appointment.appointment_date >= today,
                            ),
                            Appointment.id,
                        ),
                    )
                ).label("upcoming_count"),
                func.max(
                    case(
                        (Appointment.status.in_(completed_status_set), Appointment.appointment_date),
                    )
                ).label("last_visit_date"),
            )
            .filter(Appointment.patient_id == patient.id)
            .one()
        )

        total_appointments = int(stats_row.completed_count or 0)
        upcoming_appointments = int(stats_row.upcoming_count or 0)
        completed_appointments = total_appointments - upcoming_appointments
        last_visit_date = stats_row.last_visit_date

        # Single JOIN+SUM query for total_spent.
        # Replaces get_patient_total_spent which had N+1 (1 visits query + 1 per visit).
        total_spent = float(
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Appointment, Payment.visit_id == Appointment.id)
            .filter(
                Appointment.patient_id == patient.id,
                Payment.status == "paid",
            )
            .scalar()
            or 0.0
        )

        favorite_doctor = None  # Пока не реализовано
        pending_payments = count_pending_payments(db, patient_id=patient.id)

        return MobileQuickStats(
            total_appointments=total_appointments,
            upcoming_appointments=upcoming_appointments,
            completed_appointments=completed_appointments,
            total_spent=total_spent,
            last_visit=last_visit_date,
            favorite_doctor=favorite_doctor.name if favorite_doctor else None,
            pending_payments=pending_payments,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/notifications", response_model=list[dict])
def get_mobile_notifications(
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
                "id": notif.get("delivery_id") or notif.get("id"),
                "title": notif.get("title", ""),
                "message": notif.get("message", ""),
                "type": notif.get("event_type", notif.get("notification_type", "")),
                "data": notif.get("payload_snapshot", {}) or {},
                "sent_at": notif.get("created_at"),
                "read": notif.get("is_read", notif.get("read_at") is not None),
            }
            for notif in notifications
        ]

    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/notifications/{notification_id}/read", response_model=dict[str, Any])
async def mark_notification_read(
    notification_id: str,
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
                delivery_id=notification_id,
            )
        except PermissionError:
            raise HTTPException(status_code=404, detail="Уведомление не найдено")

        return {"message": "Уведомление отмечено как прочитанное"}

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/health", response_model=dict[str, Any])
def mobile_health_check():
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

    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


# ==================== PR-6: Missing endpoints ====================


@router.get("/doctors", response_model=list[dict[str, Any]])
def list_mobile_doctors(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    specialty: str | None = Query(None, description="Filter by specialty"),
    limit: int = Query(50, ge=1, le=200),
):
    """List doctors for the mobile app (PR-6).

    Returns a mobile-friendly list of doctors with id, name, specialty.
    Optional specialty filter.
    """
    try:
        from app.crud import clinic as crud_clinic
        if specialty:
            doctors = crud_clinic.get_doctors_by_specialty(db, specialty=specialty)
        else:
            doctors = crud_clinic.get_doctors(db, active_only=True)
        # Limit
        doctors = doctors[:limit]

        result = []
        for doctor in doctors:
            name = "Врач"
            if doctor.user is not None:
                name = doctor.user.full_name or doctor.user.username or "Врач"
            result.append({
                "id": doctor.id,
                "name": name,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "active": doctor.active,
            })
        return result

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/attest", response_model=dict[str, Any])
def attest_device(
    request: dict[str, Any],
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify device attestation (PR-6).

    Accepts Play Integrity token (Android) or Device Check token (iOS).
    Returns verification status.

    PR-6 MVP: accepts the token and returns 'pending' — actual verification
    against Google Play Integrity API / Apple Device Check API requires
    server-side credentials and is out of scope for this PR. The endpoint
    exists so the mobile app can submit tokens; verification will be
    implemented in a follow-up PR.
    """
    try:
        platform = (request.get("platform") or "").lower()
        if platform not in ("android", "ios"):
            raise HTTPException(
                status_code=400,
                detail="platform must be 'android' or 'ios'",
            )

        if platform == "android":
            token = request.get("integrity_token")
            if not token:
                raise HTTPException(
                    status_code=400,
                    detail="integrity_token is required for Android",
                )
            # TODO PR-7: verify token via Google Play Integrity API
            # For now, accept and return pending
            return {
                "status": "pending",
                "platform": "android",
                "message": "Play Integrity token received; verification pending",
                "user_id": current_user.id,
            }
        else:  # ios
            token = request.get("device_token")
            if not token:
                raise HTTPException(
                    status_code=400,
                    detail="device_token is required for iOS",
                )
            # TODO PR-7: verify token via Apple Device Check API
            return {
                "status": "pending",
                "platform": "ios",
                "message": "Device Check token received; verification pending",
                "user_id": current_user.id,
            }

    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("app/api/v1/endpoints/mobile_api.py", exc)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )
