import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import deps
from app.core.i18n import t  # noqa: F401
from app.models.clinic import Doctor
from app.models.derma_examination import DermaExamination
from app.models.derma_procedure import DermaProcedure
from app.models.user import User
from app.models.visit import Visit
from app.schemas.derma import (
    DermaExaminationCreate,
    DermaExaminationOut,
    DermaProcedureCreate,
    DermaProcedureOut,
)
from app.services.derma_api_service import DermaApiDomainError, DermaApiService

router = APIRouter(prefix="/derma", tags=["derma"])
logger = logging.getLogger(__name__)
# D-3 RBAC unification: "dermatologist" covers the lowercase/capitalized
# alias (require_roles is case-insensitive) — provisioned Dermatologist-role
# accounts must not 403 on their own specialty panel (parity with cardio.py).
DERMA_ROLES = ("Admin", "Doctor", "derma", "dermatology", "dermatologist")
DERMA_ADMIN_ROLES = {"Admin"}


class PriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    # SPEC-AUDIT-28 P0-3: validate price is positive and reasonable
    new_price: Decimal = Field(..., gt=0, le=Decimal("1000000000"))
    reason: str
    details: str | None = None


class PriceOverrideResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    original_price: Decimal
    # SPEC-AUDIT-28 P0-3: validate price is positive and reasonable
    new_price: Decimal = Field(..., gt=0, le=Decimal("1000000000"))
    reason: str
    details: str | None
    status: str
    created_at: datetime


def _is_admin_user(user: User) -> bool:
    return getattr(user, "role", None) in DERMA_ADMIN_ROLES or bool(
        getattr(user, "is_superuser", False)
    )


