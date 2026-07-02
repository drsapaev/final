"""
API endpoints для управления разрешениями групп пользователей
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.group_permissions_api_service import (
    GroupPermissionsApiDomainError,
    GroupPermissionsApiService,
)
from app.services.group_permissions_service import get_group_permissions_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class PermissionResponse(BaseModel):
    id: int
    name: str
    codename: str
    description: Optional[str]
    category: Optional[str]
    is_active: bool


class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    level: int
    is_active: bool
    is_system: bool
    permissions_count: int


class GroupResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    group_type: str
    is_active: bool
    users_count: int
    roles_count: int


class UserPermissionsResponse(BaseModel):
    user_id: int
    username: str
    permissions: List[str]
    permissions_count: int
    roles: List[str]
    groups: List[str]


class GroupPermissionsSummaryResponse(BaseModel):
    group_id: int
    group_name: str
    group_display_name: str
    group_type: str
    users_count: int
    roles: List[Dict[str, Any]]
    permissions_count: int
    permissions_by_category: Dict[str, List[Dict[str, Any]]]
    total_permissions: List[str]


class AssignRoleRequest(BaseModel):
    role_id: int


class AddUserToGroupRequest(BaseModel):
    user_id: int


class PermissionOverrideRequest(BaseModel):
    user_id: int
    permission_id: int
    override_type: str = Field(..., pattern="^(grant|deny)$")
    reason: Optional[str] = None
    expires_hours: Optional[int] = None


# ===================== ПОЛУЧЕНИЕ РАЗРЕШЕНИЙ =====================


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
def get_user_permissions(
    user_id: int,
    use_cache: bool = Query(True, description="Использовать кэш"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Получить все разрешения пользователя из БД
    Включает разрешения из ролей, групп и индивидуальные переопределения
    """
    try:
        payload = GroupPermissionsApiService(db).get_user_permissions_payload(
            user_id=user_id,
            use_cache=use_cache,
        )
        return UserPermissionsResponse(**payload)
    except GroupPermissionsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения разрешений пользователя {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения разрешений: {str(e)}",
        ) from e


