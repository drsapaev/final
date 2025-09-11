"""
API endpoints для SMS/Email двухфакторной аутентификации
"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service, TwoFactorService
from app.services.notifications import notification_service

router = APIRouter()


@router.post("/send-code")
async def send_verification_code(
    method: str = Query(..., description="Метод отправки: sms или email"),
    phone_number: Optional[str] = Query(None, description="Номер телефона для SMS"),
    email_address: Optional[str] = Query(None, description="Email адрес"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отправить код подтверждения по SMS или Email"""
    try:
        service = get_two_factor_service()
        # notification_service уже импортирован
        
        # Генерируем 6-значный код
        code = ''.join(random.choices(string.digits, k=6))
        
        # Сохраняем код в базе данных
        service.save_verification_code(
            db=db,
            user_id=current_user.id,
            method=method,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        # Отправляем код
        if method == 'sms' and phone_number:
            # Отправка SMS
            success = await notification_service.send_sms(
                phone_number=phone_number,
                message=f"Ваш код подтверждения: {code}. Код действителен 5 минут."
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Ошибка отправки SMS"
                )
                
        elif method == 'email' and email_address:
            # Отправка Email
            success = await notification_service.send_email(
                to_email=email_address,
                subject="Код подтверждения",
                body=f"Ваш код подтверждения: {code}. Код действителен 5 минут."
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Ошибка отправки Email"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный метод или отсутствуют контактные данные"
            )
        
        return {
            "success": True,
            "message": f"Код отправлен на {phone_number if method == 'sms' else email_address}",
            "method": method,
            "expires_in": 300  # 5 минут в секундах
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки кода: {str(e)}"
        )


@router.post("/verify-code")
async def verify_verification_code(
    method: str = Query(..., description="Метод верификации: sms или email"),
    code: str = Query(..., description="Код подтверждения"),
    phone_number: Optional[str] = Query(None, description="Номер телефона для SMS"),
    email_address: Optional[str] = Query(None, description="Email адрес"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Проверить код подтверждения"""
    try:
        service = get_two_factor_service()
        
        # Проверяем код
        is_valid = service.verify_code(
            db=db,
            user_id=current_user.id,
            method=method,
            code=code
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный или истекший код"
            )
        
        # Генерируем токен сессии
        session_token = service.create_session_token(
            db=db,
            user_id=current_user.id,
            method=method
        )
        
        return {
            "success": True,
            "message": "Код подтвержден успешно",
            "session_token": session_token,
            "method": method
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки кода: {str(e)}"
        )


@router.get("/verification-status")
async def get_verification_status(
    method: str = Query(..., description="Метод: sms или email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить статус верификации для метода"""
    try:
        service = get_two_factor_service()
        
        status = service.get_verification_status(
            db=db,
            user_id=current_user.id,
            method=method
        )
        
        return status
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса: {str(e)}"
        )


@router.post("/resend-code")
async def resend_verification_code(
    method: str = Query(..., description="Метод отправки: sms или email"),
    phone_number: Optional[str] = Query(None, description="Номер телефона для SMS"),
    email_address: Optional[str] = Query(None, description="Email адрес"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Повторно отправить код подтверждения"""
    try:
        service = get_two_factor_service()
        
        # Проверяем, можно ли отправить повторно
        can_resend = service.can_resend_code(
            db=db,
            user_id=current_user.id,
            method=method
        )
        
        if not can_resend:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте позже."
            )
        
        # Генерируем новый код
        code = ''.join(random.choices(string.digits, k=6))
        
        # Сохраняем код
        service.save_verification_code(
            db=db,
            user_id=current_user.id,
            method=method,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        # Отправляем код
        # notification_service уже импортирован
        
        if method == 'sms' and phone_number:
            success = await notification_service.send_sms(
                phone_number=phone_number,
                message=f"Ваш код подтверждения: {code}. Код действителен 5 минут."
            )
        elif method == 'email' and email_address:
            success = await notification_service.send_email(
                to_email=email_address,
                subject="Код подтверждения",
                body=f"Ваш код подтверждения: {code}. Код действителен 5 минут."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный метод или отсутствуют контактные данные"
            )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка отправки кода"
            )
        
        return {
            "success": True,
            "message": f"Код повторно отправлен на {phone_number if method == 'sms' else email_address}",
            "method": method,
            "expires_in": 300
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка повторной отправки: {str(e)}"
        )


@router.get("/supported-methods")
async def get_supported_methods():
    """Получить список поддерживаемых методов 2FA"""
    return {
        "methods": [
            {
                "id": "totp",
                "name": "Приложение-аутентификатор",
                "description": "Google Authenticator, Authy, Microsoft Authenticator",
                "icon": "smartphone",
                "recommended": True
            },
            {
                "id": "sms",
                "name": "SMS коды",
                "description": "Коды по SMS на номер телефона",
                "icon": "phone",
                "recommended": False
            },
            {
                "id": "email",
                "name": "Email коды",
                "description": "Коды на email адрес",
                "icon": "mail",
                "recommended": False
            }
        ]
    }


@router.get("/security-logs")
async def get_security_logs(
    limit: int = Query(50, description="Количество записей"),
    offset: int = Query(0, description="Смещение"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить журнал безопасности 2FA"""
    try:
        service = get_two_factor_service()
        
        logs = service.get_security_logs(
            db=db,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        return {
            "logs": logs,
            "total": len(logs),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения журнала: {str(e)}"
        )


@router.get("/recovery-methods")
async def get_recovery_methods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить методы восстановления"""
    try:
        service = get_two_factor_service()
        
        methods = service.get_recovery_methods(
            db=db,
            user_id=current_user.id
        )
        
        return {
            "methods": methods
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения методов восстановления: {str(e)}"
        )
