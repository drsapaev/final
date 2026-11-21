
import hashlib
import hmac
import json
import time
from datetime import date
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, StrictBool, field_validator
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import deps
from app.core.audit import log_critical_change
from app.core.config import settings
from app.core.i18n import t  # noqa: F401
from app.core.roles import DOCTOR_FAMILY_GATE_ROLES, normalize_role_value
from app.crud.patient import patient as patient_crud
from app.models.audit import AuditLog
from app.models.patient import Patient, PatientBirthDateEvidence
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.schemas import lab as lab_schemas
from app.schemas import patient as patient_schemas
from app.services.patient_access_audit import (
    _build_patient_access_entry,
    log_patient_access,
    log_patient_access_many,
)
from app.services.patient_portal_service import (
    PatientPortalDomainError,
    PatientPortalService,
)
from app.services.patient_service import PatientReadAccessDenied, PatientService
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    capture_profile_bearer,
    check_bearer_expiry,
    check_profile_bearer,
)

router = APIRouter()


def _audit_patient_read(
    *,
    request: Request,
    current_user: User,
    patient_id: int,
    resource_type: str,
    outcome: str = "success",
    extra_data: dict[str, Any] | None = None,
) -> None:
    from app.db.session import SessionLocal

    audit_db = SessionLocal()
    try:
        log_patient_access(
            audit_db,
            actor_user=current_user,
            subject_patient_id=patient_id,
            resource_type=resource_type,
            resource_id=str(patient_id),
            action="view",
            outcome=outcome,
            request=request,
            extra_data=extra_data,
        )
    finally:
        audit_db.close()


def _raise_patient_read_denied(
    *,
    request: Request,
    current_user: User,
    patient_id: int,
    resource_type: str,
    error: PatientReadAccessDenied,
) -> NoReturn:
    _audit_patient_read(
        request=request,
        current_user=current_user,
        patient_id=patient_id,
        resource_type=resource_type,
        outcome="denied",
        extra_data={"reason": error.reason},
    )
    raise HTTPException(status_code=403, detail="Access denied") from error


@router.get(
    "/appointments",
    response_model=list[appointment_schemas.AppointmentHistoryItem],
)
def get_my_appointments(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить записи текущего пациента
    """
    if not current_user.patient:
        return []

    service = PatientService(db)
    patient, appointments = service.get_patient_appointment_history_for_read(
        current_user=current_user,
        patient_id=current_user.patient.id,
    )
    return appointments if patient is not None else []


@router.get("/appointments/{appointment_id}", response_model=appointment_schemas.Appointment)
def get_my_appointment_details(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить детали записи текущего пациента
    """
    if not current_user.patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    service = PatientPortalService(db)
    try:
        return service.get_my_appointment_details(
            appointment_id=appointment_id,
            patient_id=current_user.patient.id,
        )
    except PatientPortalDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/results", response_model=list[lab_schemas.LabOrderOut])
def get_my_results(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Patient")),
):
    """
    Получить результаты анализов текущего пациента
    """
    if not current_user.patient:
        return []

    return PatientPortalService(db).get_my_results(patient_id=current_user.patient.id)


@router.get("/", response_model=list[patient_schemas.Patient])
def list_patients(
    request: Request,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    q: str | None = Query(None, description="Поиск по ФИО, телефону или документу"),
    phone: str | None = Query(None, description="Точный поиск по номеру телефона"),
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES, "Lab", "Cashier")),
):
    """
    Получить список пациентов с возможностью поиска и пагинации

    - q: общий поиск по всем полям (частичное совпадение)
    - phone: точный поиск по телефону (приоритет над q)
    """
    service = PatientService(db)
    try:
        patients = service.list_patients_for_read(
            current_user=current_user,
            skip=skip,
            limit=limit,
            search_query=q,
            phone=phone,
        )
    except PatientReadAccessDenied as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    from app.db.session import SessionLocal

    audit_db = SessionLocal()
    try:
        log_patient_access_many(
            audit_db,
            actor_user=current_user,
            subject_patient_ids=[patient.id for patient in patients],
            resource_type="patient",
            action="view",
            request=request,
        )
    finally:
        audit_db.close()
    return patients


@router.post("/", response_model=patient_schemas.Patient)
def create_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_in: patient_schemas.PatientCreate,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    service = PatientService(db)
    return service.create_patient(
        request=request, patient_in=patient_in, current_user=current_user
    )