@router.get("/users/{user_id}/permissions/check")
def check_user_permission(
    user_id: int,
    permission: str = Query(..., description="Код разрешения для проверки"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Проверить, есть ли у пользователя конкретное разрешение
    """
    try:
        service = get_group_permissions_service()
        has_permission = service.has_permission(db, user_id, permission)

        return {
            "user_id": user_id,
            "permission": permission,
            "has_permission": has_permission,
            "checked_at": datetime.utcnow().isoformat(),
            "checked_by": current_user.username,
        }

    except Exception as e:
        logger.error(
            f"Ошибка проверки разрешения {permission} для пользователя {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки разрешения: {str(e)}",
        )


# ===================== УПРАВЛЕНИЕ ГРУППАМИ =====================


@router.get("/groups", response_model=List[GroupResponse])
def get_groups(
    active_only: bool = Query(True, description="Только активные группы"),
    group_type: Optional[str] = Query(None, description="Тип группы"),
    limit: int = Query(50, ge=1, le=100, description="Количество групп"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Получить список групп пользователей
    """
    try:
        payload = GroupPermissionsApiService(db).list_groups_payload(
            active_only=active_only,
            group_type=group_type,
            limit=limit,
        )
        return [GroupResponse(**item) for item in payload]
    except Exception as e:
        logger.error(f"Ошибка получения списка групп: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения групп: {str(e)}",
        ) from e


@router.get(
    "/groups/{group_id}/permissions", response_model=GroupPermissionsSummaryResponse
)
def get_group_permissions_summary(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Получить сводку разрешений группы
    """
    try:
        service = get_group_permissions_service()
        summary = service.get_group_permissions_summary(db, group_id)

        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=summary["error"]
            )

        return GroupPermissionsSummaryResponse(**summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения сводки разрешений группы {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сводки: {str(e)}",
        )


@router.post("/groups/{group_id}/roles")
def assign_role_to_group(
    group_id: int,
    request: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Назначить роль группе
    """
    try:
        service = get_group_permissions_service()
        result = service.assign_role_to_group(
            db, group_id, request.role_id, current_user.id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка назначения роли {request.role_id} группе {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка назначения роли: {str(e)}",
        )


@router.delete("/groups/{group_id}/roles/{role_id}")
def revoke_role_from_group(
    group_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Отозвать роль у группы
    """
    try:
        service = get_group_permissions_service()
        result = service.revoke_role_from_group(db, group_id, role_id, current_user.id)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отзыва роли {role_id} у группы {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отзыва роли: {str(e)}",
        )


@router.post("/groups/{group_id}/users")
def add_user_to_group(
    group_id: int,
    request: AddUserToGroupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Добавить пользователя в группу
    """
    try:
        service = get_group_permissions_service()
        result = service.add_user_to_group(
            db, request.user_id, group_id, current_user.id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка добавления пользователя {request.user_id} в группу {group_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка добавления в группу: {str(e)}",
        )


@router.delete("/groups/{group_id}/users/{user_id}")
def remove_user_from_group(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Удалить пользователя из группы
    """
    try:
        service = get_group_permissions_service()
        result = service.remove_user_from_group(db, user_id, group_id, current_user.id)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка удаления пользователя {user_id} из группы {group_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления из группы: {str(e)}",
        )


# ===================== УПРАВЛЕНИЕ РОЛЯМИ И РАЗРЕШЕНИЯМИ =====================


@router.get("/roles", response_model=List[RoleResponse])
def get_roles(
    active_only: bool = Query(True, description="Только активные роли"),
    include_system: bool = Query(True, description="Включить системные роли"),
    limit: int = Query(50, ge=1, le=100, description="Количество ролей"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Получить список ролей
    """
    try:
        payload = GroupPermissionsApiService(db).list_roles_payload(
            active_only=active_only,
            include_system=include_system,
            limit=limit,
        )
        return [RoleResponse(**item) for item in payload]
    except Exception as e:
        logger.error(f"Ошибка получения списка ролей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения ролей: {str(e)}",
        ) from e


@router.get("/permissions", response_model=List[PermissionResponse])
def get_permissions(
    active_only: bool = Query(True, description="Только активные разрешения"),
    category: Optional[str] = Query(None, description="Категория разрешений"),
    limit: int = Query(100, ge=1, le=200, description="Количество разрешений"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Получить список разрешений
    """
    try:
        payload = GroupPermissionsApiService(db).list_permissions_payload(
            active_only=active_only,
            category=category,
            limit=limit,
        )
        return [PermissionResponse(**item) for item in payload]
    except Exception as e:
        logger.error(f"Ошибка получения списка разрешений: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения разрешений: {str(e)}",
        ) from e


# ===================== ПЕРЕОПРЕДЕЛЕНИЯ РАЗРЕШЕНИЙ =====================


@router.post("/users/permission-override")
def create_permission_override(
    request: PermissionOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin")),
):
    """
    Создать индивидуальное переопределение разрешения для пользователя
    """
    api_service = GroupPermissionsApiService(db)
    try:
        return api_service.create_permission_override(
            user_id=request.user_id,
            permission_id=request.permission_id,
            override_type=request.override_type,
            reason=request.reason,
            expires_hours=request.expires_hours,
            granted_by_user_id=current_user.id,
            granted_by_username=current_user.username,
        )
    except GroupPermissionsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        api_service.rollback()
        logger.error(f"Ошибка создания переопределения разрешения: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания переопределения: {str(e)}",
        )


# ===================== КЭШ И СТАТИСТИКА =====================


@router.post("/cache/clear")
def clear_permissions_cache(
    current_user: User = Depends(require_roles("Admin", "SuperAdmin"))
):
    """
    Очистить кэш разрешений
    """
    try:
        service = get_group_permissions_service()
        service.clear_all_cache()

        return {
            "success": True,
            "message": "Кэш разрешений очищен",
            "cleared_by": current_user.username,
            "cleared_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка очистки кэша разрешений: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка очистки кэша: {str(e)}",
        )


@router.get("/cache/stats")
def get_cache_stats(current_user: User = Depends(require_roles("Admin", "SuperAdmin"))):
    """
    Получить статистику кэша разрешений
    """
    try:
        service = get_group_permissions_service()
        stats = service.get_cache_stats()

        return {
            "success": True,
            "cache_stats": stats,
            "requested_by": current_user.username,
            "requested_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )
