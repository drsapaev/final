from __future__ import annotations

import logging  # noqa: F401
import re  # noqa: F401
from datetime import datetime  # noqa: F401
from decimal import Decimal  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query  # noqa: F401
from pydantic import BaseModel, ConfigDict, Field  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import get_db, require_roles  # noqa: F401
from app.models.clinic import ServiceCategory  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.queue_domain_service import QueueDomainService  # noqa: F401
from app.services.service_audit_service import ServiceAuditService  # noqa: F401
from app.services.service_mapping import (  # noqa: F401
    get_allowed_service_code_prefixes,
    normalize_service_code,
    resolve_queue_group_key,
)
from app.services.services_api_service import ServicesApiService  # noqa: F401

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


