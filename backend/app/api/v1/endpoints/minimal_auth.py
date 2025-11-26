"""
Минимальный endpoint авторизации без зависимостей от сложных моделей
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import get_db
from app.core.security import verify_password
from app.api.deps import create_access_token

router = APIRouter()


class MinimalLoginRequest(BaseModel):
    """Минимальная схема для входа"""
    username: str
    password: str
    remember_me: bool = False


class MinimalLoginResponse(BaseModel):
    """Минимальная схема ответа"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


@router.options("/minimal-login")
async def minimal_login_options():
    """Обработка OPTIONS запроса для CORS"""
    return {"message": "OK"}

@router.post("/minimal-login", response_model=MinimalLoginResponse)
async def minimal_login(
    request_data: MinimalLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Минимальный вход в систему без зависимостей от сложных моделей
    """
    try:
        print(f"DEBUG: Minimal login called with username={request_data.username}")
        
        # Используем прямой SQL запрос для избежания проблем с моделями
        result = db.execute(text("""
            SELECT id, username, email, full_name, role, is_active, is_superuser, hashed_password
            FROM users 
            WHERE username = :username OR email = :username
        """), {"username": request_data.username})
        
        user_row = result.fetchone()

        if not user_row:
            print(f"DEBUG: User not found for username={request_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )

        user_id, username, email, full_name, role, is_active, is_superuser, hashed_password = user_row
        
        print(f"DEBUG: User found: ID={user_id}, Username={username}, IsActive={is_active}")

        if not is_active:
            print(f"DEBUG: User is inactive")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь деактивирован"
            )

        print(f"DEBUG: Verifying password...")
        password_valid = verify_password(request_data.password, hashed_password)
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
            data={"sub": str(user_id), "user_id": user_id, "username": username},
            expires_delta=expires_delta
        )
        
        expires_in = int(expires_delta.total_seconds())
        
        print(f"DEBUG: Token created successfully, expires in {expires_in} seconds")
        
        # Формируем данные пользователя
        user_data = {
            "id": user_id,
            "username": username,
            "email": email,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
            "is_superuser": is_superuser
        }
        
        print(f"DEBUG: Successful authentication for user {username}")
        
        return MinimalLoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Exception in minimal login: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(e)}"
        )

