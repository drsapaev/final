import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi import (
    File as UploadFileField,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api import deps
from app.core.roles import (
    DOCTOR_FAMILY_GATE_ROLES,
    is_admin_role,
    is_doctor_role_spelling,
)
from app.core.specialties import (
    DENTAL_CANONICAL_SPECIALTY,
    canonical_specialty,
    specialty_variants,
)
from app.crud.file_system import file_access_log
from app.models.clinic import Doctor
from app.models.file_system import File as StoredFile
from app.models.file_system import FilePermission, FileStatus, FileType
from app.models.user import User
from app.models.visit import Visit
from app.schemas.dental import (
    DentalExaminationRequest,
    DentalProstheticRequest,
    DentalTreatmentRequest,
)
from app.schemas.file_system import FilePermissionEnum, FileTypeEnum, FileUploadRequest
from app.services.audit_service import log_audit_event
from app.services.dental_api_service import DentalApiDomainError, DentalApiService
from app.services.file_system_service import DENTAL_MEDIA_TAG, get_file_system_service
from app.utils.file_validator import validate_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dental", tags=["dental"])

DENTAL_CLINICIAN_ROLES = ("Admin", *DOCTOR_FAMILY_GATE_ROLES)
DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL = (
    "Dental examination/treatment persistence is not implemented on this endpoint. "
    "Use the canonical visit protocol or odontogram workflow until a durable dental "
    "record contract is added."
)
DENTAL_MEDIA_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}


class DentalMediaOut(BaseModel):
    """Storage-safe representation of a dental media record."""

    id: int
    title: str | None
    description: str | None
    category: Literal["photo", "xray"]
    tooth: str | None
    capture_date: date | None
    mime_type: str
    file_size: int
    patient_id: int
    visit_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid")


class DentalMediaList(BaseModel):
    items: list[DentalMediaOut]
    total: int
    page: int
    size: int


class DentalMediaUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=2000)
    category: Literal["photo", "xray"] | None = None
    tooth: str | None = Field(None, max_length=16)
    capture_date: date | None = None

    model_config = ConfigDict(extra="forbid")


def _dental_file_metadata(file_obj: StoredFile) -> dict[str, Any] | None:
    raw_metadata = file_obj.file_metadata
    if isinstance(raw_metadata, str):
        try:
            raw_metadata = json.loads(raw_metadata)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(raw_metadata, dict):
        return None
    metadata = raw_metadata.get("dental_media")
    if not isinstance(metadata, dict):
        return None
    if metadata.get("category") not in {"photo", "xray"}:
        return None
    return metadata


def _dental_file_has_tag(file_obj: StoredFile) -> bool:
    tags = file_obj.tags
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            return False
    return isinstance(tags, list) and DENTAL_MEDIA_TAG in tags


def _get_dental_media_file(db: Session, media_id: int) -> StoredFile:
    file_obj = db.query(StoredFile).filter(StoredFile.id == media_id).first()
    if (
        file_obj is None
        or file_obj.status not in {FileStatus.READY, FileStatus.ARCHIVED}
        or file_obj.file_type not in {FileType.IMAGE, FileType.XRAY}
        or file_obj.permission != FilePermission.PRIVATE
        or not file_obj.patient_id
        or not file_obj.visit_id
        or not _dental_file_has_tag(file_obj)
        or _dental_file_metadata(file_obj) is None
    ):
        raise HTTPException(status_code=404, detail="Снимок не найден")
    return file_obj


def _require_dental_visit(
    db: Session,
    user: User,
    *,
    patient_id: int,
    visit_id: int,
) -> Visit:
    visit = (
        db.query(Visit)
        .filter(Visit.id == visit_id, Visit.patient_id == patient_id)
        .first()
    )
    if not visit or str(visit.status or "").casefold() in {"canceled", "cancelled"}:
        raise HTTPException(status_code=404, detail="Визит не найден или нет доступа")

    visit_doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
    if is_admin_role(user.role):
        if (
            visit_doctor
            and canonical_specialty(visit_doctor.specialty)
            == DENTAL_CANONICAL_SPECIALTY
        ):
            return visit
        raise HTTPException(status_code=404, detail="Визит не найден или нет доступа")

    if not is_doctor_role_spelling(user.role):
        raise HTTPException(
            status_code=403, detail="Нет доступа к стоматологическому архиву"
        )

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
        .first()
    )
    if doctor:
        if canonical_specialty(doctor.specialty) != DENTAL_CANONICAL_SPECIALTY:
            raise HTTPException(
                status_code=403, detail="Только стоматолог может открыть архив"
            )
        if visit.doctor_id == doctor.id:
            return visit

    raise HTTPException(status_code=404, detail="Визит не найден или нет доступа")


