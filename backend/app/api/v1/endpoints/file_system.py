"""
API endpoints для файловой системы
"""

import io
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    status,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.core.audit import log_critical_change, extract_model_changes
from app.schemas.file_system import (
    FileExportRequest,
    FileExportResponse,
    FileFolderCreate,
    FileFolderOut,
    FileFolderTree,
    FileImportRequest,
    FileImportResponse,
    FileList,
    FileOut,
    FileQuotaOut,
    FileSearchRequest,
    FileSearchResponse,
    FileShareCreate,
    FileShareOut,
    FileStats,
    FileStorageOut,
    FileUploadRequest,
    FileUploadResponse,
)
from app.services.file_system_service import get_file_system_service

router = APIRouter()


@router.post("/upload", response_model=FileOut)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    file_type: str = Form(...),
    permission: str = Form("private"),
    patient_id: Optional[int] = Form(None),
    appointment_id: Optional[int] = Form(None),
    emr_id: Optional[int] = Form(None),
    folder_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    expires_at: Optional[datetime] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Загрузить файл"""
    try:
        # Парсим теги
        tags_list = []
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

        # Создаем данные для загрузки
        file_data = FileUploadRequest(
            filename=file.filename or "unknown",
            file_type=file_type,
            title=title,
            description=description,
            permission=permission,
            patient_id=patient_id,
            appointment_id=appointment_id,
            emr_id=emr_id,
            folder_id=folder_id,
            tags=tags_list,
            expires_at=expires_at,
        )

        # Получаем сервис
        service = get_file_system_service()

        # Загружаем файл
        uploaded_file = service.upload_file(db, file, file_data, current_user.id)
        
        # ✅ AUDIT LOG: Логируем загрузку файла
        db.refresh(uploaded_file)
        _, new_data = extract_model_changes(None, uploaded_file)
        log_critical_change(
            db=db,
            user_id=current_user.id,
            action="CREATE",
            table_name="files",
            row_id=uploaded_file.id,
            old_data=None,
            new_data=new_data,
            request=request,
            description=f"Загружен файл: {uploaded_file.filename} (ID={uploaded_file.id})",
        )
        db.commit()

        return FileOut.from_orm(uploaded_file)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки файла: {str(e)}",
        )


@router.get("/statistics", response_model=FileStats)
async def get_file_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Получить статистику файлов"""
    try:
        service = get_file_system_service()
        stats = service.get_file_statistics(db, current_user.id)

        return FileStats(**stats)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )


@router.get("/{file_id}", response_model=FileOut)
async def get_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist", "Patient")
    ),
):
    """Получить информацию о файле"""
    try:
        service = get_file_system_service()
        file_obj = service.get_file(db, file_id, current_user.id)

        if not file_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден или нет доступа",
            )

        return FileOut.from_orm(file_obj)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения файла: {str(e)}",
        )


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist", "Patient")
    ),
):
    """Скачать файл"""
    try:
        service = get_file_system_service()
        file_content, filename, mime_type = service.download_file(
            db, file_id, current_user.id
        )

        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=mime_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка скачивания файла: {str(e)}",
        )


@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist", "Patient")
    ),
):
    """Предварительный просмотр файла"""
    try:
        service = get_file_system_service()
        file_obj = service.get_file(db, file_id, current_user.id)

        if not file_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден или нет доступа",
            )

        # Проверяем, поддерживается ли предварительный просмотр
        if not file_obj.mime_type.startswith(('image/', 'text/', 'application/pdf')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Предварительный просмотр не поддерживается для этого типа файла",
            )

        file_content, filename, mime_type = service.download_file(
            db, file_id, current_user.id
        )

        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=mime_type,
            headers={"Content-Disposition": f"inline; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка предварительного просмотра: {str(e)}",
        )


@router.post("/search", response_model=FileSearchResponse)
async def search_files(
    search_request: FileSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist", "Patient")
    ),
):
    """Поиск файлов"""
    try:
        service = get_file_system_service()
        files, total, facets = service.search_files(db, search_request, current_user.id)

        # Вычисляем количество страниц
        pages = (total + search_request.size - 1) // search_request.size

        return FileSearchResponse(
            files=[FileOut.from_orm(f) for f in files],
            total=total,
            page=search_request.page,
            size=search_request.size,
            pages=pages,
            facets=facets,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка поиска файлов: {str(e)}",
        )


@router.get("/", response_model=FileList)
async def get_files(
    file_type: Optional[str] = Query(None, description="Тип файла"),
    patient_id: Optional[int] = Query(None, description="ID пациента"),
    appointment_id: Optional[int] = Query(None, description="ID записи"),
    emr_id: Optional[int] = Query(None, description="ID медкарты"),
    folder_id: Optional[int] = Query(None, description="ID папки"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist", "Patient")
    ),
):
    """Получить список файлов"""
    try:
        from app.crud.file_system import file

        # Определяем владельца файлов
        owner_id = current_user.id
        if current_user.role == "Admin":
            owner_id = None  # Админ видит все файлы

        files = file.get_multi(
            db=db,
            skip=(page - 1) * size,
            limit=size,
            file_type=file_type,
            patient_id=patient_id,
            appointment_id=appointment_id,
            emr_id=emr_id,
            folder_id=folder_id,
            owner_id=owner_id,
        )

        # Подсчитываем общее количество
        total_query = db.query(file.model).filter(file.model.owner_id == owner_id)
        if file_type:
            total_query = total_query.filter(file.model.file_type == file_type)
        if patient_id:
            total_query = total_query.filter(file.model.patient_id == patient_id)
        if appointment_id:
            total_query = total_query.filter(
                file.model.appointment_id == appointment_id
            )
        if emr_id:
            total_query = total_query.filter(file.model.emr_id == emr_id)
        if folder_id:
            total_query = total_query.filter(file.model.folder_id == folder_id)

        total = total_query.count()
        pages = (total + size - 1) // size

        return FileList(
            files=[FileOut.from_orm(f) for f in files],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка файлов: {str(e)}",
        )


