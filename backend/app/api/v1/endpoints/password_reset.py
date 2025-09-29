"""
API endpoints для восстановления паролей
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
import re

from app.db.session import get_db
from app.api.deps import require_roles
from app.models.user import User
from app.services.password_reset_service import get_password_reset_service

router = APIRouter()


class PasswordResetInitiateRequest(BaseModel):
    """Запрос на инициацию сброса пароля"""
    phone: Optional[str] = None
    email: Optional[str] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        if v is None:
            return v
        phone = re.sub(r'[^\d+]', '', v)
        if not re.match(r'^\+998\d{9}$', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone
    
    @validator('email')
    def validate_email(cls, v):
        if v is None:
            return v
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', v):
            raise ValueError('Неверный формат email адреса')
        return v
    
    @validator('email', always=True)
    def validate_contact_provided(cls, v, values):
        if not v and not values.get('phone'):
            raise ValueError('Необходимо указать номер телефона или email')
        if v and values.get('phone'):
            raise ValueError('Укажите только один способ связи: телефон или email')
        return v


class PhoneVerificationRequest(BaseModel):
    """Запрос на верификацию телефона для сброса пароля"""
    phone: str
    verification_code: str
    
    @validator('phone')
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


class PasswordResetConfirmRequest(BaseModel):
    """Запрос на подтверждение сброса пароля"""
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Пароль должен содержать минимум 6 символов')
        return v


@router.post("/initiate")
async def initiate_password_reset(
    request: PasswordResetInitiateRequest,
    db: Session = Depends(get_db)
):
    """Инициация сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()
        
        if request.phone:
            result = await password_reset_service.initiate_phone_reset(
                db=db,
                phone=request.phone
            )
        else:
            result = await password_reset_service.initiate_email_reset(
                db=db,
                email=request.email
            )
        
        if result["success"]:
            response_data = {
                "success": True,
                "message": result["message"]
            }
            
            # Добавляем дополнительную информацию если есть
            if "expires_in_minutes" in result:
                response_data["expires_in_minutes"] = result["expires_in_minutes"]
            if "expires_in_hours" in result:
                response_data["expires_in_hours"] = result["expires_in_hours"]
            
            return response_data
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if result.get("error_code") == "RATE_LIMITED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "EMAIL_SEND_FAILED":
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
            detail=f"Ошибка инициации сброса пароля: {str(e)}"
        )


@router.post("/verify-phone")
async def verify_phone_for_reset(
    request: PhoneVerificationRequest,
    db: Session = Depends(get_db)
):
    """Верификация телефона для сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()
        
        result = await password_reset_service.verify_phone_and_get_token(
            db=db,
            phone=request.phone,
            verification_code=request.verification_code
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "reset_token": result["reset_token"],
                "expires_in_hours": result["expires_in_hours"]
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "CODE_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "CODE_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "MAX_ATTEMPTS_EXCEEDED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "USER_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            
            response_data = {
                "success": False,
                "error": result["error"],
                "error_code": result.get("error_code")
            }
            
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
            detail=f"Ошибка верификации телефона: {str(e)}"
        )


@router.post("/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: Session = Depends(get_db)
):
    """Подтверждение сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()
        
        result = password_reset_service.reset_password_with_token(
            db=db,
            token=request.token,
            new_password=request.new_password
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"]
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "TOKEN_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "TOKEN_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "TOKEN_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            elif result.get("error_code") == "USER_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "PASSWORD_UPDATE_FAILED":
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
            detail=f"Ошибка подтверждения сброса пароля: {str(e)}"
        )


@router.get("/validate-token")
async def validate_reset_token(
    token: str = Query(..., description="Токен сброса пароля"),
    db: Session = Depends(get_db)
):
    """Проверка валидности токена сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()
        
        result = password_reset_service.validate_reset_token(token)
        
        if result["valid"]:
            return {
                "valid": True,
                "expires_at": result["expires_at"],
                "time_left_minutes": result["time_left_minutes"]
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "TOKEN_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "TOKEN_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "TOKEN_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            
            raise HTTPException(
                status_code=status_code,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки токена: {str(e)}"
        )


@router.get("/statistics")
async def get_password_reset_statistics(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Статистика сброса паролей (только для администраторов)"""
    try:
        password_reset_service = get_password_reset_service()
        
        stats = password_reset_service.get_statistics()
        
        return {
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )
