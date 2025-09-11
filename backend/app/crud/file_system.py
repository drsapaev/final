"""
CRUD операции для файловой системы
"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, timedelta
import hashlib
import os
import json

from app.models.file_system import (
    File, FileVersion, FileShare, FileFolder, FileAccessLog, 
    FileStorage, FileQuota, FileType, FileStatus, FilePermission
)
from app.schemas.file_system import (
    FileCreate, FileUpdate, FileSearchRequest,
    FileShareCreate, FileShareUpdate,
    FileFolderCreate, FileFolderUpdate,
    FileQuotaCreate, FileQuotaUpdate,
    FileStorageCreate, FileStorageUpdate
)


# ===================== ФАЙЛЫ =====================

class CRUDFile:
    """CRUD операции для файлов"""
    
    def __init__(self):
        self.model = File
    
    def create(self, db: Session, *, obj_in: FileCreate, owner_id: int) -> File:
        """Создать файл"""
        # Преобразуем tags в JSON строку если это список
        file_data = obj_in.dict()
        if 'tags' in file_data and isinstance(file_data['tags'], list):
            file_data['tags'] = json.dumps(file_data['tags'])
        
        db_obj = File(
            **file_data,
            owner_id=owner_id,
            status=FileStatus.UPLOADING
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get(self, db: Session, *, id: int) -> Optional[File]:
        """Получить файл по ID"""
        return db.query(File).filter(File.id == id).first()
    
    def get_by_hash(self, db: Session, *, file_hash: str) -> Optional[File]:
        """Получить файл по хешу"""
        return db.query(File).filter(File.file_hash == file_hash).first()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        file_type: Optional[FileType] = None,
        status: Optional[FileStatus] = None,
        owner_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        emr_id: Optional[int] = None,
        folder_id: Optional[int] = None
    ) -> List[File]:
        """Получить список файлов с фильтрацией"""
        query = db.query(File)
        
        if file_type:
            query = query.filter(File.file_type == file_type)
        if status:
            query = query.filter(File.status == status)
        if owner_id:
            query = query.filter(File.owner_id == owner_id)
        if patient_id:
            query = query.filter(File.patient_id == patient_id)
        if appointment_id:
            query = query.filter(File.appointment_id == appointment_id)
        if emr_id:
            query = query.filter(File.emr_id == emr_id)
        if folder_id:
            query = query.filter(File.folder_id == folder_id)
        
        return query.order_by(desc(File.created_at)).offset(skip).limit(limit).all()
    
    def search(
        self, 
        db: Session, 
        *, 
        search_request: FileSearchRequest
    ) -> Tuple[List[File], int, Dict[str, Any]]:
        """Поиск файлов с фильтрацией"""
        query = db.query(File)
        
        # Текстовый поиск
        if search_request.query:
            search_term = f"%{search_request.query}%"
            query = query.filter(
                or_(
                    File.filename.ilike(search_term),
                    File.original_filename.ilike(search_term),
                    File.title.ilike(search_term),
                    File.description.ilike(search_term)
                )
            )
        
        # Фильтры
        if search_request.file_type:
            query = query.filter(File.file_type == search_request.file_type)
        if search_request.permission:
            query = query.filter(File.permission == search_request.permission)
        if search_request.patient_id:
            query = query.filter(File.patient_id == search_request.patient_id)
        if search_request.appointment_id:
            query = query.filter(File.appointment_id == search_request.appointment_id)
        if search_request.emr_id:
            query = query.filter(File.emr_id == search_request.emr_id)
        if search_request.folder_id:
            query = query.filter(File.folder_id == search_request.folder_id)
        if search_request.owner_id:
            query = query.filter(File.owner_id == search_request.owner_id)
        
        # Фильтр по дате
        if search_request.date_from:
            query = query.filter(File.created_at >= search_request.date_from)
        if search_request.date_to:
            query = query.filter(File.created_at <= search_request.date_to)
        
        # Фильтр по размеру
        if search_request.size_min:
            query = query.filter(File.file_size >= search_request.size_min)
        if search_request.size_max:
            query = query.filter(File.file_size <= search_request.size_max)
        
        # Фильтр по тегам
        if search_request.tags:
            for tag in search_request.tags:
                query = query.filter(File.tags.contains(tag))
        
        # Подсчет общего количества
        total = query.count()
        
        # Пагинация
        files = query.order_by(desc(File.created_at)).offset(
            (search_request.page - 1) * search_request.size
        ).limit(search_request.size).all()
        
        # Фасеты для фильтрации
        facets = {
            "file_types": db.query(File.file_type, func.count(File.id)).group_by(File.file_type).all(),
            "permissions": db.query(File.permission, func.count(File.id)).group_by(File.permission).all(),
            "size_ranges": self._get_size_ranges(db, query)
        }
        
        return files, total, facets
    
    def _get_size_ranges(self, db: Session, query) -> List[Dict[str, Any]]:
        """Получить диапазоны размеров файлов"""
        ranges = [
            {"label": "0-1MB", "min": 0, "max": 1024*1024},
            {"label": "1-10MB", "min": 1024*1024, "max": 10*1024*1024},
            {"label": "10-100MB", "min": 10*1024*1024, "max": 100*1024*1024},
            {"label": "100MB+", "min": 100*1024*1024, "max": None}
        ]
        
        result = []
        for range_def in ranges:
            count_query = query
            if range_def["min"] is not None:
                count_query = count_query.filter(File.file_size >= range_def["min"])
            if range_def["max"] is not None:
                count_query = count_query.filter(File.file_size < range_def["max"])
            
            count = count_query.count()
            if count > 0:
                result.append({
                    "label": range_def["label"],
                    "count": count
                })
        
        return result
    
    def update(self, db: Session, *, db_obj: File, obj_in: FileUpdate) -> File:
        """Обновить файл"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: int) -> Optional[File]:
        """Удалить файл"""
        obj = db.query(File).filter(File.id == id).first()
        if obj:
            # Мягкое удаление - меняем статус
            obj.status = FileStatus.DELETED
            db.add(obj)
            db.commit()
            db.refresh(obj)
        return obj
    
    def hard_delete(self, db: Session, *, id: int) -> bool:
        """Жесткое удаление файла"""
        obj = db.query(File).filter(File.id == id).first()
        if obj:
            # Удаляем физический файл
            if obj.file_path and os.path.exists(obj.file_path):
                try:
                    os.remove(obj.file_path)
                except OSError:
                    pass  # Игнорируем ошибки удаления файла
            
            # Удаляем из БД
            db.delete(obj)
            db.commit()
            return True
        return False
    
    def get_user_files(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100) -> List[File]:
        """Получить файлы пользователя"""
        return self.get_multi(
            db=db, 
            skip=skip, 
            limit=limit, 
            owner_id=user_id,
            status=FileStatus.READY
        )
    
    def get_patient_files(self, db: Session, *, patient_id: int, skip: int = 0, limit: int = 100) -> List[File]:
        """Получить файлы пациента"""
        return self.get_multi(
            db=db, 
            skip=skip, 
            limit=limit, 
            patient_id=patient_id,
            status=FileStatus.READY
        )
    
    def get_expired_files(self, db: Session) -> List[File]:
        """Получить истекшие файлы"""
        return db.query(File).filter(
            File.expires_at < datetime.utcnow(),
            File.status != FileStatus.DELETED
        ).all()
    
    def cleanup_expired_files(self, db: Session) -> int:
        """Очистить истекшие файлы"""
        expired_files = self.get_expired_files(db)
        count = 0
        
        for file_obj in expired_files:
            # Удаляем физический файл
            if file_obj.file_path and os.path.exists(file_obj.file_path):
                try:
                    os.remove(file_obj.file_path)
                except OSError:
                    pass
            
            # Мягкое удаление
            file_obj.status = FileStatus.DELETED
            db.add(file_obj)
            count += 1
        
        db.commit()
        return count


# ===================== ВЕРСИИ ФАЙЛОВ =====================

class CRUDFileVersion:
    """CRUD операции для версий файлов"""
    
    def create(self, db: Session, *, file_id: int, version_data: dict, created_by: int) -> FileVersion:
        """Создать версию файла"""
        # Получаем следующий номер версии
        last_version = db.query(FileVersion).filter(
            FileVersion.file_id == file_id
        ).order_by(desc(FileVersion.version_number)).first()
        
        version_number = (last_version.version_number + 1) if last_version else 1
        
        db_obj = FileVersion(
            file_id=file_id,
            version_number=version_number,
            created_by=created_by,
            **version_data
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_file_versions(self, db: Session, *, file_id: int) -> List[FileVersion]:
        """Получить версии файла"""
        return db.query(FileVersion).filter(
            FileVersion.file_id == file_id
        ).order_by(desc(FileVersion.version_number)).all()
    
    def get_version(self, db: Session, *, file_id: int, version_number: int) -> Optional[FileVersion]:
        """Получить конкретную версию файла"""
        return db.query(FileVersion).filter(
            FileVersion.file_id == file_id,
            FileVersion.version_number == version_number
        ).first()


# ===================== СОВМЕСТНОЕ ИСПОЛЬЗОВАНИЕ =====================

class CRUDFileShare:
    """CRUD операции для совместного использования файлов"""
    
    def create(self, db: Session, *, file_id: int, share_data: FileShareCreate, created_by: int) -> FileShare:
        """Создать совместное использование файла"""
        import secrets
        
        db_obj = FileShare(
            file_id=file_id,
            created_by=created_by,
            access_token=secrets.token_urlsafe(32),
            **share_data.dict()
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_file_shares(self, db: Session, *, file_id: int) -> List[FileShare]:
        """Получить совместные использования файла"""
        return db.query(FileShare).filter(
            FileShare.file_id == file_id,
            FileShare.is_active == True
        ).all()
    
    def get_user_shares(self, db: Session, *, user_id: int) -> List[FileShare]:
        """Получить файлы, доступные пользователю"""
        return db.query(FileShare).filter(
            or_(
                FileShare.shared_with_user_id == user_id,
                FileShare.created_by == user_id
            ),
            FileShare.is_active == True
        ).all()
    
    def get_by_token(self, db: Session, *, access_token: str) -> Optional[FileShare]:
        """Получить совместное использование по токену"""
        return db.query(FileShare).filter(
            FileShare.access_token == access_token,
            FileShare.is_active == True,
            or_(
                FileShare.expires_at.is_(None),
                FileShare.expires_at > datetime.utcnow()
            )
        ).first()
    
    def update(self, db: Session, *, db_obj: FileShare, obj_in: FileShareUpdate) -> FileShare:
        """Обновить совместное использование"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def revoke(self, db: Session, *, share_id: int) -> bool:
        """Отозвать совместное использование"""
        obj = db.query(FileShare).filter(FileShare.id == share_id).first()
        if obj:
            obj.is_active = False
            db.add(obj)
            db.commit()
            return True
        return False


# ===================== ПАПКИ =====================

class CRUDFileFolder:
    """CRUD операции для папок"""
    
    def create(self, db: Session, *, folder_data: FileFolderCreate, owner_id: int) -> FileFolder:
        """Создать папку"""
        db_obj = FileFolder(
            **folder_data.dict(),
            owner_id=owner_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get(self, db: Session, *, id: int) -> Optional[FileFolder]:
        """Получить папку по ID"""
        return db.query(FileFolder).filter(FileFolder.id == id).first()
    
    def get_user_folders(self, db: Session, *, user_id: int, parent_id: Optional[int] = None) -> List[FileFolder]:
        """Получить папки пользователя"""
        query = db.query(FileFolder).filter(FileFolder.owner_id == user_id)
        if parent_id is not None:
            query = query.filter(FileFolder.parent_id == parent_id)
        return query.order_by(FileFolder.name).all()
    
    def get_folder_tree(self, db: Session, *, user_id: int, parent_id: Optional[int] = None) -> List[FileFolder]:
        """Получить дерево папок"""
        folders = self.get_user_folders(db, user_id=user_id, parent_id=parent_id)
        result = []
        
        for folder in folders:
            folder_dict = {
                "id": folder.id,
                "name": folder.name,
                "description": folder.description,
                "parent_id": folder.parent_id,
                "owner_id": folder.owner_id,
                "is_system": folder.is_system,
                "created_at": folder.created_at,
                "updated_at": folder.updated_at,
                "children": self.get_folder_tree(db, user_id=user_id, parent_id=folder.id)
            }
            result.append(folder_dict)
        
        return result
    
    def update(self, db: Session, *, db_obj: FileFolder, obj_in: FileFolderUpdate) -> FileFolder:
        """Обновить папку"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: int) -> bool:
        """Удалить папку"""
        obj = db.query(FileFolder).filter(FileFolder.id == id).first()
        if obj and not obj.is_system:
            # Проверяем, есть ли файлы в папке
            files_count = db.query(File).filter(File.folder_id == id).count()
            if files_count > 0:
                return False  # Нельзя удалить папку с файлами
            
            # Проверяем, есть ли подпапки
            children_count = db.query(FileFolder).filter(FileFolder.parent_id == id).count()
            if children_count > 0:
                return False  # Нельзя удалить папку с подпапками
            
            db.delete(obj)
            db.commit()
            return True
        return False


# ===================== КВОТЫ =====================

class CRUDFileQuota:
    """CRUD операции для квот файлов"""
    
    def create(self, db: Session, *, quota_data: FileQuotaCreate) -> FileQuota:
        """Создать квоту пользователя"""
        db_obj = FileQuota(**quota_data.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_user_quota(self, db: Session, *, user_id: int) -> Optional[FileQuota]:
        """Получить квоту пользователя"""
        return db.query(FileQuota).filter(FileQuota.user_id == user_id).first()
    
    def update_usage(self, db: Session, *, user_id: int, size_delta: int, files_delta: int) -> bool:
        """Обновить использование квоты"""
        quota = self.get_user_quota(db, user_id=user_id)
        if quota:
            quota.used_storage_bytes += size_delta
            quota.used_files += files_delta
            db.add(quota)
            db.commit()
            return True
        return False
    
    def check_quota(self, db: Session, *, user_id: int, additional_size: int = 0, additional_files: int = 0) -> Tuple[bool, str]:
        """Проверить квоту пользователя"""
        quota = self.get_user_quota(db, user_id=user_id)
        if not quota:
            return True, "Квота не установлена"
        
        # Проверяем размер
        if quota.max_storage_bytes and (quota.used_storage_bytes + additional_size) > quota.max_storage_bytes:
            return False, f"Превышена квота по размеру: {quota.used_storage_bytes + additional_size} / {quota.max_storage_bytes} байт"
        
        # Проверяем количество файлов
        if quota.max_files and (quota.used_files + additional_files) > quota.max_files:
            return False, f"Превышена квота по количеству файлов: {quota.used_files + additional_files} / {quota.max_files}"
        
        return True, "Квота в пределах нормы"


# ===================== ХРАНИЛИЩЕ =====================

class CRUDFileStorage:
    """CRUD операции для хранилища файлов"""
    
    def create(self, db: Session, *, storage_data: FileStorageCreate) -> FileStorage:
        """Создать хранилище"""
        db_obj = FileStorage(**storage_data.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_default(self, db: Session) -> Optional[FileStorage]:
        """Получить хранилище по умолчанию"""
        return db.query(FileStorage).filter(
            FileStorage.is_default == True,
            FileStorage.is_active == True
        ).first()
    
    def get_active(self, db: Session) -> List[FileStorage]:
        """Получить активные хранилища"""
        return db.query(FileStorage).filter(FileStorage.is_active == True).all()


# ===================== ЛОГИ ДОСТУПА =====================

class CRUDFileAccessLog:
    """CRUD операции для логов доступа к файлам"""
    
    def create(self, db: Session, *, file_id: int, user_id: Optional[int], action: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> FileAccessLog:
        """Создать лог доступа"""
        db_obj = FileAccessLog(
            file_id=file_id,
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_file_logs(self, db: Session, *, file_id: int, skip: int = 0, limit: int = 100) -> List[FileAccessLog]:
        """Получить логи доступа к файлу"""
        return db.query(FileAccessLog).filter(
            FileAccessLog.file_id == file_id
        ).order_by(desc(FileAccessLog.created_at)).offset(skip).limit(limit).all()
    
    def get_user_logs(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100) -> List[FileAccessLog]:
        """Получить логи доступа пользователя"""
        return db.query(FileAccessLog).filter(
            FileAccessLog.user_id == user_id
        ).order_by(desc(FileAccessLog.created_at)).offset(skip).limit(limit).all()


# Создаем экземпляры CRUD классов
file = CRUDFile()
file_version = CRUDFileVersion()
file_share = CRUDFileShare()
file_folder = CRUDFileFolder()
file_quota = CRUDFileQuota()
file_storage = CRUDFileStorage()
file_access_log = CRUDFileAccessLog()

