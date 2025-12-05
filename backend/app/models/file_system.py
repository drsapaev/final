"""
Модели для файловой системы
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


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

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # Размер в байтах
    file_type = Column(Enum(FileType), nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256 хеш
    status = Column(
        Enum(FileStatus), default=FileStatus.UPLOADING, nullable=False, index=True
    )
    permission = Column(
        Enum(FilePermission), default=FilePermission.PRIVATE, nullable=False
    )

    # Метаданные
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON массив тегов
    file_metadata = Column(Text, nullable=True)  # JSON с дополнительными данными

    # Связи с другими сущностями
    owner_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False, 
        index=True
    )  # ✅ FIX: Files must always have an owner for access control and audit (domain requirement)
    patient_id = Column(
        Integer, 
        ForeignKey("patients.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve medical files
    appointment_id = Column(
        Integer, 
        ForeignKey("appointments.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve files
    emr_id = Column(
        Integer, 
        ForeignKey("emr.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve files
    folder_id = Column(
        Integer, 
        ForeignKey("file_folders.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to allow orphaned folders

    # Временные метки
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    owner = relationship("User", foreign_keys=[owner_id])
    patient = relationship("Patient", foreign_keys=[patient_id])
    appointment = relationship("Appointment", foreign_keys=[appointment_id])
    emr = relationship("EMR", foreign_keys=[emr_id])
    folder = relationship("FileFolder", foreign_keys=[folder_id])
    versions = relationship(
        "FileVersion", back_populates="file", cascade="all, delete-orphan"
    )
    shares = relationship(
        "FileShare", back_populates="file", cascade="all, delete-orphan"
    )


class FileVersion(Base):
    """Версии файлов"""

    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(
        Integer, 
        ForeignKey("files.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )  # ✅ SECURITY: CASCADE (versions die with file)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=True)
    change_description = Column(Text, nullable=True)
    created_by = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Связи
    file = relationship("File", back_populates="versions")
    creator = relationship("User", foreign_keys=[created_by])


class FileShare(Base):
    """Совместное использование файлов"""

    __tablename__ = "file_shares"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(
        Integer, 
        ForeignKey("files.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )  # ✅ SECURITY: CASCADE (shares die with file)
    shared_with_user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve share record
    shared_with_email = Column(String(255), nullable=True, index=True)
    permission = Column(Enum(FilePermission), nullable=False)
    access_token = Column(String(64), nullable=True, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Связи
    file = relationship("File", back_populates="shares")
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    creator = relationship("User", foreign_keys=[created_by])


class FileFolder(Base):
    """Папки для организации файлов"""

    __tablename__ = "file_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(
        Integer, 
        ForeignKey("file_folders.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to allow orphaned folders
    owner_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve folders if user deleted
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Связи
    owner = relationship("User", foreign_keys=[owner_id])
    parent = relationship("FileFolder", remote_side=[id])
    children = relationship("FileFolder", back_populates="parent")
    files = relationship("File", foreign_keys="File.folder_id", back_populates="folder")


class FileAccessLog(Base):
    """Лог доступа к файлам"""

    __tablename__ = "file_access_logs"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(
        Integer, 
        ForeignKey("files.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve audit log
    user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve audit log
    action = Column(String(50), nullable=False)  # view, download, edit, delete, share
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Связи
    file = relationship("File")
    user = relationship("User")


class FileStorage(Base):
    """Настройки хранилища файлов"""

    __tablename__ = "file_storage"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    storage_type = Column(String(50), nullable=False)  # local, s3, azure, gcp
    config = Column(Text, nullable=False)  # JSON конфигурация
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    max_file_size = Column(Integer, nullable=True)  # Максимальный размер файла в байтах
    allowed_types = Column(Text, nullable=True)  # JSON массив разрешенных типов
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FileQuota(Base):
    """Квоты пользователей на файлы"""

    __tablename__ = "file_quotas"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    max_storage_bytes = Column(Integer, nullable=False)  # Максимальный размер хранилища
    used_storage_bytes = Column(
        Integer, default=0, nullable=False
    )  # Используемый размер
    max_files = Column(Integer, nullable=True)  # Максимальное количество файлов
    used_files = Column(
        Integer, default=0, nullable=False
    )  # Используемое количество файлов
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Связи
    user = relationship("User")
