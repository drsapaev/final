import logging
from datetime import date, datetime
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
from app.models.emr_v2 import EMRRecord
from app.models.user import User
from app.models.visit import Visit
from app.schemas.derma import (
    DermaExaminationCreate,
    DermaExaminationHistoryOut,
    DermaExaminationOut,
    DermaHistoryOut,
    DermaProcedureCreate,
    DermaProcedureHistoryOut,
    DermaProcedureOut,
)
from app.services.derma_api_service import DermaApiDomainError, DermaApiService
from app.services.emr_contract import extract_diagnosis_main

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


# P2-4b: the dermatology filter lives inside the EMR JSON column and cannot
# run as portable SQL across the sqlite test harness and PG JSONB, so the
# candidate records are fetched and filtered in Python.
#
# Triage P1 (owner review of #3491): the candidate scan is DELIBERATELY
# UNBOUNDED — no recency cap here. History rows are ordered by
# (examination/procedure date, created_at, id); the date may come from the
# linked Visit, one EMR may expand into several procedure rows and an EMR
# may carry no derma content at all, so a record-level cap cannot keep the
# final ``limit`` window equivalent to a full-history scan: older derma
# records would silently disappear from medical history. The only cap is
# the user-facing ``limit``, applied after the full union.
_EXAM_TEXT_FIELDS = (
    "skin_type",
    "skin_condition",
    "lesions",
    "distribution",
    "symptoms",
    "treatment_plan",
)


def _emr_candidate_records_scoped(
    db: Session, patient_ids: set[int] | None
) -> list[EMRRecord]:
    """Core EMR scan for a pre-resolved patient scope (RBAC by caller).

    ``None`` means no patient filter (admin surface), a set narrows the
    scan; an empty set yields no records.

    Exhaustive by design (triage P1): the scan MUST NOT be recency-capped.
    The final history ordering keys (visit-derived dates, expandable
    procedure entries) are not correlated with the fetch order, so any
    record-level cap would make the history silently incomplete.
    """
    query = db.query(EMRRecord).filter(EMRRecord.is_active.is_(True))
    if patient_ids is not None:
        if not patient_ids:
            return []
        query = query.filter(EMRRecord.patient_id.in_(patient_ids))
    return query.order_by(desc(EMRRecord.created_at), desc(EMRRecord.id)).all()


def _emr_candidate_records(
    db: Session, user: User, patient_id: int | None
) -> list[EMRRecord]:
    """Active EMR records visible to the user, newest-first.

    Mirrors the patient scoping of the legacy GET surface exactly: doctors
    are limited to patients of their own visits, admins see everything
    (optionally narrowed to one patient).
    """
    if patient_id is not None:
        if not _is_admin_user(user):
            _ensure_doctor_can_access_patient(db, patient_id, user)
        return _emr_candidate_records_scoped(db, {patient_id})
    if not _is_admin_user(user):
        allowed_patient_ids = _doctor_allowed_patient_ids(db, user)
        if not allowed_patient_ids:
            return []
        return _emr_candidate_records_scoped(db, allowed_patient_ids)
    return _emr_candidate_records_scoped(db, None)


def _derma_exam_has_content(
    specialty_data: dict[str, Any], diagnosis_main: str | None
) -> bool:
    """An empty derma EMR (fresh skeleton draft) must not pollute history."""
    if diagnosis_main:
        return True
    for field in _EXAM_TEXT_FIELDS:
        value = specialty_data.get(field)
        if isinstance(value, str) and value.strip():
            return True
    localization = specialty_data.get("localization")
    if isinstance(localization, dict):
        if any(isinstance(v, str) and v.strip() for v in localization.values()):
            return True
    return False


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _derma_emr_visits(
    db: Session, records: list[EMRRecord]
) -> dict[int, Visit]:
    visit_ids = {r.visit_id for r in records if r.visit_id is not None}
    if not visit_ids:
        return {}
    return {v.id: v for v in db.query(Visit).filter(Visit.id.in_(visit_ids)).all()}


def _fallback_exam_date(visit: Visit | None, record: EMRRecord) -> date:
    visit_date = getattr(visit, "visit_date", None)
    if visit_date:
        return visit_date
    if record.created_at:
        return record.created_at.date()
    return date.today()


def _derma_emr_snapshot(
    db: Session, user: User, patient_id: int | None
) -> tuple[list[EMRRecord], dict[int, Visit]]:
    """Single EMR candidate scan + single Visit load (triage P2).

    Both history sections (examinations and procedures) are projected from
    this one snapshot, so a combined read costs one EMR query and one
    Visit query instead of two of each.
    """
    records = _emr_candidate_records(db, user, patient_id)
    return records, _derma_emr_visits(db, records)


def _emr_examination_rows(
    records: list[EMRRecord], visits: dict[int, Visit]
) -> list[DermaExaminationHistoryOut]:
    rows: list[DermaExaminationHistoryOut] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
        if data.get("specialty") != "dermatology":
            continue
        specialty_data = data.get("specialty_data")
        if not isinstance(specialty_data, dict):
            specialty_data = {}
        diagnosis_main = extract_diagnosis_main(data)
        if not _derma_exam_has_content(specialty_data, diagnosis_main):
            continue
        visit = visits.get(record.visit_id)
        rows.append(
            DermaExaminationHistoryOut(
                id=f"emr-{record.id}",
                source="emr",
                patient_id=record.patient_id,
                visit_id=record.visit_id,
                doctor_id=getattr(visit, "doctor_id", None),
                examination_date=_fallback_exam_date(visit, record),
                skin_type=str(specialty_data.get("skin_type") or ""),
                skin_condition=_str_or_none(specialty_data.get("skin_condition")),
                lesions=_str_or_none(specialty_data.get("lesions")),
                distribution=_str_or_none(specialty_data.get("distribution")),
                symptoms=_str_or_none(specialty_data.get("symptoms")),
                diagnosis=diagnosis_main,
                treatment_plan=_str_or_none(specialty_data.get("treatment_plan")),
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )
    return rows


def _emr_procedure_rows(
    records: list[EMRRecord], visits: dict[int, Visit]
) -> list[DermaProcedureHistoryOut]:
    rows: list[DermaProcedureHistoryOut] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
        if data.get("specialty") != "dermatology":
            continue
        specialty_data = data.get("specialty_data")
        if not isinstance(specialty_data, dict):
            continue
        entries = specialty_data.get("procedures")
        if not isinstance(entries, list):
            continue
        visit = visits.get(record.visit_id)
        fallback_date = _fallback_exam_date(visit, record)
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            procedure_type = entry.get("procedure_type")
            if not isinstance(procedure_type, str) or not procedure_type.strip():
                continue
            rows.append(
                DermaProcedureHistoryOut(
                    id=f"emr-{record.id}-{index}",
                    source="emr",
                    patient_id=record.patient_id,
                    visit_id=record.visit_id,
                    doctor_id=getattr(visit, "doctor_id", None),
                    procedure_date=(
                        _parse_iso_date(entry.get("procedure_date")) or fallback_date
                    ),
                    procedure_type=procedure_type,
                    area_treated=_str_or_none(entry.get("area_treated")),
                    products_used=_str_or_none(entry.get("products_used")),
                    results=_str_or_none(entry.get("results")),
                    follow_up=_str_or_none(entry.get("follow_up")),
                    total_cost=None,
                    created_at=(
                        _parse_iso_datetime(entry.get("recorded_at"))
                        or record.created_at
                    ),
                    updated_at=None,
                )
            )
    return rows


def _merge_history_rows(legacy_rows: list, emr_rows: list, limit: int) -> list:
    """Union both read-only history sources, newest first, then cap."""
    def _sort_key(row):
        created = row.created_at or datetime.min
        if getattr(created, "tzinfo", None) is not None:
            created = created.replace(tzinfo=None)
        return (
            row.examination_date
            if hasattr(row, "examination_date")
            else row.procedure_date,
            created,
            str(row.id),
        )

    merged = sorted([*legacy_rows, *emr_rows], key=_sort_key, reverse=True)
    return merged[:limit]


@router.get(
    "/examinations",
    summary="Осмотры кожи (история: ЭМК + legacy)",
    response_model=list[DermaExaminationHistoryOut],
)
async def get_skin_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[DermaExaminationHistoryOut]:
    """
    История осмотров кожи (review follow-up P2-4b).

    Объединяет два read-only источника: осмотры из specialty_data ЭМК
    (emr/v2, specialty=dermatology, source="emr") и read-only строки
    закрытой legacy-таблицы derma_examinations (source="legacy").
    Скоупинг пациентов идентичен прежнему контракту; результат —
    newest-first с отсечкой limit.
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

        legacy_rows = [
            DermaExaminationHistoryOut.model_validate(row)
            for row in query.order_by(
                desc(DermaExamination.examination_date),
                desc(DermaExamination.created_at),
                desc(DermaExamination.id),
            )
            .limit(limit)
            .all()
        ]
        records, visits = _derma_emr_snapshot(db, user, patient_id)
        emr_rows = _emr_examination_rows(records, visits)
        examinations = _merge_history_rows(legacy_rows, emr_rows, limit)
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
    Чтение истории — GET /derma/examinations — объединяет ЭМК-осмотры
    и read-only legacy-строки (P2-4b).
    """
    logger.warning(
        "[derma.examinations] rejected legacy write user_id=%s",
        getattr(user, "id", None),
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
    summary="Косметические процедуры (история: ЭМК + legacy)",
    response_model=list[DermaProcedureHistoryOut],
)
async def get_cosmetic_procedures(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[DermaProcedureHistoryOut]:
    """
    История косметических процедур (review follow-up P2-4b).

    Объединяет два read-only источника: процедуры из specialty_data.procedures
    ЭМК (emr/v2, specialty=dermatology, source="emr") и read-only строки
    закрытой legacy-таблицы derma_procedures (source="legacy").
    Скоупинг пациентов идентичен прежнему контракту; результат —
    newest-first с отсечкой limit.
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

        legacy_rows = [
            DermaProcedureHistoryOut.model_validate(row)
            for row in query.order_by(
                desc(DermaProcedure.procedure_date),
                desc(DermaProcedure.created_at),
                desc(DermaProcedure.id),
            )
            .limit(limit)
            .all()
        ]
        records, visits = _derma_emr_snapshot(db, user, patient_id)
        emr_rows = _emr_procedure_rows(records, visits)
        procedures = _merge_history_rows(legacy_rows, emr_rows, limit)
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
    косметические процедуры сохраняются в specialty_data.procedures ЭМК
    (emr/v2). Возврат 410 до любого доступа к БД — fail-closed для всех
    ролей, включая Admin: двойная запись (legacy + ЭМК) расщепляла
    клинические данные по двум таблицам. Чтение истории —
    GET /derma/procedures — объединяет ЭМК-процедуры и read-only
    legacy-строки (P2-4b).
    """
    logger.warning(
        "[derma.procedures] rejected legacy write user_id=%s",
        getattr(user, "id", None),
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Эндпоинт закрыт: косметические процедуры сохраняются в specialty_data "
            "ЭМК. Таблица derma_procedures доступна только для чтения (история)."
        ),
    )


@router.get(
    "/history",
    summary="История дерматологии: осмотры + процедуры (ЭМК + legacy)",
    response_model=DermaHistoryOut,
)
async def get_derma_history(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> DermaHistoryOut:
    """
    Единый read-model истории дерматологии (triage P2 follow-up к #3491).

    Обе секции (examinations, procedures) проецируются из ОДНОГО скана
    ЭМК-кандидатов и ОДНОЙ загрузки Visit-набора; RBAC-скоуп
    (разрешённые пациенты врача) резолвится ОДИН раз и кормит и ЭМК-скан,
    и оба legacy-запроса. Фронтенд-хук истории читает оба раздела одним
    запросом вместо пары гранулярных GET /derma/examinations и
    GET /derma/procedures, каждый из которых сканировал ЭМК независимо.
    Скоупинг пациентов, объединение источников (ЭМК + read-only legacy)
    и порядок — идентичны гранулярным GET; ``limit`` применяется к каждой
    секции отдельно после полного union.
    """
    try:
        # RBAC is resolved exactly once for the whole read-model: the same
        # patient scope feeds the EMR scan and both legacy queries.
        if not _is_admin_user(user):
            allowed_patient_ids = _doctor_allowed_patient_ids(db, user)
            if patient_id is not None:
                if patient_id not in allowed_patient_ids:
                    raise HTTPException(status_code=403, detail="Access denied")
                scope_ids: set[int] | None = {patient_id}
            else:
                if not allowed_patient_ids:
                    return DermaHistoryOut(examinations=[], procedures=[])
                scope_ids = allowed_patient_ids
        else:
            scope_ids = {patient_id} if patient_id is not None else None

        records = _emr_candidate_records_scoped(db, scope_ids)
        visits = _derma_emr_visits(db, records)
        exam_emr_rows = _emr_examination_rows(records, visits)
        procedure_emr_rows = _emr_procedure_rows(records, visits)

        exam_query = db.query(DermaExamination)
        procedure_query = db.query(DermaProcedure)
        if scope_ids is not None:
            exam_query = exam_query.filter(
                DermaExamination.patient_id.in_(scope_ids)
            )
            procedure_query = procedure_query.filter(
                DermaProcedure.patient_id.in_(scope_ids)
            )

        legacy_exam_rows = [
            DermaExaminationHistoryOut.model_validate(row)
            for row in exam_query.order_by(
                desc(DermaExamination.examination_date),
                desc(DermaExamination.created_at),
                desc(DermaExamination.id),
            )
            .limit(limit)
            .all()
        ]
        legacy_procedure_rows = [
            DermaProcedureHistoryOut.model_validate(row)
            for row in procedure_query.order_by(
                desc(DermaProcedure.procedure_date),
                desc(DermaProcedure.created_at),
                desc(DermaProcedure.id),
            )
            .limit(limit)
            .all()
        ]
        history = DermaHistoryOut(
            examinations=_merge_history_rows(legacy_exam_rows, exam_emr_rows, limit),
            procedures=_merge_history_rows(
                legacy_procedure_rows, procedure_emr_rows, limit
            ),
        )
        logger.info(
            "[derma.history] listed history user_id=%s patient_id=%s "
            "examinations=%s procedures=%s",
            getattr(user, "id", None),
            patient_id,
            len(history.examinations),
            len(history.procedures),
        )
        return history
    except SQLAlchemyError:
        logger.exception(
            "[derma.history] failed to list history user_id=%s patient_id=%s",
            getattr(user, "id", None),
            patient_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
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
