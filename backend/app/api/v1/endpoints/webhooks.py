"""
API endpoints для управления webhook'ами
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from app.api import deps
from app.core.roles import Roles
from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.models.webhook import WebhookEventType, WebhookStatus, WebhookCallStatus
from app.schemas.webhook import (
    Webhook, WebhookCreate, WebhookUpdate, WebhookWithStats,
    WebhookCall, WebhookCallFilter, WebhookCallListResponse,
    WebhookEvent, WebhookEventCreate,
    WebhookStats, SystemWebhookStats,
    WebhookTestRequest, WebhookTestResponse,
    WebhookFilter, WebhookListResponse,
    WebhookBulkAction, WebhookBulkActionResponse
)
from app.crud.webhook import crud_webhook, crud_webhook_call, crud_webhook_event
from app.services.webhook_service import get_webhook_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ===================== УПРАВЛЕНИЕ WEBHOOK'АМИ =====================

@router.post("/", response_model=Webhook, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_in: WebhookCreate,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Создает новый webhook
    
    Требует роль: ADMIN или DEVELOPER
    """
    try:
        webhook = crud_webhook.create(
            db=db, 
            obj_in=webhook_in, 
            created_by=current_user.id
        )
        
        logger.info(f"Создан webhook {webhook.name} пользователем {current_user.username}")
        return webhook
        
    except Exception as e:
        logger.error(f"Ошибка создания webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка создания webhook: {str(e)}"
        )


