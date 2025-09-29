"""
API endpoints для передачи данных пользователей
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.user_data_transfer_service import get_user_data_transfer_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================

class UserDataSummaryResponse(BaseModel):
    user_id: int
    username: str
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    patient_id: Optional[int]
    data_counts: Dict[str, int]
    transferable_data: List[Dict[str, Any]]

class DataTransferRequest(BaseModel):
    source_user_id: int = Field(..., description="ID пользователя-источника")
    target_user_id: int = Field(..., description="ID пользователя-получателя")
    data_types: List[str] = Field(
        default=["appointments", "visits", "queue_entries"],
        description="Типы данных для передачи"
    )
    confirmation_required: bool = Field(
        default=True,
        description="Требуется ли подтверждение от пользователей"
    )

class DataTransferResponse(BaseModel):
    success: bool
    transferred: Dict[str, Dict[str, Any]]
    errors: List[str]
    summary: Dict[str, Any]

class TransferConfirmationRequest(BaseModel):
    token: str = Field(..., description="Токен подтверждения")

# ===================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О ДАННЫХ =====================

@router.get("/users/{user_id}/data-summary", response_model=UserDataSummaryResponse)
def get_user_data_summary(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить сводку данных пользователя для передачи
    Доступно администраторам и регистраторам
    """
    try:
        service = get_user_data_transfer_service()
        summary = service.get_user_data_summary(db, user_id)
        
        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=summary["error"]
            )
        
        return UserDataSummaryResponse(**summary)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения сводки данных пользователя {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения данных: {str(e)}"
        )


@router.get("/users/search")
def search_users_for_transfer(
    query: str = Query(..., min_length=2, description="Поисковый запрос (имя, телефон, email)"),
    limit: int = Query(10, ge=1, le=50, description="Количество результатов"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Поиск пользователей для передачи данных
    """
    try:
        from app.crud import user as crud_user
        
        users = crud_user.search_users(db, query=query, limit=limit)
        
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None
            })
        
        return {
            "users": result,
            "total": len(result),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Ошибка поиска пользователей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка поиска: {str(e)}"
        )


# ===================== ПЕРЕДАЧА ДАННЫХ =====================

@router.post("/transfer", response_model=DataTransferResponse)
def transfer_user_data(
    request: DataTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin"))
):
    """
    Передать данные от одного пользователя к другому
    Доступно только администраторам
    """
    try:
        service = get_user_data_transfer_service()
        
        # Валидируем запрос
        is_valid, error_message = service.validate_transfer_request(
            db, 
            request.source_user_id, 
            request.target_user_id,
            current_user.id
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        # Выполняем передачу
        result = service.transfer_user_data(
            db,
            source_user_id=request.source_user_id,
            target_user_id=request.target_user_id,
            data_types=request.data_types,
            initiated_by_user_id=current_user.id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return DataTransferResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка передачи данных: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка передачи данных: {str(e)}"
        )


@router.post("/transfer/request-confirmation")
def request_transfer_confirmation(
    request: DataTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Запросить подтверждение передачи данных
    Создает токен подтверждения и отправляет уведомления пользователям
    """
    try:
        service = get_user_data_transfer_service()
        
        # Валидируем запрос
        is_valid, error_message = service.validate_transfer_request(
            db, 
            request.source_user_id, 
            request.target_user_id,
            current_user.id
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        # Создаем токен подтверждения
        token = service.create_transfer_confirmation_token(
            db,
            source_user_id=request.source_user_id,
            target_user_id=request.target_user_id,
            data_types=request.data_types,
            expires_in_hours=24
        )
        
        # В реальной системе здесь была бы отправка уведомлений
        # пользователям о запросе передачи данных
        
        return {
            "success": True,
            "message": "Запрос на передачу данных создан",
            "confirmation_token": token,
            "expires_in_hours": 24,
            "created_by": current_user.username,
            "created_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания запроса на передачу: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания запроса: {str(e)}"
        )


@router.post("/transfer/confirm")
def confirm_data_transfer(
    request: TransferConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Подтвердить передачу данных по токену
    Доступно любому аутентифицированному пользователю
    """
    try:
        service = get_user_data_transfer_service()
        
        result = service.confirm_transfer_by_token(
            db,
            token=request.token,
            confirmed_by_user_id=current_user.id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка подтверждения передачи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подтверждения: {str(e)}"
        )


# ===================== ИСТОРИЯ И СТАТИСТИКА =====================

@router.get("/transfer/history")
def get_transfer_history(
    user_id: Optional[int] = Query(None, description="ID пользователя для фильтрации"),
    limit: int = Query(50, ge=1, le=100, description="Количество записей"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin"))
):
    """
    Получить историю передач данных
    Доступно только администраторам
    """
    try:
        service = get_user_data_transfer_service()
        
        history = service.get_transfer_history(
            db,
            user_id=user_id,
            limit=limit
        )
        
        return {
            "history": history,
            "total": len(history),
            "filtered_by_user": user_id,
            "requested_by": current_user.username,
            "requested_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения истории передач: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения истории: {str(e)}"
        )


@router.get("/transfer/statistics")
def get_transfer_statistics(
    period_days: int = Query(30, ge=1, le=365, description="Период в днях"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "SuperAdmin"))
):
    """
    Получить статистику передач данных
    """
    try:
        # В реальной системе здесь был бы запрос к БД для получения статистики
        
        return {
            "period_days": period_days,
            "total_transfers": 0,
            "successful_transfers": 0,
            "failed_transfers": 0,
            "most_transferred_data_types": [],
            "top_initiators": [],
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": current_user.username
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики передач: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )


# ===================== ВАЛИДАЦИЯ И УТИЛИТЫ =====================

@router.post("/transfer/validate")
def validate_transfer_request(
    source_user_id: int = Query(..., description="ID пользователя-источника"),
    target_user_id: int = Query(..., description="ID пользователя-получателя"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Валидировать возможность передачи данных между пользователями
    """
    try:
        service = get_user_data_transfer_service()
        
        is_valid, error_message = service.validate_transfer_request(
            db, 
            source_user_id, 
            target_user_id,
            current_user.id
        )
        
        return {
            "valid": is_valid,
            "message": error_message,
            "source_user_id": source_user_id,
            "target_user_id": target_user_id,
            "validated_by": current_user.username,
            "validated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка валидации запроса передачи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка валидации: {str(e)}"
        )


@router.get("/transfer/data-types")
def get_available_data_types(
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить список доступных типов данных для передачи
    """
    return {
        "data_types": [
            {
                "key": "appointments",
                "name": "Назначения",
                "description": "Записи на прием к врачам"
            },
            {
                "key": "visits",
                "name": "Визиты",
                "description": "Завершенные визиты с услугами и оплатой"
            },
            {
                "key": "queue_entries",
                "name": "Записи в очереди",
                "description": "Активные записи в очередях к специалистам"
            }
        ],
        "default_types": ["appointments", "visits", "queue_entries"],
        "requested_by": current_user.username
    }

