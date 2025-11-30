"""
API эндпоинты для управления фича-флагами
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.feature_flags import FeatureFlag, FeatureFlagHistory
from app.models.user import User
from app.services.feature_flags import FeatureFlagService, get_feature_flag_service

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class FeatureFlagResponse(BaseModel):
    """Ответ с информацией о фича-флаге"""

    id: int
    key: str
    name: str
    description: Optional[str] = None
    enabled: bool
    config: Dict[str, Any]
    category: str
    environment: str
    created_at: str
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class FeatureFlagCreateRequest(BaseModel):
    """Запрос на создание фича-флага"""

    key: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    category: str = Field(default="general", max_length=50)
    environment: str = Field(
        default="all", pattern="^(production|staging|development|all)$"
    )


class FeatureFlagUpdateRequest(BaseModel):
    """Запрос на обновление фича-флага"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    category: Optional[str] = Field(None, max_length=50)
    environment: Optional[str] = Field(
        None, pattern="^(production|staging|development|all)$"
    )
    reason: Optional[str] = Field(None, max_length=500)


class FeatureFlagToggleRequest(BaseModel):
    """Запрос на переключение состояния флага"""

    enabled: bool
    reason: Optional[str] = Field(None, max_length=500)


class FeatureFlagHistoryResponse(BaseModel):
    """Ответ с историей изменений флага"""

    id: int
    flag_key: str
    action: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    changed_by: Optional[str] = None
    changed_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class FeatureFlagStatusResponse(BaseModel):
    """Ответ с состоянием флага"""

    key: str
    enabled: bool
    config: Dict[str, Any]


class BulkToggleRequest(BaseModel):
    """Запрос на массовое переключение флагов"""

    flag_keys: List[str]
    enabled: bool
    reason: Optional[str] = Field(None, max_length=500)


# ===================== ЭНДПОИНТЫ =====================


@router.get("/admin/feature-flags", response_model=List[FeatureFlagResponse])
def get_all_feature_flags(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получает все фича-флаги
    Доступно только администраторам
    """
    service = get_feature_flag_service(db)
    flags = service.get_all_flags(category=category)

    return [
        FeatureFlagResponse(
            id=flag.id,
            key=flag.key,
            name=flag.name,
            description=flag.description,
            enabled=flag.enabled,
            config=flag.config or {},
            category=flag.category,
            environment=flag.environment,
            created_at=flag.created_at.isoformat() if flag.created_at else "",
            updated_at=flag.updated_at.isoformat() if flag.updated_at else None,
            created_by=flag.created_by,
            updated_by=flag.updated_by,
        )
        for flag in flags
    ]


@router.get("/admin/feature-flags/{flag_key}", response_model=FeatureFlagResponse)
def get_feature_flag(
    flag_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получает конкретный фича-флаг по ключу
    Доступно только администраторам
    """
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фича-флаг '{flag_key}' не найден",
        )

    return FeatureFlagResponse(
        id=flag.id,
        key=flag.key,
        name=flag.name,
        description=flag.description,
        enabled=flag.enabled,
        config=flag.config or {},
        category=flag.category,
        environment=flag.environment,
        created_at=flag.created_at.isoformat() if flag.created_at else "",
        updated_at=flag.updated_at.isoformat() if flag.updated_at else None,
        created_by=flag.created_by,
        updated_by=flag.updated_by,
    )


@router.post("/admin/feature-flags", response_model=FeatureFlagResponse)
def create_feature_flag(
    request: FeatureFlagCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Создает новый фича-флаг
    Доступно только администраторам
    """
    # Проверяем что флаг с таким ключом не существует
    existing = db.query(FeatureFlag).filter(FeatureFlag.key == request.key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Фича-флаг с ключом '{request.key}' уже существует",
        )

    service = get_feature_flag_service(db)

    try:
        flag = service.create_flag(
            key=request.key,
            name=request.name,
            description=request.description,
            enabled=request.enabled,
            config=request.config,
            category=request.category,
            environment=request.environment,
            user_id=current_user.username,
        )

        return FeatureFlagResponse(
            id=flag.id,
            key=flag.key,
            name=flag.name,
            description=flag.description,
            enabled=flag.enabled,
            config=flag.config or {},
            category=flag.category,
            environment=flag.environment,
            created_at=flag.created_at.isoformat() if flag.created_at else "",
            updated_at=flag.updated_at.isoformat() if flag.updated_at else None,
            created_by=flag.created_by,
            updated_by=flag.updated_by,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания фича-флага: {str(e)}",
        )


@router.put("/admin/feature-flags/{flag_key}", response_model=FeatureFlagResponse)
def update_feature_flag(
    flag_key: str,
    request: FeatureFlagUpdateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Обновляет фича-флаг
    Доступно только администраторам
    """
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фича-флаг '{flag_key}' не найден",
        )

    service = get_feature_flag_service(db)

    try:
        # Обновляем поля
        if request.name is not None:
            flag.name = request.name
        if request.description is not None:
            flag.description = request.description
        if request.category is not None:
            flag.category = request.category
        if request.environment is not None:
            flag.environment = request.environment

        # Обновляем состояние если указано
        if request.enabled is not None:
            service.set_flag(
                flag_key=flag_key,
                enabled=request.enabled,
                user_id=current_user.username,
                reason=request.reason,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("User-Agent"),
            )

        # Обновляем конфигурацию если указана
        if request.config is not None:
            service.update_flag_config(
                flag_key=flag_key,
                config=request.config,
                user_id=current_user.username,
                reason=request.reason,
            )

        flag.updated_by = current_user.username
        db.commit()
        db.refresh(flag)

        return FeatureFlagResponse(
            id=flag.id,
            key=flag.key,
            name=flag.name,
            description=flag.description,
            enabled=flag.enabled,
            config=flag.config or {},
            category=flag.category,
            environment=flag.environment,
            created_at=flag.created_at.isoformat() if flag.created_at else "",
            updated_at=flag.updated_at.isoformat() if flag.updated_at else None,
            created_by=flag.created_by,
            updated_by=flag.updated_by,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления фича-флага: {str(e)}",
        )


