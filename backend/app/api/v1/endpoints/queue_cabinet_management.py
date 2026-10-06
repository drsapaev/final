"""
API endpoints для управления информацией о кабинетах в очередях
"""

import logging
from datetime import date, datetime
from typing import Annotated, Any, Literal, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud.clinic import clinic_today
from app.models.user import User
from app.services.queue_cabinet_management_api_service import (
    QueueCabinetManagementApiService,
    QueueCabinetManagementDomainError,
)
from app.services.queue_domain_service import QueueDomainReadError, QueueDomainService

logger = logging.getLogger(__name__)

router = APIRouter()


def _raise_queue_cabinet_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.error(
        "Queue cabinet management endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


def _parse_day_query(day: str | None) -> date | None:
    if day is None:
        return None
    try:
        return datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc


# ===================== МОДЕЛИ ДАННЫХ =====================


class CabinetInfo(BaseModel):
    cabinet_number: str | None = None
    cabinet_floor: int | None = None
    cabinet_building: str | None = None


class QueueCabinetUpdateRequest(BaseModel):
    queue_id: int
    cabinet_info: CabinetInfo


class QueueCabinetResponse(BaseModel):
    id: int
    day: str
    owner_type: Literal["doctor", "resource"]
    owner_id: int
    owner_name: str
    owner_default_cabinet: str | None
    queue_resource_id: int | None
    # QD-2C (Codex round-8 P1): ресурсные очереди (specialist NULL)
    # — врач-ось отсутствует по дизайну, владелец = реестр
    specialist_id: int | None
    specialist_name: str
    queue_tag: str | None
    cabinet_number: str | None
    doctor_cabinet: str | None
    effective_cabinet: str | None
    cabinet_floor: int | None
    cabinet_building: str | None
    entries_count: int
    active: bool
    linked_doctor_found: bool
    doctor_has_cabinet: bool
    sync_status: str
    integrity_warnings: list[str]


class BulkCabinetUpdateRequest(BaseModel):
    updates: list[QueueCabinetUpdateRequest]


class CabinetReassignmentPreviewRequest(BaseModel):
    queue_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(
        min_length=1,
        json_schema_extra={"uniqueItems": True},
    )
    new_cabinet_number: str | None = Field(max_length=20)

    @field_validator("queue_ids")
    @classmethod
    def validate_queue_ids(cls, value: list[int]) -> list[int]:
        if (
            not value
            or any(queue_id <= 0 for queue_id in value)
            or len(set(value)) != len(value)
        ):
            raise ValueError("queue_ids must contain unique positive IDs")
        return value

    @field_validator("new_cabinet_number")
    @classmethod
    def validate_new_cabinet_number(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("new_cabinet_number cannot be blank")
        return normalized


class CabinetReassignmentPreviewError(BaseModel):
    detail: str


class CabinetReassignmentPreviewItem(BaseModel):
    queue_id: int
    queue_day: date
    owner_type: Literal["doctor", "resource"]
    owner_id: int
    owner_name: str
    owner_default_cabinet: str | None
    old_cabinet_number: str | None
    new_cabinet_number: str | None
    waiting_count: int
    blocking_reasons: list[
        Literal[
            "patient_called",
            "clinical_work_in_progress",
            "active_service_execution",
        ]
    ]
    can_apply: bool


class CabinetReassignmentPreviewResponse(BaseModel):
    clinic_day: date
    items: list[CabinetReassignmentPreviewItem]
    can_apply: bool


class CabinetReassignmentApplyTarget(BaseModel):
    queue_id: Annotated[int, Field(gt=0, strict=True)]
    expected_owner_type: Literal["doctor", "resource"]
    expected_owner_id: Annotated[int, Field(gt=0, strict=True)]
    expected_cabinet_number: str | None = Field(..., max_length=20)


class CabinetReassignmentApplyRequest(BaseModel):
    targets: list[CabinetReassignmentApplyTarget] = Field(min_length=1)
    new_cabinet_number: str | None = Field(..., max_length=20)
    reason_code: Literal[
        "room_unavailable",
        "equipment_issue",
        "schedule_change",
        "administrative_correction",
    ]

    @field_validator("targets")
    @classmethod
    def validate_unique_targets(
        cls, value: list[CabinetReassignmentApplyTarget]
    ) -> list[CabinetReassignmentApplyTarget]:
        queue_ids = [target.queue_id for target in value]
        if not queue_ids or len(set(queue_ids)) != len(queue_ids):
            raise ValueError("targets must contain unique queue IDs")
        return value

    @field_validator("new_cabinet_number")
    @classmethod
    def normalize_new_cabinet(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("new_cabinet_number cannot be blank")
        return normalized


class CabinetReassignmentApplyResponse(BaseModel):
    clinic_day: date
    changed_queue_ids: list[int]
    unchanged_queue_ids: list[int]
    applied_at: datetime


class CabinetReassignmentApplyError(BaseModel):
    detail: str
    code: (
        Literal[
            "idempotency_in_flight",
            "idempotency_payload_mismatch",
            "idempotency_uncertain_outcome",
        ]
        | None
    ) = None


class CabinetReassignmentIdempotencyError(BaseModel):
    code: Literal["idempotency_key_invalid", "idempotency_unavailable"]
    detail: str


class QueueCabinetMutationError(BaseModel):
    detail: str


# ===================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================


@router.get("/queues/cabinet-info", response_model=list[QueueCabinetResponse])
def get_queues_cabinet_info(
    day: str | None = Query(
        None,
        description="Дата в формате YYYY-MM-DD; по умолчанию текущий день клиники",
    ),
    specialist_id: int | None = Query(None, description="ID специалиста"),
    cabinet_number: str | None = Query(None, description="Номер кабинета"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить информацию о кабинетах для очередей
    """
    try:
        requested_day = _parse_day_query(day)
        payload = QueueDomainService(db).list_queue_cabinet_info(
            day=requested_day if requested_day is not None else clinic_today(db),
            specialist_id=specialist_id,
            cabinet_number=cabinet_number,
        )
        return [QueueCabinetResponse(**item) for item in payload]
    except QueueDomainReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("get_queues_cabinet_info", exc)


@router.get("/queues/{queue_id}/cabinet-info", response_model=QueueCabinetResponse)
def get_queue_cabinet_info(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить информацию о кабинете для конкретной очереди
    """
    try:
        payload = QueueDomainService(db).get_queue_cabinet_info(queue_id=queue_id)
        return QueueCabinetResponse(**payload)
    except QueueDomainReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("get_queue_cabinet_info", exc)


# ===================== ОБНОВЛЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================


@router.post(
    "/queues/cabinet-info/preview",
    response_model=CabinetReassignmentPreviewResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": CabinetReassignmentPreviewError,
            "description": "Authentication is required.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": CabinetReassignmentPreviewError,
            "description": "The caller must have the Admin role.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": CabinetReassignmentPreviewError,
            "description": "One or more requested queues were not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": CabinetReassignmentPreviewError,
            "description": "A target is not for clinic-local today or its owner is unavailable.",
        },
    },
)
def preview_cabinet_reassignment(
    request: CabinetReassignmentPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Preview an explicit same-day cabinet reassignment without writing state."""
    try:
        payload = QueueCabinetManagementApiService(db).preview_cabinet_reassignment(
            queue_ids=request.queue_ids,
            new_cabinet_number=request.new_cabinet_number,
        )
        return CabinetReassignmentPreviewResponse(**payload)
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("preview_cabinet_reassignment", exc)


@router.post(
    "/queues/cabinet-info/apply",
    response_model=CabinetReassignmentApplyResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": CabinetReassignmentIdempotencyError,
            "description": "The idempotency key exceeds the middleware limit.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": CabinetReassignmentApplyError,
            "description": "Authentication is required.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": CabinetReassignmentApplyError,
            "description": "The caller must have the Admin role.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": CabinetReassignmentApplyError,
            "description": "One or more requested queues were not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": CabinetReassignmentApplyError,
            "description": "Queue state changed or an active patient/clinical operation blocks reassignment.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": CabinetReassignmentApplyError,
            "description": "The reassignment or its mandatory audit could not be committed.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": CabinetReassignmentIdempotencyError,
            "description": "Required idempotency coordination is unavailable; no command is executed.",
        },
    },
)
def apply_cabinet_reassignment(
    request: CabinetReassignmentApplyRequest,
    http_request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Apply an explicit same-day reassignment; middleware provides keyed replay."""
    # The key is required so the global middleware can bind/replay this command.
    # It is intentionally neither persisted nor logged by this endpoint.
    _ = idempotency_key
    service = QueueCabinetManagementApiService(db)
    try:
        payload = service.apply_cabinet_reassignment(
            targets=[target.model_dump() for target in request.targets],
            new_cabinet_number=request.new_cabinet_number,
            reason_code=request.reason_code,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            request_id=getattr(http_request.state, "request_id", "unknown"),
        )
        return CabinetReassignmentApplyResponse(**payload)
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("apply_cabinet_reassignment", exc)


@router.put(
    "/queues/{queue_id}/cabinet-info",
    response_model=dict[str, Any],
    responses={
        status.HTTP_409_CONFLICT: {
            "model": QueueCabinetMutationError,
            "description": "Existing daily queue cabinet snapshots can only be changed with the explicit reassignment command.",
        }
    },
)
def update_queue_cabinet_info(
    queue_id: int,
    cabinet_info: CabinetInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Обновить информацию о кабинете для очереди
    Доступно только администраторам и регистраторам
    """
    service = QueueCabinetManagementApiService(db)
    try:
        return service.update_queue_cabinet_info(
            queue_id=queue_id,
            cabinet_info=(
                cabinet_info.model_dump(exclude_unset=True)
                if hasattr(cabinet_info, "model_dump")
                else cabinet_info.dict(exclude_unset=True)
            ),
            updated_by=current_user.username,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("update_queue_cabinet_info", exc)


@router.put("/queues/cabinet-info/bulk", response_model=dict[str, Any])
def bulk_update_cabinet_info(
    request: BulkCabinetUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Массовое обновление информации о кабинетах для нескольких очередей
    """
    service = QueueCabinetManagementApiService(db)
    try:
        updates = (
            request.model_dump(exclude_unset=True)["updates"]
            if hasattr(request, "model_dump")
            else request.dict(exclude_unset=True)["updates"]
        )
        return service.bulk_update_cabinet_info(
            updates=updates,
            updated_by=current_user.username,
        )
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("bulk_update_cabinet_info", exc)


# ===================== СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ DOCTORS =====================


@router.post(
    "/queues/sync-cabinet-info",
    response_model=dict[str, Any],
    responses={
        status.HTTP_409_CONFLICT: {
            "model": QueueCabinetMutationError,
            "description": "Legacy synchronization into existing daily queues is disabled.",
        }
    },
)
def sync_cabinet_info_from_doctors(
    day: str | None = Query(
        None, description="Deprecated: existing daily queue snapshots are read-only"
    ),
    specialist_id: int | None = Query(None, description="ID конкретного специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Keep the route for compatibility; callers receive 409 because queue-day
    cabinet snapshots are no longer synchronized from owner defaults.
    """
    service = QueueCabinetManagementApiService(db)
    try:
        return service.sync_cabinet_info_from_doctors(
            day=day,
            specialist_id=specialist_id,
            synced_by=current_user.username,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("sync_cabinet_info_from_doctors", exc)


# ===================== СТАТИСТИКА ПО КАБИНЕТАМ =====================


@router.get("/queues/cabinet-statistics", response_model=dict[str, Any])
def get_cabinet_statistics(
    date_from: str | None = Query(None, description="Дата начала в формате YYYY-MM-DD"),
    date_to: str | None = Query(
        None, description="Дата окончания в формате YYYY-MM-DD"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить статистику использования кабинетов
    """
    try:
        return QueueCabinetManagementApiService(db).get_cabinet_statistics(
            date_from=date_from,
            date_to=date_to,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("get_cabinet_statistics", exc)