@router.get("/", response_model=WebhookListResponse)
async def get_webhooks(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[WebhookStatus] = None,
    event_type: Optional[str] = None,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER, Roles.REGISTRAR]))
):
    """
    Получает список webhook'ов с фильтрацией
    
    Требует роль: ADMIN, DEVELOPER или REGISTRAR
    """
    try:
        # Обычные пользователи видят только свои webhook'и
        created_by = None if current_user.role in [Roles.ADMIN, Roles.MANAGER] else current_user.id
        
        webhooks = crud_webhook.get_multi(
            db=db,
            skip=skip,
            limit=limit,
            status=status_filter,
            event_type=event_type,
            created_by=created_by
        )
        
        # Подсчитываем общее количество
        total = len(crud_webhook.get_multi(db=db, skip=0, limit=10000, created_by=created_by))
        pages = (total + limit - 1) // limit
        
        return WebhookListResponse(
            items=webhooks,
            total=total,
            page=(skip // limit) + 1,
            size=limit,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения webhook'ов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения webhook'ов"
        )


@router.get("/{webhook_id}", response_model=WebhookWithStats)
async def get_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER, Roles.REGISTRAR]))
):
    """
    Получает webhook по ID со статистикой
    
    Требует роль: ADMIN, DEVELOPER или REGISTRAR
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role not in [Roles.ADMIN, Roles.MANAGER] and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра этого webhook'а"
        )
    
    # Получаем статистику
    stats = crud_webhook.get_stats(db=db, id=webhook_id)
    
    webhook_dict = webhook.__dict__.copy()
    webhook_dict.update({
        "success_rate": stats.get("success_rate", 0),
        "recent_24h": stats.get("recent_24h", {})
    })
    
    return WebhookWithStats(**webhook_dict)


@router.put("/{webhook_id}", response_model=Webhook)
async def update_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    webhook_in: WebhookUpdate,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Обновляет webhook
    
    Требует роль: ADMIN или DEVELOPER
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role != Roles.ADMIN and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для изменения этого webhook'а"
        )
    
    try:
        webhook = crud_webhook.update(db=db, db_obj=webhook, obj_in=webhook_in)
        logger.info(f"Обновлен webhook {webhook.name} пользователем {current_user.username}")
        return webhook
        
    except Exception as e:
        logger.error(f"Ошибка обновления webhook {webhook_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка обновления webhook: {str(e)}"
        )


@router.delete("/{webhook_id}")
async def delete_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Удаляет webhook
    
    Требует роль: ADMIN или DEVELOPER
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role != Roles.ADMIN and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для удаления этого webhook'а"
        )
    
    try:
        crud_webhook.remove(db=db, id=webhook_id)
        logger.info(f"Удален webhook {webhook.name} пользователем {current_user.username}")
        return {"message": "Webhook успешно удален"}
        
    except Exception as e:
        logger.error(f"Ошибка удаления webhook {webhook_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка удаления webhook"
        )


# ===================== УПРАВЛЕНИЕ СТАТУСОМ =====================

@router.post("/{webhook_id}/activate", response_model=Webhook)
async def activate_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Активирует webhook
    
    Требует роль: ADMIN или DEVELOPER
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role != Roles.ADMIN and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для активации этого webhook'а"
        )
    
    webhook = crud_webhook.activate(db=db, id=webhook_id)
    logger.info(f"Активирован webhook {webhook.name} пользователем {current_user.username}")
    return webhook


@router.post("/{webhook_id}/deactivate", response_model=Webhook)
async def deactivate_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Деактивирует webhook
    
    Требует роль: ADMIN или DEVELOPER
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role != Roles.ADMIN and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для деактивации этого webhook'а"
        )
    
    webhook = crud_webhook.deactivate(db=db, id=webhook_id)
    logger.info(f"Деактивирован webhook {webhook.name} пользователем {current_user.username}")
    return webhook


# ===================== ТЕСТИРОВАНИЕ =====================

@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    test_request: WebhookTestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Тестирует webhook отправкой тестового события
    
    Требует роль: ADMIN или DEVELOPER
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role != Roles.ADMIN and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для тестирования этого webhook'а"
        )
    
    try:
        webhook_service = get_webhook_service(db)
        
        # Подготавливаем тестовые данные
        test_data = test_request.test_data or {
            "test": True,
            "message": "Это тестовое событие",
            "timestamp": datetime.utcnow().isoformat(),
            "user": current_user.username
        }
        
        # Отправляем тестовый webhook в фоне
        background_tasks.add_task(
            webhook_service.trigger_event,
            test_request.event_type,
            test_data,
            source="test",
            source_id=str(current_user.id),
            correlation_id=f"test-{webhook_id}-{int(datetime.utcnow().timestamp())}"
        )
        
        logger.info(f"Отправлен тестовый webhook {webhook.name} пользователем {current_user.username}")
        
        return WebhookTestResponse(
            success=True,
            call_id=0  # Будет создан в фоне
        )
        
    except Exception as e:
        logger.error(f"Ошибка тестирования webhook {webhook_id}: {e}")
        return WebhookTestResponse(
            success=False,
            error_message=str(e),
            call_id=0
        )


# ===================== ВЫЗОВЫ WEBHOOK'ОВ =====================

@router.get("/{webhook_id}/calls", response_model=WebhookCallListResponse)
async def get_webhook_calls(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[WebhookCallStatus] = None,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER, Roles.REGISTRAR]))
):
    """
    Получает вызовы webhook'а
    
    Требует роль: ADMIN, DEVELOPER или REGISTRAR
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role not in [Roles.ADMIN, Roles.MANAGER] and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра вызовов этого webhook'а"
        )
    
    calls = crud_webhook_call.get_multi_by_webhook(
        db=db,
        webhook_id=webhook_id,
        skip=skip,
        limit=limit,
        status=status_filter
    )
    
    # Подсчитываем общее количество
    total = len(crud_webhook_call.get_multi_by_webhook(
        db=db, webhook_id=webhook_id, skip=0, limit=10000
    ))
    pages = (total + limit - 1) // limit
    
    return WebhookCallListResponse(
        items=calls,
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        pages=pages
    )


@router.get("/calls/{call_id}", response_model=WebhookCall)
async def get_webhook_call(
    *,
    db: Session = Depends(get_db),
    call_id: int,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER, Roles.REGISTRAR]))
):
    """
    Получает детали вызова webhook'а
    
    Требует роль: ADMIN, DEVELOPER или REGISTRAR
    """
    call = crud_webhook_call.get(db=db, id=call_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вызов webhook'а не найден"
        )
    
    # Проверяем права доступа через webhook
    webhook = crud_webhook.get(db=db, id=call.webhook_id)
    if (current_user.role not in [Roles.ADMIN, Roles.MANAGER] and 
        webhook and webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра этого вызова"
        )
    
    return call


# ===================== СТАТИСТИКА =====================

@router.get("/{webhook_id}/stats", response_model=WebhookStats)
async def get_webhook_stats(
    *,
    db: Session = Depends(get_db),
    webhook_id: int,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER, Roles.REGISTRAR]))
):
    """
    Получает статистику webhook'а
    
    Требует роль: ADMIN, DEVELOPER или REGISTRAR
    """
    webhook = crud_webhook.get(db=db, id=webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook не найден"
        )
    
    # Проверяем права доступа
    if (current_user.role not in [Roles.ADMIN, Roles.MANAGER] and 
        webhook.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра статистики этого webhook'а"
        )
    
    stats = crud_webhook.get_stats(db=db, id=webhook_id)
    return WebhookStats(**stats)


