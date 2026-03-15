from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.clinic import Doctor
from app.services.queue_domain_service import QueueDomainService
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
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: Optional[str] = None  # K, D, C, L, S, O
    service_code: Optional[str] = None  # K01, D02, C03, etc.
    requires_doctor: Optional[bool] = None
    queue_tag: Optional[str] = None
    is_consultation: Optional[bool] = None
    allow_doctor_price_override: Optional[bool] = None
    department_key: Optional[str] = None  # ✅ ДОБАВЛЕНО: связь с отделением

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


def _row_to_out(r) -> ServiceOut:
    price = None
    try:
        price = float(r.price) if r.price is not None else None
    except Exception:
        price = None
    return ServiceOut(
        id=r.id,
        code=r.code,
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
        service_code=getattr(r, 'service_code', None),
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
    return ServicesApiService(db).list_service_categories(active=active)


@router.post(
    "/categories", response_model=ServiceCategoryOut, summary="Создать категорию услуг"
)
async def create_service_category(
    category_data: ServiceCategoryCreate,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Создать новую категорию услуг"""
    try:
        return ServicesApiService(db).create_service_category(category_data=category_data)
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
    """Обновить существующую категорию услуг"""
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
    # user=Depends(require_roles("Admin")),
):
    """Удалить категорию услуг"""
    try:
        return ServicesApiService(db).delete_service_category(category_id=category_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
        rows = ServicesApiService(db).list_services(
            q=q,
            active=active,
            category_id=category_id,
            department=department,
            limit=limit,
            offset=offset,
        )
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


class ServiceCodeMappingsResponse(BaseModel):
    """Response schema for service code mappings endpoint"""

    specialty_to_code: dict = {}
    code_to_name: dict = {}
    category_mapping: dict = {}
    specialty_aliases: dict = {}


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
    payload = QueueDomainService(db).get_service_code_mappings_payload()
    return ServiceCodeMappingsResponse(**payload)


@router.get("/{service_id}", response_model=ServiceOut, summary="Получить услугу по ID")
async def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Получить конкретную услугу по ID"""
    service = ServicesApiService(db).get_service(service_id=service_id)
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
    """Обновить существующую услугу"""
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
    # user=Depends(require_roles("Admin")),
):
    """Удалить услугу"""
    try:
        return ServicesApiService(db).delete_service(service_id=service_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ==================== ВРЕМЕННЫЙ ENDPOINT ДЛЯ ВРАЧЕЙ ====================


class DoctorOut(BaseModel):
    id: int
    specialty: str
    cabinet: Optional[str] = None
    active: bool = True

    class Config:
        from_attributes = True


@router.get(
    "/admin/doctors",
    response_model=List[DoctorOut],
    summary="Список врачей (временный)",
)
async def list_doctors_temp(
    db: Session = Depends(get_db),
):
    """Временный endpoint для получения списка врачей"""
    return ServicesApiService(db).list_doctors_temp()


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

    class Config:
        from_attributes = True


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



