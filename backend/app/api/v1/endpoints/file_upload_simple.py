"""Legacy simple file upload endpoint.

This route is kept only for explicit dev/test use. Production document upload
must go through the canonical file/document service with full storage policy.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User

from typing import Any
router = APIRouter()
logger = logging.getLogger(__name__)

ENABLE_SIMPLE_FILE_UPLOAD_ENV = "ENABLE_SIMPLE_FILE_UPLOAD"
MAX_SIMPLE_UPLOAD_BYTES = 10 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".txt"}
BACKEND_DIR = Path(__file__).resolve().parents[4]
SIMPLE_UPLOAD_ROOT = BACKEND_DIR / "uploads" / "simple"


def _simple_upload_enabled() -> bool:
    return os.getenv(ENABLE_SIMPLE_FILE_UPLOAD_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _normalize_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _sanitize_filename(filename: str | None) -> str:
    raw_name = (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._")
    if not safe_name:
        safe_name = "upload"

    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file extension",
        )
    return safe_name


async def _read_limited_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(READ_CHUNK_BYTES)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > MAX_SIMPLE_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file is too large",
            )
        chunks.append(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    return b"".join(chunks)


def _build_target_path(safe_filename: str, file_hash: str) -> tuple[Path, str]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    storage_name = f"{timestamp}_{file_hash[:16]}_{safe_filename}"
    root = SIMPLE_UPLOAD_ROOT.resolve()
    target_path = (root / storage_name).resolve()

    if root != target_path.parent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload filename",
        )

    return target_path, storage_name


@router.post("/upload-simple", response_model=dict[str, Any])
async def upload_file_simple(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restricted legacy upload path for explicit dev/test use only."""
    if not _simple_upload_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simple upload endpoint is disabled",
        )

    del db

    try:
        content_type = _normalize_content_type(file.content_type)
        if content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(
                "Simple upload rejected by content type",
                extra={
                    "content_type": content_type or None,
                    "user_id": getattr(current_user, "id", None),
                    "has_title": bool(title),
                    "classification": "non_retryable_validation_error",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported file type",
            )

        safe_filename = _sanitize_filename(file.filename)
        content = await _read_limited_upload(file)
        file_hash = hashlib.sha256(content).hexdigest()
        target_path, storage_name = _build_target_path(safe_filename, file_hash)

        SIMPLE_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as uploaded_file:
            uploaded_file.write(content)

        logger.info(
            "Simple upload stored",
            extra={
                "content_type": content_type,
                "file_size": len(content),
                "storage_name": storage_name,
                "user_id": getattr(current_user, "id", None),
                "has_title": bool(title),
                "classification": "accepted",
            },
        )

        return {
            "success": True,
            "message": "File uploaded successfully",
            "filename": storage_name,
            "content_type": content_type,
            "file_size": len(content),
            "file_hash": file_hash,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Simple upload failed",
            extra={
                "user_id": getattr(current_user, "id", None),
                "has_title": bool(title),
                "classification": "retryable_endpoint_error",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed",
        ) from exc