def _require_dental_file_context(db: Session, file_obj: StoredFile) -> None:
    visit = (
        db.query(Visit)
        .filter(Visit.id == file_obj.visit_id, Visit.patient_id == file_obj.patient_id)
        .first()
    )
    doctor = (
        db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
        if visit and visit.doctor_id is not None
        else None
    )
    if (
        not visit
        or not doctor
        or canonical_specialty(doctor.specialty) != DENTAL_CANONICAL_SPECIALTY
    ):
        raise HTTPException(status_code=404, detail="Снимок не найден")


def _require_dental_media_editor(db: Session, user: User, file_obj: StoredFile) -> None:
    if is_admin_role(user.role):
        return
    if file_obj.owner_id != user.id or not is_doctor_role_spelling(user.role):
        raise HTTPException(status_code=403, detail="Нет прав для изменения снимка")
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == user.id, Doctor.active.is_(True))
        .first()
    )
    if doctor and canonical_specialty(doctor.specialty) == DENTAL_CANONICAL_SPECIALTY:
        return
    raise HTTPException(
        status_code=403, detail="Только стоматолог может изменить снимок"
    )


def _dental_media_out(file_obj: StoredFile) -> DentalMediaOut:
    metadata = _dental_file_metadata(file_obj) or {}
    capture_date = metadata.get("capture_date")
    if isinstance(capture_date, str):
        try:
            capture_date = date.fromisoformat(capture_date)
        except ValueError:
            capture_date = None
    return DentalMediaOut(
        id=file_obj.id,
        title=file_obj.title,
        description=file_obj.description,
        category=metadata["category"],
        tooth=metadata.get("tooth"),
        capture_date=capture_date,
        mime_type=file_obj.mime_type,
        file_size=file_obj.file_size,
        patient_id=file_obj.patient_id,
        visit_id=file_obj.visit_id,
        created_at=file_obj.created_at,
        updated_at=file_obj.updated_at,
    )


def _audit_dental_media_event(
    db: Session,
    user: User,
    request: Request,
    *,
    patient_id: int,
    visit_id: int,
    action: str,
    resource_id: str,
    reason_code: dict[str, Any] | None = None,
) -> None:
    log_audit_event(
        db,
        event_type=f"DENTAL_MEDIA_{action.upper()}",
        actor_user_id=user.id,
        actor_role=user.role,
        subject_patient_id=patient_id,
        resource_type="dental_media",
        resource_id=resource_id,
        action=action,
        reason_code={"visit_id": visit_id, **(reason_code or {})},
        request=request,
    )


def _dental_media_storage_path(file_obj: StoredFile) -> Path:
    storage_root = Path(get_file_system_service().base_storage_path).resolve()
    try:
        candidate = Path(file_obj.file_path).resolve()
        if not candidate.is_relative_to(storage_root):
            raise HTTPException(status_code=404, detail="Снимок не найден")
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Снимок не найден") from exc
    return candidate


