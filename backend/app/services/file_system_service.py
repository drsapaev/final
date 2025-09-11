"""
Сервис файловой системы
"""
import os
import hashlib
import mimetypes
import shutil
import zipfile
import tempfile
import io
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, BinaryIO
from pathlib import Path
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import UploadFile, HTTPException, status

from app.crud.file_system import (
    file, file_version, file_share, file_folder, 
    file_quota, file_storage, file_access_log
)
from app.schemas.file_system import (
    FileCreate, FileUpdate, FileUploadRequest, FileUploadResponse,
    FileSearchRequest, FileExportRequest, FileImportRequest,
    FileTypeEnum, FileStatus, FilePermissionEnum
)
from app.models.file_system import File, FileType, FileStatus as FileStatusEnum, FileShare

logger = logging.getLogger(__name__)


class FileSystemService:
    """Сервис файловой системы"""
    
    def __init__(self):
        self.base_storage_path = os.getenv("FILE_STORAGE_PATH", "storage/files")
        self.temp_storage_path = os.getenv("TEMP_STORAGE_PATH", "storage/temp")
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))  # 100MB
        self.allowed_extensions = {
            FileType.DOCUMENT: ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'],
            FileType.IMAGE: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
            FileType.VIDEO: ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
            FileType.AUDIO: ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
            FileType.ARCHIVE: ['.zip', '.rar', '.7z', '.tar', '.gz'],
            FileType.MEDICAL_RECORD: ['.pdf', '.doc', '.docx', '.xml'],
            FileType.LAB_RESULT: ['.pdf', '.xlsx', '.csv', '.xml'],
            FileType.XRAY: ['.dcm', '.dicom', '.jpg', '.jpeg', '.png'],
            FileType.PRESCRIPTION: ['.pdf', '.xml', '.json'],
            FileType.REPORT: ['.pdf', '.doc', '.docx', '.xlsx'],
            FileType.BACKUP: ['.zip', '.sql', '.bak'],
            FileType.OTHER: []
        }
        
        # Создаем директории если их нет
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Создать необходимые директории"""
        os.makedirs(self.base_storage_path, exist_ok=True)
        os.makedirs(self.temp_storage_path, exist_ok=True)
        
        # Создаем поддиректории по годам и месяцам
        current_date = datetime.now()
        year_month = current_date.strftime("%Y/%m")
        os.makedirs(os.path.join(self.base_storage_path, year_month), exist_ok=True)
    
    def _get_file_type(self, filename: str, mime_type: str) -> FileType:
        """Определить тип файла по имени и MIME типу"""
        ext = Path(filename).suffix.lower()
        
        for file_type, extensions in self.allowed_extensions.items():
            if ext in extensions:
                return file_type
        
        # Дополнительная проверка по MIME типу
        if mime_type.startswith('image/'):
            return FileType.IMAGE
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type == 'application/pdf':
            return FileType.DOCUMENT
        elif mime_type in ['application/zip', 'application/x-rar-compressed']:
            return FileType.ARCHIVE
        
        return FileType.OTHER
    
    def _generate_file_hash(self, file_content: bytes) -> str:
        """Генерировать SHA-256 хеш файла"""
        return hashlib.sha256(file_content).hexdigest()
    
    def _generate_file_path(self, filename: str, file_hash: str) -> str:
        """Генерировать путь для сохранения файла"""
        # Используем первые 2 символа хеша для создания поддиректории
        hash_prefix = file_hash[:2]
        current_date = datetime.now()
        year_month = current_date.strftime("%Y/%m")
        
        # Создаем уникальное имя файла
        name, ext = os.path.splitext(filename)
        unique_filename = f"{file_hash[:8]}_{name}{ext}"
        
        return os.path.join(self.base_storage_path, year_month, hash_prefix, unique_filename)
    
    def _check_file_quota(self, db: Session, user_id: int, file_size: int) -> Tuple[bool, str]:
        """Проверить квоту пользователя"""
        return file_quota.check_quota(db, user_id=user_id, additional_size=file_size, additional_files=1)
    
    def upload_file(
        self, 
        db: Session, 
        upload_file: UploadFile, 
        file_data: FileUploadRequest,
        user_id: int
    ) -> File:
        """Загрузить файл"""
        try:
            # Читаем содержимое файла
            file_content = upload_file.file.read()
            file_size = len(file_content)
            
            # Проверяем размер файла
            if file_size > self.max_file_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Файл слишком большой. Максимальный размер: {self.max_file_size} байт"
                )
            
            # Проверяем квоту пользователя
            quota_ok, quota_message = self._check_file_quota(db, user_id, file_size)
            if not quota_ok:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=quota_message
                )
            
            # Определяем тип файла
            mime_type = upload_file.content_type or mimetypes.guess_type(upload_file.filename)[0] or 'application/octet-stream'
            file_type = self._get_file_type(upload_file.filename, mime_type)
            
            # Генерируем хеш файла
            file_hash = self._generate_file_hash(file_content)
            
            # Проверяем, не загружен ли уже такой файл
            existing_file = file.get_by_hash(db, file_hash=file_hash)
            if existing_file:
                # Создаем ссылку на существующий файл
                file_create_data = FileCreate(
                    filename=file_data.filename,
                    original_filename=upload_file.filename,
                    file_path=existing_file.file_path,
                    file_type=file_data.file_type,
                    mime_type=mime_type,
                    file_size=file_size,
                    file_hash=file_hash,
                    title=file_data.title,
                    description=file_data.description,
                    tags=file_data.tags,
                    permission=file_data.permission,
                    patient_id=file_data.patient_id,
                    appointment_id=file_data.appointment_id,
                    emr_id=file_data.emr_id,
                    expires_at=file_data.expires_at,
                    file_metadata=file_data.file_metadata
                )
            else:
                # Генерируем путь для нового файла
                file_path = self._generate_file_path(upload_file.filename, file_hash)
                
                # Создаем директорию если нужно
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Сохраняем файл
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                file_create_data = FileCreate(
                    filename=file_data.filename,
                    original_filename=upload_file.filename,
                    file_path=file_path,
                    file_type=file_data.file_type,
                    mime_type=mime_type,
                    file_size=file_size,
                    file_hash=file_hash,
                    title=file_data.title,
                    description=file_data.description,
                    tags=file_data.tags,
                    permission=file_data.permission,
                    patient_id=file_data.patient_id,
                    appointment_id=file_data.appointment_id,
                    emr_id=file_data.emr_id,
                    expires_at=file_data.expires_at,
                    file_metadata=file_data.file_metadata
                )
            
            # Создаем запись в БД
            db_file = file.create(db, obj_in=file_create_data, owner_id=user_id)
            
            # Обновляем статус на READY
            db_file.status = FileStatusEnum.READY
            db.add(db_file)
            db.commit()
            
            # Обновляем квоту пользователя
            file_quota.update_usage(db, user_id=user_id, size_delta=file_size, files_delta=1)
            
            # Логируем загрузку
            file_access_log.create(
                db, 
                file_id=db_file.id, 
                user_id=user_id, 
                action="upload"
            )
            
            return db_file
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка загрузки файла: {str(e)}"
            )
    
    def get_file(self, db: Session, file_id: int, user_id: Optional[int] = None) -> Optional[File]:
        """Получить файл"""
        db_file = file.get(db, id=file_id)
        if not db_file:
            return None
        
        # Проверяем права доступа
        if not self._check_file_access(db, db_file, user_id):
            return None
        
        # Логируем доступ
        if user_id:
            file_access_log.create(
                db, 
                file_id=file_id, 
                user_id=user_id, 
                action="view"
            )
        
        return db_file
    
    def _check_file_access(self, db: Session, file_obj: File, user_id: Optional[int]) -> bool:
        """Проверить права доступа к файлу"""
        if not user_id:
            return file_obj.permission == FilePermissionEnum.PUBLIC
        
        # Владелец файла имеет полный доступ
        if file_obj.owner_id == user_id:
            return True
        
        # Проверяем совместное использование
        shares = file_share.get_file_shares(db, file_id=file_obj.id)
        for share in shares:
            if (share.shared_with_user_id == user_id or 
                (share.access_token and share.expires_at and share.expires_at > datetime.utcnow())):
                return True
        
        # Проверяем права по типу файла
        if file_obj.permission == FilePermissionEnum.PUBLIC:
            return True
        elif file_obj.permission == FilePermissionEnum.PRIVATE:
            return False
        elif file_obj.permission == FilePermissionEnum.RESTRICTED:
            # Здесь можно добавить дополнительную логику проверки ролей
            return False
        elif file_obj.permission == FilePermissionEnum.CONFIDENTIAL:
            return False
        
        return False
    
    def download_file(self, db: Session, file_id: int, user_id: Optional[int] = None) -> Tuple[bytes, str, str]:
        """Скачать файл"""
        db_file = self.get_file(db, file_id, user_id)
        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден или нет доступа"
            )
        
        if not os.path.exists(db_file.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден на диске"
            )
        
        # Читаем файл
        with open(db_file.file_path, 'rb') as f:
            file_content = f.read()
        
        # Логируем скачивание
        if user_id:
            file_access_log.create(
                db, 
                file_id=file_id, 
                user_id=user_id, 
                action="download"
            )
        
        return file_content, db_file.filename, db_file.mime_type
    
    def search_files(self, db: Session, search_request: FileSearchRequest, user_id: int) -> Tuple[List[File], int, Dict[str, Any]]:
        """Поиск файлов"""
        # Добавляем фильтр по пользователю если не админ
        if not self._is_admin(db, user_id):
            search_request.owner_id = user_id
        
        return file.search(db, search_request=search_request)
    
    def _is_admin(self, db: Session, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        return user and user.role == "Admin"
    
    def delete_file(self, db: Session, file_id: int, user_id: int) -> bool:
        """Удалить файл"""
        db_file = file.get(db, id=file_id)
        if not db_file:
            return False
        
        # Проверяем права доступа
        if db_file.owner_id != user_id and not self._is_admin(db, user_id):
            return False
        
        # Мягкое удаление
        result = file.delete(db, id=file_id)
        if result:
            # Обновляем квоту пользователя
            file_quota.update_usage(db, user_id=user_id, size_delta=-db_file.file_size, files_delta=-1)
            
            # Логируем удаление
            file_access_log.create(
                db, 
                file_id=file_id, 
                user_id=user_id, 
                action="delete"
            )
        
        return result is not None
    
    def create_file_share(self, db: Session, file_id: int, share_data: dict, user_id: int) -> FileShare:
        """Создать совместное использование файла"""
        # Проверяем права доступа
        db_file = file.get(db, id=file_id)
        if not db_file or db_file.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для создания совместного использования"
            )
        
        from app.schemas.file_system import FileShareCreate
        share_create = FileShareCreate(**share_data)
        return file_share.create(db, file_id=file_id, share_data=share_create, created_by=user_id)
    
    def export_files(self, db: Session, export_request: FileExportRequest, user_id: int) -> str:
        """Экспортировать файлы в архив"""
        # Получаем файлы для экспорта
        files_to_export = []
        for file_id in export_request.file_ids:
            db_file = self.get_file(db, file_id, user_id)
            if db_file:
                files_to_export.append(db_file)
        
        if not files_to_export:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файлы для экспорта не найдены"
            )
        
        # Создаем временный архив
        temp_dir = tempfile.mkdtemp()
        archive_path = os.path.join(temp_dir, f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_request.format}")
        
        try:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for db_file in files_to_export:
                    if os.path.exists(db_file.file_path):
                        # Добавляем файл в архив
                        arcname = db_file.original_filename
                        zipf.write(db_file.file_path, arcname)
                        
                        # Добавляем метаданные если нужно
                        if export_request.include_metadata:
                            metadata = {
                                "filename": db_file.filename,
                                "original_filename": db_file.original_filename,
                                "file_type": db_file.file_type,
                                "mime_type": db_file.mime_type,
                                "file_size": db_file.file_size,
                                "title": db_file.title,
                                "description": db_file.description,
                                "tags": db_file.tags,
                                "created_at": db_file.created_at.isoformat(),
                                "updated_at": db_file.updated_at.isoformat()
                            }
                            zipf.writestr(f"{arcname}.metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            
            return archive_path
            
        except Exception as e:
            logger.error(f"Ошибка создания архива: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка создания архива: {str(e)}"
            )
    
    async def import_files(self, db: Session, import_request: FileImportRequest, user_id: int) -> Dict[str, Any]:
        """Импортировать файлы из архива"""
        temp_dir = tempfile.mkdtemp()
        extracted_path = os.path.join(temp_dir, "extracted")
        
        try:
            # Извлекаем архив
            with zipfile.ZipFile(io.BytesIO(import_request.import_data), 'r') as zipf:
                zipf.extractall(extracted_path)
            
            processed_files = 0
            errors = []
            
            # Обрабатываем извлеченные файлы
            for root, dirs, files in os.walk(extracted_path):
                for filename in files:
                    if filename.endswith('.metadata.json'):
                        continue  # Пропускаем файлы метаданных
                    
                    file_path = os.path.join(root, filename)
                    
                    try:
                        # Читаем файл
                        with open(file_path, 'rb') as f:
                            file_content = f.read()
                        
                        # Определяем тип файла
                        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                        file_type = self._get_file_type(filename, mime_type)
                        
                        # Создаем UploadFile объект
                        upload_file = UploadFile(
                            filename=filename,
                            file=io.BytesIO(file_content),
                            size=len(file_content)
                        )
                        
                        # Создаем данные для загрузки
                        file_data = FileUploadRequest(
                            filename=filename,
                            file_type=file_type,
                            folder_id=import_request.target_folder_id
                        )
                        
                        # Загружаем файл
                        await self.upload_file(db, upload_file, file_data, user_id)
                        processed_files += 1
                        
                    except Exception as e:
                        errors.append(f"Ошибка обработки файла {filename}: {str(e)}")
            
            return {
                "processed_files": processed_files,
                "errors": errors,
                "success": len(errors) == 0
            }
            
        except Exception as e:
            logger.error(f"Ошибка импорта файлов: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка импорта файлов: {str(e)}"
            )
        finally:
            # Очищаем временные файлы
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def get_file_statistics(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Получить статистику файлов"""
        # Общая статистика
        total_files = db.query(File).filter(File.owner_id == user_id).count()
        total_size = db.query(func.sum(File.file_size)).filter(File.owner_id == user_id).scalar() or 0
        
        # Статистика по типам
        files_by_type = db.query(File.file_type, func.count(File.id)).filter(
            File.owner_id == user_id
        ).group_by(File.file_type).all()
        
        # Статистика по правам доступа
        files_by_permission = db.query(File.permission, func.count(File.id)).filter(
            File.owner_id == user_id
        ).group_by(File.permission).all()
        
        # Недавние загрузки
        recent_uploads = db.query(File).filter(
            File.owner_id == user_id
        ).order_by(desc(File.created_at)).limit(10).all()
        
        # Использование квоты
        quota = file_quota.get_user_quota(db, user_id=user_id)
        storage_usage = {
            "used_bytes": quota.used_storage_bytes if quota else 0,
            "max_bytes": quota.max_storage_bytes if quota else 0,
            "used_files": quota.used_files if quota else 0,
            "max_files": quota.max_files if quota else 0
        }
        
        return {
            "total_files": total_files,
            "total_size": total_size,
            "files_by_type": dict(files_by_type),
            "files_by_permission": dict(files_by_permission),
            "recent_uploads": recent_uploads,
            "storage_usage": storage_usage
        }
    
    def cleanup_expired_files(self, db: Session) -> int:
        """Очистить истекшие файлы"""
        return file.cleanup_expired_files(db)


# Глобальный экземпляр сервиса
file_system_service = FileSystemService()

def get_file_system_service() -> FileSystemService:
    """Получить экземпляр сервиса файловой системы"""
    return file_system_service
