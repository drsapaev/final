from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.services_api_service import ServicesApiService

router = APIRouter(tags=["services"])


class ServiceCategoryOut(BaseModel):
    id: int
    code: str
    name_ru: Optional[str] = None
    name_uz: Optional[str] = None
    name_en: Optional[str] = None
    specialty: Optional[str] = None
    active: bool = True

    class Config:
        from_attributes = True


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
    category_code: Optional[str] = None
    service_code: Optional[str] = None
    requires_doctor: Optional[bool] = None
    queue_tag: Optional[str] = None
    is_consultation: Optional[bool] = None
    allow_doctor_price_override: Optional[bool] = None
    department_key: Optional[str] = None

    class Config:
        from_attributes = True


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
    category_code: Optional[str] = Field(None, max_length=2, pattern="^[KDCLSOP]$")
    service_code: Optional[str] = Field(None, max_length=16)
    requires_doctor: bool = False
    queue_tag: Optional[str] = Field(None, max_length=32)
    is_consultation: bool = False
    allow_doctor_price_override: bool = False
    department_key: Optional[str] = Field(None, max_length=50)


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
    category_code: Optional[str] = Field(None, max_length=2, pattern="^[KDCLSOP]$")
    service_code: Optional[str] = Field(None, max_length=16)
    requires_doctor: Optional[bool] = None
    queue_tag: Optional[str] = Field(None, max_length=32)
    is_consultation: Optional[bool] = None
    allow_doctor_price_override: Optional[bool] = None
    department_key: Optional[str] = Field(None, max_length=50)


def _row_to_out(row) -> ServiceOut:
    price = None
    try:
        price = float(row.price) if row.price is not None else None
    except Exception:
        price = None
    return ServiceOut(
        id=row.id,
        code=row.code,
        name=row.name,
        department=row.department,
        unit=row.unit,
        price=price,
        currency=row.currency,
        active=bool(row.active),
        category_id=row.category_id,
        duration_minutes=row.duration_minutes,
        doctor_id=row.doctor_id,
        category_code=getattr(row, "category_code", None),
        service_code=getattr(row, "service_code", None),
        requires_doctor=getattr(row, "requires_doctor", None),
        queue_tag=getattr(row, "queue_tag", None),
        is_consultation=getattr(row, "is_consultation", None),
        allow_doctor_price_override=getattr(row, "allow_doctor_price_override", None),
        department_key=getattr(row, "department_key", None),
    )


class QueueGroupInfo(BaseModel):
    display_name: str
    display_name_uz: Optional[str] = None
    service_codes: List[str] = []
    service_prefixes: List[str] = []
    exclude_codes: List[str] = []
    queue_tag: str
    tab_key: str


class QueueGroupsResponse(BaseModel):
    groups: Dict[str, QueueGroupInfo] = {}
    code_to_group: Dict[str, str] = {}
    tab_to_group: Dict[str, str] = {}


class DoctorOut(BaseModel):
    id: int
    specialty: str
    cabinet: Optional[str] = None
    active: bool = True

    class Config:
        from_attributes = True


class ServiceResolveResponse(BaseModel):
    service_id: Optional[int] = None
    service_code: Optional[str] = None
    normalized_code: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    departments: List[str] = []
    ui_type: Optional[str] = None

    class Config:
        from_attributes = True


class ServiceCodeMappingsResponse(BaseModel):
    specialty_to_code: dict = {}
    code_to_name: dict = {}
    category_mapping: dict = {}
    specialty_aliases: dict = {}


@router.get("/categories", response_model=List[ServiceCategoryOut], summary="Список категорий услуг")
async def list_service_categories(
    db: Session = Depends(get_db),
    active: Optional[bool] = Query(default=None),
):
    return ServicesApiService(db).list_service_categories(active=active)


@router.post("/categories", response_model=ServiceCategoryOut, summary="Создать категорию услуг")
async def create_service_category(
    category_data: ServiceCategoryCreate,
    db: Session = Depends(get_db),
):
    try:
        return ServicesApiService(db).create_service_category(category_data=category_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/categories/{category_id}", response_model=ServiceCategoryOut, summary="Обновить категорию услуг")
async def update_service_category(
    category_id: int,
    category_data: ServiceCategoryUpdate,
    db: Session = Depends(get_db),
):
    try:
        return ServicesApiService(db).update_service_category(
            category_id=category_id,
            category_data=category_data,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/categories/{category_id}", summary="Удалить категорию услуг")
async def delete_service_category(
    category_id: int,
    db: Session = Depends(get_db),
):
    try:
        return ServicesApiService(db).delete_service_category(category_id=category_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=List[ServiceOut], summary="Каталог услуг")
async def list_services(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(default=None, max_length=120),
    active: Optional[bool] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    department: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    try:
        rows = ServicesApiService(db).list_services(
            q=q,
            active=active,
            category_id=category_id,
            department=department,
            limit=limit,
            offset=offset,
        )
        return [_row_to_out(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ошибка получения услуг: {str(exc)}") from exc


@router.get("/queue-groups", response_model=QueueGroupsResponse, summary="Получить группы очередей (SSOT)")
async def get_queue_groups(
    db: Session = Depends(get_db),
):
    payload = ServicesApiService(db).get_queue_groups_payload()
    return QueueGroupsResponse(**payload)


@router.get("/{service_id}", response_model=ServiceOut, summary="Получить услугу по ID")
async def get_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    service = ServicesApiService(db).get_service(service_id=service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    return _row_to_out(service)


@router.post("", response_model=ServiceOut, summary="Создать услугу")
async def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
):
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
):
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


@router.delete("/{service_id}", summary="Удалить услугу")
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
):
    try:
        return ServicesApiService(db).delete_service(service_id=service_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/admin/doctors", response_model=List[DoctorOut], summary="Список врачей (временный)")
async def list_doctors_temp(
    db: Session = Depends(get_db),
):
    return ServicesApiService(db).list_doctors_temp()


@router.get("/resolve", response_model=ServiceResolveResponse, summary="Разрешить услугу (SSOT)")
async def resolve_service_endpoint(
    service_id: Optional[int] = Query(None, description="ID услуги"),
    code: Optional[str] = Query(None, description="Код услуги"),
    db: Session = Depends(get_db),
):
    if not service_id and not code:
        raise HTTPException(
            status_code=400,
            detail="Необходимо указать либо service_id, либо code (или оба)",
        )
    result = ServicesApiService(db).resolve_service(service_id=service_id, code=code)
    return ServiceResolveResponse(**result)


@router.get("/code-mappings", response_model=ServiceCodeMappingsResponse, summary="Получить маппинги кодов услуг (SSOT)")
async def get_service_code_mappings(
    db: Session = Depends(get_db),
):
    payload = ServicesApiService(db).get_service_code_mappings_payload()
    return ServiceCodeMappingsResponse(**payload)
