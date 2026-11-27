"""Admin configuration for clinic-specific laboratory equipment adapters."""

import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.models.lab import LabEquipmentIntegrationProfile, LabEquipmentIntegrationProfileVersion
from app.models.user import User
from app.services.lab_equipment_integration_service import (
    IntegrationProfileError,
    approve_analyzer_mapping_version,
    activate_profile_version,
    create_profile,
    create_profile_version,
    list_pending_analyzer_approvals,
    list_profiles,
    record_physical_validation,
    record_simulator_check,
)

router = APIRouter()
AdminActor = Depends(require_active_roles("Admin"))
LabActor = Depends(require_active_roles("Lab"))
LabOrAdminActor = Depends(require_active_roles("Admin", "Lab"))


class IntegrationProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_role: Literal["analyzer", "printer", "label_printer", "scanner", "local_agent"]


class IntegrationProfileVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_key: str = Field(min_length=1, max_length=100)
    protocol_code: str = Field(min_length=1, max_length=64)
    transport_code: str = Field(min_length=1, max_length=32)
    mapping_profile: dict[str, Any] = Field(default_factory=dict)
    transport_settings: dict[str, Any] = Field(default_factory=dict)
    device_settings: dict[str, Any] = Field(default_factory=dict)


class SimulatorCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1_000_000, repr=False)


class SimulatorCheckOut(BaseModel):
    version_id: int = Field(gt=0)
    adapter_key: str = Field(min_length=1, max_length=100)
    status: Literal["PASS"]
    result_count: int = Field(ge=0, le=100)
    evidence_ref: str = Field(pattern=r"^synthetic-test://sha256/[0-9a-f]{64}$")


async def _read_simulator_request(request: Request) -> SimulatorCheckRequest:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 6_000_000:
            raise HTTPException(
                status_code=413, detail={"code": "simulator_request_too_large"}
            )
    try:
        decoded = json.loads(body)
        return SimulatorCheckRequest.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError):
        # Never include the parsed value, Pydantic input, or submitted message in
        # a validation response. Analyzer/device payloads may contain sensitive
        # data even though this endpoint is intended for synthetic probes only.
        raise HTTPException(
            status_code=422, detail={"code": "simulator_request_invalid"}
        ) from None


class PhysicalValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PASS", "FAIL"]
    evidence_ref: str = Field(min_length=1, max_length=255)


class IntegrationProfileVersionOut(BaseModel):
    id: int
    profile_id: int
    version_no: int
    status: str
    adapter_key: str
    protocol_code: str
    transport_code: str
    mapping_profile: dict[str, Any]
    transport_settings: dict[str, Any]
    device_settings: dict[str, Any]
    simulator_validation_status: str
    simulator_validated_at: datetime | None
    simulator_evidence_ref: str | None
    physical_validation_status: str
    physical_validated_at: datetime | None
    physical_validated_by_user_id: int | None
    physical_evidence_ref: str | None
    clinical_approved_by_user_id: int | None
    clinical_approved_at: datetime | None
    clinical_approval_configuration_version_id: int | None
    clinical_approval_authority_snapshot: dict[str, Any] | None
    created_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class IntegrationProfileOut(BaseModel):
    id: int
    equipment_id: int
    device_role: str
    created_at: datetime
    versions: list[IntegrationProfileVersionOut]

    model_config = ConfigDict(from_attributes=True)


class AnalyzerMappingApprovalOut(BaseModel):
    version_id: int
    profile_id: int
    version_no: int
    equipment_id: int
    equipment_name: str
    equipment_model: str | None
    adapter_key: str
    protocol_code: str
    mapping_profile: dict[str, Any]
    simulator_validation_status: str
    simulator_evidence_ref: str | None
    physical_validation_status: str
    physical_evidence_ref: str | None
    created_at: datetime


def _handle_profile_error(exc: IntegrationProfileError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code})


