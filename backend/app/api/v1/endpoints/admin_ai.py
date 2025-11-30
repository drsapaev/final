"""
API endpoints для управления AI в админ панели
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.crud import ai_config as crud_ai
from app.schemas.ai_config import (
    AIProviderOut, AIProviderCreate, AIProviderUpdate, AIProviderTestRequest,
    AIPromptTemplateOut, AIPromptTemplateCreate, AIPromptTemplateUpdate,
    AIUsageLogOut, AISystemSettings, AITestResult, AIStatsResponse
)

router = APIRouter()

# ===================== AI ПРОВАЙДЕРЫ =====================

@router.get("/ai/providers", response_model=List[AIProviderOut])
def get_ai_providers(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить список AI провайдеров"""
    try:
        providers = crud_ai.get_ai_providers(db, active_only=active_only)
        
        # Скрываем API ключи в ответе
        for provider in providers:
            if provider.api_key:
                provider.api_key = "***скрыт***"
        
        return providers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения AI провайдеров: {str(e)}"
        )


@router.get("/ai/providers/{provider_id}", response_model=AIProviderOut)
def get_ai_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить AI провайдера по ID"""
    provider = crud_ai.get_ai_provider_by_id(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI провайдер с ID {provider_id} не найден"
        )
    
    # Скрываем API ключ
    if provider.api_key:
        provider.api_key = "***скрыт***"
    
    return provider


@router.post("/ai/providers", response_model=AIProviderOut)
def create_ai_provider(
    provider: AIProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Создать AI провайдера"""
    try:
        # Проверяем уникальность имени
        existing = crud_ai.get_ai_provider_by_name(db, provider.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Провайдер с именем '{provider.name}' уже существует"
            )
        
        new_provider = crud_ai.create_ai_provider(db, provider)
        
        # Скрываем API ключ в ответе
        if new_provider.api_key:
            new_provider.api_key = "***скрыт***"
        
        return new_provider
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания AI провайдера: {str(e)}"
        )


@router.put("/ai/providers/{provider_id}", response_model=AIProviderOut)
def update_ai_provider(
    provider_id: int,
    provider: AIProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить AI провайдера"""
    try:
        updated_provider = crud_ai.update_ai_provider(db, provider_id, provider)
        if not updated_provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI провайдер с ID {provider_id} не найден"
            )
        
        # Скрываем API ключ в ответе
        if updated_provider.api_key:
            updated_provider.api_key = "***скрыт***"
        
        return updated_provider
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления AI провайдера: {str(e)}"
        )


@router.delete("/ai/providers/{provider_id}")
def delete_ai_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Удалить AI провайдера"""
    try:
        success = crud_ai.delete_ai_provider(db, provider_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI провайдер с ID {provider_id} не найден"
            )
        
        return {"success": True, "message": "AI провайдер деактивирован"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления AI провайдера: {str(e)}"
        )


@router.post("/ai/providers/{provider_id}/test", response_model=AITestResult)
def test_ai_provider(
    provider_id: int,
    test_request: AIProviderTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Тестировать AI провайдера"""
    try:
        provider = crud_ai.get_ai_provider_by_id(db, provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI провайдер с ID {provider_id} не найден"
            )
        
        if not provider.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Провайдер неактивен"
            )
        
        # Здесь будет реальное тестирование AI провайдера
        # Пока возвращаем заглушку
        import time
        import random
        
        start_time = time.time()
        
        # Симуляция запроса
        time.sleep(random.uniform(0.5, 2.0))
        
        response_time = int((time.time() - start_time) * 1000)
        
        # Тестовый ответ
        test_response = f"Тестовый ответ от {provider.display_name}: {test_request.test_prompt}"
        
        # Логируем тест
        crud_ai.create_ai_usage_log(
            db=db,
            user_id=current_user.id,
            provider_id=provider_id,
            task_type="test",
            tokens_used=len(test_request.test_prompt.split()) * 2,  # Примерная оценка
            response_time_ms=response_time,
            success=True
        )
        
        return AITestResult(
            success=True,
            response_text=test_response,
            response_time_ms=response_time,
            tokens_used=len(test_request.test_prompt.split()) * 2,
            provider_info={
                "name": provider.name,
                "model": provider.model,
                "temperature": provider.temperature
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Логируем ошибку
        crud_ai.create_ai_usage_log(
            db=db,
            user_id=current_user.id,
            provider_id=provider_id,
            task_type="test",
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования AI провайдера: {str(e)}"
        )


# ===================== СИСТЕМНЫЕ НАСТРОЙКИ =====================

@router.get("/ai/settings")
def get_ai_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки AI системы"""
    try:
        settings = crud_ai.get_ai_system_settings(db)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек AI: {str(e)}"
        )


@router.put("/ai/settings")
def update_ai_settings(
    settings: AISystemSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить настройки AI системы"""
    try:
        updated_settings = crud_ai.update_ai_system_settings(
            db, settings.model_dump(), current_user.id
        )
        return {
            "success": True,
            "message": "Настройки AI обновлены",
            "settings": updated_settings
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек AI: {str(e)}"
        )


# ===================== СТАТИСТИКА =====================

@router.get("/ai/stats", response_model=AIStatsResponse)
def get_ai_stats(
    days_back: int = 30,
    provider_id: Optional[int] = None,
    specialty: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить статистику использования AI"""
    try:
        stats = crud_ai.get_ai_usage_stats(
            db, days_back=days_back, provider_id=provider_id, specialty=specialty
        )
        return AIStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики AI: {str(e)}"
        )


@router.get("/ai/usage-logs", response_model=List[AIUsageLogOut])
def get_ai_usage_logs(
    skip: int = 0,
    limit: int = 100,
    provider_id: Optional[int] = None,
    task_type: Optional[str] = None,
    success_only: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить логи использования AI"""
    try:
        query = db.query(crud_ai.AIUsageLog)
        
        if provider_id:
            query = query.filter(crud_ai.AIUsageLog.provider_id == provider_id)
        if task_type:
            query = query.filter(crud_ai.AIUsageLog.task_type == task_type)
        if success_only is not None:
            query = query.filter(crud_ai.AIUsageLog.success == success_only)
        
        logs = query.order_by(desc(crud_ai.AIUsageLog.created_at)).offset(skip).limit(limit).all()
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения логов AI: {str(e)}"
        )