def can_replay_patient_creation(
    db: Session, *, record_id: int, response_body: bytes, actor: User, request: Request,
) -> bool:
    if not actor.is_superuser and normalize_role_value(actor.role) not in {"admin", "registrar"}:
        return False
    patient = db.get(Patient, record_id)
    if patient is None or patient.is_deleted is not False:
        return False

    current_body = patient_schemas.Patient.model_validate(patient).model_dump_json(by_alias=True).encode()
    if current_body != response_body:
        return False

    log_patient_access(
        db, actor_user=actor, subject_patient_id=patient.id,
        resource_type="patient", resource_id=str(patient.id), action="view",
        request=request, extra_data={"operation": "patient_create_replay"},
    )
    return True


@router.get("/deleted", response_model=list[patient_schemas.Patient])
def get_deleted_patients(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.require_roles("Admin")),
):
    from app.crud.patient import get_deleted_patients as do_get_deleted

    return do_get_deleted(db, skip=skip, limit=limit)


@router.get("/{patient_id}", response_model=patient_schemas.Patient)
def get_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES, "Lab", "Cashier", "Patient")),
):
    """
    Получить пациента по ID
    """
    service = PatientService(db)
    try:
        patient = service.get_patient_for_read(
            current_user=current_user,
            patient_id=patient_id,
        )
    except PatientReadAccessDenied as exc:
        _raise_patient_read_denied(
            request=request,
            current_user=current_user,
            patient_id=patient_id,
            resource_type="patient",
            error=exc,
        )
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))
    _audit_patient_read(
        request=request,
        current_user=current_user,
        patient_id=patient.id,
        resource_type="patient",
    )
    return patient


@router.put("/{patient_id}", response_model=patient_schemas.Patient)
def update_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    patient_in: patient_schemas.PatientUpdate,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    service = PatientService(db)
    return service.update_patient(
        request=request,
        patient_id=patient_id,
        patient_in=patient_in,
        current_user=current_user,
    )


@router.delete("/{patient_id}", response_model=dict[str, Any])
def delete_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin")),
):
    service = PatientService(db)
    return service.delete_patient(
        request=request, patient_id=patient_id, current_user=current_user
    )


@router.get(
    "/{patient_id}/appointments",
    response_model=list[appointment_schemas.AppointmentHistoryItem],
)
def get_patient_appointments(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES, "Patient")),
):
    """
    Получить все записи пациента
    """
    service = PatientService(db)
    try:
        patient, appointments = service.get_patient_appointment_history_for_read(
            current_user=current_user,
            patient_id=patient_id,
        )
    except PatientReadAccessDenied as exc:
        _raise_patient_read_denied(
            request=request,
            current_user=current_user,
            patient_id=patient_id,
            resource_type="appointment_history",
            error=exc,
        )
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))
    _audit_patient_read(
        request=request,
        current_user=current_user,
        patient_id=patient.id,
        resource_type="appointment_history",
        extra_data={"appointment_count": len(appointments)},
    )
    return appointments


# ===================== SOFT-DELETE ENDPOINTS =====================


