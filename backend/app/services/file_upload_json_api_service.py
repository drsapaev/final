"""
Endpoint для загрузки файлов через JSON
"""

import base64
import hashlib
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class FileUploadRequest(BaseModel):
    filename: str
    content: str  # base64 encoded content
    title: str = None
    description: str = None


@router.post("/upload-json")
async def upload_file_json(
    request: FileUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загрузка файла через JSON (base64)"""
    try:
        logger.info(
            "JSON file upload started user_id=%s has_title=%s has_description=%s",
            getattr(current_user, "id", None),
            bool(request.title),
            bool(request.description),
        )

        # Декодируем содержимое файла
        try:
            content = base64.b64decode(request.content)
        except Exception as exc:
            logger.warning(
                "JSON file upload base64 decode failed user_id=%s error_type=%s",
                getattr(current_user, "id", None),
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=400, detail="Ошибка декодирования base64"
            ) from None

        file_size = len(content)
        logger.info(
            "JSON file upload decoded user_id=%s file_size=%s",
            getattr(current_user, "id", None),
            file_size,
        )

        # Создаем хеш файла
        file_hash = hashlib.sha256(content).hexdigest()

        # Создаем имя файла
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request.filename}"

        # Сохраняем файл
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(
            "JSON file upload saved user_id=%s file_size=%s",
            getattr(current_user, "id", None),
            file_size,
        )

        return {
            "success": True,
            "message": "Файл успешно загружен",
            "filename": safe_filename,
            "original_filename": request.filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "file_path": file_path,
            "title": request.title,
            "description": request.description,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "JSON file upload failed user_id=%s error_type=%s",
            getattr(current_user, "id", None),
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Ошибка загрузки файла") from None

