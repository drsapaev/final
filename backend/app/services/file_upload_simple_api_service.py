"""
Упрощенный endpoint для загрузки файлов
"""

import hashlib
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload-simple")
async def upload_file_simple(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Упрощенная загрузка файла"""
    try:
        logger.info("Simple file upload started")

        # Читаем содержимое файла
        content = await file.read()
        file_size = len(content)

        logger.info("Simple file upload content read")

        # Создаем хеш файла
        file_hash = hashlib.sha256(content).hexdigest()

        # Создаем имя файла
        filename = file.filename or "unknown"
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"

        # Сохраняем файл
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info("Simple file upload saved")

        return {
            "success": True,
            "message": "Файл успешно загружен",
            "filename": safe_filename,
            "original_filename": filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "file_path": file_path,
        }

    except Exception as exc:
        logger.error("Simple file upload failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Ошибка загрузки файла") from None
