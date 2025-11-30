from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import service as crud
from app.models.clinic import Doctor, ServiceCategory
from app.models.service import Service
from app.services.service_mapping import normalize_service_code

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

    category = ServiceCategory(**category_data.dict())
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

    for field, value in category_data.dict(exclude_unset=True).items():
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
    # Проверяем уникальность кода
    if service_data.code:
        existing = db.query(Service).filter(Service.code == service_data.code).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Услуга с кодом '{service_data.code}' уже существует",
            )

    # Проверяем существование категории
    if service_data.category_id:
        category = (
            db.query(ServiceCategory)
            .filter(ServiceCategory.id == service_data.category_id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=400, detail="Указанная категория не найдена"
            )

    # Normalize service codes before creating the service
    service_dict = service_data.dict()
    if service_dict.get('code'):
        service_dict['code'] = normalize_service_code(service_dict['code'])
    if service_dict.get('service_code'):
        service_dict['service_code'] = normalize_service_code(
            service_dict['service_code']
        )
    if service_dict.get('category_code'):
        service_dict['category_code'] = normalize_service_code(
            service_dict['category_code']
        )

    service = Service(**service_dict)
    db.add(service)
    db.commit()
    db.refresh(service)
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

    # Проверяем уникальность кода при обновлении
    if service_data.code and service_data.code != service.code:
        existing = db.query(Service).filter(Service.code == service_data.code).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Услуга с кодом '{service_data.code}' уже существует",
            )

    # Проверяем существование категории
    if service_data.category_id:
        category = (
            db.query(ServiceCategory)
            .filter(ServiceCategory.id == service_data.category_id)
            .first()
        )
        if not category:
            raise HTTPException(
                status_code=400, detail="Указанная категория не найдена"
            )

    # Normalize service codes before updating
    update_dict = service_data.dict(exclude_unset=True)
    if 'code' in update_dict and update_dict['code'] is not None:
        update_dict['code'] = normalize_service_code(update_dict['code'])
    if 'service_code' in update_dict and update_dict['service_code'] is not None:
        update_dict['service_code'] = normalize_service_code(
            update_dict['service_code']
        )
    if 'category_code' in update_dict and update_dict['category_code'] is not None:
        update_dict['category_code'] = normalize_service_code(
            update_dict['category_code']
        )

    for field, value in update_dict.items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return _row_to_out(service)


@router.delete("/{service_id}", summary="Удалить услугу")
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    # user=Depends(require_roles("Admin")),
):
    """Удалить услугу"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    db.delete(service)
    db.commit()
    return {"message": "Услуга успешно удалена"}


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
    doctors = db.query(Doctor).filter(Doctor.active == True).all()
    return doctors


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
