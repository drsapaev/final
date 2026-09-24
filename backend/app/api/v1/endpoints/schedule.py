from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import schedule as crud
from app.models.clinic import Doctor
from app.models.department import Department
from app.schemas.schedule import ScheduleCreateIn, ScheduleRowOut
from app.services.appointment_eligibility import ensure_doctor_eligible_for_appointment

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _resolve_active_department(
    db: Session, department: str | None
) -> Department | None:
    """Merged-#3340 follow-up (owner P2): CREATE-time department resolution
    with the ACTIVE gate the shared `_resolve_department_id` deliberately
    lacks for reads.

    The previous create flow resolved the key to an id UNCONDITIONALLY, so
    `Department(key="cardio", active=False)` produced an ACTIVE
    ScheduleTemplate advertising a booking route the patient-booking
    contract refuses with `department_inactive` — the schedule API was
    publishing a заведомо непригодный route. Unknown and deactivated keys
    are now controlled 400s BEFORE any INSERT, with the two shapes
    distinguished (the reads keep their exact-key empty-answer semantics;
    only the WRITE path refuses):

    * `department_unknown`  — no department carries the key;
    * `department_inactive` — the department exists but is deactivated.

    #3402 review round (owner P2-2): the plain-SELECT check was NOT atomic
    with the INSERT — a concurrently committed admin deactivation between
    the check and `crud.create_schedule(...)` + `db.commit()` still produced
    an ACTIVE template over an INACTIVE department (the exact race this
    helper was written to close). The re-read now takes the department ROW
    LOCK in the create transaction:

        ``.populate_existing().with_for_update()``

    so the active check and the schedule INSERT serialize against any
    concurrent department deactivation/delete (the admin UPDATE blocks
    until the create commits, or the create re-reads the committed
    ``active=False`` and refuses). ``populate_existing()`` is NOT optional:
    with_for_update() alone does not rewrite already-loaded identity-map
    attributes, so the re-check could silently validate a stale
    ``active=True`` snapshot — the same staleness class pinned for the
    booking department lock (PR #3386 / merged-#3340 follow-up P1).

    Canonical lock order (see `_lock_schedule_doctor`): DOCTOR first, then
    DEPARTMENT — the same order the patient-booking path establishes
    (doctor resolved before the department row lock), so the two writers
    never form an AB-BA cycle.

    Dialect note: PostgreSQL (production) enforces the row lock; SQLite
    (tests) silently drops FOR UPDATE — the serialization property is
    pinned on a disposable PostgreSQL.
    """
    if not department:
        return None
    row = (
        db.query(Department)
        .filter(Department.key == department)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=400,
            detail={"reason": "department_unknown"},
        )
    if not getattr(row, "active", True):
        raise HTTPException(
            status_code=400,
            detail={"reason": "department_inactive"},
        )
    return row


