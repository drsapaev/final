"""API endpoints для управления врачами в админ панели."""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.roles import DOCTOR_ROLES, is_login_blocked_role
from app.core.security import require_roles
from app.core.specialties import specialty_variants
from app.crud import clinic as crud_clinic
from app.models.user import User
from app.schemas.clinic import (
    DoctorCreate,
    DoctorOut,
    DoctorUpdate,
    DoctorUserOption,
    ScheduleCreate,
    ScheduleOut,
    ServiceUnavailableDetail,
    SpecialtyVocabularyItem,
    WeeklyScheduleUpdate,
)
from app.services.admin_doctors_stats_service import AdminDoctorsStatsService
from app.services.medical_specialty_catalog import (
    MedicalSpecialtyCatalogError,
    MedicalSpecialtyCatalogService,
)
from app.services.user_mgmt._base import (
    DOCTOR_PROFILE_ROLES,
    is_doctor_profile_incomplete,
)

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


_DUPLICATE_DOCTOR_LINK_DETAIL = "Пользователь уже привязан к другому врачу"


def _is_doctor_user_id_unique_violation(exc: IntegrityError) -> bool:
    """True when an IntegrityError comes from UNIQUE(doctors.user_id).

    The race guard for the concurrent-link window: two requests can both
    pass the get_doctor_by_user_id pre-check before either commits, and
    the losing commit raises from the DB constraint instead (Codex P2,
    round-6). Constraint-name coverage per backend:
    - PostgreSQL (migration 0048): 'duplicate key value violates unique
      constraint "uq_doctors_user_id"'.
    - SQLite (tests, column-level unique=True): 'UNIQUE constraint
      failed: doctors.user_id'.
    Foreign-key violations on the same column match neither pattern and
    keep the generic 500 path.
    """
    text = str(getattr(exc, "orig", None) or exc)
    return "uq_doctors_user_id" in text or "doctors.user_id" in text


def _raise_duplicate_doctor_link_error() -> HTTPException:
    """Same client error the pre-check returns, for the losing race."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=_DUPLICATE_DOCTOR_LINK_DETAIL,
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
        # PR-21: include department fields
        "department_id": doctor.department_id,
        "department": doctor.department.name_ru if doctor.department else None,
        # Lifecycle (decision #5): admin must see "Profile incomplete /
        # Specialty required" for auto-created (or never completed) profiles.
        "profile_incomplete": is_doctor_profile_incomplete(doctor.specialty),
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
        # QD-1.1 (queue resource role cleanup, Codex round-3/4): synthetic
        # queue-resource Doctor rows (sentinel owners) are hidden — they
        # are queue machinery, not manageable staff profiles. Filtering in
        # the crud query (not after the row cap) so pagination cannot crowd
        # real doctors out of the page.
        doctors = crud_clinic.get_doctors(
            db, skip=skip, limit=limit, active_only=active_only,
            exclude_internal_only=True,
        )
        if specialty:
            # D-1 canonical vocabulary: any dental-family spelling finds
            # every family row (Codex round-5 P2 — the exact comparison
            # silently returned no doctors for legacy spellings after 0049).
            wanted = set(specialty_variants(specialty))
            doctors = [d for d in doctors if (d.specialty or "") in wanted]
        return [_serialize_doctor(db, doctor) for doctor in doctors]
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "get_doctors") from exc


@router.get("/doctors/available-users", response_model=list[DoctorUserOption])
def get_available_doctor_users(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
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


@router.get("/doctors/stats", response_model=dict[str, Any])
def get_doctors_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    return _get_doctors_stats_payload(db)


class SpecialtyCatalogCreateIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=100)
    title_ru: str = Field(..., min_length=1, max_length=200)
    title_uz: str | None = Field(None, max_length=200)
    title_en: str | None = Field(None, max_length=200)
    active: bool = True
    sort_order: int = 0


class SpecialtyCatalogUpdateIn(BaseModel):
    title_ru: str | None = Field(None, min_length=1, max_length=200)
    title_uz: str | None = Field(None, max_length=200)
    title_en: str | None = Field(None, max_length=200)
    active: bool | None = None
    sort_order: int | None = None


@router.get(
    "/doctors/specialty-vocabulary",
    response_model=list[SpecialtyVocabularyItem],
    responses={
        503: {
            "model": ServiceUnavailableDetail,
            "description": (
                "Каталог специальностей не настроен (миграции/seed 0051 не выполнены)"
            ),
        }
    },
)
def get_doctor_specialty_vocabulary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Medical specialty catalog — codes selectable at new-doctor onboarding.

    Runtime SSOT is the ``medical_specialties`` table (migration 0051);
    there is deliberately NO hardcoded fallback. Ordering: sort_order,
    then code (deterministic). Frontend label resolution per owner spec:
    locale → catalog translation → title_ru → code (the ru titles are a
    compatibility fallback for kk/uz-Cyrl, not a translation claim).
    """
    try:
        rows = MedicalSpecialtyCatalogService(db).list_active()
    except MedicalSpecialtyCatalogError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Каталог медицинских специальностей не настроен: "
                "выполните миграции БД (baseline seed 0051)."
            ),
        ) from exc
    return [
        SpecialtyVocabularyItem(
            code=row.code,
            title_ru=row.title_ru,
            title_uz=row.title_uz,
            title_en=row.title_en,
        )
        for row in rows
    ]