@router.post(
    "/admin/feature-flags/{flag_key}/toggle", response_model=FeatureFlagStatusResponse
)
def toggle_feature_flag(
    flag_key: str,
    request: FeatureFlagToggleRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Переключает состояние фича-флага
    Доступно только администраторам
    """
    service = get_feature_flag_service(db)

    success = service.set_flag(
        flag_key=flag_key,
        enabled=request.enabled,
        user_id=current_user.username,
        reason=request.reason,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("User-Agent"),
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фича-флаг '{flag_key}' не найден",
        )

    config = service.get_flag_config(flag_key)

    return FeatureFlagStatusResponse(
        key=flag_key, enabled=request.enabled, config=config
    )


@router.post("/admin/feature-flags/bulk-toggle")
def bulk_toggle_feature_flags(
    request: BulkToggleRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Массовое переключение состояния фича-флагов
    Доступно только администраторам
    """
    service = get_feature_flag_service(db)
    results = []

    for flag_key in request.flag_keys:
        success = service.set_flag(
            flag_key=flag_key,
            enabled=request.enabled,
            user_id=current_user.username,
            reason=request.reason,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent"),
        )

        results.append(
            {
                "flag_key": flag_key,
                "success": success,
                "enabled": request.enabled if success else None,
            }
        )

    return {
        "results": results,
        "total": len(request.flag_keys),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
    }


@router.delete("/admin/feature-flags/{flag_key}")
def delete_feature_flag(
    flag_key: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Удаляет фича-флаг
    Доступно только администраторам
    """
    service = get_feature_flag_service(db)

    success = service.delete_flag(
        flag_key=flag_key, user_id=current_user.username, reason=reason
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фича-флаг '{flag_key}' не найден",
        )

    return {"message": f"Фича-флаг '{flag_key}' успешно удален"}


@router.get(
    "/admin/feature-flags/{flag_key}/history",
    response_model=List[FeatureFlagHistoryResponse],
)
def get_feature_flag_history(
    flag_key: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получает историю изменений фича-флага
    Доступно только администраторам
    """
    service = get_feature_flag_service(db)
    history = service.get_flag_history(flag_key, limit)

    return [
        FeatureFlagHistoryResponse(
            id=record.id,
            flag_key=record.flag_key,
            action=record.action,
            old_value=record.old_value,
            new_value=record.new_value,
            changed_by=record.changed_by,
            changed_at=record.changed_at.isoformat() if record.changed_at else "",
            ip_address=record.ip_address,
            user_agent=record.user_agent,
            reason=record.reason,
        )
        for record in history
    ]


# ===================== ПУБЛИЧНЫЕ ЭНДПОИНТЫ =====================


@router.get(
    "/feature-flags/status/{flag_key}", response_model=FeatureFlagStatusResponse
)
def get_feature_flag_status(flag_key: str, db: Session = Depends(get_db)):
    """
    Получает статус фича-флага (публичный эндпоинт)
    Доступно всем авторизованным пользователям
    """
    service = get_feature_flag_service(db)

    enabled = service.is_enabled(flag_key)
    config = service.get_flag_config(flag_key)

    return FeatureFlagStatusResponse(key=flag_key, enabled=enabled, config=config)


@router.get("/feature-flags/status")
def get_multiple_feature_flags_status(
    keys: str, db: Session = Depends(get_db)  # Comma-separated list of flag keys
):
    """
    Получает статус нескольких фича-флагов
    Доступно всем авторизованным пользователям

    Args:
        keys: Список ключей флагов через запятую (например: "flag1,flag2,flag3")
    """
    service = get_feature_flag_service(db)
    flag_keys = [key.strip() for key in keys.split(",") if key.strip()]

    results = {}
    for flag_key in flag_keys:
        results[flag_key] = {
            "enabled": service.is_enabled(flag_key),
            "config": service.get_flag_config(flag_key),
        }

    return results
