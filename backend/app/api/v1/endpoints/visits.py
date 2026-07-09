# app/api/v1/endpoints/visits.py
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.clinic import Doctor
from app.models.visit import Visit
from app.services.visits_api_service import VisitsApiService

router = APIRouter()
logger = logging.getLogger(__name__)
VISIT_READ_ROLES = ("Admin", "Registrar", "Doctor", "Cashier", "Lab", "Nurse")


# Pydantic fallbacks (если полноценные схемы уже есть в app.schemas, в следующих шагах заменим)
class VisitCreate(BaseModel):
    patient_id: int | None = None
    doctor_id: int | None = None
    notes: str | None = None
    planned_date: date | None = None  # <-- новая поддержка
    department: str | None = None
    source: str | None = Field(default="desk", max_length=20)


class VisitOut(BaseModel):
    id: int
    patient_id: int | None = None
    doctor_id: int | None = None
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    notes: str | None = None
    planned_date: date | None = None  # <-- новая поддержка
    source: str | None = None
    patient_name: str | None = None
    patient_fio: str | None = None
    patient_phone: str | None = None
    patient_birth_year: int | None = None
    birth_year: int | None = None
    address: str | None = None
    patient: dict[str, Any] | None = None
    doctor_name: str | None = None
    room: str | None = None
    doctor: dict[str, Any] | None = None


class VisitServiceIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitWithServices(BaseModel):
    visit: VisitOut
    services: list[VisitServiceIn]


def _visits(db: Session) -> Table:
    """
    Return reflected visits table. Использует autoload_with, не bind.
    """
    md = MetaData()
    return Table("visits", md, autoload_with=db.get_bind())


def _vservices(db: Session) -> Table:
    md = MetaData()
    return Table("visit_services", md, autoload_with=db.get_bind())


def _isValid_time_str(value: str) -> bool:
    """R-27 fix: validate HH:MM time string (24-hour, leading zeros required)."""
    if not value or len(value) != 5 or value[2] != ":":
        return False
    try:
        hours = int(value[:2])
        minutes = int(value[3:])
    except (ValueError, TypeError):
        return False
    return 0 <= hours <= 23 and 0 <= minutes <= 59


def _update_queue_entries_for_visit_owner(
    db: Session,
    *,
    visit_id: int,
    patient_id: int | None,
    status_value: str,
) -> None:
    if patient_id is None:
        return

    db.execute(
        text(
            """
            UPDATE queue_entries
            SET status = :status_value
            WHERE visit_id = :visit_id
              AND patient_id = :patient_id
            """
        ),
        {
            "status_value": status_value,
            "visit_id": visit_id,
            "patient_id": patient_id,
        },
    )


def _ensure_visit_doctor_access(db: Session, visit: Visit, current_user) -> None:
    if getattr(current_user, "role", None) == "Admin" or getattr(
        current_user, "is_superuser", False
    ):
        return
    if getattr(current_user, "role", None) != "Doctor":
        return

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")
    if visit.doctor_id == doctor.id:
        return

    assigned_doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor and visit.doctor_id == current_user.id:
        return
    if assigned_doctor and assigned_doctor.user_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _doctor_allowed_visit_doctor_ids(db: Session, current_user) -> set[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    allowed_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor:
        allowed_ids.add(current_user.id)
    return allowed_ids


def _ensure_doctor_can_create_visit_for_payload(
    db: Session,
    payload: VisitCreate,
    current_user,
) -> None:
    if getattr(current_user, "role", None) == "Admin" or getattr(
        current_user, "is_superuser", False
    ):
        return
    if getattr(current_user, "role", None) != "Doctor":
        return

    doctor_id = getattr(payload, "doctor_id", None)
    if doctor_id is None or doctor_id not in _doctor_allowed_visit_doctor_ids(
        db, current_user
    ):
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/visits", response_model=list[VisitOut], summary="Список визитов")
def list_visits(
    patient_id: int | None = Query(default=None),
    doctor_id: int | None = Query(default=None),
    status_q: str | None = Query(default=None),
    planned: date | None = Query(default=None, alias="planned_date"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VISIT_READ_ROLES)),
):
    if getattr(current_user, "role", None) == "Doctor":
        if doctor_id is None:
            raise HTTPException(status_code=403, detail="Access denied")
        if doctor_id not in _doctor_allowed_visit_doctor_ids(db, current_user):
            raise HTTPException(status_code=403, detail="Access denied")

    rows = VisitsApiService(db).list_visits(
        patient_id=patient_id,
        doctor_id=doctor_id,
        status_q=status_q,
        planned=planned,
        limit=limit,
        offset=offset,
    )
    return [VisitOut(**row) for row in rows]  # type: ignore[arg-type]


@router.post(
    "/visits",
    response_model=VisitOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin", "Registrar", "Doctor"))],
    summary="Создать визит",
)
def create_visit(
    request: Request,
    payload: VisitCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    _ensure_doctor_can_create_visit_for_payload(db, payload, current_user)
    result = VisitsApiService(db).create_visit(
        request=request,
        payload=payload,
        current_user=current_user,
    )
    return VisitOut(**result)


@router.get(
    "/visits/{visit_id}", response_model=VisitWithServices, summary="Карточка визита"
)
def get_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(*VISIT_READ_ROLES)),
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "Visit not found")
    _ensure_visit_doctor_access(db, visit, current_user)

    payload = VisitsApiService(db).get_visit(visit_id=visit_id)
    return VisitWithServices(
        visit=VisitOut(**payload["visit"]),
        services=[VisitServiceIn(**item) for item in payload["services"]],
    )


@router.post(
    "/visits/{visit_id}/services",
    summary="Добавить услугу к визиту",
response_model=dict[str, Any],
)
def add_service(
    visit_id: int,
    item: VisitServiceIn,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Registrar", "Doctor", "Cashier")),
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "Visit not found")
    _ensure_visit_doctor_access(db, visit, current_user)
    return VisitsApiService(db).add_service(visit_id=visit_id, item=item)


@router.post(
    "/visits/{visit_id}/status",
    summary="Смена статуса визита",
)
def set_status(
    visit_id: int,
    status_new: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    if status_new not in {"open", "in_progress", "closed", "canceled"}:
        raise HTTPException(400, "Invalid status")
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "Visit not found")
    _ensure_visit_doctor_access(db, visit, current_user)

    visit.status = status_new
    if status_new == "in_progress" and hasattr(visit, "started_at"):
        visit.started_at = datetime.now(UTC)
    if status_new in {"closed", "canceled"} and hasattr(visit, "finished_at"):
        visit.finished_at = datetime.now(UTC)

    # [FIX] Также обновляем статус в очереди, если есть связанная запись
    if status_new == "canceled":
        try:
            _update_queue_entries_for_visit_owner(
                db,
                visit_id=visit_id,
                patient_id=visit.patient_id,
                status_value="canceled",
            )
        except Exception:
            # Ошибка обновления очереди не должна блокировать обновление визита
            pass

    db.commit()
    db.refresh(visit)

    # Convert ORM object to Pydantic model
    return VisitOut(
        id=visit.id,
        patient_id=visit.patient_id,
        doctor_id=visit.doctor_id,
        status=visit.status,
        created_at=visit.created_at,
        started_at=getattr(visit, "started_at", None),
        finished_at=getattr(visit, "finished_at", None),
        notes=visit.notes,
        planned_date=visit.visit_date
    )


#
# Reschedule endpoints — перенос визита
#
@router.post(
    "/visits/{visit_id}/reschedule",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на конкретную дату (new_date в формате YYYY-MM-DD)",
)
@router.post(
    "/{visit_id}/reschedule",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на конкретную дату (legacy alias)",
)
def reschedule_visit(
    visit_id: int,
    new_date: date = Query(..., alias="new_date"),
    new_time: str | None = Query(None, alias="new_time", description="Опциональное новое время в формате HH:MM"),
    db: Session = Depends(get_db),
):
    """
    Перенос визита на указанную дату (записывается в visit_date).
    Опционально обновляет visit_time, если передан new_time (формат HH:MM).
    """
    t = _visits(db)
    # Проверка наличия колонки visit_date
    if not hasattr(t.c, "visit_date"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visits table has no visit_date column; check your schema.",
        )

    vrow = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    if not vrow:
        raise HTTPException(404, "Visit not found")

    # Запретим перенос, если визит завершён/отменён или уже начат
    if vrow.get("status") in {"closed", "canceled"}:
        raise HTTPException(
            status_code=409, detail="Cannot reschedule closed or canceled visit"
        )
    if vrow.get("started_at"):
        raise HTTPException(
            status_code=409, detail="Cannot reschedule a visit that has been started"
        )

    # R-27 fix: обновляем и дату, и опционально время
    update_values: dict = {"visit_date": new_date}
    if new_time is not None:
        # Валидация формата HH:MM
        new_time_str = new_time.strip()
        if not _isValid_time_str(new_time_str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="new_time must be in HH:MM format (e.g. 09:30)",
            )
        update_values["visit_time"] = new_time_str

    upd = (
        t.update().where(t.c.id == visit_id).values(**update_values).returning(t)
    )
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")

    # [FIX] Обновляем статус в очереди для старой даты
    try:
        from sqlalchemy import text
        # Помечаем старую запись очереди как перенесенную
        db.execute(
            text(
                """
                UPDATE queue_entries
                SET status = 'rescheduled'
                WHERE visit_id = :visit_id
                  AND patient_id = :patient_id
                """
            ),
            {"visit_id": visit_id, "patient_id": vrow.get("patient_id")}
        )
    except Exception:
        pass

    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]


@router.post(
    "/visits/{visit_id}/reschedule/tomorrow",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на завтра (planned_date = today + 1)",
)
@router.post(
    "/{visit_id}/reschedule/tomorrow",
    dependencies=[Depends(require_roles("Admin", "Registrar"))],
    summary="Перенести визит на завтра (legacy alias)",
)
def reschedule_visit_tomorrow(visit_id: int, db: Session = Depends(get_db)):
    t = _visits(db)
    if not hasattr(t.c, "visit_date"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="visits table has no visit_date column; check your schema.",
        )

    vrow = db.execute(select(t).where(t.c.id == visit_id)).mappings().first()
    if not vrow:
        raise HTTPException(404, "Visit not found")

    if vrow.get("status") in {"closed", "canceled"}:
        raise HTTPException(
            status_code=409, detail="Cannot reschedule closed or canceled visit"
        )
    if vrow.get("started_at"):
        raise HTTPException(
            status_code=409, detail="Cannot reschedule a visit that has been started"
        )

    tomorrow = date.today() + timedelta(days=1)
    upd = (
        t.update().where(t.c.id == visit_id).values(visit_date=tomorrow).returning(t)
    )
    row = db.execute(upd).mappings().first()
    if not row:
        raise HTTPException(404, "Visit not found")

    # [FIX] Обновляем статус в очереди для старой даты
    try:
        from sqlalchemy import text
        # Помечаем старую запись очереди как перенесенную
        db.execute(
            text(
                """
                UPDATE queue_entries
                SET status = 'rescheduled'
                WHERE visit_id = :visit_id
                  AND patient_id = :patient_id
                """
            ),
            {"visit_id": visit_id, "patient_id": vrow.get("patient_id")}
        )
    except Exception:
        pass

    db.commit()
    return VisitOut(**row)  # type: ignore[arg-type]