def _doctor_allowed_doctor_ids(db: Session, user: User) -> set[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    allowed_doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor:
        allowed_doctor_ids.add(user.id)
    return allowed_doctor_ids


def _doctor_allowed_patient_ids(db: Session, user: User) -> set[int]:
    allowed_doctor_ids = _doctor_allowed_doctor_ids(db, user)
    rows = (
        db.query(Visit.patient_id)
        .filter(
            Visit.doctor_id.in_(allowed_doctor_ids),
            Visit.patient_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _ensure_doctor_can_access_patient(db: Session, patient_id: int, user: User) -> None:
    if _is_admin_user(user):
        return
    if patient_id not in _doctor_allowed_patient_ids(db, user):
        raise HTTPException(status_code=403, detail="Access denied")


@router.get(
    "/examinations",
    summary="Осмотры кожи",
    response_model=list[DermaExaminationOut],
)
async def get_skin_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[DermaExaminationOut]:
    """
    Получить список осмотров кожи
    """
    try:
        query = db.query(DermaExamination)
        if not _is_admin_user(user):
            if patient_id is not None:
                _ensure_doctor_can_access_patient(db, patient_id, user)
            else:
                allowed_patient_ids = _doctor_allowed_patient_ids(db, user)
                if not allowed_patient_ids:
                    return []
                query = query.filter(DermaExamination.patient_id.in_(allowed_patient_ids))

        if patient_id is not None:
            query = query.filter(DermaExamination.patient_id == patient_id)

        examinations = (
            query.order_by(
                desc(DermaExamination.examination_date),
                desc(DermaExamination.created_at),
                desc(DermaExamination.id),
            )
            .limit(limit)
            .all()
        )
        logger.info(
            "[derma.examinations] listed examinations user_id=%s patient_id=%s count=%s",
            getattr(user, "id", None),
            patient_id,
            len(examinations),
        )
        return examinations
    except SQLAlchemyError:
        logger.exception(
            "[derma.examinations] failed to list examinations user_id=%s patient_id=%s",
            getattr(user, "id", None),
            patient_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post(
    "/examinations",
    summary="Создать осмотр кожи",
    response_model=DermaExaminationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_skin_examination(
    examination_data: DermaExaminationCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
) -> DermaExaminationOut:
    """
    Устаревший эндпоинт записи (review follow-up P2-4a к #3448).

    Таблица derma_examinations объявлена read-only (история): новые осмотры
    сохраняются в specialty_data ЭМК (emr/v2). Возврат 410 до любого
    доступа к БД — fail-closed для всех ролей, включая Admin: двойная
    запись (legacy + ЭМК) расщепляла клинические данные по двум таблицам.
    Чтение истории — GET /derma/examinations — не изменяется.
    """
    logger.warning(
        "[derma.examinations] rejected legacy write user_id=%s patient_id=%s visit_id=%s",
        getattr(user, "id", None),
        getattr(examination_data, "patient_id", None),
        getattr(examination_data, "visit_id", None),
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Эндпоинт закрыт: осмотры кожи сохраняются в specialty_data ЭМК. "
            "Таблица derma_examinations доступна только для чтения (история)."
        ),
    )


@router.get(
    "/procedures",
    summary="Косметические процедуры",
    response_model=list[DermaProcedureOut],
)
async def get_cosmetic_procedures(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[DermaProcedureOut]:
    """
    Получить список косметических процедур
    """
    try:
        query = db.query(DermaProcedure)
        if not _is_admin_user(user):
            if patient_id is not None:
                _ensure_doctor_can_access_patient(db, patient_id, user)
            else:
                allowed_patient_ids = _doctor_allowed_patient_ids(db, user)
                if not allowed_patient_ids:
                    return []
                query = query.filter(DermaProcedure.patient_id.in_(allowed_patient_ids))

        if patient_id is not None:
            query = query.filter(DermaProcedure.patient_id == patient_id)

        procedures = (
            query.order_by(
                desc(DermaProcedure.procedure_date),
                desc(DermaProcedure.created_at),
                desc(DermaProcedure.id),
            )
            .limit(limit)
            .all()
        )
        logger.info(
            "[derma.procedures] listed procedures user_id=%s patient_id=%s count=%s",
            getattr(user, "id", None),
            patient_id,
            len(procedures),
        )
        return procedures
    except SQLAlchemyError:
        logger.exception(
            "[derma.procedures] failed to list procedures user_id=%s patient_id=%s",
            getattr(user, "id", None),
            patient_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post(
    "/procedures",
    summary="Создать косметическую процедуру",
    response_model=DermaProcedureOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_cosmetic_procedure(
    procedure_data: DermaProcedureCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
) -> DermaProcedureOut:
    """
    Устаревший эндпоинт записи (review follow-up P2-4a к #3448).

    Таблица derma_procedures объявлена read-only (история): новые
    косметические процедуры сохраняются в specialty_data ЭМК (emr/v2).
    Возврат 410 до любого доступа к БД — fail-closed для всех ролей,
    включая Admin: двойная запись (legacy + ЭМК) расщепляла клинические
    данные по двум таблицам. Чтение истории — GET /derma/procedures —
    не изменяется.
    """
    logger.warning(
        "[derma.procedures] rejected legacy write user_id=%s patient_id=%s visit_id=%s",
        getattr(user, "id", None),
        getattr(procedure_data, "patient_id", None),
        getattr(procedure_data, "visit_id", None),
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Эндпоинт закрыт: косметические процедуры сохраняются в specialty_data "
            "ЭМК. Таблица derma_procedures доступна только для чтения (история)."
        ),
    )


@router.post(
    "/price-override",
    summary="Изменить цену процедуры",
    response_model=PriceOverrideResponse,
)
async def create_price_override(
    override_data: PriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
) -> PriceOverrideResponse:
    """
    Дерматолог изменяет цену процедуры с указанием причины
    """
    try:
        service = DermaApiService(db)
        price_override = service.create_price_override(
            override_data=override_data,
            user_id=user.id,
        )

        return PriceOverrideResponse(
            id=price_override.id,
            visit_id=price_override.visit_id,
            service_id=price_override.service_id,
            original_price=price_override.original_price,
            new_price=price_override.new_price,
            reason=price_override.reason,
            details=price_override.details,
            status=price_override.status,
            created_at=price_override.created_at,
        )

    except DermaApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/price-overrides", summary="Получить изменения цен", response_model=list[PriceOverrideResponse])
async def get_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    visit_id: int | None = Query(None, description="ID визита"),
    status: str | None = Query(
        None, description="Статус (pending, approved, rejected)"
    ),
    limit: int = Query(50, ge=1, le=100),
) -> list[PriceOverrideResponse]:
    """
    Получить список изменений цен дерматолога
    """
    try:
        overrides = DermaApiService(db).get_price_overrides(
            user_id=user.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

        return [
            PriceOverrideResponse(
                id=override.id,
                visit_id=override.visit_id,
                service_id=override.service_id,
                original_price=override.original_price,
                new_price=override.new_price,
                reason=override.reason,
                details=override.details,
                status=override.status,
                created_at=override.created_at,
            )
            for override in overrides
        ]

    except DermaApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/photo-gallery", summary="Фотогалерея", response_model=dict[str, Any])
async def get_photo_gallery(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    patient_id: int | None = None,
) -> dict[str, Any]:
    """
    Получить фотогалерею пациента
    """
    try:
        return {"message": "Фотогалерея будет доступна в следующей версии"}
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )
