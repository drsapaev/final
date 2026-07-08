from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.clinic import ServiceCategory
from app.models.service import Service
from app.models.user import User
from app.services.queue_domain_service import QueueDomainService
from app.services.service_audit_service import ServiceAuditService
from app.services.service_mapping import (
    get_allowed_service_code_prefixes,
    normalize_service_code,
    resolve_queue_group_key,
)
from app.services.services_api_service import ServicesApiService

router = APIRouter(tags=["services"])
logger = logging.getLogger(__name__)


class ServiceCategoryOut(BaseModel):
    id: int
    code: str
    name_ru: str | None = None
    name_uz: str | None = None
    name_en: str | None = None
    specialty: str | None = None
    active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ServiceCategoryCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name_ru: str | None = Field(None, max_length=100)
    name_uz: str | None = Field(None, max_length=100)
    name_en: str | None = Field(None, max_length=100)
    specialty: str | None = Field(None, max_length=100)
    active: bool = True


class ServiceCategoryUpdate(BaseModel):
    code: str | None = Field(None, max_length=50)
    name_ru: str | None = Field(None, max_length=100)
    name_uz: str | None = Field(None, max_length=100)
    name_en: str | None = Field(None, max_length=100)
    specialty: str | None = Field(None, max_length=100)
    active: bool | None = None


class ServiceOut(BaseModel):
    id: int
    code: str | None = None
    name: str
    department: str | None = None
    unit: str | None = None
    price: float | None = None
    currency: str | None = None
    active: bool = True
    category_id: int | None = None
    duration_minutes: int | None = None
    doctor_id: int | None = None
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: str | None = None  # K, D, C, L, S, O
    service_code: str | None = None  # K01, D02, C03, etc.
    requires_doctor: bool | None = None
    queue_tag: str | None = None
    is_consultation: bool | None = None
    allow_doctor_price_override: bool | None = None
    department_key: str | None = None  # ✅ ДОБАВЛЕНО: связь с отделением

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    code: str | None = Field(None, max_length=32)
    name: str = Field(..., max_length=256)
    department: str | None = Field(None, max_length=64)
    unit: str | None = Field(None, max_length=32)
    price: Decimal | None = None
    currency: str | None = Field("UZS", max_length=8)
    active: bool = True
    category_id: int | None = None
    duration_minutes: int | None = Field(30, ge=1, le=480)
    doctor_id: int | None = None
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: str | None = Field(None, max_length=2, pattern="^[KDCLSOP]$")
    service_code: str | None = Field(None, max_length=16)
    requires_doctor: bool = False
    queue_tag: str | None = Field(None, max_length=32)
    is_consultation: bool = False
    allow_doctor_price_override: bool = False
    department_key: str | None = Field(
        None, max_length=50
    )  # ✅ ДОБАВЛЕНО: связь с отделением


class ServiceUpdate(BaseModel):
    code: str | None = Field(None, max_length=32)
    name: str | None = Field(None, max_length=256)
    department: str | None = Field(None, max_length=64)
    unit: str | None = Field(None, max_length=32)
    price: Decimal | None = None
    currency: str | None = Field(None, max_length=8)
    active: bool | None = None
    category_id: int | None = None
    duration_minutes: int | None = Field(None, ge=1, le=480)
    doctor_id: int | None = None
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: str | None = Field(None, max_length=2, pattern="^[KDCLSOP]$")
    service_code: str | None = Field(None, max_length=16)
    requires_doctor: bool | None = None
    queue_tag: str | None = Field(None, max_length=32)
    is_consultation: bool | None = None
    allow_doctor_price_override: bool | None = None
    department_key: str | None = Field(
        None, max_length=50
    )  # ✅ ДОБАВЛЕНО: связь с отделением


def _normalize_service_code_payload(payload: dict[str, Any]) -> str | None:
    """
    Canonicalize code/service_code to the same normalized value.

    This keeps the catalog from drifting into mixed code representations.
    """

    raw_code = payload.get("service_code") or payload.get("code")
    if not raw_code:
        return None

    if payload.get("code") and payload.get("service_code"):
        normalized_code = normalize_service_code(payload["code"])
        normalized_service_code = normalize_service_code(payload["service_code"])
        if normalized_code != normalized_service_code:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Поля code и service_code должны совпадать "
                    "и использовать один и тот же код услуги"
                ),
            )
        canonical_code = normalized_code
    else:
        canonical_code = normalize_service_code(raw_code)

    payload["code"] = canonical_code
    payload["service_code"] = canonical_code
    return canonical_code


def _normalize_category_code_value(value: str | None) -> str | None:
    if not value:
        return None

    normalized = normalize_service_code(value)
    if len(normalized) == 1 and normalized.isalpha():
        return normalized.upper()
    return normalized


def _resolve_category_specialty(
    db: Session, category_id: int | None
) -> str | None:
    if not category_id:
        return None

    category = (
        db.query(ServiceCategory).filter(ServiceCategory.id == category_id).first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Указанная категория не найдена")

    return category.specialty


def _validate_service_code_prefix_alignment(
    *,
    service_code: str | None,
    category_specialty: str | None,
    queue_tag: str | None,
    department_key: str | None,
    category_code: str | None,
) -> None:
    if not service_code:
        return

    normalized_code = normalize_service_code(service_code)
    if not re.match(r"^[A-Z]\d{1,2}$", normalized_code):
        logger.info(
            "[FIX:ADM-06] Legacy service code format accepted without prefix validation: %s",
            normalized_code,
        )
        return

    expected_group = resolve_queue_group_key(
        queue_tag=queue_tag,
        department_key=department_key,
    )
    allowed_prefixes = get_allowed_service_code_prefixes(
        queue_tag=queue_tag,
        department_key=department_key,
        category_specialty=category_specialty,
        category_code=category_code,
    )

    if expected_group and allowed_prefixes:
        prefix = normalized_code[0]
        if prefix not in allowed_prefixes:
            allowed = ", ".join(sorted(allowed_prefixes))
            logger.warning(
                (
                    "[FIX:ADM-06] Rejecting service code prefix mismatch: "
                    "code=%s prefix=%s expected_group=%s allowed_prefixes=%s "
                    "queue_tag=%s department_key=%s category_specialty=%s category_code=%s"
                ),
                normalized_code,
                prefix,
                expected_group,
                allowed,
                queue_tag,
                department_key,
                category_specialty,
                category_code,
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Код услуги {normalized_code} не согласован с выбранной "
                    f"категорией/очередью {expected_group}. Допустимые префиксы: {allowed}"
                ),
            )

    logger.info(
        "[FIX:ADM-06] Accepted service code prefix: code=%s expected_group=%s allowed_prefixes=%s",
        normalized_code,
        expected_group,
        sorted(allowed_prefixes) if allowed_prefixes else [],
    )


def _should_validate_service_code_alignment(
    change_set: dict[str, Any],
    existing_service: Service | None = None,
) -> bool:
    routing_fields = {
        "code",
        "service_code",
        "category_id",
        "queue_tag",
        "department_key",
        "category_code",
    }
    if existing_service is None:
        return True
    return bool(routing_fields.intersection(change_set.keys()))


def _coerce_department_value(row: Any) -> str | None:
    department = getattr(row, "department", None)
    if isinstance(department, str):
        return department
    if department is None:
        return None

    for attr in ("key", "name_ru", "name", "code"):
        value = getattr(department, attr, None)
        if isinstance(value, str) and value.strip():
            return value

    return None


def _row_to_out(r) -> ServiceOut:
    price = None
    try:
        price = float(r.price) if r.price is not None else None
    except Exception:
        price = None
    department = _coerce_department_value(r)
    return ServiceOut(
        id=r.id,
        code=r.service_code or r.code,
        name=r.name,
        department=department,
        unit=r.unit,
        price=price,
        currency=r.currency,
        active=bool(r.active),
        category_id=r.category_id,
        duration_minutes=r.duration_minutes,
        doctor_id=r.doctor_id,
        # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
        category_code=getattr(r, 'category_code', None),
        service_code=getattr(r, 'service_code', None) or r.code,
        requires_doctor=getattr(r, 'requires_doctor', None),
        queue_tag=getattr(r, 'queue_tag', None),
        is_consultation=getattr(r, 'is_consultation', None),
        allow_doctor_price_override=getattr(r, 'allow_doctor_price_override', None),
        department_key=getattr(r, 'department_key', None),  # ✅ ДОБАВЛЕНО
    )


# ==================== КАТЕГОРИИ УСЛУГ ====================


@router.get(
    "/categories",
    response_model=list[ServiceCategoryOut],
    summary="Список категорий услуг",
)
async def list_service_categories(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin", "Registrar", "Doctor")),
    active: bool | None = Query(default=None),
):
    """Delegate category listing to the service layer."""
    return ServicesApiService(db).list_service_categories(active=active)


@router.post(
    "/categories", response_model=ServiceCategoryOut, summary="Создать категорию услуг"
)
async def create_service_category(
    category_data: ServiceCategoryCreate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Delegate category creation to the service layer."""
    try:
        return ServicesApiService(db).create_service_category(
            category_data=category_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/categories/{category_id}",
    response_model=ServiceCategoryOut,
    summary="Обновить категорию услуг",
)
async def update_service_category(
    category_id: int,
    category_data: ServiceCategoryUpdate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Delegate category updates to the service layer."""
    try:
        return ServicesApiService(db).update_service_category(
            category_id=category_id,
            category_data=category_data,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/categories/{category_id}", summary="Удалить категорию услуг", response_model=dict[str, Any])
async def delete_service_category(
    category_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Delegate category deletion to the service layer."""
    try:
        return ServicesApiService(db).delete_service_category(
            category_id=category_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ==================== УСЛУГИ ====================


@router.get("", response_model=list[ServiceOut], summary="Каталог услуг")
async def list_services(
    db: Session = Depends(get_db),
    # user=Depends(
    #     require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")
    # ),
    q: str | None = Query(default=None, max_length=120),
    active: bool | None = Query(default=None),
    category_id: int | None = Query(default=None),
    department: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Delegate service listing to the service layer."""
    try:
        rows = ServicesApiService(db).list_services(
            q=q,
            active=active,
            category_id=category_id,
            department=department,
            limit=limit,
            offset=offset,
        )
        return [_row_to_out(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Error listing services: {str(exc)}",
        ) from exc


# ==================== QUEUE GROUPS (SSOT) - MUST BE BEFORE /{service_id} ====================


class QueueGroupInfo(BaseModel):
    """Schema for a single queue group"""
    display_name: str
    display_name_uz: str | None = None
    service_codes: list[str] = []
    service_prefixes: list[str] = []
    exclude_codes: list[str] = []
    queue_tag: str
    tab_key: str


class QueueGroupsResponse(BaseModel):
    """Response schema for queue-groups endpoint"""
    groups: dict[str, QueueGroupInfo] = {}
    code_to_group: dict[str, str] = {}
    tab_to_group: dict[str, str] = {}


@router.get(
    "/queue-groups",
    response_model=QueueGroupsResponse,
    summary="Получить группы очередей (SSOT)",
)
async def get_queue_groups(
    db: Session = Depends(get_db),
):
    """
    ⭐ SSOT: Возвращает структуру групп очередей для синхронизации frontend.

    Используется для:
    - Определения какие услуги относятся к какой вкладке регистратуры
    - Фильтрации записей по отделениям
    - Группировки услуг в одну очередь (Shared Queues)

    Returns:
        - groups: Словарь групп очередей с их настройками
        - code_to_group: Маппинг service_code -> group_key (K01 -> cardiology)
        - tab_to_group: Маппинг tab_key -> group_key (cardio -> cardiology)
    """
    payload = QueueDomainService(db).get_queue_groups_payload()
    groups = {
        key: QueueGroupInfo(**value)
        for key, value in payload["groups"].items()
    }
    return QueueGroupsResponse(
        groups=groups,
        code_to_group=payload["code_to_group"],
        tab_to_group=payload["tab_to_group"],
    )


# ==================== SERVICE CODE MAPPINGS (SSOT) - MUST BE BEFORE /{service_id} ====================

class ServiceCodeRepairItem(BaseModel):
    id: int
    before_code: str | None = None
    before_service_code: str | None = None
    after_code: str | None = None
    after_service_code: str | None = None
    changed: bool = False


class ServiceCodeRepairResponse(BaseModel):
    dry_run: bool
    scanned: int
    updated: int
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    affected_services: list[ServiceCodeRepairItem] = Field(default_factory=list)


@router.post(
    "/admin/repair-code-drift",
    response_model=ServiceCodeRepairResponse,
    summary="Нормализовать code/service_code в каталоге услуг",
)
async def repair_service_code_drift(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    dry_run: bool = Query(
        True,
        description="Только показать план исправления без записи в БД",
    ),
):
    """
    Deterministic repair for legacy service catalog drift.

    Canonical rule for this slice:
    - prefer `service_code` when present
    - otherwise fall back to `code`
    - write the same normalized value back to both fields

    This helper only touches the service catalog rows. It does not rewrite
    historical `VisitService` snapshots.
    """

    services = db.query(Service).order_by(Service.id).all()
    service_by_id = {service.id: service for service in services}
    seen_canonical_codes: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    affected_services: list[ServiceCodeRepairItem] = []

    for service in services:
        source_code = service.service_code or service.code
        if not source_code:
            continue

        canonical_code = normalize_service_code(source_code)
        if not canonical_code:
            continue

        owner_id = seen_canonical_codes.get(canonical_code)
        if owner_id is not None and owner_id != service.id:
            conflicts.append(
                {
                    "canonical_code": canonical_code,
                    "existing_service_id": owner_id,
                    "conflicting_service_id": service.id,
                    "existing_service_name": service_by_id[owner_id].name,
                    "conflicting_service_name": service.name,
                }
            )
            continue

        seen_canonical_codes[canonical_code] = service.id

        current_code = normalize_service_code(service.code) if service.code else None
        current_service_code = (
            normalize_service_code(service.service_code)
            if service.service_code
            else None
        )
        changed = current_code != canonical_code or current_service_code != canonical_code

        if changed:
            affected_services.append(
                ServiceCodeRepairItem(
                    id=service.id,
                    before_code=service.code,
                    before_service_code=service.service_code,
                    after_code=canonical_code,
                    after_service_code=canonical_code,
                    changed=True,
                )
            )

    if conflicts:
        logger.warning(
            "[FIX:SVC-REPAIR] Conflicts detected for service code repair: %s",
            conflicts,
        )
        if not dry_run:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        "Найдены конфликтующие коды услуг. Сначала устраните "
                        "дубликаты перед применением repair"
                    ),
                    "conflicts": conflicts,
                },
            )

    if not dry_run and affected_services:
        for item in affected_services:
            service = service_by_id[item.id]
            service.code = item.after_code
            service.service_code = item.after_service_code
            db.add(service)

        db.commit()
        logger.info(
            "[FIX:SVC-REPAIR] Applied service code repair: scanned=%s updated=%s conflicts=%s",
            len(services),
            len(affected_services),
            len(conflicts),
        )
    else:
        logger.info(
            "[FIX:SVC-REPAIR] Planned service code repair: scanned=%s updated=%s conflicts=%s dry_run=%s",
            len(services),
            len(affected_services),
            len(conflicts),
            dry_run,
        )

    return ServiceCodeRepairResponse(
        dry_run=dry_run,
        scanned=len(services),
        updated=len(affected_services) if not conflicts or dry_run else 0,
        conflicts=conflicts,
        affected_services=affected_services,
    )


@router.post("", response_model=ServiceOut, summary="Создать услугу")
async def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Delegate service creation to the service layer."""
    try:
        service = ServicesApiService(db).create_service(service_data=service_data)
        return _row_to_out(service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{service_id}", response_model=ServiceOut, summary="Обновить услугу")
async def update_service(
    service_id: int,
    service_data: ServiceUpdate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Delegate service updates to the service layer."""
    try:
        service = ServicesApiService(db).update_service(
            service_id=service_id,
            service_data=service_data,
        )
        return _row_to_out(service)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{service_id}", summary="Удалить услугу", response_model=dict[str, Any])
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Delegate service deletion to the service layer."""
    try:
        return ServicesApiService(db).delete_service(service_id=service_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ==================== ВРЕМЕННЫЙ ENDPOINT ДЛЯ ВРАЧЕЙ ====================


class DoctorOut(BaseModel):
    id: int
    specialty: str
    cabinet: str | None = None
    active: bool = True

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/admin/doctors",
    response_model=list[DoctorOut],
    summary="Список врачей (временный)",
)
async def list_doctors_temp(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
):
    """Delegate temporary doctor listing to the service layer."""
    # P1 FIX: cap results to prevent unbounded response
    return ServicesApiService(db).list_doctors_temp()[offset:offset + limit]


# ==================== ИСТОРИЯ ИЗМЕНЕНИЙ УСЛУГ (AUDIT LOG) ====================


class ServiceAuditLogOut(BaseModel):
    """Response schema for service audit log"""

    id: int
    service_id: int
    user_id: int | None = None
    action: str
    changes: dict | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    comment: str | None = None
    created_at: datetime

    # Enriched fields
    user_name: str | None = None
    service_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/{service_id}/history",
    response_model=list[ServiceAuditLogOut],
    summary="История изменений услуги",
)
async def get_service_history(
    service_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Получить историю изменений услуги.

    Возвращает все изменения услуги с информацией о том, кто и когда их сделал.
    """
    # Check if service exists
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    audit_service = ServiceAuditService(db)
    logs = audit_service.get_service_history(
        service_id=service_id,
        limit=limit,
        offset=offset,
    )

    # Enrich with user and service names
    result = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "service_id": log.service_id,
            "user_id": log.user_id,
            "action": log.action,
            "changes": log.changes,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "comment": log.comment,
            "created_at": log.created_at,
            "user_name": log.user.full_name if log.user else "Система",
            "service_name": service.name,
        }
        result.append(ServiceAuditLogOut(**log_dict))

    return result