def _lock_schedule_doctor(db: Session, doctor_id: int | None) -> Doctor | None:
    """#3402 review round (owner P2-1 + P2-2): validate and ROW-LOCK the
    schedule doctor — INDEPENDENT of the department payload.

    Two defects closed at once:

    * P2-1 (shape): the previous validation ran only when a department was
      ALSO supplied (`if doctor_id is not None and department_row is not
      None`), so `{"doctor_id": 999999, "department": null}` bypassed the
      controlled `doctor_unknown` 400 entirely and died later as an FK
      IntegrityError (500-class) inside `crud.create_schedule(...)` +
      `db.commit()`. The doctor is now resolved and refused FIRST, whether
      or not a department accompanies it.
    * P2-1 (eligibility): existence + department consistency were checked,
      but NOT the booking eligibility contract — a deactivated doctor, an
      incomplete ("general" placeholder) profile, or a doctor whose owner
      account is deactivated/non-doctor could still receive an ACTIVE
      schedule template and surface in `/available-slots`, while patient
      booking refuses the same doctor. `ensure_doctor_eligible_for_appointment`
      — the single source of truth every live booking writer already
      enforces — now gates the template too (404/409 semantics are the
      helper's own contract; the dangling shape stays the schedule
      vocabulary's `doctor_unknown` 400 and never reaches the helper).
    * P2-2 (atomicity): the re-read takes the DOCTOR ROW LOCK
      (``.populate_existing().with_for_update()``) in the create
      transaction, so a concurrent doctor deactivation/lifecycle change
      serializes BEHIND the template create instead of racing it.

    Canonical lock order: DOCTOR → DEPARTMENT (`_resolve_active_department`),
    matching the patient-booking path where the doctor row is resolved
    before the department row lock — no new AB-BA lock order is introduced.

    ``None`` input (department-only / fully anonymous template) has nothing
    to validate and passes through. A doctor WITHOUT a department stays a
    legal template shape (the consistency check binds doctor+department
    only when both are present) — but the doctor itself must be eligible.
    """
    if doctor_id is None:
        return None
    locked = (
        db.query(Doctor)
        .filter(Doctor.id == int(doctor_id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if locked is None:
        # A dangling doctor_id would otherwise die as an FK IntegrityError
        # (500) at INSERT time — the controlled refusal, for BOTH payload
        # shapes (with and without a department).
        raise HTTPException(
            status_code=400,
            detail={"reason": "doctor_unknown"},
        )
    # The booking contract's eligibility gate (active, completed profile,
    # active owner with a doctor-family role). The unknown-doctor 404 of
    # the helper is unreachable here — the row above is locked in-session.
    ensure_doctor_eligible_for_appointment(db, int(doctor_id))
    return locked


def _to_out(r) -> ScheduleRowOut:
    return ScheduleRowOut(
        id=r.id,
        # Round-9 (codex P2, PR #3340): the DTO declares `department: str | None`
        # — the canonical KEY string. `r.department` is the RELATIONSHIP
        # attribute: a department-backed row coerced a Department OBJECT into
        # the str field (500-class mismatch, the round-4 appointment reads
        # already fixed).
        department=getattr(r.department, "key", None),
        doctor_id=r.doctor_id,
        weekday=int(r.weekday),
        start_time=str(r.start_time),
        end_time=str(r.end_time),
        room=r.room,
        capacity_per_hour=r.capacity_per_hour,
        active=bool(r.active),
    )


@router.get("", response_model=list[ScheduleRowOut], summary="Список расписаний")
async def list_templates(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: str | None = Query(default=None, max_length=64),
    doctor_id: int | None = Query(default=None, ge=1),
    weekday: int | None = Query(default=None, ge=0, le=6),
    active: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows = crud.list_schedules(
        db,
        department=department,
        doctor_id=doctor_id,
        weekday=weekday,
        active=active,
        limit=limit,
        offset=offset,
    )
    return [_to_out(r) for r in rows]


@router.post("", response_model=ScheduleRowOut, summary="Создать расписание")
async def create_template(
    payload: ScheduleCreateIn,
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin")),
):
    # #3402 review round (owner P2-1/P2-2): the write boundary is now
    # transactional. Canonical lock order DOCTOR → DEPARTMENT (the booking
    # path's order — no new AB-BA cycle), then every check runs on the
    # LOCKED rows, then INSERT, then COMMIT — a concurrent admin
    # deactivation/delete of either entity serializes BEHIND the create
    # (or the create refuses on the committed state), so an ACTIVE
    # template can no longer advertise a route the booking contract
    # refuses.
    doctor_row = _lock_schedule_doctor(db, payload.doctor_id or None)

    # Merged-#3340 follow-up (owner P2): unknown AND DEACTIVATED keys are
    # refused BEFORE any INSERT — an active template advertising an
    # inactive department publishes a booking route the booking contract
    # itself rejects (see _resolve_active_department).
    department_row = _resolve_active_department(db, payload.department)

    # Merged-#3340 follow-up (owner P2): a doctor+department template must
    # be INTERNALLY CONSISTENT. The two entities were previously resolved
    # independently, so a Cardiologist could be scheduled under dentistry:
    # the template advertised the doctor as available in a department the
    # patient-booking routing refuses with `doctor_department_mismatch` —
    # an internally contradictory schedule. The check runs BEFORE the
    # INSERT (до commit) against the LOCKED rows (a concurrently committed
    # department re-assignment is visible to the re-read), with the booking
    # contract's established vocabulary.
    if doctor_row is not None and department_row is not None:
        if doctor_row.department_id is None:
            raise HTTPException(
                status_code=400,
                detail={"reason": "doctor_department_missing"},
            )
        if int(doctor_row.department_id) != int(department_row.id):
            raise HTTPException(
                status_code=400,
                detail={"reason": "doctor_department_mismatch"},
            )

    row = crud.create_schedule(
        db,
        department=payload.department,
        doctor_id=payload.doctor_id,
        weekday=payload.weekday,
        start_time=payload.start_time,
        end_time=payload.end_time,
        room=payload.room,
        capacity_per_hour=payload.capacity_per_hour,
        active=payload.active,
    )
    if payload.department and row.department_id is None:
        # Round-9 (codex P2): the create payload carries the canonical KEY —
        # an unknown key must be a controlled refusal, not a silently-NULL
        # template the reads can never group under a department again.
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={"reason": "department_unknown"},
        )
    # Round-10 (owner P2, PR #3340): the mutation is only real when it
    # SURVIVES the request. The CRUD helper stops at `flush()` (a nested
    # savepoint inside the request transaction), and `get_db` only CLOSES
    # the session after the response — the uncommitted INSERT was rolled
    # back in production, so the endpoint answered a ScheduleRowOut (with
    # a generated id) for a row that never existed. COMMIT here, after the
    # unknown-key gate above (a refused create must not persist), then
    # refresh so the serialized row reflects the committed state.
    db.commit()
    db.refresh(row)
    # Round-9 (codex P2): the DTO maps `department` through the KEY
    # accessor — the raw ORM row would validate a Department OBJECT into
    # the `str | None` field (500-class response mismatch).
    return _to_out(row)


@router.delete("/{id}", summary="Удалить расписание", response_model=dict[str, Any])
async def delete_template(
    id: int = Path(..., ge=1),
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin")),
):
    ok = crud.delete_schedule(db, id_=id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


# Новые endpoints для интеграции с панелью регистратора


@router.get(
    "/weekly", summary="Расписание на неделю", response_model=list[dict[str, Any]]
)
async def get_weekly_schedule(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: str | None = Query(default=None, description="Отделение"),
    doctor_id: int | None = Query(default=None, description="ID врача"),
    week_start: str | None = Query(
        default=None, description="Начало недели (YYYY-MM-DD)"
    ),
):
    """
    Получить расписание на неделю с возможностью фильтрации по отделению или врачу
    """
    if week_start:
        try:
            start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
    else:
        # Если дата не указана, берем начало текущей недели (понедельник)
        today = date.today()
        start_date = today - timedelta(days=today.weekday())

    weekly_schedule = crud.get_weekly_schedule(
        db, start_date=start_date, department=department, doctor_id=doctor_id
    )
    return weekly_schedule


@router.get("/daily", summary="Расписание на день", response_model=dict[str, Any])
async def get_daily_schedule(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
    department: str | None = Query(default=None, description="Отделение"),
    doctor_id: int | None = Query(default=None, description="ID врача"),
):
    """
    Получить расписание на конкретный день
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD"
        )

    daily_schedule = crud.get_daily_schedule(
        db, target_date=target_date, department=department, doctor_id=doctor_id
    )
    return daily_schedule


@router.get(
    "/available-slots",
    summary="Доступные слоты для записи",
    response_model=list[dict[str, Any]],
)
async def get_available_slots(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    date_str: str = Query(..., description="Дата (YYYY-MM-DD)"),
    department: str = Query(..., description="Отделение"),
    doctor_id: int | None = Query(default=None, description="ID врача"),
    limit: int = Query(default=100, ge=1, le=500, description="Макс. слотов"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
):
    """
    Получить доступные слоты времени для записи на конкретную дату
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD"
        )

    available_slots = crud.get_available_slots(
        db, target_date=target_date, department=department, doctor_id=doctor_id
    )
    # P1 FIX: cap results to prevent unbounded response
    return available_slots[offset : offset + limit]


@router.get(
    "/doctors", summary="Список врачей по отделениям", response_model=dict[str, Any]
)
async def get_doctors_by_department(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
    department: str | None = Query(default=None, description="Отделение"),
):
    """
    Получить список врачей, сгруппированных по отделениям
    """
    doctors = crud.get_doctors_by_department(db, department=department)
    return doctors


@router.get("/departments", summary="Список отделений", response_model=dict[str, Any])
async def get_departments(
    db: Session = Depends(deps.get_db),
    user=Depends(deps.require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить список всех отделений с расписанием
    """
    departments = crud.get_departments(db)
    return departments