@router.get(
    "/lab-equipment-integrations",
    response_model=list[IntegrationProfileOut],
)
def get_lab_equipment_integrations(
    response: Response,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    response.headers["Cache-Control"] = "private, no-store"
    return list_profiles(db)


@router.get(
    "/lab-equipment-integration-approvals",
    response_model=list[AnalyzerMappingApprovalOut],
)
def get_pending_analyzer_mapping_approvals(
    response: Response,
    db: Session = Depends(get_db),
    actor: User = LabOrAdminActor,
):
    response.headers["Cache-Control"] = "private, no-store"
    return list_pending_analyzer_approvals(db, actor=actor)


@router.post(
    "/lab-equipment-integration-versions/{version_id}/clinical-approval",
    response_model=IntegrationProfileVersionOut,
)
def approve_lab_analyzer_mapping(
    version_id: int,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = LabActor,
):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return approve_analyzer_mapping_version(
            db, version_id=version_id, actor=actor
        )
    except IntegrationProfileError as exc:
        raise _handle_profile_error(exc) from exc


@router.get(
    "/equipment/{equipment_id}/lab-integration",
    response_model=IntegrationProfileOut | None,
)
def get_equipment_lab_integration(
    equipment_id: int,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    response.headers["Cache-Control"] = "private, no-store"
    return next(
        (profile for profile in list_profiles(db) if profile.equipment_id == equipment_id),
        None,
    )


@router.post(
    "/equipment/{equipment_id}/lab-integration",
    response_model=IntegrationProfileOut,
    status_code=201,
)
def register_equipment_lab_integration(
    equipment_id: int,
    payload: IntegrationProfileCreate,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    try:
        profile = create_profile(
            db,
            equipment_id=equipment_id,
            device_role=payload.device_role,
            actor=actor,
        )
    except IntegrationProfileError as exc:
        raise _handle_profile_error(exc) from exc
    return profile


@router.post(
    "/lab-equipment-integrations/{profile_id}/versions",
    response_model=IntegrationProfileVersionOut,
    status_code=201,
)
def create_lab_integration_version(
    profile_id: int,
    payload: IntegrationProfileVersionCreate,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    try:
        return create_profile_version(
            db,
            profile_id=profile_id,
            adapter_key=payload.adapter_key,
            protocol_code=payload.protocol_code,
            transport_code=payload.transport_code,
            mapping_profile=payload.mapping_profile,
            transport_settings=payload.transport_settings,
            device_settings=payload.device_settings,
            actor=actor,
        )
    except IntegrationProfileError as exc:
        raise _handle_profile_error(exc) from exc


@router.post(
    "/lab-equipment-integration-versions/{version_id}/simulator-check",
    response_model=SimulatorCheckOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["message"],
                        "additionalProperties": False,
                        "properties": {
                            "message": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 1000000,
                            }
                        },
                    }
                }
            },
        }
    },
)
async def run_synthetic_simulator_check(
    version_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    response.headers["Cache-Control"] = "private, no-store"
    payload = await _read_simulator_request(request)
    try:
        return record_simulator_check(
            db,
            version_id=version_id,
            payload=payload.message,
            actor=actor,
        )
    except IntegrationProfileError as exc:
        raise _handle_profile_error(exc) from exc


@router.post(
    "/lab-equipment-integration-versions/{version_id}/physical-validation",
    response_model=IntegrationProfileVersionOut,
)
def save_physical_validation(
    version_id: int,
    payload: PhysicalValidationRequest,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    try:
        return record_physical_validation(
            db,
            version_id=version_id,
            status=payload.status,
            evidence_ref=payload.evidence_ref,
            actor=actor,
        )
    except IntegrationProfileError as exc:
        raise _handle_profile_error(exc) from exc


@router.post(
    "/lab-equipment-integration-versions/{version_id}/activate",
    response_model=IntegrationProfileVersionOut,
)
def activate_lab_equipment_integration(
    version_id: int,
    db: Session = Depends(get_db),
    actor: User = AdminActor,
):
    try:
        return activate_profile_version(db, version_id=version_id, actor=actor)
    except IntegrationProfileError as exc:
        raise _handle_profile_error(exc) from exc


__all__ = ["router"]
