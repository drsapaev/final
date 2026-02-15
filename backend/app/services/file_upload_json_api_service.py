"""
Endpoint для загрузки файлов через JSON
"""

import base64
import hashlib
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


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
        print(f"📁 Получен файл: {request.filename}")
        print(f"👤 Пользователь: {current_user.username}")

        # Декодируем содержимое файла
        try:
            content = base64.b64decode(request.content)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Ошибка декодирования base64: {e}"
            )

        file_size = len(content)
        print(f"📊 Размер файла: {file_size} байт")

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

        print(f"✅ Файл сохранен: {file_path}")

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
        print(f"❌ Ошибка загрузки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки файла: {str(e)}")

