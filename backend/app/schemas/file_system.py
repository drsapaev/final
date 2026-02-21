"""
Схемы для файловой системы
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    permission: FilePermissionEnum = FilePermissionEnum.PRIVATE
    patient_id: int | None = None
    appointment_id: int | None = None
    emr_id: int | None = None
    expires_at: datetime | None = None


class FileCreate(FileBase):
    file_path: str = Field(..., max_length=500)  # ✅ CERTIFICATION: Обязательное поле для file_path
    file_size: int = Field(..., gt=0)
    file_hash: str | None = Field(None, max_length=64)
    file_metadata: dict[str, Any] | None = None


class FileUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    permission: FilePermissionEnum | None = None
    expires_at: datetime | None = None
    file_metadata: dict[str, Any] | None = None


class FileOut(FileBase):
    id: int
    file_path: str
    file_size: int
    file_hash: str | None
    status: FileStatusEnum
    metadata: dict[str, Any] | None = None
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Кастомная сериализация для преобразования JSON строк в Python объекты"""
        import json
        data = {
            "id": obj.id,
            "filename": obj.filename,
            "original_filename": obj.original_filename,
            "file_type": obj.file_type.value if hasattr(obj.file_type, 'value') else obj.file_type,
            "mime_type": obj.mime_type,
            "title": obj.title,
            "description": obj.description,
            "permission": obj.permission.value if hasattr(obj.permission, 'value') else obj.permission,
            "patient_id": obj.patient_id,
            "appointment_id": obj.appointment_id,
            "emr_id": obj.emr_id,
            "expires_at": obj.expires_at,
            "file_path": obj.file_path,
            "file_size": obj.file_size,
            "file_hash": obj.file_hash,
            "status": obj.status.value if hasattr(obj.status, 'value') else obj.status,
            "owner_id": obj.owner_id,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }

        # Преобразуем tags из JSON строки в список
        if obj.tags:
            try:
                data["tags"] = json.loads(obj.tags) if isinstance(obj.tags, str) else obj.tags
            except (json.JSONDecodeError, TypeError):
                data["tags"] = []
        else:
            data["tags"] = None

        # Преобразуем file_metadata из JSON строки в словарь (и переименовываем в metadata)
        if obj.file_metadata:
            try:
                data["metadata"] = json.loads(obj.file_metadata) if isinstance(obj.file_metadata, str) else obj.file_metadata
            except (json.JSONDecodeError, TypeError):
                data["metadata"] = {}
        else:
            data["metadata"] = None

        return cls(**data)


class FileList(BaseModel):
    files: list[FileOut]
    total: int
    page: int
    size: int
    pages: int


# ===================== ВЕРСИИ ФАЙЛОВ =====================


class FileVersionBase(BaseModel):
    version_number: int = Field(..., gt=0)
    change_description: str | None = None


class FileVersionCreate(FileVersionBase):
    file_path: str
    file_size: int = Field(..., gt=0)
    file_hash: str | None = Field(None, max_length=64)


class FileVersionOut(FileVersionBase):
    id: int
    file_id: int
    file_path: str
    file_size: int
    file_hash: str | None
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===================== СОВМЕСТНОЕ ИСПОЛЬЗОВАНИЕ =====================


class FileShareBase(BaseModel):
    shared_with_user_id: int | None = None
    shared_with_email: str | None = Field(None, max_length=255)
    permission: FilePermissionEnum
    expires_at: datetime | None = None


class FileShareCreate(FileShareBase):
    pass


class FileShareUpdate(BaseModel):
    permission: FilePermissionEnum | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class FileShareOut(FileShareBase):
    id: int
    file_id: int
    access_token: str | None
    is_active: bool
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# ===================== ПАПКИ =====================


class FileFolderBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    parent_id: int | None = None


class FileFolderCreate(FileFolderBase):
    pass


class FileFolderUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    parent_id: int | None = None


class FileFolderOut(FileFolderBase):
    id: int
    owner_id: int
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileFolderTree(FileFolderOut):
    children: list['FileFolderTree'] = []
    files: list[FileOut] = []


# ===================== ЗАГРУЗКА ФАЙЛОВ =====================


class FileUploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    file_type: FileTypeEnum
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    permission: FilePermissionEnum = FilePermissionEnum.PRIVATE
    patient_id: int | None = None
    appointment_id: int | None = None
    emr_id: int | None = None
    folder_id: int | None = None
    expires_at: datetime | None = None
    file_metadata: dict[str, Any] | None = None


class FileUploadResponse(BaseModel):
    upload_id: str
    upload_url: str
    expires_at: datetime
    max_file_size: int
    allowed_types: list[str]


class FileUploadComplete(BaseModel):
    upload_id: str
    file_hash: str
    file_size: int


# ===================== ПОИСК И ФИЛЬТРАЦИЯ =====================


class FileSearchRequest(BaseModel):
    query: str | None = None
    file_type: FileTypeEnum | None = None
    permission: FilePermissionEnum | None = None
    patient_id: int | None = None
    appointment_id: int | None = None
    emr_id: int | None = None
    folder_id: int | None = None
    tags: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    size_min: int | None = None
    size_max: int | None = None
    owner_id: int | None = None
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class FileSearchResponse(BaseModel):
    files: list[FileOut]
    total: int
    page: int
    size: int
    pages: int
    facets: dict[str, Any] = {}


# ===================== КВОТЫ =====================


class FileQuotaBase(BaseModel):
    max_storage_bytes: int = Field(..., gt=0)
    max_files: int | None = Field(None, gt=0)


class FileQuotaCreate(FileQuotaBase):
    user_id: int


class FileQuotaUpdate(BaseModel):
    max_storage_bytes: int | None = Field(None, gt=0)
    max_files: int | None = Field(None, gt=0)


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
    config: dict[str, Any]
    max_file_size: int | None = None
    allowed_types: list[str] | None = None


class FileStorageCreate(FileStorageBase):
    is_default: bool = False


class FileStorageUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    config: dict[str, Any] | None = None
    max_file_size: int | None = None
    allowed_types: list[str] | None = None
    is_active: bool | None = None


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
    files_by_type: dict[str, int]
    files_by_permission: dict[str, int]
    recent_uploads: list[FileOut]
    storage_usage: dict[str, Any]


# ===================== ЭКСПОРТ/ИМПОРТ =====================


class FileExportRequest(BaseModel):
    file_ids: list[int]
    format: str = Field(..., pattern="^(zip|tar|tar.gz)$")
    include_metadata: bool = True
    include_versions: bool = False


class FileExportResponse(BaseModel):
    export_id: str
    download_url: str
    expires_at: datetime
    file_size: int | None = None


class FileImportRequest(BaseModel):
    import_data: bytes
    format: str = Field(..., pattern="^(zip|tar|tar.gz)$")
    target_folder_id: int | None = None
    overwrite_existing: bool = False


class FileImportResponse(BaseModel):
    import_id: str
    processed_files: int
    errors: list[str] = []
    success: bool


# ===================== ОБНОВЛЕНИЕ РЕКУРСИВНЫХ ССЫЛОК =====================

# Обновляем рекурсивные ссылки
FileFolderTree.model_rebuild()