@router.post(
    "/media",
    summary="Загрузить стоматологическое фото или рентген",
    response_model=DentalMediaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dental_media(
    request: Request,
    file: UploadFile = UploadFileField(...),
    patient_id: int = Form(..., gt=0),
    visit_id: int = Form(..., gt=0),
    category: Literal["photo", "xray"] = Form(...),
    tooth: str | None = Form(None, max_length=16),
    capture_date: date | None = Form(None),
    title: str | None = Form(None, max_length=255),
    description: str | None = Form(None, max_length=2000),
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> DentalMediaOut:
    _require_dental_visit(db, user, patient_id=patient_id, visit_id=visit_id)

    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    extension = Path(filename).suffix.casefold()
    expected_mime_type = DENTAL_MEDIA_EXTENSIONS.get(extension)
    if not filename or not expected_mime_type:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только изображения JPG/PNG и документы PDF",
        )
    # Never pass a potentially identifying client filename to storage logs.
    safe_filename = f"dental-media{extension}"
    file.filename = safe_filename

    is_valid, error_message, file_info = await validate_upload_file(file)
    if not is_valid or not file_info or file_info.get("mime") != expected_mime_type:
        raise HTTPException(
            status_code=400,
            detail=(
                "Файл не прошёл проверку формата"
                if not error_message
                else f"Файл не прошёл проверку формата: {error_message}"
            ),
        )
    if file.content_type not in {None, "application/octet-stream", expected_mime_type}:
        raise HTTPException(
            status_code=400, detail="MIME-тип не соответствует содержимому файла"
        )
    if extension == ".pdf" and category != "xray":
        raise HTTPException(
            status_code=400, detail="PDF можно загрузить только в категорию рентгена"
        )

    normalized_tooth = tooth.strip() if tooth and tooth.strip() else None
    metadata = {
        "dental_media": {
            "category": category,
            "tooth": normalized_tooth,
            "capture_date": capture_date.isoformat() if capture_date else None,
        }
    }
    file_type = FileTypeEnum.XRAY if category == "xray" else FileTypeEnum.IMAGE
    upload_request = FileUploadRequest(
        filename=safe_filename,
        file_type=file_type,
        title=title,
        description=description,
        permission=FilePermissionEnum.PRIVATE,
        patient_id=patient_id,
        visit_id=visit_id,
        tags=[DENTAL_MEDIA_TAG],
        file_metadata=metadata,
    )
    uploaded_file = get_file_system_service().upload_file(
        db, file, upload_request, user.id
    )
    uploaded_file.mime_type = expected_mime_type
    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)
    _audit_dental_media_event(
        db,
        user,
        request,
        patient_id=patient_id,
        visit_id=visit_id,
        action="create",
        resource_id=str(uploaded_file.id),
    )
    return _dental_media_out(uploaded_file)