@router.get(
    "/admin/audit/recent",
    response_model=list[ServiceAuditLogOut],
    summary="Последние изменения услуг",
)
async def get_recent_service_changes(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    Получить последние изменения всех услуг.

    Полезно для мониторинга активности и аудита.
    """
    audit_service = ServiceAuditService(db)
    logs = audit_service.get_recent_changes(
        limit=limit,
        offset=offset,
    )

    # Enrich with user and service names
    result = []
    for log in logs:
        service = db.query(Service).filter(Service.id == log.service_id).first()
        log_dict = {
            "id": log.id,
            "service_id": log.service_id,
            "user_id": log.user_id,
            "action": log.action,
            "changes": log.changes,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "comment": log.comment,
            "created_at": log.created_at,
            "user_name": log.user.full_name if log.user else "Система",
            "service_name": service.name if service else f"Услуга #{log.service_id}",
        }
        result.append(ServiceAuditLogOut(**log_dict))

    return result


# ==================== РАЗРЕШЕНИЕ УСЛУГ (SSOT) ====================


class ServiceResolveResponse(BaseModel):
    """Response schema для resolve_service endpoint"""

    service_id: int | None = None
    service_code: str | None = None
    normalized_code: str | None = None
    category: str | None = None
    subcategory: str | None = None
    departments: list[str] = []
    ui_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/resolve", response_model=ServiceResolveResponse, summary="Разрешить услугу (SSOT)"
)
async def resolve_service_endpoint(
    service_id: int | None = Query(None, description="ID услуги"),
    code: str | None = Query(None, description="Код услуги"),
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier")),
):
    """
    Универсальный endpoint для разрешения услуги.

    Возвращает полную информацию об услуге: нормализованный код, категорию,
    подкатегорию, отделения и UI-тип для фронтенда.

    Можно указать либо service_id, либо code (или оба).
    """
    from app.services.service_mapping import resolve_service

    # Валидация: должен быть указан хотя бы один параметр
    if not service_id and not code:
        raise HTTPException(
            status_code=400,
            detail="Необходимо указать либо service_id, либо code (или оба)",
        )

    # Вызов SSOT функции
    result = resolve_service(service_id=service_id, code=code, db=db)

    return ServiceResolveResponse(**result)


# ==================== SERVICE CODE MAPPINGS (SSOT) ====================


class ServiceBatchUpdateRequest(BaseModel):
    """Request schema for batch update"""

    service_ids: list[int] = Field(..., min_items=1, max_items=100)
    updates: dict[str, Any] = Field(..., min_items=1)
    comment: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ServiceBatchUpdateResponse(BaseModel):
    """Response schema for batch update"""

    updated_count: int
    failed_count: int
    updated_services: list[int] = []
    failed_services: list[dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "/admin/batch-update",
    response_model=ServiceBatchUpdateResponse,
    summary="Массовое обновление услуг",
)
async def batch_update_services(
    request: ServiceBatchUpdateRequest,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """
    Массовое обновление нескольких услуг одновременно.

    Позволяет изменить одинаковые поля у группы услуг.
    Например: изменить цену, активность, категорию и т.д.
    """
    updated_services = []
    failed_services = []
    audit_service = ServiceAuditService(db)

    for service_id in request.service_ids:
        try:
            service = db.query(Service).filter(Service.id == service_id).first()
            if not service:
                failed_services.append({
                    "service_id": service_id,
                    "error": "Услуга не найдена"
                })
                continue

            # Snapshot old state for audit
            old_service_snapshot = Service(
                id=service.id,
                code=service.code,
                service_code=service.service_code,
                name=service.name,
                category_id=service.category_id,
                category_code=service.category_code,
                price=service.price,
                currency=service.currency,
                duration_minutes=service.duration_minutes,
                doctor_id=service.doctor_id,
                department_key=service.department_key,
                queue_tag=service.queue_tag,
                requires_doctor=service.requires_doctor,
                is_consultation=service.is_consultation,
                allow_doctor_price_override=service.allow_doctor_price_override,
                active=service.active,
            )

            # Apply updates
            for field, value in request.updates.items():
                if hasattr(service, field):
                    setattr(service, field, value)

            db.add(service)
            db.flush()  # Flush to catch any DB errors before commit

            # Log audit
            try:
                audit_service.log_service_update(
                    service_id=service.id,
                    old_service=old_service_snapshot,
                    new_service=service,
                    user_id=None,
                    comment=f"Batch update: {request.comment}" if request.comment else "Batch update",
                )
            except Exception as e:
                logger.warning(f"Failed to log batch audit for service {service_id}: {e}")

            updated_services.append(service_id)

        except Exception as e:
            logger.error(f"Failed to update service {service_id}: {e}")
            failed_services.append({
                "service_id": service_id,
                "error": str(e)
            })

    # Commit all changes
    if updated_services:
        db.commit()

    return ServiceBatchUpdateResponse(
        updated_count=len(updated_services),
        failed_count=len(failed_services),
        updated_services=updated_services,
        failed_services=failed_services,
    )


class ServiceCodeMappingsResponse(BaseModel):
    """Response schema for service code mappings endpoint"""

    specialty_to_code: dict = {}
    code_to_name: dict = {}
    category_mapping: dict = {}


@router.get(
    "/code-mappings",
    response_model=ServiceCodeMappingsResponse,
    summary="Получить маппинги кодов услуг (SSOT)",
)
async def get_service_code_mappings(
    db: Session = Depends(get_db),
):
    """
    ⭐ SSOT: Возвращает все маппинги кодов услуг для синхронизации frontend.

    Используется frontend для:
        - specialty_aliases: Алиасы для specialty (derma -> dermatology)
        - specialty_to_code: Маппинг specialty -> service_code
        - code_to_name: Человекочитаемые названия кодов
        - category_mapping: Категории услуг для фильтрации
    """
    payload = QueueDomainService(db).get_service_code_mappings_payload()
    return ServiceCodeMappingsResponse(**payload)
@router.get("/{service_id}", response_model=ServiceOut, summary="Получить услугу по ID")
async def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Delegate service lookup to the service layer."""
    service = ServicesApiService(db).get_service(service_id=service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _row_to_out(service)

