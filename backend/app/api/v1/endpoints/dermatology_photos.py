"""
API endpoints для работы с фото в дерматологии
Основа: passport.md стр. 1789-2063
"""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import dermatology_photos as crud_photos
from app.models.dermatology_photos import DermatologyPhoto
from app.models.user import User

router = APIRouter()

# Настройки для загрузки фото
UPLOAD_DIR = "uploads/dermatology"
THUMBNAIL_SIZE = (300, 300)
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Создаем директории если не существуют
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(f"{UPLOAD_DIR}/thumbnails", exist_ok=True)

# ===================== ЗАГРУЗКА ФОТО =====================


@router.post("/upload")
async def upload_photos(
    files: List[UploadFile] = File(...),
    patient_id: int = Form(...),
    category: str = Form(...),  # before, after, progress
    patient_name: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Загрузка фото для дерматологического пациента
    """
    try:
        uploaded_photos = []

        for file in files:
            # Проверяем размер файла
            if file.size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Файл {file.filename} слишком большой (максимум 10MB)",
                )

            # Проверяем расширение
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неподдерживаемый формат файла: {file_ext}",
                )

            # Генерируем уникальное имя файла
            file_id = str(uuid.uuid4())
            filename = f"{file_id}{file_ext}"
            file_path = os.path.join(UPLOAD_DIR, filename)

            # Сохраняем файл
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            # Создаем миниатюру
            thumbnail_path = os.path.join(
                f"{UPLOAD_DIR}/thumbnails", f"thumb_{filename}"
            )
            try:
                with Image.open(file_path) as img:
                    img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                    img.save(thumbnail_path, "JPEG", quality=85)
            except Exception as e:
                print(f"Ошибка создания миниатюры: {e}")
                thumbnail_path = None

            # Сохраняем в БД
            photo_data = {
                "patient_id": patient_id,
                "category": category,
                "filename": filename,
                "original_filename": file.filename,
                "file_path": file_path,
                "thumbnail_path": thumbnail_path,
                "file_size": file.size,
                "mime_type": file.content_type,
                "notes": notes,
                "uploaded_by": current_user.id,
            }

            photo = crud_photos.create_photo(db, photo_data)
            uploaded_photos.append(photo)

        return {
            "success": True,
            "message": f"Загружено {len(files)} фото",
            "photos": [
                {
                    "id": photo.id,
                    "url": f"/api/v1/dermatology/photos/{photo.id}/image",
                    "thumbnail_url": (
                        f"/api/v1/dermatology/photos/{photo.id}/thumbnail"
                        if photo.thumbnail_path
                        else None
                    ),
                    "category": photo.category,
                    "created_at": photo.created_at.isoformat(),
                    "notes": photo.notes,
                }
                for photo in uploaded_photos
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки фото: {str(e)}",
        )


# ===================== ПОЛУЧЕНИЕ ФОТО =====================


@router.get("/")
def get_patient_photos(
    patient_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Получить фото пациента
    """
    try:
        photos = crud_photos.get_patient_photos(db, patient_id, category)

        return {
            "before": [
                {
                    "id": photo.id,
                    "url": f"/api/v1/dermatology/photos/{photo.id}/image",
                    "thumbnail_url": (
                        f"/api/v1/dermatology/photos/{photo.id}/thumbnail"
                        if photo.thumbnail_path
                        else None
                    ),
                    "category": photo.category,
                    "created_at": photo.created_at.isoformat(),
                    "notes": photo.notes,
                }
                for photo in photos
                if photo.category == "before"
            ],
            "after": [
                {
                    "id": photo.id,
                    "url": f"/api/v1/dermatology/photos/{photo.id}/image",
                    "thumbnail_url": (
                        f"/api/v1/dermatology/photos/{photo.id}/thumbnail"
                        if photo.thumbnail_path
                        else None
                    ),
                    "category": photo.category,
                    "created_at": photo.created_at.isoformat(),
                    "notes": photo.notes,
                }
                for photo in photos
                if photo.category == "after"
            ],
            "progress": [
                {
                    "id": photo.id,
                    "url": f"/api/v1/dermatology/photos/{photo.id}/image",
                    "thumbnail_url": (
                        f"/api/v1/dermatology/photos/{photo.id}/thumbnail"
                        if photo.thumbnail_path
                        else None
                    ),
                    "category": photo.category,
                    "created_at": photo.created_at.isoformat(),
                    "notes": photo.notes,
                }
                for photo in photos
                if photo.category == "progress"
            ],
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения фото: {str(e)}",
        )


@router.get("/{photo_id}/image")
def get_photo_image(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Получить изображение фото
    """
    try:
        photo = crud_photos.get_photo(db, photo_id)
        if not photo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено"
            )

        if not os.path.exists(photo.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Файл фото не найден"
            )

        from fastapi.responses import FileResponse

        return FileResponse(
            photo.file_path,
            media_type=photo.mime_type,
            filename=photo.original_filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения изображения: {str(e)}",
        )


@router.get("/{photo_id}/thumbnail")
def get_photo_thumbnail(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Получить миниатюру фото
    """
    try:
        photo = crud_photos.get_photo(db, photo_id)
        if not photo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено"
            )

        if not photo.thumbnail_path or not os.path.exists(photo.thumbnail_path):
            # Возвращаем оригинальное изображение если миниатюра не найдена
            return get_photo_image(photo_id, db, current_user)

        from fastapi.responses import FileResponse

        return FileResponse(
            photo.thumbnail_path,
            media_type="image/jpeg",
            filename=f"thumb_{photo.original_filename}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения миниатюры: {str(e)}",
        )


# ===================== УПРАВЛЕНИЕ ФОТО =====================


@router.delete("/{photo_id}")
def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Удалить фото
    """
    try:
        photo = crud_photos.get_photo(db, photo_id)
        if not photo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено"
            )

        # Удаляем файлы с диска
        if os.path.exists(photo.file_path):
            os.remove(photo.file_path)

        if photo.thumbnail_path and os.path.exists(photo.thumbnail_path):
            os.remove(photo.thumbnail_path)

        # Удаляем запись из БД
        crud_photos.delete_photo(db, photo_id)

        return {"success": True, "message": "Фото удалено"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления фото: {str(e)}",
        )


@router.put("/{photo_id}")
def update_photo(
    photo_id: int,
    notes: str = Form(""),
    category: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Обновить информацию о фото
    """
    try:
        photo_data = {}
        if notes:
            photo_data["notes"] = notes
        if category:
            photo_data["category"] = category

        if not photo_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет данных для обновления",
            )

        photo = crud_photos.update_photo(db, photo_id, photo_data)
        if not photo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Фото не найдено"
            )

        return {
            "success": True,
            "message": "Фото обновлено",
            "photo": {
                "id": photo.id,
                "category": photo.category,
                "notes": photo.notes,
                "updated_at": photo.updated_at.isoformat(),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления фото: {str(e)}",
        )


# ===================== СТАТИСТИКА =====================


@router.get("/stats/patient/{patient_id}")
def get_patient_photo_stats(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "derma")),
):
    """
    Получить статистику фото пациента
    """
    try:
        stats = crud_photos.get_patient_photo_stats(db, patient_id)

        return {
            "patient_id": patient_id,
            "total_photos": stats.get("total", 0),
            "before_count": stats.get("before", 0),
            "after_count": stats.get("after", 0),
            "progress_count": stats.get("progress", 0),
            "total_size": stats.get("total_size", 0),
            "last_upload": stats.get("last_upload"),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )
