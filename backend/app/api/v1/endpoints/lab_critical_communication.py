"""Laboratory follow-through and explicit clinical acknowledgment."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.api.v1.endpoints.lab_reporting import _doctor_allowed_visit_ids
from app.core.roles import normalize_role_value
from app.models.lab import LabReportInstance
from app.models.lab_critical_communication import LabCriticalCommunication
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.lab_critical_communication import (
    acknowledge,
    assign_responsible_doctor,
    escalate,
)
from app.services.lab_reporting import LabReportingDomainError

router = APIRouter(
    prefix="/lab/critical-communications", tags=["lab-critical-communications"]
)
Db = Annotated[Session, Depends(get_db)]
Staff = Annotated[User, Depends(require_active_roles("Admin", "Lab", "Doctor"))]
Admin = Annotated[User, Depends(require_active_roles("Admin"))]
Doctor = Annotated[User, Depends(require_active_roles("Doctor"))]


class CommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_instance_id: int
    supersedes_communication_id: int | None
    state: Literal[
        "needs_assignment",
        "pending",
        "inbox_recorded",
        "escalated",
        "acknowledged",
        "superseded",
    ]
    attempts: int
    created_at: datetime
    inbox_recorded_at: datetime | None
    acknowledged_at: datetime | None
    escalated_at: datetime | None
    available_actions: list[Literal["assign", "escalate", "acknowledge"]] = Field(
        default_factory=list
    )


def _out(task: LabCriticalCommunication, user: User) -> CommunicationOut:
    actions = []
    if task.state not in {"acknowledged", "superseded"}:
        if user.is_superuser or normalize_role_value(user.role) == "admin":
            if task.state in {"needs_assignment", "escalated"}:
                actions.append("assign")
            if task.state != "escalated":
                actions.append("escalate")
        elif user.id == task.recipient_user_id:
            actions.append("acknowledge")
    return CommunicationOut.model_validate(task).model_copy(
        update={"available_actions": actions}
    )


@router.get("", response_model=list[CommunicationOut])
def list_communications(
    db: Db,
    user: Staff,
    response: Response,
    visit_id: Annotated[int | None, Query(gt=0)] = None,
    before_id: Annotated[int | None, Query(gt=0)] = None,
    open_only: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = select(LabCriticalCommunication).join(
        LabReportInstance,
        LabReportInstance.id == LabCriticalCommunication.report_instance_id,
    )
    if not user.is_superuser and normalize_role_value(user.role) not in {"admin", "lab"}:
        if visit_id is None:
            raise HTTPException(422, "Visit is required")
        _doctor_allowed_visit_ids(db, user, requested_visit_ids=[visit_id])
        query = query.where(LabCriticalCommunication.recipient_user_id == user.id)
    if visit_id is not None:
        query = query.where(LabReportInstance.visit_id == visit_id)
    if before_id is not None:
        query = query.where(LabCriticalCommunication.id < before_id)
    if open_only:
        query = query.where(
            LabCriticalCommunication.state.notin_(["acknowledged", "superseded"])
        )
    rows = list(
        db.scalars(query.order_by(LabCriticalCommunication.id.desc()).limit(limit))
    )
    if rows:
        log_audit_event(
            db,
            event_type="LAB_CRITICAL_COMMUNICATION_LIST",
            actor_user_id=user.id,
            actor_role=user.role,
            resource_type="lab_critical_communication",
            action="view",
        )
    response.headers["Cache-Control"] = "private, no-store"
    return [_out(row, user) for row in rows]


@router.post("/{task_id}/assign", response_model=CommunicationOut)
def assign_communication(task_id: int, db: Db, user: Admin):
    try:
        return _out(assign_responsible_doctor(db, task_id, actor_user_id=user.id), user)
    except LabReportingDomainError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


@router.post("/{task_id}/escalate", response_model=CommunicationOut)
def escalate_communication(task_id: int, db: Db, user: Admin):
    try:
        return _out(escalate(db, task_id, actor_user_id=user.id), user)
    except LabReportingDomainError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


@router.post("/{task_id}/acknowledge", response_model=CommunicationOut)
def acknowledge_communication(task_id: int, db: Db, user: Doctor):
    try:
        return _out(acknowledge(db, task_id, actor_user_id=user.id), user)
    except LabReportingDomainError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
