"""Split from app.api.v1.endpoints.user_management.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.user_management._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.user_management._helpers import router  # noqa: F401


@router.post("/users/export", response_model=UserExportResponse)
async def export_users(
    export_data: UserExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Экспорт пользователей"""
    try:
        service = get_user_management_service()
        users = UserManagementApiService(db).get_export_users(
            export_filters=export_data.filters
        )

        if not users:
            return UserExportResponse(
                success=False, message="Нет пользователей для экспорта", record_count=0
            )

        # Запускаем экспорт в фоновом режиме
        background_tasks.add_task(
            service.export_users_background, users, export_data, current_user.id, db
        )

        return UserExportResponse(
            success=True,
            message=f"Экспорт {len(users)} пользователей запущен в фоновом режиме",
            record_count=len(users),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


