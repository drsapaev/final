"""
API endpoints для файловой системы
"""

import io
import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import NoReturn, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.audit import extract_model_changes
from app.models.user import User
from app.schemas.file_system import (
    FileExportRequest,
    FileExportResponse,
    FileImportRequest,
    FileImportResponse,
    FileList,
    FileOut,
    FileSearchRequest,
    FileSearchResponse,
    FileShareCreate,
    FileShareOut,
    FileStats,
    FileUploadRequest,
)
from app.services.file_system_api_service import FileSystemApiService
from app.services.file_system_service import get_file_system_service
from app.utils.file_validator import validate_upload_file

router = APIRouter()
logger = logging.getLogger(__name__)

IMPORT_ARCHIVE_READ_CHUNK_BYTES = 1024 * 1024


def raise_file_system_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.error(
        "File system endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


async def _read_limited_import_archive(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(IMPORT_ARCHIVE_READ_CHUNK_BYTES)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Import archive is too large",
            )
        chunks.append(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import archive is empty",
        )

    return b"".join(chunks)


@router.post("/upload", response_model=FileOut)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    file_type: str = Form(...),
    permission: str = Form("private"),
    patient_id: int | None = Form(None),
    appointment_id: int | None = Form(None),
    visit_id: int | None = Form(None),
    emr_id: int | None = Form(None),
    folder_id: int | None = Form(None),
    tags: str | None = Form(None),
    expires_at: datetime | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Загрузить файл"""
    try:
        # ✅ SECURITY: Validate file (magic number, size, type)
        is_valid, error_msg, file_info = await validate_upload_file(file)

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {error_msg}",
            )

        # Парсим теги
        tags_list = []
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

        # #43: Scan for malware before saving\n        is_clean, threat = scan_for_malware(file_content)\n        if not is_clean:\n            raise HTTPException(status_code=400, detail=f"File rejected: malware detected ({threat})")\n\n        # FILES-AUDIT-28 P1: validate patient_id ownership
        if patient_id is not None and current_user.role not in ("Admin", "Registrar"):
            from app.models.patient import Patient
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                raise HTTPException(status_code=404, detail=t("patient.not_found"))
            if current_user.role in ("Doctor", "cardio", "derma", "dentist"):
                from app.models.clinic import Doctor
                from app.models.visit import Visit
                doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
                if doctor:
                    has_visit = db.query(Visit).filter(
                        Visit.patient_id == patient_id, Visit.doctor_id == doctor.id
                    ).first()
                    if not has_visit:
                        raise HTTPException(status_code=403, detail="Нет доступа к данному пациенту")

        # Создаем данные для загрузки
        file_data = FileUploadRequest(
            filename=file.filename or "unknown",
            file_type=file_type,
            title=title,
            description=description,
            permission=permission,

            patient_id=patient_id,
            appointment_id=appointment_id,
            visit_id=visit_id,
            emr_id=emr_id,
            folder_id=folder_id,
            tags=tags_list,
            expires_at=expires_at,
        )

        # Получаем сервис
        service = get_file_system_service()

        # Загружаем файл
        uploaded_file = service.upload_file(db, file, file_data, current_user.id)
        FileSystemApiService(db).finalize_file_create_audit(
            request=request,
            user_id=current_user.id,
            uploaded_file=uploaded_file,
        )

        return FileOut.from_orm(uploaded_file)

    except HTTPException:
        raise
    except Exception as e:
        raise_file_system_internal_error("upload_file", e)


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
        raise_file_system_internal_error("get_file_statistics", e)


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
        raise_file_system_internal_error("get_file", e)


@router.get("/{file_id}/download", response_model=dict[str, Any])
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
        raise_file_system_internal_error("download_file", e)


@router.get("/{file_id}/preview", response_model=dict[str, Any])
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
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                # FILES-AUDIT-28 P0-3: prevent content-type sniffing (SVG XSS)
                "X-Content-Type-Options": "nosniff",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_file_system_internal_error("preview_file", e)


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
        raise_file_system_internal_error("search_files", e)


@router.get("/", response_model=FileList)
async def get_files(
    file_type: str | None = Query(None, description="Тип файла"),
    patient_id: int | None = Query(None, description="ID пациента"),
    appointment_id: int | None = Query(None, description="ID записи"),
    visit_id: int | None = Query(None, description="ID визита"),
    emr_id: int | None = Query(None, description="ID медкарты"),
    folder_id: int | None = Query(None, description="ID папки"),
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
            visit_id=visit_id,
            emr_id=emr_id,
            folder_id=folder_id,
            owner_id=owner_id,
        )

        total = FileSystemApiService(db).count_files(
            file_model=file.model,
            owner_id=owner_id,
            file_type=file_type,
            patient_id=patient_id,
            appointment_id=appointment_id,
            visit_id=visit_id,
            emr_id=emr_id,
            emr_record_id=None,
            folder_id=folder_id,
        )
        pages = (total + size - 1) // size

        return FileList(
            files=[FileOut.from_orm(f) for f in files],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    except Exception as e:
        raise_file_system_internal_error("get_files", e)


@router.put("/{file_id}", response_model=FileOut)
async def update_file(
    request: Request,
    file_id: int,
    title: str | None = Form(None),
    description: str | None = Form(None),
    permission: str | None = Form(None),
    tags: str | None = Form(None),
    expires_at: datetime | None = Form(None),
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
        FileSystemApiService(db).finalize_file_update_audit(
            request=request,
            user_id=current_user.id,
            file_id=file_id,
            old_data=old_data,
            updated_file=updated_file,
            description=f"Обновлен файл ID={file_id}: {updated_file.filename}",
        )

        return FileOut.from_orm(updated_file)

    except HTTPException:
        raise
    except Exception as e:
        raise_file_system_internal_error("update_file", e)


@router.put("/{file_id}/content", response_model=FileOut)
async def replace_file_content(
    request: Request,
    file_id: int,
    file: UploadFile = File(...),
    change_description: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """
    ✅ CERTIFICATION: Заменить содержимое файла с версионированием.
    Создает версию старого файла перед заменой и сохраняет SHA256 хеш.
    """
    try:
        service = get_file_system_service()

        # Заменяем содержимое файла (создает версию автоматически)
        updated_file = service.replace_file_content(
            db, file_id, file, current_user.id, change_description
        )
        FileSystemApiService(db).finalize_file_update_audit(
            request=request,
            user_id=current_user.id,
            file_id=file_id,
            old_data=None,  # Старая версия сохранена в FileVersion
            updated_file=updated_file,
            description=(
                f"Заменено содержимое файла ID={file_id}: {updated_file.filename} "
                f"(хеш: {updated_file.file_hash[:8]}...)"
            ),
        )

        return FileOut.from_orm(updated_file)

    except HTTPException:
        raise
    except Exception as e:
        raise_file_system_internal_error("replace_file_content", e)


@router.delete("/{file_id}", response_model=dict[str, Any])
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

        FileSystemApiService(db).finalize_file_delete_audit(
            request=request,
            user_id=current_user.id,
            file_id=file_id,
            old_data=old_data,
            filename=filename,
        )

        return {"success": True, "message": "Файл удален"}

    except HTTPException:
        raise
    except Exception as e:
        raise_file_system_internal_error("delete_file", e)


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
        raise_file_system_internal_error("create_file_share", e)


@router.get("/{file_id}/shares", response_model=list[FileShareOut])
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
        raise_file_system_internal_error("get_file_shares", e)


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
        raise_file_system_internal_error("export_files", e)


@router.post("/import", response_model=FileImportResponse)
async def import_files(
    file: UploadFile = File(...),
    target_folder_id: int | None = Form(None),
    overwrite_existing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "Nurse", "Receptionist")
    ),
):
    """Импортировать файлы из архива"""
    try:
        # Читаем содержимое файла
        service = get_file_system_service()
        file_content = await _read_limited_import_archive(
            file, service.max_import_archive_size
        )

        # Определяем формат архива
        file_format = "zip"  # По умолчанию ZIP
        if file.filename:
            if file.filename.endswith('.tar.gz'):
                file_format = "tar.gz"
            elif file.filename.endswith('.tar'):
                file_format = "tar"

        if file_format != "zip":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only ZIP imports are supported",
            )

        # Создаем запрос на импорт
        import_request = FileImportRequest(
            import_data=file_content,
            format=file_format,
            target_folder_id=target_folder_id,
            overwrite_existing=overwrite_existing,
        )

        result = await service.import_files(db, import_request, current_user.id)

        return FileImportResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise_file_system_internal_error("import_files", e)


@router.post("/cleanup", response_model=dict[str, Any])
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
        raise_file_system_internal_error("cleanup_files", e)
