"""
Схемы для файловой системы
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from app.models.file_system import FilePermission, FileStatus, FileType


class FileTypeEnum(str, Enum):
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    ARCHIVE = "archive"
    MEDICAL_RECORD = "medical_record"
    LAB_RESULT = "lab_result"
    XRAY = "xray"
    PRESCRIPTION = "prescription"
    REPORT = "report"
    BACKUP = "backup"
    OTHER = "other"


class FileStatusEnum(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    DELETED = "deleted"
    ARCHIVED = "archived"


class FilePermissionEnum(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


# ===================== ФАЙЛЫ =====================


class FileBase(BaseModel):
    filename: str = Field(..., max_length=255)
    original_filename: str = Field(..., max_length=255)
    file_type: FileTypeEnum
    mime_type: str = Field(..., max_length=100)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    permission: FilePermissionEnum = FilePermissionEnum.PRIVATE
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    emr_id: Optional[int] = None
    expires_at: Optional[datetime] = None


class FileCreate(FileBase):
    file_size: int = Field(..., gt=0)
    file_hash: Optional[str] = Field(None, max_length=64)
    file_metadata: Optional[Dict[str, Any]] = None


class FileUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    permission: Optional[FilePermissionEnum] = None
    expires_at: Optional[datetime] = None
    file_metadata: Optional[Dict[str, Any]] = None


class FileOut(FileBase):
    id: int
    file_path: str
    file_size: int
    file_hash: Optional[str]
    status: FileStatusEnum
    metadata: Optional[Dict[str, Any]]
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileList(BaseModel):
    files: List[FileOut]
    total: int
    page: int
    size: int
    pages: int


# ===================== ВЕРСИИ ФАЙЛОВ =====================


class FileVersionBase(BaseModel):
    version_number: int = Field(..., gt=0)
    change_description: Optional[str] = None


class FileVersionCreate(FileVersionBase):
    file_path: str
    file_size: int = Field(..., gt=0)
    file_hash: Optional[str] = Field(None, max_length=64)


class FileVersionOut(FileVersionBase):
    id: int
    file_id: int
    file_path: str
    file_size: int
    file_hash: Optional[str]
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===================== СОВМЕСТНОЕ ИСПОЛЬЗОВАНИЕ =====================


class FileShareBase(BaseModel):
    shared_with_user_id: Optional[int] = None
    shared_with_email: Optional[str] = Field(None, max_length=255)
    permission: FilePermissionEnum
    expires_at: Optional[datetime] = None


class FileShareCreate(FileShareBase):
    pass


class FileShareUpdate(BaseModel):
    permission: Optional[FilePermissionEnum] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class FileShareOut(FileShareBase):
    id: int
    file_id: int
    access_token: Optional[str]
    is_active: bool
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===================== ПАПКИ =====================


class FileFolderBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None


class FileFolderCreate(FileFolderBase):
    pass


class FileFolderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None


class FileFolderOut(FileFolderBase):
    id: int
    owner_id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileFolderTree(FileFolderOut):
    children: List['FileFolderTree'] = []
    files: List[FileOut] = []


# ===================== ЗАГРУЗКА ФАЙЛОВ =====================


class FileUploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    file_type: FileTypeEnum
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    permission: FilePermissionEnum = FilePermissionEnum.PRIVATE
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    emr_id: Optional[int] = None
    folder_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    file_metadata: Optional[Dict[str, Any]] = None


class FileUploadResponse(BaseModel):
    upload_id: str
    upload_url: str
    expires_at: datetime
    max_file_size: int
    allowed_types: List[str]


class FileUploadComplete(BaseModel):
    upload_id: str
    file_hash: str
    file_size: int


# ===================== ПОИСК И ФИЛЬТРАЦИЯ =====================


class FileSearchRequest(BaseModel):
    query: Optional[str] = None
    file_type: Optional[FileTypeEnum] = None
    permission: Optional[FilePermissionEnum] = None
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    emr_id: Optional[int] = None
    folder_id: Optional[int] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    size_min: Optional[int] = None
    size_max: Optional[int] = None
    owner_id: Optional[int] = None
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class FileSearchResponse(BaseModel):
    files: List[FileOut]
    total: int
    page: int
    size: int
    pages: int
    facets: Dict[str, Any] = {}


# ===================== КВОТЫ =====================


class FileQuotaBase(BaseModel):
    max_storage_bytes: int = Field(..., gt=0)
    max_files: Optional[int] = Field(None, gt=0)


class FileQuotaCreate(FileQuotaBase):
    user_id: int


class FileQuotaUpdate(BaseModel):
    max_storage_bytes: Optional[int] = Field(None, gt=0)
    max_files: Optional[int] = Field(None, gt=0)


class FileQuotaOut(FileQuotaBase):
    id: int
    user_id: int
    used_storage_bytes: int
    used_files: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===================== ХРАНИЛИЩЕ =====================


class FileStorageBase(BaseModel):
    name: str = Field(..., max_length=100)
    storage_type: str = Field(..., max_length=50)
    config: Dict[str, Any]
    max_file_size: Optional[int] = None
    allowed_types: Optional[List[str]] = None


class FileStorageCreate(FileStorageBase):
    is_default: bool = False


class FileStorageUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    config: Optional[Dict[str, Any]] = None
    max_file_size: Optional[int] = None
    allowed_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


class FileStorageOut(FileStorageBase):
    id: int
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===================== СТАТИСТИКА =====================


class FileStats(BaseModel):
    total_files: int
    total_size: int
    files_by_type: Dict[str, int]
    files_by_permission: Dict[str, int]
    recent_uploads: List[FileOut]
    storage_usage: Dict[str, Any]


# ===================== ЭКСПОРТ/ИМПОРТ =====================


class FileExportRequest(BaseModel):
    file_ids: List[int]
    format: str = Field(..., pattern="^(zip|tar|tar.gz)$")
    include_metadata: bool = True
    include_versions: bool = False


class FileExportResponse(BaseModel):
    export_id: str
    download_url: str
    expires_at: datetime
    file_size: Optional[int] = None


class FileImportRequest(BaseModel):
    import_data: bytes
    format: str = Field(..., pattern="^(zip|tar|tar.gz)$")
    target_folder_id: Optional[int] = None
    overwrite_existing: bool = False


class FileImportResponse(BaseModel):
    import_id: str
    processed_files: int
    errors: List[str] = []
    success: bool


# ===================== ВАЛИДАТОРЫ =====================


@validator('tags')
def validate_tags(cls, v):
    if v is not None:
        if len(v) > 20:
            raise ValueError('Максимум 20 тегов')
        for tag in v:
            if len(tag) > 50:
                raise ValueError('Тег не может быть длиннее 50 символов')
    return v


@validator('shared_with_email')
def validate_email(cls, v):
    if v is not None:
        import re

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Неверный формат email')
    return v


# Обновляем рекурсивные ссылки
FileFolderTree.model_rebuild()
