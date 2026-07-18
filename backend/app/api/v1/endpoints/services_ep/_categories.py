"""Split from services.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.services_ep._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.services_ep._helpers import router  # noqa: F401


@router.get(
    "/categories",
    response_model=list[ServiceCategoryOut],
    summary="Список категорий услуг",
)
async def list_service_categories(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "Cashier")),
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
    current_user: User = Depends(require_roles("Admin")),
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
    current_user: User = Depends(require_roles("Admin")),
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
    current_user: User = Depends(require_roles("Admin")),
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


