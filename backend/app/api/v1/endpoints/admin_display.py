"""
API endpoints для управления табло в админ панели
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
import shutil
from pathlib import Path

from app.api.deps import get_db, require_roles
from app.models.user import User

router = APIRouter()

# ===================== УПРАВЛЕНИЕ ТАБЛО =====================

@router.get("/display/boards")
def get_display_boards(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить список табло"""
    try:
        # Пока возвращаем заглушку с базовым табло
        return [
            {
                "id": 1,
                "name": "main_board",
                "display_name": "Главное табло",
                "location": "Зона ожидания, 1 этаж",
                "theme": "light",
                "show_patient_names": "initials",
                "show_doctor_photos": True,
                "queue_display_count": 5,
                "show_announcements": True,
                "show_banners": True,
                "show_videos": False,
                "call_display_duration": 30,
                "sound_enabled": True,
                "voice_announcements": False,
                "voice_language": "ru",
                "volume_level": 70,
                "colors": {
                    "primary": "#0066cc",
                    "secondary": "#f8f9fa",
                    "text": "#333333",
                    "background": "#ffffff"
                },
                "active": True,
                "created_at": "2025-01-27T10:00:00Z"
            }
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка табло: {str(e)}"
        )


@router.get("/display/boards/{board_id}")
def get_display_board(
    board_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить конфигурацию табло"""
    try:
        # Пока возвращаем заглушку
        if board_id == 1:
            return {
                "id": 1,
                "name": "main_board",
                "display_name": "Главное табло",
                "location": "Зона ожидания, 1 этаж",
                "theme": "light",
                "show_patient_names": "initials",
                "show_doctor_photos": True,
                "queue_display_count": 5,
                "call_display_duration": 30,
                "sound_enabled": True,
                "voice_announcements": False,
                "voice_language": "ru",
                "volume_level": 70,
                "active": True,
                "banners": [],
                "videos": []
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Табло с ID {board_id} не найдено"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения табло: {str(e)}"
        )


@router.put("/display/boards/{board_id}")
def update_display_board(
    board_id: int,
    board_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить настройки табло"""
    try:
        # Здесь будет реальная логика обновления
        # Пока возвращаем успех
        
        return {
            "success": True,
            "message": "Настройки табло обновлены",
            "board_id": board_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления табло: {str(e)}"
        )


# ===================== БАННЕРЫ =====================

@router.get("/display/boards/{board_id}/banners")
def get_display_banners(
    board_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить баннеры табло"""
    try:
        # Пока возвращаем заглушку
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения баннеров: {str(e)}"
        )


@router.post("/display/boards/{board_id}/banners")
def create_display_banner(
    board_id: int,
    banner_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Создать баннер для табло"""
    try:
        # Здесь будет реальная логика создания баннера
        return {
            "success": True,
            "message": "Баннер создан",
            "banner_id": 1
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания баннера: {str(e)}"
        )


@router.post("/display/upload-banner")
def upload_banner_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("Admin"))
):
    """Загрузить изображение для баннера"""
    try:
        # Проверяем тип файла
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Файл должен быть изображением"
            )
        
        # Проверяем размер файла (макс 10MB)
        if file.size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Размер файла не должен превышать 10MB"
            )
        
        # Создаем директорию
        upload_dir = Path("static/uploads/banners")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем файл
        import uuid
        file_extension = file.filename.split(".")[-1] if file.filename else "png"
        filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = upload_dir / filename
        
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        banner_url = f"/static/uploads/banners/{filename}"
        
        return {
            "success": True,
            "banner_url": banner_url,
            "filename": filename,
            "size": file.size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки баннера: {str(e)}"
        )


# ===================== ТЕМЫ =====================

@router.get("/display/themes")
def get_display_themes(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить темы оформления табло"""
    try:
        # Возвращаем базовые темы
        themes = [
            {
                "id": 1,
                "name": "light",
                "display_name": "Светлая тема",
                "css_variables": {
                    "--primary-color": "#0066cc",
                    "--secondary-color": "#f8f9fa",
                    "--text-color": "#333333",
                    "--background-color": "#ffffff",
                    "--border-color": "#dee2e6"
                },
                "font_family": "system-ui, sans-serif",
                "active": True,
                "is_default": True
            },
            {
                "id": 2,
                "name": "dark",
                "display_name": "Темная тема",
                "css_variables": {
                    "--primary-color": "#0d6efd",
                    "--secondary-color": "#1a1a1a",
                    "--text-color": "#ffffff",
                    "--background-color": "#000000",
                    "--border-color": "#333333"
                },
                "font_family": "system-ui, sans-serif",
                "active": True,
                "is_default": False
            },
            {
                "id": 3,
                "name": "medical",
                "display_name": "Медицинская тема",
                "css_variables": {
                    "--primary-color": "#28a745",
                    "--secondary-color": "#e8f5e8",
                    "--text-color": "#2c3e50",
                    "--background-color": "#f8fff8",
                    "--border-color": "#c3e6cb"
                },
                "font_family": "system-ui, sans-serif",
                "active": True,
                "is_default": False
            }
        ]
        
        return themes if not active_only else [t for t in themes if t["active"]]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения тем: {str(e)}"
        )


# ===================== ТЕСТИРОВАНИЕ ТАБЛО =====================

@router.post("/display/boards/{board_id}/test")
def test_display_board(
    board_id: int,
    test_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Тестировать табло"""
    try:
        test_type = test_data.get("test_type", "call")
        
        if test_type == "call":
            # Тестовый вызов пациента
            return {
                "success": True,
                "message": "Тестовый вызов отправлен на табло",
                "test_data": {
                    "ticket_number": "A007",
                    "patient_name": "Тестовый П.",
                    "doctor_name": "Доктор Тест",
                    "cabinet": "101",
                    "call_time": datetime.utcnow().isoformat()
                }
            }
        elif test_type == "announcement":
            # Тестовое объявление
            return {
                "success": True,
                "message": "Тестовое объявление отправлено",
                "test_data": {
                    "announcement": "Тестовое объявление от админ панели",
                    "type": "info"
                }
            }
        else:
            return {
                "success": True,
                "message": f"Тест типа {test_type} выполнен"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования табло: {str(e)}"
        )


# ===================== СТАТИСТИКА ТАБЛО =====================

@router.get("/display/stats")
def get_display_stats(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить статистику табло"""
    try:
        # Пока возвращаем заглушку
        return {
            "total_boards": 1,
            "active_boards": 1,
            "total_calls_today": 45,
            "total_announcements": 3,
            "total_banners": 2,
            "uptime_percentage": 99.8,
            "by_board": {
                "main_board": {
                    "calls": 45,
                    "announcements": 3,
                    "uptime": 99.8
                }
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики табло: {str(e)}"
        )
