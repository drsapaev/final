"""
API endpoints для управления настройками клиники в админ панели
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
import shutil
import os
from pathlib import Path

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.crud import clinic as crud_clinic
from app.schemas.clinic import (
    ClinicSettingsOut, ClinicSettingsCreate, ClinicSettingsUpdate, ClinicSettingsBatch,
    QueueSettingsUpdate, QueueTestRequest,
    ServiceCategoryOut, ServiceCategoryCreate, ServiceCategoryUpdate
)

router = APIRouter()

# ===================== НАСТРОЙКИ КЛИНИКИ =====================

@router.get("/clinic/settings", response_model=List[ClinicSettingsOut])
def get_clinic_settings(
    category: str = "clinic",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки клиники по категории"""
    try:
        settings = crud_clinic.get_settings_by_category(db, category)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек: {str(e)}"
        )


@router.get("/clinic/settings/{key}", response_model=ClinicSettingsOut)
def get_clinic_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить конкретную настройку по ключу"""
    setting = crud_clinic.get_setting_by_key(db, key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Настройка с ключом '{key}' не найдена"
        )
    return setting


@router.put("/clinic/settings", response_model=List[ClinicSettingsOut])
def update_clinic_settings_batch(
    settings: ClinicSettingsBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Массовое обновление настроек клиники"""
    try:
        updated_settings = crud_clinic.update_settings_batch(
            db, "clinic", settings.settings, current_user.id
        )
        return updated_settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек: {str(e)}"
        )


@router.put("/clinic/settings/{key}", response_model=ClinicSettingsOut)
def update_clinic_setting(
    key: str,
    setting: ClinicSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить конкретную настройку"""
    updated_setting = crud_clinic.update_setting(db, key, setting, current_user.id)
    if not updated_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Настройка с ключом '{key}' не найдена"
        )
    return updated_setting


@router.post("/clinic/settings", response_model=ClinicSettingsOut)
def create_clinic_setting(
    setting: ClinicSettingsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Создать новую настройку"""
    try:
        # Проверяем, не существует ли уже такая настройка
        existing = crud_clinic.get_setting_by_key(db, setting.key)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Настройка с ключом '{setting.key}' уже существует"
            )
        
        new_setting = crud_clinic.create_setting(db, setting, current_user.id)
        return new_setting
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания настройки: {str(e)}"
        )


# ===================== ЗАГРУЗКА ЛОГОТИПА =====================

@router.post("/clinic/logo")
def upload_clinic_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("Admin"))
):
    """Загрузить логотип клиники"""
    try:
        # Проверяем тип файла
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Файл должен быть изображением"
            )
        
        # Проверяем размер файла (макс 5MB)
        if file.size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Размер файла не должен превышать 5MB"
            )
        
        # Создаем директорию если не существует
        upload_dir = Path("static/uploads/clinic")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерируем имя файла
        file_extension = file.filename.split(".")[-1] if file.filename else "png"
        filename = f"logo.{file_extension}"
        file_path = upload_dir / filename
        
        # Сохраняем файл
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Возвращаем URL логотипа
        logo_url = f"/static/uploads/clinic/{filename}"
        
        return {
            "success": True,
            "logo_url": logo_url,
            "filename": filename,
            "size": file.size,
            "content_type": file.content_type
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки логотипа: {str(e)}"
        )


# ===================== НАСТРОЙКИ ОЧЕРЕДЕЙ =====================

@router.get("/queue/settings")
def get_queue_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки системы очередей"""
    try:
        settings = crud_clinic.get_queue_settings(db)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек очередей: {str(e)}"
        )


@router.put("/queue/settings")
def update_queue_settings(
    settings: QueueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить настройки системы очередей"""
    try:
        updated_settings = crud_clinic.update_queue_settings(
            db, settings.model_dump(), current_user.id
        )
        return {
            "success": True,
            "message": "Настройки очередей обновлены",
            "settings": updated_settings
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления настроек очередей: {str(e)}"
        )


@router.post("/queue/test")
def test_queue_generation(
    request: QueueTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Тестирование генерации QR токена для очереди"""
    try:
        # Получаем врача
        doctor = crud_clinic.get_doctor_by_id(db, request.doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {request.doctor_id} не найден"
            )
        
        # Генерируем тестовый токен
        from datetime import datetime, date
        import uuid
        
        test_date = datetime.strptime(request.date, "%Y-%m-%d").date() if request.date else date.today()
        test_token = str(uuid.uuid4())
        
        return {
            "success": True,
            "message": "Тестовый QR токен сгенерирован",
            "test_data": {
                "token": test_token,
                "doctor_id": doctor.id,
                "doctor_specialty": doctor.specialty,
                "doctor_cabinet": doctor.cabinet,
                "date": test_date.isoformat(),
                "start_number": doctor.start_number_online,
                "max_per_day": doctor.max_online_per_day,
                "qr_url": f"/pwa/queue?token={test_token}"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования очереди: {str(e)}"
        )


# ===================== ИНФОРМАЦИЯ О СИСТЕМЕ =====================

@router.get("/system/info")
def get_system_info(
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить информацию о системе"""
    try:
        import psutil
        import platform
        from datetime import datetime
        
        return {
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "disk_usage": psutil.disk_usage('/').percent
            },
            "application": {
                "version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "development"),
                "timezone": os.getenv("TIMEZONE", "Asia/Tashkent"),
                "uptime": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return {
            "error": f"Не удалось получить информацию о системе: {str(e)}",
            "basic_info": {
                "environment": os.getenv("ENVIRONMENT", "development"),
                "timezone": os.getenv("TIMEZONE", "Asia/Tashkent")
            }
        }


# ===================== КАТЕГОРИИ УСЛУГ =====================

@router.get("/service-categories", response_model=List[ServiceCategoryOut])
def get_service_categories(
    specialty: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить категории услуг"""
    try:
        categories = crud_clinic.get_service_categories(db, specialty=specialty, active_only=active_only)
        return categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения категорий: {str(e)}"
        )