@router.get("/doctors-catalog", response_model=list[SpecialtyVocabularyItem])
def admin_list_medical_specialties(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Полный каталог специальностей (включая неактивные) — Admin UI."""
    from app.services.specialty_catalog_admin import list_all

    return [
        SpecialtyVocabularyItem(
            code=row.code, title_ru=row.title_ru,
            title_uz=row.title_uz, title_en=row.title_en,
        )
        for row in list_all(db)
    ]


@router.post("/doctors-catalog", response_model=SpecialtyVocabularyItem, status_code=201)
def admin_create_medical_specialty(
    payload: SpecialtyCatalogCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Создать специальность в каталоге (canonical code + titles)."""
    from app.services.specialty_catalog_admin import (
        SpecialtyCatalogConflictError,
        SpecialtyCatalogValidationError,
        create as catalog_create,
    )

    try:
        row = catalog_create(
            db, code=payload.code, title_ru=payload.title_ru,
            title_uz=payload.title_uz, title_en=payload.title_en,
            active=payload.active, sort_order=payload.sort_order,
        )
    except SpecialtyCatalogValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SpecialtyCatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SpecialtyVocabularyItem(
        code=row.code, title_ru=row.title_ru,
        title_uz=row.title_uz, title_en=row.title_en,
    )


@router.put("/doctors-catalog/{code}", response_model=SpecialtyVocabularyItem)
def admin_update_medical_specialty(
    code: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить titles/active/sort_order специальности каталога.

    ``code`` — неизменяемый идентификатор: переименование запрещено,
    потому что значение хранится в ``Doctor.specialty`` существующих врачей.
    """
    from app.services.specialty_catalog_admin import update as catalog_update

    row = catalog_update(
        db, code,
        title_ru=payload.get("title_ru"),
        title_uz=payload.get("title_uz"),
        title_en=payload.get("title_en"),
        active=payload.get("active"),
        sort_order=payload.get("sort_order"),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Специальность не найдена")
    return SpecialtyVocabularyItem(
        code=row.code, title_ru=row.title_ru,
        title_uz=row.title_uz, title_en=row.title_en,
    )


@router.delete("/doctors-catalog/{code}")
def admin_delete_medical_specialty(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Удалить специальность каталога (только если её не использует врач)."""
    from app.services.specialty_catalog_admin import delete as catalog_delete

    deleted, refs = catalog_delete(db, code)
    if refs:
        raise HTTPException(
            status_code=409,
            detail=f"Специальность используется {refs}+ врач(ом) — сначала деактивируйте её",
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Специальность не найдена")
    return {"deleted": code}


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
    # QD-1.1 (queue resource role cleanup, Codex round-3 P1): sentinel-linked
    # resource rows answer 404 on the single-record surface too (hidden from
    # the list, read-only by mutation guards).
    _reject_sentinel_linked_doctor(db, doctor)
    return _serialize_doctor(db, doctor)


def _reject_sentinel_linked_doctor(db: Session, doctor) -> None:
    """QD-1.1 (queue resource role cleanup, Codex round-3 P1): Doctor rows
    linked to internal-only sentinel users are queue machinery, not
    manageable staff profiles — an ordinary admin-panel mutation
    (deactivate/reassign/delete) would break the username+is_active queue
    resolution, and the ghost-state guard would then BLOCK reactivation
    ('Resource' is not a doctor-family role). They are read-only at this
    boundary and answer 404, like the hidden user-management rows."""
    if doctor is None or doctor.user_id is None:
        return
    user = db.query(User).filter(User.id == doctor.user_id).first()
    if user is not None and is_login_blocked_role(getattr(user, "role", None)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Врач с ID {doctor.id} не найден",
        )


def _validate_linked_owner_allows_active(
    db: Session, user_id: int | None, active: bool
) -> None:
    """Ghost-state guard: an ACTIVE linked Doctor requires an ACTIVE owner
    User whose current role belongs to the doctor family.

    Closes the residual ghost states an admin could otherwise produce via
    the API (Codex P2-C):
      - Doctor.active=True over a DEACTIVATED User (owner cannot log in,
    but the profile stays visible in selectors/queues);
      - Doctor.active=True over a User whose role is not doctor-family
    (non-doctor user != active Doctor profile).
    Inactive Doctors are unrestricted: any owner state is reversible and
    reactivation re-validates through this guard.
    """
    if not active or user_id is None:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Профиль врача нельзя сделать активным: связанный "
                f"пользователь user_id={user_id} не найден."
            ),
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Профиль врача нельзя сделать активным, пока связанный "
                "пользователь деактивирован (is_active=False). Сначала "
                "реактивируйте учётную запись пользователя, иначе возникнет "
                "состояние ghost-doctor (активный врач без активного "
                "владельца)."
            ),
        )
    owner_role = str(user.role.value) if hasattr(user.role, "value") else str(user.role)
    if owner_role not in DOCTOR_PROFILE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Профиль врача нельзя сделать активным: роль владельца "
                f"'{owner_role}' не относится к врачебным. Реактивация "
                "профиля возможна только для пользователя с врачебной ролью."
            ),
        )


