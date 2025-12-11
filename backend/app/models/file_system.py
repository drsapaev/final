"""
Модели для файловой системы
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient
    from app.models.appointment import Appointment
    from app.models.emr import EMR


class FileType(str, enum.Enum):
    """Типы файлов"""

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


class FileStatus(str, enum.Enum):
    """Статусы файлов"""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    DELETED = "deleted"
    ARCHIVED = "archived"


class FilePermission(str, enum.Enum):
    """Права доступа к файлам"""

    PUBLIC = "public"
    PRIVATE = "private"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class File(Base):
    """Модель файла"""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # Размер в байтах
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # SHA-256 хеш
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus), default=FileStatus.UPLOADING, nullable=False, index=True
    )
    permission: Mapped[FilePermission] = mapped_column(
        Enum(FilePermission), default=FilePermission.PRIVATE, nullable=False
    )

    # Метаданные
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON массив тегов
    file_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON с дополнительными данными

    # Связи с другими сущностями
    owner_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False, 
        index=True
    )  # ✅ FIX: Files must always have an owner for access control and audit
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("patients.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve medical files
    appointment_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("appointments.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve files
    emr_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("emr.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve files
    folder_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("file_folders.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to allow orphaned folders

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    patient: Mapped[Optional["Patient"]] = relationship("Patient", foreign_keys=[patient_id])
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", foreign_keys=[appointment_id])
    emr: Mapped[Optional["EMR"]] = relationship("EMR", foreign_keys=[emr_id])
    folder: Mapped[Optional["FileFolder"]] = relationship("FileFolder", foreign_keys=[folder_id])
    versions: Mapped[List["FileVersion"]] = relationship(
        "FileVersion", back_populates="file", cascade="all, delete-orphan"
    )
    shares: Mapped[List["FileShare"]] = relationship(
        "FileShare", back_populates="file", cascade="all, delete-orphan"
    )


class FileVersion(Base):
    """Версии файлов"""

    __tablename__ = "file_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("files.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )  # ✅ SECURITY: CASCADE (versions die with file)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    change_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Связи
    file: Mapped["File"] = relationship("File", back_populates="versions")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class FileShare(Base):
    """Совместное использование файлов"""

    __tablename__ = "file_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("files.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )  # ✅ SECURITY: CASCADE (shares die with file)
    shared_with_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve share record
    shared_with_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    permission: Mapped[FilePermission] = mapped_column(Enum(FilePermission), nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Связи
    file: Mapped["File"] = relationship("File", back_populates="shares")
    shared_with_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[shared_with_user_id])
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class FileFolder(Base):
    """Папки для организации файлов"""

    __tablename__ = "file_folders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("file_folders.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to allow orphaned folders
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve folders if user deleted
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Связи
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    parent: Mapped[Optional["FileFolder"]] = relationship("FileFolder", remote_side=[id])
    children: Mapped[List["FileFolder"]] = relationship("FileFolder", back_populates="parent")
    files: Mapped[List["File"]] = relationship("File", foreign_keys="File.folder_id", back_populates="folder")


class FileAccessLog(Base):
    """Лог доступа к файлам"""

    __tablename__ = "file_access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("files.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve audit log
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve audit log
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # view, download, edit, delete, share
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Связи
    file: Mapped[Optional["File"]] = relationship("File")
    user: Mapped[Optional["User"]] = relationship("User")


class FileStorage(Base):
    """Настройки хранилища файлов"""

    __tablename__ = "file_storage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    storage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # local, s3, azure, gcp
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON конфигурация
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Максимальный размер файла в байтах
    allowed_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON массив разрешенных типов
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FileQuota(Base):
    """Квоты пользователей на файлы"""

    __tablename__ = "file_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    max_storage_bytes: Mapped[int] = mapped_column(Integer, nullable=False)  # Максимальный размер хранилища
    used_storage_bytes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # Используемый размер
    max_files: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Максимальное количество файлов
    used_files: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # Используемое количество файлов
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Связи
    user: Mapped["User"] = relationship("User")
