"""
API endpoints для верификации телефонных номеров
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
import re

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User
from app.services.phone_verification_service import get_phone_verification_service
from app.services.sms_providers import SMSProviderType

router = APIRouter()


class SendVerificationCodeRequest(BaseModel):
    """Запрос на отправку кода верификации"""
    phone: str
    purpose: str = "verification"
    provider: Optional[str] = None
    custom_message: Optional[str] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        # Удаляем все символы кроме цифр и +
        phone = re.sub(r'[^\d+]', '', v)
        
        # Проверяем формат
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        
        return phone
    
    @validator('purpose')
    def validate_purpose(cls, v):
        allowed_purposes = ['verification', 'password_reset', 'phone_change', 'registration']
        if v not in allowed_purposes:
            raise ValueError(f'Цель должна быть одной из: {", ".join(allowed_purposes)}')
        return v


class VerifyCodeRequest(BaseModel):
    """Запрос на проверку кода верификации"""
    phone: str
    code: str
    purpose: str = "verification"
    
    @validator('phone')
    def validate_phone(cls, v):
        phone = re.sub(r'[^\d+]', '', v)
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone
    
    @validator('code')
    def validate_code(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


class UpdatePhoneRequest(BaseModel):
    """Запрос на обновление номера телефона"""
    new_phone: str
    verification_code: str
    
    @validator('new_phone')
    def validate_phone(cls, v):
        phone = re.sub(r'[^\d+]', '', v)
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone
    
    @validator('verification_code')
    def validate_code(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


@router.post("/send-code")
async def send_verification_code(
    request: SendVerificationCodeRequest,
    current_user: User = Depends(get_current_user)
):
    """Отправка кода верификации"""
    try:
        verification_service = get_phone_verification_service()
        
        # Определяем провайдера SMS
        provider_type = None
        if request.provider:
            try:
                provider_type = SMSProviderType(request.provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неподдерживаемый SMS провайдер: {request.provider}"
                )
        
        # Отправляем код
        result = await verification_service.send_verification_code(
            phone=request.phone,
            purpose=request.purpose,
            provider_type=provider_type,
            custom_message=request.custom_message
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "expires_in_minutes": result["expires_in_minutes"],
                "provider": result.get("provider")
            }
        else:
            # Определяем HTTP статус код по типу ошибки
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if result.get("error_code") == "RATE_LIMITED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "SMS_SEND_FAILED":
                status_code = status.HTTP_502_BAD_GATEWAY
            
            raise HTTPException(
                status_code=status_code,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки кода верификации: {str(e)}"
        )


@router.post("/verify-code")
async def verify_code(
    request: VerifyCodeRequest,
    current_user: User = Depends(get_current_user)
):
    """Проверка кода верификации"""
    try:
        verification_service = get_phone_verification_service()
        
        result = verification_service.verify_code(
            phone=request.phone,
            code=request.code,
            purpose=request.purpose
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "phone": result["phone"],
                "verified_at": result["verified_at"]
            }
        else:
            # Определяем HTTP статус код по типу ошибки
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "CODE_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "CODE_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "MAX_ATTEMPTS_EXCEEDED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            
            response_data = {
                "success": False,
                "error": result["error"],
                "error_code": result.get("error_code")
            }
            
            # Добавляем информацию об оставшихся попытках
            if "attempts_left" in result:
                response_data["attempts_left"] = result["attempts_left"]
            
            raise HTTPException(
                status_code=status_code,
                detail=response_data
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки кода: {str(e)}"
        )


@router.get("/status")
async def get_verification_status(
    phone: str = Query(..., description="Номер телефона в формате +998XXXXXXXXX"),
    purpose: str = Query("verification", description="Цель верификации"),
    current_user: User = Depends(get_current_user)
):
    """Получение статуса верификации"""
    try:
        # Валидация номера телефона
        phone = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^\+998\d{9}$', phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Номер телефона должен быть в формате +998XXXXXXXXX"
            )
        
        verification_service = get_phone_verification_service()
        
        status_info = verification_service.get_verification_status(phone, purpose)
        
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса верификации: {str(e)}"
        )


@router.delete("/cancel")
async def cancel_verification(
    phone: str = Query(..., description="Номер телефона в формате +998XXXXXXXXX"),
    purpose: str = Query("verification", description="Цель верификации"),
    current_user: User = Depends(get_current_user)
):
    """Отмена верификации"""
    try:
        # Валидация номера телефона
        phone = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^\+998\d{9}$', phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Номер телефона должен быть в формате +998XXXXXXXXX"
            )
        
        verification_service = get_phone_verification_service()
        
        success = verification_service.cancel_verification(phone, purpose)
        
        if success:
            return {
                "success": True,
                "message": "Верификация отменена"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Активная верификация не найдена"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отмены верификации: {str(e)}"
        )


@router.put("/update-phone")
async def update_user_phone(
    request: UpdatePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление номера телефона пользователя"""
    try:
        verification_service = get_phone_verification_service()
        
        result = await verification_service.verify_and_update_user_phone(
            db=db,
            user_id=current_user.id,
            phone=request.new_phone,
            code=request.verification_code,
            purpose="phone_change"
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "phone": result["phone"],
                "verified_at": result["verified_at"]
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "PHONE_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            elif result.get("error_code") == "USER_UPDATE_FAILED":
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            raise HTTPException(
                status_code=status_code,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления номера телефона: {str(e)}"
        )


@router.get("/statistics")
async def get_verification_statistics(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Статистика верификаций (только для администраторов)"""
    try:
        verification_service = get_phone_verification_service()
        
        stats = verification_service.get_statistics()
        
        return {
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )


@router.post("/admin/send-code")
async def admin_send_verification_code(
    phone: str = Query(..., description="Номер телефона в формате +998XXXXXXXXX"),
    purpose: str = Query("verification", description="Цель верификации"),
    provider: Optional[str] = Query(None, description="SMS провайдер"),
    message: Optional[str] = Query(None, description="Кастомное сообщение с {code}"),
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Отправка кода верификации администратором"""
    try:
        # Валидация номера телефона
        phone = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^\+998\d{9}$', phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Номер телефона должен быть в формате +998XXXXXXXXX"
            )
        
        verification_service = get_phone_verification_service()
        
        # Определяем провайдера SMS
        provider_type = None
        if provider:
            try:
                provider_type = SMSProviderType(provider)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неподдерживаемый SMS провайдер: {provider}"
                )
        
        # Отправляем код
        result = await verification_service.send_verification_code(
            phone=phone,
            purpose=purpose,
            provider_type=provider_type,
            custom_message=message
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "phone": phone,
                "purpose": purpose,
                "expires_in_minutes": result["expires_in_minutes"],
                "provider": result.get("provider"),
                "sent_by_admin": current_user.username
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки кода администратором: {str(e)}"
        )