@router.get(
    "/media",
    summary="Список стоматологических снимков пациента",
    response_model=DentalMediaList,
)
def list_dental_media(
    request: Request,
    patient_id: int = Query(..., gt=0),
    visit_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> DentalMediaList:
    _require_dental_visit(db, user, patient_id=patient_id, visit_id=visit_id)
    query = (
        db.query(StoredFile)
        .join(
            Visit,
            (Visit.id == StoredFile.visit_id)
            & (Visit.patient_id == StoredFile.patient_id),
        )
        .join(
            Doctor,
            Doctor.id == Visit.doctor_id,
        )
        .filter(
            StoredFile.patient_id == patient_id,
            StoredFile.file_type.in_([FileType.IMAGE, FileType.XRAY]),
            StoredFile.status.in_([FileStatus.READY, FileStatus.ARCHIVED]),
            StoredFile.permission == FilePermission.PRIVATE,
            StoredFile.tags.ilike(f'%"{DENTAL_MEDIA_TAG}"%'),
            StoredFile.file_metadata.ilike('%"category"%'),
            func.lower(Doctor.specialty).in_(
                [specialty.lower() for specialty in specialty_variants("dentistry")]
            ),
        )
    )
    total = query.count()
    files = (
        query.order_by(desc(StoredFile.created_at), desc(StoredFile.id))
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    valid_files = [
        file_obj for file_obj in files if _dental_file_metadata(file_obj) is not None
    ]
    _audit_dental_media_event(
        db,
        user,
        request,
        patient_id=patient_id,
        visit_id=visit_id,
        action="view",
        resource_id=str(visit_id),
        reason_code={"result_count": len(valid_files), "page": page},
    )
    return DentalMediaList(
        items=[_dental_media_out(file_obj) for file_obj in valid_files],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/media/{media_id}/content",
    summary="Защищённый просмотр стоматологического снимка",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}, "application/pdf": {}}}
    },
)
def view_dental_media(
    media_id: int,
    request: Request,
    visit_id: int = Query(..., gt=0),
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> Response:
    file_obj = _get_dental_media_file(db, media_id)
    _require_dental_file_context(db, file_obj)
    _require_dental_visit(
        db,
        user,
        patient_id=file_obj.patient_id,
        visit_id=visit_id,
    )
    path = _dental_media_storage_path(file_obj)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Снимок не найден")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Снимок не найден") from exc
    file_access_log.create(
        db,
        file_id=file_obj.id,
        user_id=user.id,
        action="preview",
    )
    _audit_dental_media_event(
        db,
        user,
        request,
        patient_id=file_obj.patient_id,
        visit_id=visit_id,
        action="view",
        resource_id=str(file_obj.id),
    )
    extension = next(
        (
            extension
            for extension, mime_type in DENTAL_MEDIA_EXTENSIONS.items()
            if mime_type == file_obj.mime_type
        ),
        None,
    )
    if extension is None:
        raise HTTPException(status_code=404, detail="Снимок не найден")
    return Response(
        content=content,
        media_type=file_obj.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="dental-media-{file_obj.id}{extension}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.patch(
    "/media/{media_id}",
    summary="Изменить метаданные стоматологического снимка",
    response_model=DentalMediaOut,
)
def update_dental_media(
    media_id: int,
    request: Request,
    updates: DentalMediaUpdate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> DentalMediaOut:
    file_obj = _get_dental_media_file(db, media_id)
    _require_dental_file_context(db, file_obj)
    _require_dental_media_editor(db, user, file_obj)
    values = updates.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="Укажите метаданные для изменения")
    if values.get("category") == "photo" and file_obj.mime_type == "application/pdf":
        raise HTTPException(
            status_code=400, detail="PDF можно хранить только в категории рентгена"
        )
    if "category" in values and values["category"] is None:
        raise HTTPException(status_code=400, detail="Категория не может быть пустой")

    metadata = _dental_file_metadata(file_obj) or {}
    for field in ("category", "tooth", "capture_date"):
        if field in values:
            value = values[field]
            metadata[field] = value.isoformat() if isinstance(value, date) else value
    if "category" in values:
        file_obj.file_type = (
            FileType.XRAY if values["category"] == "xray" else FileType.IMAGE
        )
    if "title" in values:
        file_obj.title = values["title"]
    if "description" in values:
        file_obj.description = values["description"]
    file_obj.file_metadata = json.dumps(
        {"dental_media": metadata},
        ensure_ascii=False,
    )
    db.add(file_obj)
    file_access_log.create(
        db,
        file_id=file_obj.id,
        user_id=user.id,
        action="metadata_update",
    )
    db.refresh(file_obj)
    _audit_dental_media_event(
        db,
        user,
        request,
        patient_id=file_obj.patient_id,
        visit_id=file_obj.visit_id,
        action="edit",
        resource_id=str(file_obj.id),
        reason_code={"fields": sorted(values)},
    )
    return _dental_media_out(file_obj)


@router.delete(
    "/media/{media_id}",
    summary="Мягко удалить стоматологический снимок",
    response_model=dict[str, bool],
)
def delete_dental_media(
    media_id: int,
    request: Request,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, bool]:
    file_obj = _get_dental_media_file(db, media_id)
    _require_dental_file_context(db, file_obj)
    _require_dental_media_editor(db, user, file_obj)
    deleted = get_file_system_service().delete_file(
        db, media_id, user.id, allow_protected_domain=True
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Снимок не найден или уже удалён")
    _audit_dental_media_event(
        db,
        user,
        request,
        patient_id=file_obj.patient_id,
        visit_id=file_obj.visit_id,
        action="delete",
        resource_id=str(file_obj.id),
    )
    return {"success": True}


class DentalPriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    # SPEC-AUDIT-28 P0-3: validate price is positive and reasonable
    new_price: Decimal = Field(..., gt=0, le=Decimal("1000000000"))
    reason: str
    details: str | None = None
    treatment_completed: bool = True


class DentalPriceOverrideResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    original_price: Decimal
    # SPEC-AUDIT-28 P0-3: validate price is positive and reasonable
    new_price: Decimal = Field(..., gt=0, le=Decimal("1000000000"))
    reason: str
    details: str | None
    status: str
    treatment_completed: bool
    created_at: datetime


@router.get(
    "/examinations",
    summary="Стоматологические осмотры",
    response_model=list[dict[str, Any]],
)
async def get_dental_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список стоматологических осмотров
    """
    try:
        return []
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/examinations",
    summary="Создать стоматологический осмотр",
    response_model=dict[str, Any],
)
async def create_dental_examination(
    examination_data: DentalExaminationRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, Any]:
    """
    Создать новый стоматологический осмотр
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL,
    )