def _validate_active_doctor_has_user(user_id: int | None, active: bool) -> None:
    """Lifecycle invariant (decision #13): a NORMAL active system Doctor must
    have a linked User account. Creating/updating an ``active=True`` doctor
    without ``user_id`` is rejected. Inactive userless rows remain legal for
    historical/special records (DB keeps them; existing rows are untouched —
    no deletion, no auto-link; pre-existing data is inventoried and BLOCKED
    at deploy time by backend/scripts/reconcile_userless_active_doctors.py,
    exit code 1 when any active userless row exists — Codex round-7 P2).
    """
    if active and user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Активный врач должен быть привязан к учётной записи "
                "пользователя (user_id). Создание активного врача без "
                "пользователя запрещено (инвариант 1 User = 1 Doctor)."
            ),
        )




def _validate_specialty_assignable(db: Session, specialty: str | None) -> None:
    """Catalog write-boundary (Codex P1): any NEW specialty assignment through
    the admin doctors API must reference an ACTIVE catalog code (migration
    0051). Unknown codes, legacy dental aliases and the "general" sentinel
    are rejected with 400 — the catalog is the runtime SSOT, and a
    deactivated specialty can no longer be assigned to new doctors.
    Historical rows keep their stored value untouched (no-cascade rule).
    """
    if specialty is None:
        # Field absent / not being set — nothing to validate (Codex P2:
        # blank strings are NOT skipped, only a genuinely unset value is).
        return
    if not specialty.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Специальность не может быть пустой строкой.",
        )
    catalog = MedicalSpecialtyCatalogService(db)
    try:
        if catalog.is_selectable_for_onboarding(specialty):
            return
    except MedicalSpecialtyCatalogError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Каталог медицинских специальностей не настроен: "
                "выполните миграции БД (baseline seed 0051)."
            ),
        ) from exc
    existing = catalog.get_by_code(specialty)
    detail = (
        f"Специальность '{specialty}' деактивирована в каталоге — "
        "назначение новым врачам недоступно."
        if existing
        else (
            f"Специальность '{specialty}' отсутствует в каталоге "
            "(medical_specialties). Доступные коды — см. "
            "/admin/doctors/specialty-vocabulary."
        )
    )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post(
    "/doctors",
    response_model=DoctorOut,
    responses={
        503: {
            "model": ServiceUnavailableDetail,
            "description": (
                "Каталог специальностей не настроен (миграции/seed 0051 не выполнены)"
            ),
        }
    },
)
def create_doctor(
    doctor: DoctorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Создать врача."""
    try:
        # Decision #13: no NEW active userless doctors via API.
        _validate_active_doctor_has_user(doctor.user_id, doctor.active)

        if doctor.user_id:
            _validate_doctor_user(db, doctor.user_id)
            # Ghost-state guard: active linked Doctor requires an active,
            # doctor-family owner (same contract as update_doctor).
            _validate_linked_owner_allows_active(db, doctor.user_id, doctor.active)
            existing_doctor = crud_clinic.get_doctor_by_user_id(db, doctor.user_id)
            if existing_doctor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь уже привязан к другому врачу",
                )

        _validate_specialty_assignable(db, doctor.specialty)

        new_doctor = crud_clinic.create_doctor(db, doctor)
        return _serialize_doctor(db, new_doctor)
    except HTTPException:
        raise
    except IntegrityError as exc:
        # Concurrent-link race (Codex P2 round-6): both requests passed the
        # get_doctor_by_user_id pre-check before either committed; the DB
        # UNIQUE constraint (uq_doctors_user_id) rejected the losing commit
        # here. Roll back the poisoned session and surface the same client
        # error the pre-check would have returned instead of a 500.
        db.rollback()
        if _is_doctor_user_id_unique_violation(exc):
            raise _raise_duplicate_doctor_link_error() from exc
        raise _admin_doctors_http_error(exc, "create_doctor") from exc
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "create_doctor") from exc


@router.put(
    "/doctors/{doctor_id}",
    response_model=DoctorOut,
    responses={
        503: {
            "model": ServiceUnavailableDetail,
            "description": (
                "Каталог специальностей не настроен (миграции/seed 0051 не выполнены)"
            ),
        }
    },
)
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
        # QD-1.1 (queue resource role cleanup, Codex round-3 P1): sentinel-
        # linked resource rows are read-only — deactivation would break the
        # doctorless queue resolution and the ghost-state guard would then
        # block reactivation ('Resource' is not a doctor-family role).
        _reject_sentinel_linked_doctor(db, existing_doctor)

        if (
            doctor.user_id
            and doctor.user_id != existing_doctor.user_id
            and existing_doctor.user_id is not None
        ):
            # Codex P2-E: unilateral reassignment of a Doctor profile away
            # from a doctor-role owner leaves that owner (still role=Doctor)
            # without a profile — /auth/me and clinical endpoints can no
            # longer resolve the account. There is no explicit business
            # transfer contract yet, so the risky path is REJECTED (option A).
            # Reassignment stays allowed when the old owner is gone (userless
            # row repair) or has no doctor-family role anymore.
            old_owner = (
                db.query(User)
                .filter(User.id == existing_doctor.user_id)
                .first()
            )
            old_owner_role = (
                str(old_owner.role.value)
                if old_owner and hasattr(old_owner.role, "value")
                else (str(old_owner.role) if old_owner else None)
            )
            if old_owner is not None and old_owner_role in DOCTOR_PROFILE_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Нельзя перепривязать профиль врача к другому "
                        "пользователю, пока текущий владелец сохраняет "
                        f"врачебную роль ('{old_owner_role}'). Сначала "
                        "измените роль текущего владельца (это деактивирует "
                        "профиль) или удалите связь, иначе владелец останется "
                        "без профиля при активной врачебной роли."
                    ),
                )

        if doctor.user_id and doctor.user_id != existing_doctor.user_id:
            _validate_doctor_user(db, doctor.user_id)
            other_doctor = crud_clinic.get_doctor_by_user_id(db, doctor.user_id)
            if other_doctor and other_doctor.id != doctor_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь уже привязан к другому врачу",
                )

        # Decision #13: the resulting doctor state must not be active+userless
        # (e.g. activating a userless doctor, or unsetting user_id on an
        # active one). Fields not present in the payload keep current values.
        # Validated BEFORE the explicit-detachment guard below so a request
        # that violates BOTH contracts surfaces the #13 active-userless 400
        # first (the detachment 409 is about the OWNER-role contract, which
        # is only reachable for inactive resulting rows).
        payload_set = doctor.model_fields_set
        target_user_id = (
            doctor.user_id if "user_id" in payload_set else existing_doctor.user_id
        )
        target_active = (
            doctor.active if "active" in payload_set else existing_doctor.active
        )
        _validate_active_doctor_has_user(target_user_id, bool(target_active))
        # Ghost-state guard (Codex P2-C): never allow the resulting state
        # Doctor.active=True + User.is_active=False for a linked Doctor.
        _validate_linked_owner_allows_active(db, target_user_id, bool(target_active))

        if (
            "user_id" in payload_set
            and doctor.user_id is None
            and existing_doctor.user_id is not None
        ):
            # Codex round-4 P2: EXPLICIT DETACHMENT (user_id=null) is the
            # same risky path as reassignment to another user — the old
            # owner keeps their doctor-family role but loses the profile,
            # so /auth/me and clinical endpoints can no longer resolve that
            # account. The active-userless guard does not catch it (the
            # resulting row is typically inactive), so it is rejected here
            # under the same option-A contract: change the owner's role
            # first (the lifecycle mirror deactivates the profile) — only
            # then may the link be detached.
            old_owner = (
                db.query(User)
                .filter(User.id == existing_doctor.user_id)
                .first()
            )
            old_owner_role = (
                str(old_owner.role.value)
                if old_owner and hasattr(old_owner.role, "value")
                else (str(old_owner.role) if old_owner else None)
            )
            if old_owner is not None and old_owner_role in DOCTOR_PROFILE_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Нельзя отвязать профиль врача от пользователя, "
                        "пока владелец сохраняет врачебную роль "
                        f"('{old_owner_role}'): учётная запись останется "
                        "без профиля и потеряет доступ к врачу-панелям. "
                        "Сначала измените роль владельца (это деактивирует "
                        "профиль через lifecycle-зеркало), затем отвяжите "
                        "профиль."
                    ),
                )

        specialty_payload_present = "specialty" in doctor.model_fields_set
        specialty_changed = specialty_payload_present and (
            (doctor.specialty or "").strip()
            != (existing_doctor.specialty or "").strip()
        )
        resulting_active = (
            doctor.active if "active" in doctor.model_fields_set else existing_doctor.active
        )
        activating_inactive_profile = resulting_active and not existing_doctor.active
        if specialty_changed or (
            # No-cascade contract: an UNCHANGED historical value (possibly
            # now inactive/absent in the catalog) must not block unrelated
            # edits — only a genuine CHANGE is validated (Codex P2). The one
            # exception is ACTIVATION of an inactive profile: carrying the
            # stored specialty (unchanged OR omitted from the payload) into
            # an ACTIVE doctor is a NEW assignment and must pass the catalog
            # (round-6 follow-up; #3010 round-6 P1 — an activation-only
            # {"active": true} payload used to bypass the gate entirely and
            # reactivate a profile holding a deactivated/unknown/sentinel
            # code).
            activating_inactive_profile
        ):
            # Payload present → validate the payload value (raw, so the
            # None-is-unset semantics of _validate_specialty_assignable are
            # preserved); payload omits specialty → validate the STORED
            # value the activation would carry into the active state.
            _validate_specialty_assignable(
                db,
                doctor.specialty
                if specialty_payload_present
                else existing_doctor.specialty,
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
    except IntegrityError as exc:
        # Same concurrent-link race as create_doctor (Codex P2 round-6):
        # both requests passed the pre-check, the losing commit hits the
        # UNIQUE(doctors.user_id) constraint. Roll back and return the
        # duplicate-link client error instead of a 500.
        db.rollback()
        if _is_doctor_user_id_unique_violation(exc):
            raise _raise_duplicate_doctor_link_error() from exc
        raise _admin_doctors_http_error(exc, "update_doctor") from exc
    except Exception as exc:
        raise _admin_doctors_http_error(exc, "update_doctor") from exc


@router.delete("/doctors/{doctor_id}", response_model=dict[str, Any])
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Удалить врача (мягкое удаление)."""
    try:
        # QD-1.1 (queue resource role cleanup, Codex round-3 P1): sentinel-
        # linked resource rows are read-only (soft-deleting/deactivating them
        # would break the doctorless queue resolution).
        existing_doctor = crud_clinic.get_doctor_by_id(db, doctor_id)
        _reject_sentinel_linked_doctor(db, existing_doctor)
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


@router.get("/specialties", response_model=dict[str, Any])
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
