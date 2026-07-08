"""
Endpoint для загрузки файлов через JSON
"""

import base64
import hashlib
import logging
import os
from binascii import Error as BinasciiError
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_JSON_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_JSON_UPLOAD_BASE64_CHARS = ((MAX_JSON_UPLOAD_BYTES + 2) // 3) * 4


class FileUploadRequest(BaseModel):
    filename: str
    content: str  # base64 encoded content
    title: str = None
    description: str = None


@router.post("/upload-json", response_model=dict[str, Any])
async def upload_file_json(
    request: FileUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Загрузка файла через JSON (base64)"""
    try:
        logger.info(
            "JSON file upload requested role=%s has_title=%s has_description=%s",
            getattr(current_user, "role", None),
            bool(request.title),
            bool(request.description),
        )

        if len(request.content) > MAX_JSON_UPLOAD_BASE64_CHARS:
            raise HTTPException(status_code=413, detail="Uploaded file is too large")

        # Декодируем содержимое файла
        try:
            content = base64.b64decode(request.content, validate=True)
        except BinasciiError as e:
            logger.warning(
                "JSON file upload rejected during base64 decode (%s)",
                type(e).__name__,
            )
            raise HTTPException(
                status_code=400, detail="Ошибка декодирования base64"
            ) from e

        file_size = len(content)
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if file_size > MAX_JSON_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Uploaded file is too large")

        logger.info("JSON file upload decoded size_bytes=%s", file_size)

        # Создаем хеш файла
        file_hash = hashlib.sha256(content).hexdigest()

        # Создаем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = f"{timestamp}_{file_hash[:16]}"

        # Сохраняем файл
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(
            "JSON file upload saved storage=local_uploads size_bytes=%s",
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
    except Exception as e:
        logger.error(
            "JSON file upload failed (%s)",
            type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Ошибка загрузки файла") from e
