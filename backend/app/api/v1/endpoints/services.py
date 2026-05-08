from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import service as crud
from app.models.clinic import Doctor, ServiceCategory
from app.models.service import Service
from app.models.visit import VisitService
from app.models.service_audit import ServiceAuditLog
from app.models.user import User
from app.services.service_mapping import (
    get_allowed_service_code_prefixes,
    normalize_service_code,
    resolve_queue_group_key,
)
from app.services.service_audit_service import ServiceAuditService

router = APIRouter(tags=["services"])
logger = logging.getLogger(__name__)


class ServiceCategoryOut(BaseModel):
    id: int
    code: str
    name_ru: Optional[str] = None
    name_uz: Optional[str] = None
    name_en: Optional[str] = None
    specialty: Optional[str] = None
    active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ServiceCategoryCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name_ru: Optional[str] = Field(None, max_length=100)
    name_uz: Optional[str] = Field(None, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(None, max_length=100)
    active: bool = True


class ServiceCategoryUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name_ru: Optional[str] = Field(None, max_length=100)
    name_uz: Optional[str] = Field(None, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(None, max_length=100)
    active: Optional[bool] = None


class ServiceOut(BaseModel):
    id: int
    code: Optional[str] = None
    name: str
    department: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    active: bool = True
    category_id: Optional[int] = None
    duration_minutes: Optional[int] = None
    doctor_id: Optional[int] = None
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: Optional[str] = None  # K, D, C, L, S, O
    service_code: Optional[str] = None  # K01, D02, C03, etc.
    requires_doctor: Optional[bool] = None
    queue_tag: Optional[str] = None
    is_consultation: Optional[bool] = None
    allow_doctor_price_override: Optional[bool] = None
    department_key: Optional[str] = None  # ✅ ДОБАВЛЕНО: связь с отделением

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    code: Optional[str] = Field(None, max_length=32)
    name: str = Field(..., max_length=256)
    department: Optional[str] = Field(None, max_length=64)
    unit: Optional[str] = Field(None, max_length=32)
    price: Optional[Decimal] = None
    currency: Optional[str] = Field("UZS", max_length=8)
    active: bool = True
    category_id: Optional[int] = None
    duration_minutes: Optional[int] = Field(30, ge=1, le=480)
    doctor_id: Optional[int] = None
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: Optional[str] = Field(None, max_length=2, pattern="^[KDCLSOP]$")
    service_code: Optional[str] = Field(None, max_length=16)
    requires_doctor: bool = False
    queue_tag: Optional[str] = Field(None, max_length=32)
    is_consultation: bool = False
    allow_doctor_price_override: bool = False
    department_key: Optional[str] = Field(
        None, max_length=50
    )  # ✅ ДОБАВЛЕНО: связь с отделением


class ServiceUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=32)
    name: Optional[str] = Field(None, max_length=256)
    department: Optional[str] = Field(None, max_length=64)
    unit: Optional[str] = Field(None, max_length=32)
    price: Optional[Decimal] = None
    currency: Optional[str] = Field(None, max_length=8)
    active: Optional[bool] = None
    category_id: Optional[int] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    doctor_id: Optional[int] = None
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: Optional[str] = Field(None, max_length=2, pattern="^[KDCLSOP]$")
    service_code: Optional[str] = Field(None, max_length=16)
    requires_doctor: Optional[bool] = None
    queue_tag: Optional[str] = Field(None, max_length=32)
    is_consultation: Optional[bool] = None
    allow_doctor_price_override: Optional[bool] = None
    department_key: Optional[str] = Field(
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


def _row_to_out(r) -> ServiceOut:
    price = None
    try:
        price = float(r.price) if r.price is not None else None
    except Exception:
        price = None
    return ServiceOut(
        id=r.id,
        code=r.service_code or r.code,
        name=r.name,
        department=r.department,
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
    response_model=List[ServiceCategoryOut],
    summary="Список категорий услуг",
)
async def list_service_categories(
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin", "Registrar", "Doctor")),
    active: Optional[bool] = Query(default=None),
):
    """Получить список всех категорий услуг"""
    query = db.query(ServiceCategory)
    if active is not None:
        query = query.filter(ServiceCategory.active == active)
    categories = query.order_by(ServiceCategory.name_ru).all()
    return categories


@router.post(
    "/categories", response_model=ServiceCategoryOut, summary="Создать категорию услуг"
)
async def create_service_category(
    category_data: ServiceCategoryCreate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Создать новую категорию услуг"""
    # Проверяем уникальность кода
    existing = (
        db.query(ServiceCategory)
        .filter(ServiceCategory.code == category_data.code)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Категория с кодом '{category_data.code}' уже существует",
        )

    category = ServiceCategory(**category_data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


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
    """Обновить существующую категорию услуг"""
    category = (
        db.query(ServiceCategory).filter(ServiceCategory.id == category_id).first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # Проверяем уникальность кода при обновлении
    if category_data.code and category_data.code != category.code:
        existing = (
            db.query(ServiceCategory)
            .filter(ServiceCategory.code == category_data.code)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Категория с кодом '{category_data.code}' уже существует",
            )

    for field, value in category_data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", summary="Удалить категорию услуг")
async def delete_service_category(
    category_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Удалить категорию услуг"""
    category = (
        db.query(ServiceCategory).filter(ServiceCategory.id == category_id).first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # Проверяем, есть ли связанные услуги
    services_count = (
        db.query(Service).filter(Service.category_id == category_id).count()
    )
    if services_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить категорию: к ней привязано {services_count} услуг",
        )

    db.delete(category)
    db.commit()
    return {"message": "Категория успешно удалена"}


# ==================== УСЛУГИ ====================


@router.get("", response_model=List[ServiceOut], summary="Каталог услуг")
async def list_services(
    db: Session = Depends(get_db),
    # user=Depends(
    #     require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier", "User")
    # ),
    q: Optional[str] = Query(default=None, max_length=120),
    active: Optional[bool] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    department: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Получить список услуг с фильтрацией"""
    try:
        rows = crud.list_services(db, q=q, active=active, limit=limit, offset=offset)

        # Дополнительная фильтрация
        if category_id is not None:
            rows = [r for r in rows if getattr(r, 'category_id', None) == category_id]
        if department:
            rows = [r for r in rows if getattr(r, 'department', None) == department]

        return [_row_to_out(r) for r in rows]
    except Exception as e:
        import traceback

        print(f"Error in list_services: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения услуг: {str(e)}")


# ==================== QUEUE GROUPS (SSOT) - MUST BE BEFORE /{service_id} ====================


class QueueGroupInfo(BaseModel):
    """Schema for a single queue group"""
    display_name: str
    display_name_uz: Optional[str] = None
    service_codes: List[str] = []
    service_prefixes: List[str] = []
    exclude_codes: List[str] = []
    queue_tag: str
    tab_key: str


class QueueGroupsResponse(BaseModel):
    """Response schema for queue-groups endpoint"""
    groups: Dict[str, QueueGroupInfo] = {}
    code_to_group: Dict[str, str] = {}
    tab_to_group: Dict[str, str] = {}


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
    from app.services.service_mapping import QUEUE_GROUPS, get_queue_group_for_service
    
    # Build groups from SSOT
    groups = {}
    for key, data in QUEUE_GROUPS.items():
        groups[key] = QueueGroupInfo(
            display_name=data["display_name"],
            display_name_uz=data.get("display_name_uz"),
            service_codes=data.get("service_codes", []),
            service_prefixes=data.get("service_prefixes", []),
            exclude_codes=data.get("exclude_codes", []),
            queue_tag=data["queue_tag"],
            tab_key=data["tab_key"],
        )
    
    # Build code_to_group mapping
    code_to_group = {}
    
    # Add explicit service codes
    for key, data in QUEUE_GROUPS.items():
        for code in data.get("service_codes", []):
            code_to_group[code] = key
    
    # Enrich with actual DB data
    try:
        services = db.query(Service).filter(Service.active == True).all()
        for service in services:
            if service.service_code:
                group = get_queue_group_for_service(service.service_code)
                if group:
                    code_to_group[service.service_code] = group
    except Exception:
        pass  # Use static mappings if DB query fails
    
    # Build tab_to_group mapping
    tab_to_group = {data["tab_key"]: key for key, data in QUEUE_GROUPS.items()}
    
    return QueueGroupsResponse(
        groups=groups,
        code_to_group=code_to_group,
        tab_to_group=tab_to_group,
    )


class ServiceCodeRepairItem(BaseModel):
    id: int
    before_code: Optional[str] = None
    before_service_code: Optional[str] = None
    after_code: Optional[str] = None
    after_service_code: Optional[str] = None
    changed: bool = False


class ServiceCodeRepairResponse(BaseModel):
    dry_run: bool
    scanned: int
    updated: int
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    affected_services: List[ServiceCodeRepairItem] = Field(default_factory=list)


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


@router.get("/{service_id}", response_model=ServiceOut, summary="Получить услугу по ID")
async def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Получить конкретную услугу по ID"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    return _row_to_out(service)


@router.post("", response_model=ServiceOut, summary="Создать услугу")
async def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Создать новую услугу"""
    service_dict = service_data.model_dump()
    canonical_code = _normalize_service_code_payload(service_dict)

    # Проверяем уникальность кода
    if canonical_code:
        existing = (
            db.query(Service)
            .filter(or_(Service.code == canonical_code, Service.service_code == canonical_code))
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Услуга с кодом '{canonical_code}' уже существует",
            )

    # Проверяем существование категории
    category_specialty = _resolve_category_specialty(db, service_dict.get("category_id"))

    if service_dict.get('code'):
        service_dict['code'] = normalize_service_code(service_dict['code'])
    if service_dict.get('service_code'):
        service_dict['service_code'] = normalize_service_code(
            service_dict['service_code']
        )
    if service_dict.get('category_code'):
        service_dict['category_code'] = _normalize_category_code_value(
            service_dict['category_code']
        )

    _validate_service_code_prefix_alignment(
        service_code=canonical_code,
        category_specialty=category_specialty,
        queue_tag=service_dict.get("queue_tag"),
        department_key=service_dict.get("department_key"),
        category_code=service_dict.get("category_code"),
    )

    service = Service(**service_dict)
    db.add(service)
    db.commit()
    db.refresh(service)

    # ✅ AUDIT: Log service creation
    try:
        audit_service = ServiceAuditService(db)
        audit_service.log_service_creation(
            service=service,
            user_id=None,  # TODO: Get from current_user when auth is enabled
        )
    except Exception as e:
        logger.warning(f"Failed to log service audit: {e}")

    return _row_to_out(service)


@router.put("/{service_id}", response_model=ServiceOut, summary="Обновить услугу")
async def update_service(
    service_id: int,
    service_data: ServiceUpdate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Обновить существующую услугу"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    # ✅ AUDIT: Snapshot old service state before changes
    audit_service = ServiceAuditService(db)
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

    update_dict = service_data.model_dump(exclude_unset=True)
    canonical_code = _normalize_service_code_payload(update_dict)

    # Проверяем уникальность кода при обновлении
    current_code = service.service_code or service.code
    if canonical_code and canonical_code != current_code:
        existing = (
            db.query(Service)
            .filter(Service.id != service_id)
            .filter(or_(Service.code == canonical_code, Service.service_code == canonical_code))
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Услуга с кодом '{canonical_code}' уже существует",
            )

    # Проверяем существование категории
    category_specialty = _resolve_category_specialty(
        db, update_dict.get("category_id", service.category_id)
    )

    if 'code' in update_dict and update_dict['code'] is not None:
        update_dict['code'] = normalize_service_code(update_dict['code'])
    if 'service_code' in update_dict and update_dict['service_code'] is not None:
        update_dict['service_code'] = normalize_service_code(
            update_dict['service_code']
        )
    if 'category_code' in update_dict and update_dict['category_code'] is not None:
        update_dict['category_code'] = _normalize_category_code_value(
            update_dict['category_code']
        )

    if _should_validate_service_code_alignment(update_dict, service):
        merged_service_code = (
            update_dict.get("service_code")
            or update_dict.get("code")
            or service.service_code
            or service.code
        )
        _validate_service_code_prefix_alignment(
            service_code=merged_service_code,
            category_specialty=category_specialty,
            queue_tag=update_dict.get("queue_tag", service.queue_tag),
            department_key=update_dict.get("department_key", service.department_key),
            category_code=update_dict.get("category_code", service.category_code),
        )

    for field, value in update_dict.items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)

    # ✅ AUDIT: Log the update
    try:
        audit_service.log_service_update(
            service_id=service.id,
            old_service=old_service_snapshot,
            new_service=service,
            user_id=None,  # TODO: Get from current_user when auth is enabled
            # ip_address=request.client.host,  # TODO: Add request dependency
            # user_agent=request.headers.get("user-agent"),
        )
    except Exception as e:
        logger.warning(f"Failed to log service audit: {e}")

    return _row_to_out(service)


@router.delete("/{service_id}", summary="Удалить услугу")
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Деактивировать услугу вместо физического удаления."""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    visit_usage_count = (
        db.query(VisitService)
        .filter(VisitService.service_id == service_id)
        .count()
    )

    changed = False
    if service.active:
        service.active = False
        changed = True

    if changed:
        db.add(service)

    db.commit()
    db.refresh(service)

    # ✅ AUDIT: Log service deactivation/deletion
    try:
        audit_service = ServiceAuditService(db)
        audit_service.log_service_change(
            service_id=service.id,
            action="deactivate",
            user_id=None,  # TODO: Get from current_user when auth is enabled
            changes={"active": {"old": True, "new": False}},
            comment=f"Soft delete (visit usage: {visit_usage_count})",
        )
    except Exception as e:
        logger.warning(f"Failed to log service audit: {e}")

    if visit_usage_count > 0:
        logger.info(
            "[FIX:SVC-DELETE] service_id=%s has visit history=%s; soft-deactivated instead of deleting",
            service_id,
            visit_usage_count,
        )
        return {
            "message": (
                "Услуга уже использовалась в истории визитов, поэтому она "
                "деактивирована вместо удаления"
            ),
            "service_id": service_id,
            "active": service.active,
            "visit_usage_count": visit_usage_count,
        }

    logger.info(
        "[FIX:SVC-DELETE] service_id=%s soft-deactivated instead of deleting",
        service_id,
    )
    return {
        "message": "Услуга деактивирована вместо удаления",
        "service_id": service_id,
        "active": service.active,
        "visit_usage_count": visit_usage_count,
    }


# ==================== ВРЕМЕННЫЙ ENDPOINT ДЛЯ ВРАЧЕЙ ====================


class DoctorOut(BaseModel):
    id: int
    specialty: str
    cabinet: Optional[str] = None
    active: bool = True

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/admin/doctors",
    response_model=List[DoctorOut],
    summary="Список врачей (временный)",
)
async def list_doctors_temp(
    db: Session = Depends(get_db),
):
    """Временный endpoint для получения списка врачей"""
    doctors = db.query(Doctor).filter(Doctor.active == True).all()
    return doctors


# ==================== ИСТОРИЯ ИЗМЕНЕНИЙ УСЛУГ (AUDIT LOG) ====================


class ServiceAuditLogOut(BaseModel):
    """Response schema for service audit log"""

    id: int
    service_id: int
    user_id: Optional[int] = None
    action: str
    changes: Optional[dict] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    comment: Optional[str] = None
    created_at: datetime

    # Enriched fields
    user_name: Optional[str] = None
    service_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/{service_id}/history",
    response_model=List[ServiceAuditLogOut],
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
    response_model=List[ServiceAuditLogOut],
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

    service_id: Optional[int] = None
    service_code: Optional[str] = None
    normalized_code: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    departments: List[str] = []
    ui_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/resolve", response_model=ServiceResolveResponse, summary="Разрешить услугу (SSOT)"
)
async def resolve_service_endpoint(
    service_id: Optional[int] = Query(None, description="ID услуги"),
    code: Optional[str] = Query(None, description="Код услуги"),
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


class ServiceCodeMappingsResponse(BaseModel):
    """Response schema for service code mappings endpoint"""

    specialty_to_code: dict = {}
    code_to_name: dict = {}
    category_mapping: dict = {}
    specialty_aliases: dict = {}


class ServiceBatchUpdateRequest(BaseModel):
    """Request schema for batch update"""

    service_ids: List[int] = Field(..., min_items=1, max_items=100)
    updates: Dict[str, Any] = Field(..., min_items=1)
    comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceBatchUpdateResponse(BaseModel):
    """Response schema for batch update"""

    updated_count: int
    failed_count: int
    updated_services: List[int] = []
    failed_services: List[Dict[str, Any]] = []

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
    
    Используется для централизации service code resolution на frontend.
    
    Returns:
        - specialty_to_code: Маппинг specialty -> default service code (K01, D01, etc.)
        - code_to_name: Маппинг service code -> display name
        - category_mapping: Маппинг specialty -> category code (K, D, L, etc.)
        - specialty_aliases: Алиасы для specialty (derma -> dermatology)
    """
    from app.services.service_mapping import SPECIALTY_ALIASES
    
    # Static mappings from SSOT
    specialty_to_code = {
        "cardiology": "K01",
        "cardio": "K01",
        "dermatology": "D01",
        "derma": "D01",
        "stomatology": "S01",
        "dental": "S01",
        "laboratory": "L01",
        "lab": "L01",
        "ecg": "K10",
        "echokg": "K11",
        "echo": "K11",
        "procedures": "P01",
        "cosmetology": "C01",
    }
    
    code_to_name = {
        "K01": "Консультация кардиолога",
        "K10": "ЭКГ",
        "K11": "ЭхоКГ",
        "D01": "Консультация дерматолога",
        "S01": "Консультация стоматолога",
        "L01": "Лабораторные анализы",
        "P01": "Процедуры",
        "C01": "Косметология",
    }
    
    category_mapping = {
        "cardiology": "K",
        "ecg": "K",
        "echokg": "K",
        "dermatology": "D",
        "laboratory": "L",
        "stomatology": "S",
        "cosmetology": "C",
        "procedures": "P",
    }
    
    # Try to enrich with actual DB data
    try:
        services = db.query(Service).filter(Service.active == True).all()
        for service in services:
            if service.service_code and service.name:
                code_to_name[service.service_code] = service.name
            if service.queue_tag and service.service_code:
                if service.queue_tag in {"ecg", "echokg", "echo"}:
                    continue
                specialty_to_code[service.queue_tag] = service.service_code
    except Exception:
        pass  # Use static mappings if DB query fails
    
    return ServiceCodeMappingsResponse(
        specialty_to_code=specialty_to_code,
        code_to_name=code_to_name,
        category_mapping=category_mapping,
        specialty_aliases=SPECIALTY_ALIASES,
    )