@router.get("/treatments", summary="Планы лечения", response_model=list[dict[str, Any]])
async def get_treatment_plans(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список планов лечения
    """
    try:
        return []
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/treatments", summary="Создать план лечения", response_model=dict[str, Any]
)
async def create_treatment_plan(
    treatment_data: DentalTreatmentRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, Any]:
    """
    Создать новый план лечения
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL,
    )


@router.get(
    "/prosthetics", summary="Протезирование", response_model=list[dict[str, Any]]
)
async def get_prosthetics(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список протезов
    """
    try:
        return []
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/prosthetics", summary="Создать протез", response_model=dict[str, Any])
async def create_prosthetic(
    prosthetic_data: DentalProstheticRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> dict[str, Any]:
    """
    Создать новый протез
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=DENTAL_PERSISTENCE_NOT_IMPLEMENTED_DETAIL,
    )


@router.get("/xray", summary="Рентгеновские снимки", response_model=dict[str, Any])
async def get_xray_images(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    patient_id: int | None = None,
) -> dict[str, Any]:
    """
    Получить рентгеновские снимки пациента
    """
    try:
        return {
            "message": "Модуль рентгеновских снимков будет доступен в следующей версии"
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/price-override",
    summary="Указать цену после лечения",
    response_model=DentalPriceOverrideResponse,
)
async def create_dental_price_override(
    override_data: DentalPriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
) -> DentalPriceOverrideResponse:
    """
    Стоматолог указывает цену после проведенного лечения
    """
    service = DentalApiService(db)
    try:
        price_override = await service.create_dental_price_override(
            override_data=override_data,
            user=user,
        )
        return DentalPriceOverrideResponse(
            id=price_override.id,
            visit_id=price_override.visit_id,
            service_id=price_override.service_id,
            original_price=price_override.original_price,
            new_price=price_override.new_price,
            reason=price_override.reason,
            details=price_override.details,
            status=price_override.status,
            treatment_completed=override_data.treatment_completed,
            created_at=price_override.created_at,
        )
    except DentalApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        service.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/price-overrides",
    summary="Получить изменения цен стоматолога",
    response_model=list[DentalPriceOverrideResponse],
)
async def get_dental_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles(*DENTAL_CLINICIAN_ROLES)),
    visit_id: int | None = Query(None, description="ID визита"),
    status: str | None = Query(
        None, description="Статус (pending, approved, rejected)"
    ),
    limit: int = Query(50, ge=1, le=100),
) -> list[DentalPriceOverrideResponse]:
    """
    Получить список изменений цен стоматолога
    """
    try:
        overrides = DentalApiService(db).get_dental_price_overrides(
            user_id=user.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )
        return [
            DentalPriceOverrideResponse(
                id=override.id,
                visit_id=override.visit_id,
                service_id=override.service_id,
                original_price=override.original_price,
                new_price=override.new_price,
                reason=override.reason,
                details=override.details,
                status=override.status,
                treatment_completed=True,
                created_at=override.created_at,
            )
            for override in overrides
        ]
    except DentalApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


class PriceOverrideApprovalRequest(BaseModel):
    action: str
    rejection_reason: str | None = None


@router.put(
    "/price-override/{override_id}/approve",
    summary="Одобрить/отклонить изменение цены",
    response_model=dict[str, Any],
)
async def approve_price_override(
    override_id: int,
    approval_data: PriceOverrideApprovalRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Одобрить или отклонить изменение цены стоматологом
    Доступно только для регистраторов и администраторов
    """
    service = DentalApiService(db)
    try:
        return await service.approve_price_override(
            override_id=override_id,
            approval_data=approval_data,
            user=user,
        )
    except DentalApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        service.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/price-overrides/pending",
    summary="Получить ожидающие одобрения изменения цен",
    response_model=dict[str, Any],
)
async def get_pending_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Получить список изменений цен, ожидающих одобрения
    Доступно только для регистраторов и администраторов
    """
    try:
        return DentalApiService(db).get_pending_price_overrides(limit=limit)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
