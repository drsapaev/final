"""
API endpoints для управления SMS провайдерами
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User
from app.services.sms_providers import get_sms_manager, SMSProviderType, SMSMessage

router = APIRouter()


class SMSTestRequest(BaseModel):
    """Запрос на тестовую отправку SMS"""
    phone: str
    message: str
    provider: Optional[str] = None


class SMSProviderInfo(BaseModel):
    """Информация о SMS провайдере"""
    name: str
    available: bool
    balance: Optional[float] = None
    currency: Optional[str] = None
    error: Optional[str] = None


@router.get("/providers", response_model=List[SMSProviderInfo])
async def get_sms_providers(
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Получить список доступных SMS провайдеров"""
    try:
        sms_manager = get_sms_manager()
        providers = []
        
        for provider_type in SMSProviderType:
            provider = sms_manager.get_provider(provider_type)
            
            if provider:
                # Получаем баланс провайдера
                try:
                    balance_info = await provider.get_balance()
                    providers.append(SMSProviderInfo(
                        name=provider_type.value,
                        available=True,
                        balance=balance_info.get("balance"),
                        currency=balance_info.get("currency"),
                        error=balance_info.get("error") if not balance_info.get("success") else None
                    ))
                except Exception as e:
                    providers.append(SMSProviderInfo(
                        name=provider_type.value,
                        available=False,
                        error=str(e)
                    ))
            else:
                providers.append(SMSProviderInfo(
                    name=provider_type.value,
                    available=False,
                    error="Provider not configured"
                ))
        
        return providers
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting SMS providers: {str(e)}"
        )


@router.get("/balance/{provider}")
async def get_provider_balance(
    provider: str,
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Получить баланс конкретного провайдера"""
    try:
        # Проверяем валидность провайдера
        try:
            provider_type = SMSProviderType(provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}"
            )
        
        sms_manager = get_sms_manager()
        balance_info = await sms_manager.get_balance(provider_type)
        
        return balance_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting balance: {str(e)}"
        )


@router.post("/test")
async def test_sms_sending(
    request: SMSTestRequest,
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Тестовая отправка SMS"""
    try:
        # Определяем провайдер
        provider_type = None
        if request.provider:
            try:
                provider_type = SMSProviderType(request.provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid provider: {request.provider}"
                )
        
        sms_manager = get_sms_manager()
        
        # Отправляем тестовое SMS
        result = await sms_manager.send_sms(
            phone=request.phone,
            text=request.message,
            provider_type=provider_type
        )
        
        return {
            "success": result.success,
            "message_id": result.message_id,
            "provider": result.provider,
            "error": result.error,
            "status": result.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending test SMS: {str(e)}"
        )


@router.post("/send-2fa-code")
async def send_2fa_code(
    phone: str,
    code: str,
    provider: Optional[str] = None,
    current_user: User = Depends(require_roles(["Admin", "Registrar"]))
):
    """Отправить код 2FA (для администраторов и регистраторов)"""
    try:
        # Определяем провайдер
        provider_type = None
        if provider:
            try:
                provider_type = SMSProviderType(provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid provider: {provider}"
                )
        
        sms_manager = get_sms_manager()
        
        # Отправляем код 2FA
        result = await sms_manager.send_2fa_code(
            phone=phone,
            code=code,
            provider_type=provider_type
        )
        
        return {
            "success": result.success,
            "message_id": result.message_id,
            "provider": result.provider,
            "error": result.error,
            "status": result.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending 2FA code: {str(e)}"
        )


@router.get("/status/{message_id}")
async def get_message_status(
    message_id: str,
    provider: str,
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Получить статус отправленного сообщения"""
    try:
        # Проверяем валидность провайдера
        try:
            provider_type = SMSProviderType(provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}"
            )
        
        sms_manager = get_sms_manager()
        provider_instance = sms_manager.get_provider(provider_type)
        
        if not provider_instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider} not available"
            )
        
        status_info = await provider_instance.get_message_status(message_id)
        
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting message status: {str(e)}"
        )


