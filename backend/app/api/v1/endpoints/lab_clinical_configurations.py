"""Clinic administration and lab-physician approval for clinical settings."""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.models.lab import LabClinicalConfigurationVersion
from app.models.user import User
from app.services.lab_clinical_configuration_service import (
    ClinicalConfigurationError,
    approve_version,
    create_draft,
    list_versions,
    submit_for_approval,
    update_draft,
)

router = APIRouter()


class ConfigurationMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration_snapshot: dict[str, Any] = Field(default_factory=dict, repr=False)
    primary_lab_physician_user_id: int | None = None
    substitute_lab_physician_user_id: int | None = None


class ConfigurationVersionOut(BaseModel):
    id: int
    version_no: int
    status: str
    configuration_schema_version: int
    configuration_snapshot: dict[str, Any]
    primary_lab_physician_user_id: int | None
    substitute_lab_physician_user_id: int | None
    approved_by_user_id: int | None
    approved_role_code: str | None
    approval_authority_snapshot: dict[str, Any] | None
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    archived_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


def _handle_error(exc: ClinicalConfigurationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code})


async def _read_mutation(request: Request) -> ConfigurationMutation:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2_500_000:
            raise HTTPException(status_code=413, detail={"code": "configuration_request_too_large"})
    try:
        return ConfigurationMutation.model_validate(json.loads(body))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError):
        # Clinical instructions and thresholds must not be copied into API errors.
        raise HTTPException(
            status_code=422, detail={"code": "configuration_request_invalid"}
        ) from None


@router.get(
    "/lab-clinical-configurations",
    response_model=list[ConfigurationVersionOut],
)
def get_clinical_configurations(
    response: Response,
    db: Session = Depends(get_db),
    actor: User = Depends(require_active_roles("Admin", "Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return list_versions(db)


@router.post(
    "/lab-clinical-configurations",
    response_model=ConfigurationVersionOut,
    status_code=201,
)
async def create_clinical_configuration_draft(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = Depends(require_active_roles("Admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    payload = await _read_mutation(request)
    try:
        return create_draft(
            db,
            configuration_snapshot=payload.configuration_snapshot,
            primary_lab_physician_user_id=payload.primary_lab_physician_user_id,
            substitute_lab_physician_user_id=payload.substitute_lab_physician_user_id,
            actor=actor,
        )
    except ClinicalConfigurationError as exc:
        raise _handle_error(exc) from exc


@router.put(
    "/lab-clinical-configurations/{version_id}",
    response_model=ConfigurationVersionOut,
)
async def update_clinical_configuration_draft(
    version_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = Depends(require_active_roles("Admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    payload = await _read_mutation(request)
    try:
        return update_draft(
            db,
            version_id=version_id,
            configuration_snapshot=payload.configuration_snapshot,
            primary_lab_physician_user_id=payload.primary_lab_physician_user_id,
            substitute_lab_physician_user_id=payload.substitute_lab_physician_user_id,
            actor=actor,
        )
    except ClinicalConfigurationError as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/lab-clinical-configurations/{version_id}/submit",
    response_model=ConfigurationVersionOut,
)
def submit_clinical_configuration(
    version_id: int,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = Depends(require_active_roles("Admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return submit_for_approval(db, version_id=version_id, actor=actor)
    except ClinicalConfigurationError as exc:
        raise _handle_error(exc) from exc


@router.post(
    "/lab-clinical-configurations/{version_id}/approve",
    response_model=ConfigurationVersionOut,
)
def approve_clinical_configuration(
    version_id: int,
    response: Response,
    db: Session = Depends(get_db),
    actor: User = Depends(require_active_roles("Lab")),
):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return approve_version(db, version_id=version_id, actor=actor)
    except ClinicalConfigurationError as exc:
        raise _handle_error(exc) from exc


__all__ = ["router"]