@router.delete("/{patient_id}/soft", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
def soft_delete_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Мягкое удаление пациента (пометка как удалённый).

    Пациент остаётся в базе, но не отображается в списках.
    Можно восстановить через POST /{patient_id}/restore
    """
    from app.crud.patient import soft_delete_patient as do_soft_delete

    patient = do_soft_delete(db, patient_id=patient_id, deleted_by=current_user.id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    # Audit log
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="SOFT_DELETE",
        table_name="patients",
        row_id=patient_id,
        old_data={"is_deleted": False},
        new_data={"is_deleted": True},
        request=request,
        description=f"Мягкое удаление пациента: {patient.short_name()}",
    )

    return {"message": "Пациент помечен как удалённый", "patient_id": patient_id}


@router.post("/{patient_id}/restore", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
def restore_patient(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin")),
):
    """
    Восстановить удалённого пациента.

    Только администраторы могут восстанавливать пациентов.
    """
    from app.crud.patient import restore_patient as do_restore

    patient = do_restore(db, patient_id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    # Audit log
    log_critical_change(
        db=db,
        user_id=current_user.id,
        action="RESTORE",
        table_name="patients",
        row_id=patient_id,
        old_data={"is_deleted": True},
        new_data={"is_deleted": False},
        request=request,
        description=f"Восстановлен пациент: {patient.short_name()}",
    )

    return {"message": "Пациент восстановлен", "patient_id": patient_id}


# ===================== FAMILY RELATIONS ENDPOINTS =====================


@router.get("/{patient_id}/family", response_model=dict[str, Any])
def get_patient_family(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """
    Получить семью/родственников пациента.

    Возвращает список связей с данными родственников.
    """
    from app.crud.family_relation import get_patient_as_relative
    from app.crud.family_relation import get_patient_family as do_get_family

    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    # Получаем родственников пациента
    family = do_get_family(db, patient_id=patient_id)

    # Получаем пациентов, для которых данный пациент является родственником
    as_relative_of = get_patient_as_relative(db, patient_id=patient_id)

    return {
        "patient_id": patient_id,
        "patient_name": patient.short_name(),
        "family": family,
        "is_relative_of": as_relative_of,
    }


@router.post("/{patient_id}/family", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def add_family_relation(
    *,
    request: Request,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    related_patient_id: int = Query(..., description="ID родственника"),
    relation_type: str = Query("other", description="Тип связи: parent, child, guardian, spouse, sibling, other"),
    description: str | None = Query(None, description="Описание связи"),
    is_primary_contact: bool = Query(False, description="Основное контактное лицо"),
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Добавить связь с родственником.

    Типы связей:
    - parent: родитель
    - child: ребёнок
    - guardian: опекун
    - spouse: супруг(а)
    - sibling: брат/сестра
    - other: другое
    """
    from app.crud.family_relation import create_family_relation

    try:
        relation = create_family_relation(
            db,
            patient_id=patient_id,
            related_patient_id=related_patient_id,
            relation_type=relation_type,
            description=description,
            is_primary_contact=is_primary_contact,
            created_by=current_user.id,
        )

        return {
            "message": "Связь добавлена",
            "relation_id": relation.id,
            "patient_id": patient_id,
            "related_patient_id": related_patient_id,
            "relation_type": relation_type,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Internal server error")


@router.delete("/{patient_id}/family/{relation_id}", status_code=status.HTTP_200_OK, response_model=dict[str, Any])
def remove_family_relation(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    relation_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Удалить связь с родственником.
    """
    from app.crud.family_relation import delete_family_relation

    success = delete_family_relation(db, relation_id=relation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Связь не найдена")

    return {"message": "Связь удалена", "relation_id": relation_id}


@router.get("/{patient_id}/primary-contact", response_model=dict[str, Any])
def get_primary_contact(
    *,
    db: Session = Depends(deps.get_db),
    patient_id: int,
    current_user: User = Depends(deps.require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """
    Получить основное контактное лицо для пациента.

    Используется для пациентов без телефона (дети, пожилые).
    """
    from app.crud.family_relation import get_primary_contact as do_get_primary

    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    primary = do_get_primary(db, patient_id=patient_id)

    if primary:
        return {
            "has_primary_contact": True,
            "contact": {
                "id": primary.id,
                "full_name": primary.short_name(),
                "phone": primary.phone,
            },
        }

    return {"has_primary_contact": False, "contact": None}


# Historical birth dates lack reliable provenance. An administrator may attest
# the exact current value after reviewing a real record; the capability is
# bound to the full patient context and current date generation.
_BIRTH_REVIEW_TTL = 600
_BIRTH_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class _BirthReviewRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                response = await handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={"error": "validation_error", "message": "Ошибка валидации запроса", "detail": []},
                    headers=_BIRTH_NO_STORE,
                )
            except StarletteHTTPException as exc:
                exc.headers = {**(exc.headers or {}), **_BIRTH_NO_STORE}
                raise
            response.headers.update(_BIRTH_NO_STORE)
            return response

        return safe_handler


class BirthDateReviewResponse(BaseModel):
    patient_id: int
    birth_date: date
    precision: str
    generation: int
    review_expires_at: int
    token: str


class BirthDateAttestation(BaseModel):
    confirmed_exact_date: StrictBool
    expected_generation: int = Field(gt=0, strict=True)
    review_expires_at: int = Field(gt=0, strict=True)
    token: str = Field(min_length=64, max_length=64)

    @field_validator("confirmed_exact_date")
    @classmethod
    def require_review(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Необходимо подтвердить точную дату рождения")
        return value


birth_review_router = APIRouter(route_class=_BirthReviewRoute)


def _birth_review_context(db: Session, bearer, patient_id: int):
    actor = db.query(User).filter(User.id == bearer.user_id).with_for_update().populate_existing().first()
    if not actor or not actor.is_active or (
        not actor.is_superuser and normalize_role_value(actor.role) != "admin"
    ):
        raise HTTPException(status_code=403, detail="Доступ запрещён", headers=_BIRTH_NO_STORE)
    check_profile_bearer(db, actor, bearer)
    patient = db.query(Patient).filter(Patient.id == patient_id).with_for_update().populate_existing().first()
    if patient is None or patient.is_deleted:
        raise HTTPException(status_code=404, detail="Пациент не найден", headers=_BIRTH_NO_STORE)
    if patient.birth_date is None or not patient.birth_date_generation or patient.birth_date_generation < 1:
        raise HTTPException(status_code=409, detail="Дата рождения недоступна для проверки", headers=_BIRTH_NO_STORE)
    return actor, patient


def _birth_review_token(actor: User, patient: Patient, expires_at: int) -> str:
    if not settings.SECRET_KEY:
        raise HTTPException(status_code=503, detail="Проверка недоступна", headers=_BIRTH_NO_STORE)
    values = [
        "patient-birth-review-v1", actor.id, actor.auth_epoch, patient.id, patient.user_id,
        patient.birth_date.isoformat(), patient.birth_date_generation, patient.birth_date_precision, expires_at,
    ]
    key = hmac.new(settings.SECRET_KEY.encode(), b"patient-birth-review-v1", hashlib.sha256).digest()
    return hmac.new(key, json.dumps(values, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()


@birth_review_router.post("/{patient_id}/birth-date/review", response_model=BirthDateReviewResponse)
def review_birth_date(
    patient_id: int, request: Request, response: Response,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles("Admin")),
) -> BirthDateReviewResponse:
    try:
        bearer = capture_profile_bearer(request, current_user)
        actor, patient = _birth_review_context(db, bearer, patient_id)
        existing = db.query(PatientBirthDateEvidence.id).filter_by(
            patient_id=patient.id, birth_date_generation=patient.birth_date_generation
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Дата уже подтверждена", headers=_BIRTH_NO_STORE)
        expires_at = int(time.time()) + _BIRTH_REVIEW_TTL
        result = BirthDateReviewResponse(
            patient_id=patient.id, birth_date=patient.birth_date, precision=patient.birth_date_precision,
            generation=patient.birth_date_generation, review_expires_at=expires_at,
            token=_birth_review_token(actor, patient, expires_at),
        )
        audit = _build_patient_access_entry(
            db, actor_user=actor, subject_patient_id=patient.id, resource_type="patient",
            resource_id=str(patient.id), action="view", request=request,
        )
        if audit is None:
            raise RuntimeError("patient access audit unavailable")
        db.add(audit)
        check_bearer_expiry(bearer)
        db.commit()
        response.headers.update(_BIRTH_NO_STORE)
        return result
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен", headers=_BIRTH_NO_STORE) from None
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось проверить дату", headers=_BIRTH_NO_STORE) from None


@birth_review_router.post("/{patient_id}/birth-date/attest")
def attest_birth_date(
    patient_id: int, payload: BirthDateAttestation, request: Request, response: Response,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_active_roles("Admin")),
) -> dict[str, Any]:
    try:
        bearer = capture_profile_bearer(request, current_user)
        actor, patient = _birth_review_context(db, bearer, patient_id)
        now = int(time.time())
        if (
            payload.expected_generation != patient.birth_date_generation
            or payload.review_expires_at <= now
            or payload.review_expires_at > now + _BIRTH_REVIEW_TTL
            or not payload.token.isascii()
            or not hmac.compare_digest(payload.token, _birth_review_token(actor, patient, payload.review_expires_at))
        ):
            raise HTTPException(status_code=409, detail="Контекст проверки устарел", headers=_BIRTH_NO_STORE)
        existing = db.query(PatientBirthDateEvidence.id).filter_by(
            patient_id=patient.id, birth_date_generation=patient.birth_date_generation
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Дата уже подтверждена", headers=_BIRTH_NO_STORE)
        role = str(getattr(actor.role, "value", actor.role))
        db.add(PatientBirthDateEvidence(
            patient_id=patient.id, patient_id_snapshot=patient.id,
            birth_date_generation=patient.birth_date_generation, actor_user_id_snapshot=actor.id,
            actor_role=role,
        ))
        db.add(AuditLog(
            action="patient_birth_date_attested", event_type="patient_birth_date_attested",
            entity_type="patient", entity_id=patient.id, actor_user_id=actor.id,
            actor_role=role, actor_type="staff", outcome="success",
            payload={"birth_date_generation": patient.birth_date_generation},
            reason_code={"code": "admin_reviewed_historical_record"},
        ))
        check_bearer_expiry(bearer)
        db.commit()
        response.headers.update(_BIRTH_NO_STORE)
        return {"success": True, "patient_id": patient_id}
    except ProfileBearerInvalid:
        db.rollback()
        raise HTTPException(status_code=401, detail="Сеанс недоступен", headers=_BIRTH_NO_STORE) from None
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось сохранить подтверждение", headers=_BIRTH_NO_STORE) from None


router.include_router(birth_review_router)

