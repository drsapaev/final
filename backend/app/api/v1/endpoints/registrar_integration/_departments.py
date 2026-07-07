from __future__ import annotations

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa

@router.get("/registrar/departments")
def get_registrar_departments(
    active_only: bool = Query(True, description="Только активные отделения"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "Cashier")
    ),
):
    """
    Получить список отделений для регистратуры
    Доступен для регистраторов, в отличие от admin endpoint
    """
    try:
        query = db.query(Department)

        if active_only:
            query = query.filter(Department.active == True)

        # Сортируем по display_order
        query = query.order_by(Department.display_order)

        departments = query.all()

        # Формируем ответ
        result = []
        for dept in departments:
            # Получаем queue_prefix из настроек очереди
            from app.models.department import DepartmentQueueSettings

            queue_settings = (
                db.query(DepartmentQueueSettings)
                .filter(DepartmentQueueSettings.department_id == dept.id)
                .first()
            )

            result.append(
                {
                    "id": dept.id,
                    "key": dept.key,
                    "name_ru": dept.name_ru,
                    "name_uz": dept.name_uz,
                    "icon": dept.icon,
                    "color": dept.color,
                    "gradient": dept.gradient,
                    "display_order": dept.display_order,
                    "active": dept.active,
                    "description": dept.description,
                    "queue_prefix": (
                        queue_settings.queue_prefix
                        if queue_settings
                        else dept.key.upper()[0]
                    ),
                }
            )

        return {"success": True, "data": result, "count": len(result)}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== СПРАВОЧНИК УСЛУГ ДЛЯ РЕГИСТРАТУРЫ =====================


# ===================== ПРОФИЛИ ОЧЕРЕДЕЙ (DYNAMIC TABS) =====================

