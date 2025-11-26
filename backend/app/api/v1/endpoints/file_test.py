"""
Тестовый endpoint для файлов
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/test")
async def test_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Тестовый endpoint для файлов"""
    return {
        "success": True,
        "message": "Файловая система работает",
        "user": current_user.username,
        "role": current_user.role
    }

@router.post("/test-upload")
async def test_upload(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Тестовый endpoint для загрузки"""
    return {
        "success": True,
        "message": "Тестовая загрузка работает",
        "user": current_user.username
    }

