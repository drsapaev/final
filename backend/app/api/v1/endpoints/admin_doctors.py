"""API endpoints для управления врачами в админ панели."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit_helper import log_action
from app.api.deps import get_db
from app.core.roles import DOCTOR_ROLES
from app.core.security import require_roles
from app.crud import clinic as crud_clinic
from app.models.user import User
from app.schemas.clinic import (
    DoctorCreate,
    DoctorOut,
    DoctorUpdate,
    DoctorUserOption,
    ScheduleCreate,
    ScheduleOut,
    WeeklyScheduleUpdate,
)
from app.services.admin_doctors_stats_service import AdminDoctorsStatsService

router = APIRouter()
logger = logging.getLogger(__name__)

ADMIN_DOCTORS_PUBLIC_ERROR = "Internal server error"

DOCTOR_ROLE_VALUES = {
    str(role.value) if hasattr(role, "value") else str(role)
    for role in DOCTOR_ROLES
}


def _admin_doctors_http_error(exc: Exception, operation: str) -> HTTPException:
    logger.warning(
        "Admin doctors endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=ADMIN_DOCTORS_PUBLIC_ERROR,
    )


def _validate_doctor_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден",
        )

    user_role = str(user.role.value) if hasattr(user.role, "value") else str(user.role)
    if user_role not in DOCTOR_ROLE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Выбранный пользователь не имеет doctor-роль",
        )

    return user


def _serialize_doctor_user(
    user: User | None,
    *,
    linked_doctor_id: int | None = None,
) -> dict | None:
    if not user:
        return None

    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "phone": profile.phone if profile else None,
        "role": user.role,
        "is_active": user.is_active,
        "linked_doctor_id": linked_doctor_id,
    }


def _serialize_doctor(db: Session, doctor) -> DoctorOut:
    doctor_dict = {
        "id": doctor.id,
        "user_id": doctor.user_id,
        "specialty": doctor.specialty,
        "cabinet": doctor.cabinet,
        "price_default": doctor.price_default,
        "start_number_online": doctor.start_number_online,
        "max_online_per_day": doctor.max_online_per_day,
        "auto_close_time": doctor.auto_close_time,
        "active": doctor.active,
        "created_at": doctor.created_at,
        "updated_at": doctor.updated_at,
        "user": _serialize_doctor_user(doctor.user, linked_doctor_id=doctor.id),
    }
    schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
    doctor_dict["schedules"] = [ScheduleOut.model_validate(s) for s in schedules]
    return DoctorOut(**doctor_dict)


@router.get("/doctors", response_model=list[DoctorOut])
def get_doctors(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    specialty: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить список врачей."""
    try:
        doctors = crud_clinic.get_doctors(
            db, skip=skip, limit=limit, active_only=active_only
        )
        if specialty:
            doctors = [d for d in doctors if d.specialty == specialty]
        return [_serialize_doctor(db, doctor) for doctor in doctors]
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "get_doctors") from exc


@router.get("/doctors/available-users", response_model=list[DoctorUserOption])
def get_available_doctor_users(
    doctor_id: int | None = Query(
        None,
        description="ID редактируемого врача, чтобы вернуть уже привязанного пользователя",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить существующие doctor-capable user accounts для привязки."""
    current_doctor = crud_clinic.get_doctor_by_id(db, doctor_id) if doctor_id else None
    current_user_id = current_doctor.user_id if current_doctor else None

    linked_doctors = crud_clinic.get_doctors(db, skip=0, limit=1000, active_only=False)
    linked_map = {
        doctor.user_id: doctor.id
        for doctor in linked_doctors
        if doctor.user_id is not None
    }

    query = db.query(User).filter(User.role.in_(sorted(DOCTOR_ROLE_VALUES)))
    if linked_map:
        if current_user_id is not None:
            query = query.filter(
                or_(
                    User.id == current_user_id,
                    User.id.notin_(list(linked_map.keys())),
                )
            )
        else:
            query = query.filter(User.id.notin_(list(linked_map.keys())))

    users = query.order_by(User.is_active.desc(), User.full_name.asc(), User.username.asc()).all()
    return [
        DoctorUserOption(
            **(
                _serialize_doctor_user(
                    user,
                    linked_doctor_id=linked_map.get(user.id),
                )
                or {}
            )
        )
        for user in users
    ]


@router.get("/doctors/stats")
def get_doctors_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    return _get_doctors_stats_payload(db)


@router.get("/doctors/{doctor_id}", response_model=DoctorOut)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить врача по ID."""
    doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Врач с ID {doctor_id} не найден",
        )
    return _serialize_doctor(db, doctor)


@router.post("/doctors", response_model=DoctorOut)
def create_doctor(
    doctor: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Создать врача."""
    try:
        if doctor.user_id:
            _validate_doctor_user(db, doctor.user_id)
            existing_doctor = crud_clinic.get_doctor_by_user_id(db, doctor.user_id)
            if existing_doctor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь уже привязан к другому врачу",
                )

        new_doctor = crud_clinic.create_doctor(db, doctor)
        return _serialize_doctor(db, new_doctor)
    except HTTPException:
        raise
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "create_doctor") from exc


@router.put("/doctors/{doctor_id}", response_model=DoctorOut)
def update_doctor(
    doctor_id: int,
    doctor: DoctorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить врача."""
    try:
        existing_doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        if not existing_doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )

        if doctor.user_id and doctor.user_id != existing_doctor.user_id:
            _validate_doctor_user(db, doctor.user_id)
            other_doctor = crud_clinic.get_doctor_by_user_id(db, doctor.user_id)
            if other_doctor and other_doctor.id != doctor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь уже привязан к другому врачу",
                )

        updated_doctor = crud_clinic.update_doctor(db, doctor_id, doctor)
        if not updated_doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )

        return _serialize_doctor(db, updated_doctor)
    except HTTPException:
        raise
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "update_doctor") from exc


@router.delete("/doctors/{doctor_id}")
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Удалить врача (мягкое удаление)."""
    try:
        success = crud_clinic.delete_doctor(db, doctor_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )
        return {"success": True, "message": "Врач успешно деактивирован"}
    except HTTPException:
        raise
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "delete_doctor") from exc


@router.get("/doctors/{doctor_id}/schedule", response_model=list[ScheduleOut])
def get_doctor_schedule(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить расписание врача."""
    doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Врач с ID {doctor_id} не найден",
        )
    return crud_clinic.get_doctor_schedules(db, doctor_id)


@router.put("/doctors/{doctor_id}/schedule", response_model=list[ScheduleOut])
def update_doctor_schedule(
    doctor_id: int,
    schedule_data: WeeklyScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить недельное расписание врача."""
    try:
        doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )
        schedules_dict = [schedule.model_dump() for schedule in schedule_data.schedules]
        return crud_clinic.update_weekly_schedule(db, doctor_id, schedules_dict)
    except HTTPException:
        raise
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "update_doctor_schedule") from exc


@router.post("/doctors/{doctor_id}/schedule", response_model=ScheduleOut)
def create_schedule(
    doctor_id: int,
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Создать расписание для врача."""
    try:
        doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )
        schedule.doctor_id = doctor_id
        return crud_clinic.create_schedule(db, schedule)
    except HTTPException:
        raise
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "create_schedule") from exc


@router.get("/specialties")
def get_specialties(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить список специальностей."""
    try:
        return AdminDoctorsStatsService(db).get_specialties()
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "get_specialties") from exc


def _get_doctors_stats_payload(db: Session):
    """Получить статистику по врачам."""
    try:
        return AdminDoctorsStatsService(db).get_doctors_stats()
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "get_doctors_stats") from exc