@router.get("/system/stats", response_model=SystemWebhookStats)
async def get_system_webhook_stats(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Получает общую статистику системы webhook'ов
    
    Требует роль: ADMIN или DEVELOPER
    """
    try:
        webhook_service = get_webhook_service(db)
        stats = webhook_service.get_system_webhook_stats()
        return SystemWebhookStats(**stats)
        
    except Exception as e:
        logger.error(f"Ошибка получения системной статистики: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статистики"
        )


# ===================== МАССОВЫЕ ОПЕРАЦИИ =====================

@router.post("/bulk-action", response_model=WebhookBulkActionResponse)
async def webhook_bulk_action(
    *,
    db: Session = Depends(get_db),
    bulk_action: WebhookBulkAction,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Выполняет массовое действие над webhook'ами
    
    Требует роль: ADMIN или DEVELOPER
    """
    processed = 0
    failed = 0
    errors = []
    
    for webhook_id in bulk_action.webhook_ids:
        try:
            webhook = crud_webhook.get(db=db, id=webhook_id)
            if not webhook:
                errors.append(f"Webhook {webhook_id} не найден")
                failed += 1
                continue
            
            # Проверяем права доступа
            if (current_user.role != Roles.ADMIN and 
                webhook.created_by != current_user.id):
                errors.append(f"Недостаточно прав для webhook {webhook_id}")
                failed += 1
                continue
            
            # Выполняем действие
            if bulk_action.action == "activate":
                crud_webhook.activate(db=db, id=webhook_id)
            elif bulk_action.action == "deactivate":
                crud_webhook.deactivate(db=db, id=webhook_id)
            elif bulk_action.action == "delete":
                crud_webhook.remove(db=db, id=webhook_id)
            
            processed += 1
            
        except Exception as e:
            errors.append(f"Ошибка обработки webhook {webhook_id}: {str(e)}")
            failed += 1
    
    logger.info(f"Массовое действие {bulk_action.action}: обработано {processed}, ошибок {failed}")
    
    return WebhookBulkActionResponse(
        success=failed == 0,
        processed=processed,
        failed=failed,
        errors=errors
    )


# ===================== СОБЫТИЯ =====================

@router.post("/events/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_webhook_event(
    *,
    db: Session = Depends(get_db),
    event: WebhookEventCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """
    Триггерит событие для всех подписанных webhook'ов
    
    Требует роль: ADMIN или DEVELOPER
    """
    try:
        webhook_service = get_webhook_service(db)
        
        # Отправляем событие в фоне
        background_tasks.add_task(
            webhook_service.trigger_event,
            event.event_type,
            event.event_data,
            source=event.source,
            source_id=event.source_id,
            correlation_id=event.correlation_id
        )
        
        logger.info(f"Триггерено событие {event.event_type.value} пользователем {current_user.username}")
        
        return {"message": "Событие принято к обработке"}
        
    except Exception as e:
        logger.error(f"Ошибка триггера события: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обработки события"
        )


# ===================== ОЧИСТКА =====================

@router.post("/cleanup/calls")
async def cleanup_webhook_calls(
    *,
    db: Session = Depends(get_db),
    days: int = 30,
    current_user: User = Depends(require_roles([Roles.ADMIN]))
):
    """
    Очищает старые вызовы webhook'ов
    
    Требует роль: ADMIN
    """
    try:
        deleted_count = crud_webhook_call.cleanup_old(db=db, days=days)
        logger.info(f"Очищено {deleted_count} старых вызовов webhook'ов пользователем {current_user.username}")
        
        return {
            "message": f"Удалено {deleted_count} старых вызовов webhook'ов",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки вызовов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка очистки вызовов"
        )


@router.post("/cleanup/events")
async def cleanup_webhook_events(
    *,
    db: Session = Depends(get_db),
    days: int = 7,
    current_user: User = Depends(require_roles([Roles.ADMIN]))
):
    """
    Очищает старые события webhook'ов
    
    Требует роль: ADMIN
    """
    try:
        deleted_count = crud_webhook_event.cleanup_old(db=db, days=days)
        logger.info(f"Очищено {deleted_count} старых событий пользователем {current_user.username}")
        
        return {
            "message": f"Удалено {deleted_count} старых событий",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки событий: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка очистки событий"
        )
