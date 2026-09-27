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
    DermaExaminationHistoryPage,
    DermaExaminationOut,
    DermaProcedureCreate,
    DermaProcedureHistoryOut,
    DermaProcedureHistoryPage,
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


# --- Unified derma history (review follow-up P2-4b, canonical server-side union) ---
#
# The history GETs below union two read-only sources server-side: rows
# projected out of dermatology EMR records (emr/v2, data.specialty) and the
# closed legacy tables. The dermatology filter itself runs in SQL —
# EMRRecord.data["specialty"].as_string() compiles portably (JSON_EXTRACT on
# the SQLite test harness, ->> on PostgreSQL JSONB) — so the candidate set
# is exact and uncapped: no recency scan window, no silent truncation
# (review P1 on #3490/#3491). The merged history is paginated with the
# canonical page/size/total/pages envelope (FileList contract), so consumers
# get an explicit completeness signal instead of asymmetric client-side
# source limits (review P2 on #3490).
_EXAM_TEXT_FIELDS = (
    "skin_type",
    "skin_condition",
    "lesions",
    "distribution",
    "symptoms",
    "treatment_plan",
)


def _apply_history_patient_scope(
    db: Session,
    query: Any,
    patient_id: int | None,
    user: User,
    patient_id_column: Any,
) -> Any:
    """Apply the patient scoping shared by both history sources.

    Doctors are limited to the patients of their own visits (403 when the
    explicitly requested patient is foreign); admins see everything,
    optionally narrowed to one patient. Returns the scoped query or None
    when a doctor has no allowed patients at all (empty history).
    """
    if not _is_admin_user(user):
        if patient_id is not None:
            _ensure_doctor_can_access_patient(db, patient_id, user)
        else:
            allowed_patient_ids = _doctor_allowed_patient_ids(db, user)
            if not allowed_patient_ids:
                return None
            query = query.filter(patient_id_column.in_(allowed_patient_ids))
    if patient_id is not None:
        query = query.filter(patient_id_column == patient_id)
    return query


def _derma_emr_records(
    db: Session, user: User, patient_id: int | None
) -> list[EMRRecord]:
    """All active dermatology EMR records in scope, newest first (uncapped)."""
    query = db.query(EMRRecord).filter(
        EMRRecord.is_active.is_(True),
        EMRRecord.data["specialty"].as_string() == "dermatology",
    )
    query = _apply_history_patient_scope(
        db, query, patient_id, user, EMRRecord.patient_id
    )
    if query is None:
        return []
    return query.order_by(desc(EMRRecord.created_at), desc(EMRRecord.id)).all()


def _history_visit_map(db: Session, records: list[EMRRecord]) -> dict[int, Visit]:
    visit_ids = {r.visit_id for r in records if r.visit_id is not None}
    if not visit_ids:
        return {}
    return {v.id: v for v in db.query(Visit).filter(Visit.id.in_(visit_ids)).all()}


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _history_exam_date(visit: Visit | None, record: EMRRecord) -> date:
    visit_date = getattr(visit, "visit_date", None)
    if visit_date:
        return visit_date
    if record.created_at:
        return record.created_at.date()
    return date.today()


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


def _emr_examination_rows(
    records: list[EMRRecord], visits: dict[int, Visit]
) -> list[DermaExaminationHistoryOut]:
    rows: list[DermaExaminationHistoryOut] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
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
                examination_date=_history_exam_date(visit, record),
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
    """Project specialty_data.cosmetic_procedures entries into history rows."""
    rows: list[DermaProcedureHistoryOut] = []
    for record in records:
        data = record.data if isinstance(record.data, dict) else {}
        specialty_data = data.get("specialty_data")
        if not isinstance(specialty_data, dict):
            continue
        entries = specialty_data.get("cosmetic_procedures")
        if not isinstance(entries, list):
            continue
        visit = visits.get(record.visit_id)
        fallback_date = _history_exam_date(visit, record)
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
                    created_at=record.created_at,
                    updated_at=None,
                )
            )
    return rows


def _history_sort_key(row: Any) -> tuple[Any, ...]:
    primary_date = (
        row.examination_date
        if hasattr(row, "examination_date")
        else row.procedure_date
    )
    created = row.created_at or datetime.min
    if created.tzinfo is not None:
        created = created.replace(tzinfo=None)
    return (primary_date, created)


def _merge_history_rows(legacy_rows: list[Any], emr_rows: list[Any]) -> list[Any]:
    """Union both read-only sources, newest first.

    Ties keep EMR rows ahead of legacy rows and preserve each source's
    build order (EMR entries stay in array order inside one record,
    mirroring the stable-sort merge order of the previous client-side
    implementation). Numeric positions are the only tie-breaker: a
    lexicographic fallback on the synthetic string ids would misorder
    records as soon as record ids gain a digit ("emr-9-3" vs "emr-10-0").
    """
    keyed: list[tuple[tuple[Any, ...], Any]] = [
        (*_history_sort_key(row), -position, row)
        for position, row in enumerate(emr_rows)
    ]
    keyed.extend(
        (*_history_sort_key(row), -(len(emr_rows) + position), row)
        for position, row in enumerate(legacy_rows)
    )
    keyed.sort(key=lambda entry: entry[:-1], reverse=True)
    return [entry[-1] for entry in keyed]


def _paginate_history(
    legacy_rows: list[Any], emr_rows: list[Any], page: int, size: int
) -> tuple[list[Any], int, int]:
    """Union both read-only sources, newest first, exact total, page slice."""
    merged = _merge_history_rows(legacy_rows, emr_rows)
    total = len(merged)
    pages = (total + size - 1) // size
    start = (page - 1) * size
    return merged[start : start + size], total, pages


@router.get(
    "/examinations",
    summary="Осмотры кожи (история: ЭМК + legacy)",
    response_model=DermaExaminationHistoryPage,
)
async def get_skin_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    patient_id: int | None = None,
) -> DermaExaminationHistoryPage:
    """
    История осмотров кожи (review follow-up P2-4b).

    Объединяет два read-only источника: осмотры из specialty_data ЭМК
    (emr/v2, specialty=dermatology, source="emr") и строки закрытой
    legacy-таблицы derma_examinations (source="legacy"). Скоупинг
    пациентов идентичен прежнему контракту. Пагинация — канонический
    конверт page/size/total/pages (контракт GET /files): total точен по
    обоим источникам, без скрытых усечений.
    """
    try:
        query = _apply_history_patient_scope(
            db,
            db.query(DermaExamination),
            patient_id,
            user,
            DermaExamination.patient_id,
        )
        legacy_rows: list[DermaExaminationHistoryOut] = []
        if query is not None:
            legacy_rows = [
                DermaExaminationHistoryOut.model_validate(row)
                for row in query.order_by(
                    desc(DermaExamination.examination_date),
                    desc(DermaExamination.created_at),
                    desc(DermaExamination.id),
                ).all()
            ]
        records = _derma_emr_records(db, user, patient_id)
        visits = _history_visit_map(db, records)
        emr_rows = _emr_examination_rows(records, visits)
        page_items, total, pages = _paginate_history(
            legacy_rows, emr_rows, page, size
        )
        logger.info(
            "[derma.examinations] listed examinations user_id=%s patient_id=%s"
            " count=%s total=%s",
            getattr(user, "id", None),
            patient_id,
            len(page_items),
            total,
        )
        return DermaExaminationHistoryPage(
            items=page_items, total=total, page=page, size=size, pages=pages
        )
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
    Чтение истории — GET /derma/examinations — объединяет осмотры ЭМК
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
    response_model=DermaProcedureHistoryPage,
)
async def get_cosmetic_procedures(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DERMA_ROLES)),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    patient_id: int | None = None,
) -> DermaProcedureHistoryPage:
    """
    История косметических процедур (review follow-up P2-4b).

    Объединяет два read-only источника: процедуры из
    specialty_data.cosmetic_procedures ЭМК (emr/v2, specialty=dermatology,
    source="emr", total_cost=None — цена не хранится в ЭМК) и строки закрытой
    legacy-таблицы derma_procedures (source="legacy"). Скоупинг пациентов
    идентичен прежнему контракту. Пагинация — канонический конверт
    page/size/total/pages (контракт GET /files): total точен по обоим
    источникам, без скрытых усечений.
    """
    try:
        query = _apply_history_patient_scope(
            db,
            db.query(DermaProcedure),
            patient_id,
            user,
            DermaProcedure.patient_id,
        )
        legacy_rows: list[DermaProcedureHistoryOut] = []
        if query is not None:
            legacy_rows = [
                DermaProcedureHistoryOut.model_validate(row)
                for row in query.order_by(
                    desc(DermaProcedure.procedure_date),
                    desc(DermaProcedure.created_at),
                    desc(DermaProcedure.id),
                ).all()
            ]
        records = _derma_emr_records(db, user, patient_id)
        visits = _history_visit_map(db, records)
        emr_rows = _emr_procedure_rows(records, visits)
        page_items, total, pages = _paginate_history(
            legacy_rows, emr_rows, page, size
        )
        logger.info(
            "[derma.procedures] listed procedures user_id=%s patient_id=%s"
            " count=%s total=%s",
            getattr(user, "id", None),
            patient_id,
            len(page_items),
            total,
        )
        return DermaProcedureHistoryPage(
            items=page_items, total=total, page=page, size=size, pages=pages
        )
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
    объединяет процедуры ЭМК и read-only legacy-строки (P2-4b).
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
