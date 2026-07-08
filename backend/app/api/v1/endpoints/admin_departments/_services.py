"""Split from app.api.v1.endpoints.admin_departments.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.admin_departments._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_departments._helpers import router  # noqa: F401


@router.get("/{department_id}/services", response_model=dict)
def get_department_services(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить услуги отделения"""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    services = (
        db.query(DepartmentService)
        .filter(DepartmentService.department_id == department_id)
        .order_by(DepartmentService.display_order)
        .all()
    )

    return {
        "success": True,
        "data": [
            {
                "id": ds.id,
                "service": {
                    "id": ds.service.id,
                    "name": ds.service.name,
                    "code": ds.service.service_code or get_service_code(
                        ds.service.id, db
                    ),
                    "base_price": float(ds.service.price) if ds.service.price else None,
                },
                "is_default": ds.is_default,
                "display_order": ds.display_order,
                "price_override": (
                    float(ds.price_override) if ds.price_override else None
                ),
            }
            for ds in services
        ],
        "count": len(services),
    }