@router.put("/{file_id}", response_model=FileOut)
async def update_file(
    request: Request,
    file_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    permission: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    expires_at: Optional[datetime] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Обновить файл"""
    try:
        from app.crud.file_system import file
        from app.schemas.file_system import FileUpdate

        # Получаем файл
        db_file = file.get(db, id=file_id)
        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден"
            )

        # Проверяем права доступа
        if db_file.owner_id != current_user.id and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для изменения файла",
            )

        # Парсим теги
        tags_list = None
        if tags is not None:
            tags_list = (
                [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else []
            )

        # Создаем данные для обновления
        update_data = FileUpdate(
            title=title,
            description=description,
            permission=permission,
            tags=tags_list,
            expires_at=expires_at,
        )

        # ✅ AUDIT LOG: Сохраняем старые данные перед обновлением
        old_data, _ = extract_model_changes(db_file, None)
        
        # Обновляем файл
        updated_file = file.update(db, db_obj=db_file, obj_in=update_data)
        
        # ✅ AUDIT LOG: Логируем обновление файла
        db.refresh(updated_file)
        _, new_data = extract_model_changes(None, updated_file)
        log_critical_change(
            db=db,
            user_id=current_user.id,
            action="UPDATE",
            table_name="files",
            row_id=file_id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            description=f"Обновлен файл ID={file_id}: {updated_file.filename}",
        )
        db.commit()

        return FileOut.from_orm(updated_file)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления файла: {str(e)}",
        )


@router.delete("/{file_id}")
async def delete_file(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Удалить файл"""
    try:
        # ✅ Получаем файл перед удалением для логирования
        from app.crud.file_system import file as file_crud
        db_file = file_crud.get(db, id=file_id)
        if not db_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден"
            )
        
        # Сохраняем данные для аудита перед удалением
        old_data, _ = extract_model_changes(db_file, None)
        filename = db_file.filename
        
        # ✅ FIX: Выполняем удаление ПЕРЕД логированием аудита
        service = get_file_system_service()
        success = service.delete_file(db, file_id, current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Файл не найден или нет прав для удаления",
            )
        
        # ✅ AUDIT LOG: Логируем удаление файла ПОСЛЕ успешного удаления
        log_critical_change(
            db=db,
            user_id=current_user.id,
            action="DELETE",
            table_name="files",
            row_id=file_id,
            old_data=old_data,
            new_data=None,
            request=request,
            description=f"Удален файл ID={file_id}: {filename}",
        )
        db.commit()

        return {"success": True, "message": "Файл удален"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления файла: {str(e)}",
        )


@router.post("/{file_id}/share", response_model=FileShareOut)
async def create_file_share(
    file_id: int,
    share_data: FileShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Создать совместное использование файла"""
    try:
        service = get_file_system_service()
        share = service.create_file_share(
            db, file_id, share_data.dict(), current_user.id
        )

        return FileShareOut.from_orm(share)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания совместного использования: {str(e)}",
        )


@router.get("/{file_id}/shares", response_model=List[FileShareOut])
async def get_file_shares(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Получить совместные использования файла"""
    try:
        # Проверяем права доступа
        from app.crud.file_system import file, file_share

        db_file = file.get(db, id=file_id)
        if not db_file or db_file.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для просмотра совместных использований",
            )

        shares = file_share.get_file_shares(db, file_id=file_id)

        return [FileShareOut.from_orm(share) for share in shares]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения совместных использований: {str(e)}",
        )


@router.post("/export", response_model=FileExportResponse)
async def export_files(
    export_request: FileExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Экспортировать файлы в архив"""
    try:
        service = get_file_system_service()
        archive_path = service.export_files(db, export_request, current_user.id)

        # Создаем временный файл для ответа
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{export_request.format}"
        )
        shutil.copy2(archive_path, temp_file.name)
        temp_file.close()

        # Удаляем исходный файл
        os.unlink(archive_path)

        return FileExportResponse(
            export_id=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            download_url=f"/api/v1/files/download-export/{os.path.basename(temp_file.name)}",
            expires_at=datetime.now() + timedelta(hours=24),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка экспорта файлов: {str(e)}",
        )


@router.post("/import", response_model=FileImportResponse)
async def import_files(
    file: UploadFile = File(...),
    target_folder_id: Optional[int] = Form(None),
    overwrite_existing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Импортировать файлы из архива"""
    try:
        # Читаем содержимое файла
        file_content = await file.read()

        # Определяем формат архива
        file_format = "zip"  # По умолчанию ZIP
        if file.filename:
            if file.filename.endswith('.tar.gz'):
                file_format = "tar.gz"
            elif file.filename.endswith('.tar'):
                file_format = "tar"

        # Создаем запрос на импорт
        import_request = FileImportRequest(
            import_data=file_content,
            format=file_format,
            target_folder_id=target_folder_id,
            overwrite_existing=overwrite_existing,
        )

        service = get_file_system_service()
        result = await service.import_files(db, import_request, current_user.id)

        return FileImportResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка импорта файлов: {str(e)}",
        )


@router.post("/cleanup")
async def cleanup_files(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Очистить истекшие файлы"""
    try:
        service = get_file_system_service()
        cleaned_count = service.cleanup_expired_files(db)

        return {
            "success": True,
            "message": f"Очищено {cleaned_count} истекших файлов",
            "cleaned_count": cleaned_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка очистки файлов: {str(e)}",
        )
