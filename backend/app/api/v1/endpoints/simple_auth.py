"""
Упрощенный endpoint авторизации без сложных зависимостей
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_password
from app.api.deps import create_access_token

router = APIRouter()


class SimpleLoginRequest(BaseModel):
    """Простая схема для входа"""
    username: str
    password: str
    remember_me: bool = False


class SimpleLoginResponse(BaseModel):
    """Простая схема ответа"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


@router.post("/simple-login", response_model=SimpleLoginResponse)
async def simple_login(
    request_data: SimpleLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Упрощенный вход в систему без сложных зависимостей
    """
    try:
        print(f"DEBUG: Simple login called with username={request_data.username}")
        
        # Ищем пользователя по username или email
        user = db.query(User).filter(
            (User.username == request_data.username) | 
            (User.email == request_data.username)
        ).first()

        if not user:
            print(f"DEBUG: User not found for username={request_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )

        print(f"DEBUG: User found: ID={user.id}, Username={user.username}, IsActive={user.is_active}")

        if not user.is_active:
            print(f"DEBUG: User is inactive")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь деактивирован"
            )

        print(f"DEBUG: Verifying password...")
        password_valid = verify_password(request_data.password, user.hashed_password)
        print(f"DEBUG: Password verification result: {password_valid}")
        
        if not password_valid:
            print(f"DEBUG: Invalid password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )

        # Создаем токен
        expires_delta = timedelta(hours=24 if request_data.remember_me else 8)
        access_token = create_access_token(
            data={"sub": str(user.id), "user_id": user.id, "username": user.username},
            expires_delta=expires_delta
        )
        
        expires_in = int(expires_delta.total_seconds())
        
        print(f"DEBUG: Token created successfully, expires in {expires_in} seconds")
        
        # Формируем данные пользователя
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        }
        
        print(f"DEBUG: Successful authentication for user {user.username}")
        
        return SimpleLoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Exception in simple login: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(e)}"
        )


@router.get("/me")
async def get_current_user_simple(
    db: Session = Depends(get_db),
    current_user: User = Depends(lambda: None)  # Временно отключено
):
    """
    Получить информацию о текущем пользователе
    """
    # Временная заглушка
    return {"message": "Endpoint /me временно недоступен"}

