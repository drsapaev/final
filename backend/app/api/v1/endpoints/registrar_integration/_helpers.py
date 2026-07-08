"""Registrar integration helpers, constants, utilities.

Split from registrar_integration.py (3509 LOC → modular).
"""
from __future__ import annotations

"""
API endpoints для интеграции регистратуры с админ панелью
Основа: detail.md стр. 85-183
"""

import logging  # noqa: F401
from datetime import UTC, date, datetime  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401
from sqlalchemy import and_, func, text  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import get_db, require_roles  # noqa: F401
from app.crud import clinic as crud_clinic  # noqa: F401
from app.crud import online_queue as crud_queue  # noqa: F401
from app.models.department import Department, DepartmentService  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.canonical_visit_service import (  # noqa: F401
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.queue_service import queue_service  # noqa: F401
from app.services.service_mapping import (  # noqa: F401
    get_service_code,
    resolve_queue_group_key,
)

# [OK] Используем прямой SQL вместо импорта модели для избежания конфликта DailyQueue
# Проблема: DailyQueue определен в двух местах (queue_old.py и online_queue.py)
# Решение: используем прямой SQL запрос через text() для доступа к queue_entries без импорта модели

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_queue_status_for_registrar(raw_status: str | None) -> str:
    """Keep payment state out of the operational queue status shown to registrars."""
    if not raw_status or raw_status == "paid":
        return "waiting"
    return raw_status


REGISTRAR_PAYMENT_ROLES = {"admin", "registrar", "cashier"}
REGISTRAR_DOCTOR_ACTION_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "cardiologist",
    "derma",
    "dermatologist",
    "dentist",
    "lab",
}
REGISTRAR_START_VISIT_ROLES = REGISTRAR_DOCTOR_ACTION_ROLES
REGISTRAR_PRINT_TICKET_ROLES = {"admin", "registrar", "cashier", "doctor"}
REGISTRAR_COMPLETE_ROLES = REGISTRAR_DOCTOR_ACTION_ROLES
REGISTRAR_CANCEL_ROLES = {"admin", "registrar", "cashier", "receptionist", "doctor"}
REGISTRAR_DOCTOR_SECONDARY_ACTION_ROLES = REGISTRAR_DOCTOR_ACTION_ROLES
REGISTRAR_START_STATUSES = {"waiting", "queued"}
REGISTRAR_PRINT_STATUSES = {"waiting", "queued"}
REGISTRAR_COMPLETE_STATUSES = {"called", "in_cabinet", "in_progress"}
REGISTRAR_CANCEL_BLOCKED_STATUSES = {"canceled", "cancelled", "completed", "done", "served"}
REGISTRAR_HIDDEN_QUEUE_STATUSES = {"canceled", "cancelled", "no_show"}
REGISTRAR_VIEW_EMR_STATUSES = {"completed", "done", "served"}
REGISTRAR_SCHEDULE_NEXT_STATUSES = {"completed", "done", "served"}


def _registrar_user_role_names(user: User | None) -> set[str]:
    role_names: set[str] = set()
    primary_role = getattr(user, "role", None)
    if primary_role:
        role_names.add(str(primary_role).strip().lower())

    for role in getattr(user, "roles", None) or []:
        role_name = getattr(role, "name", None)
        if role_name:
            role_names.add(str(role_name).strip().lower())

    return role_names


def _registrar_can_mark_paid(user: User | None, payment_status: str | None) -> bool:
    if str(payment_status or "").strip().lower() == "paid":
        return False
    return bool(_registrar_user_role_names(user) & REGISTRAR_PAYMENT_ROLES)


def _registrar_can_start_visit(user: User | None, queue_status: str | None) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        normalized_status in REGISTRAR_START_STATUSES
        and bool(_registrar_user_role_names(user) & REGISTRAR_START_VISIT_ROLES)
    )


def _registrar_can_print_ticket(
    user: User | None,
    *,
    payment_status: str | None,
    queue_status: str | None,
) -> bool:
    normalized_payment_status = str(payment_status or "").strip().lower()
    normalized_queue_status = str(queue_status or "").strip().lower()
    return (
        (
            normalized_payment_status == "paid"
            or normalized_queue_status in REGISTRAR_PRINT_STATUSES
        )
        and bool(_registrar_user_role_names(user) & REGISTRAR_PRINT_TICKET_ROLES)
    )


def _registrar_can_complete(user: User | None, queue_status: str | None) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        normalized_status in REGISTRAR_COMPLETE_STATUSES
        and bool(_registrar_user_role_names(user) & REGISTRAR_COMPLETE_ROLES)
    )


def _registrar_can_cancel(user: User | None, queue_status: str | None) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        normalized_status not in REGISTRAR_CANCEL_BLOCKED_STATUSES
        and bool(_registrar_user_role_names(user) & REGISTRAR_CANCEL_ROLES)
    )


def _registrar_can_view_emr(
    user: User | None,
    *,
    payment_status: str | None,
    queue_status: str | None,
    visit_id: int | None,
) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    normalized_payment_status = str(payment_status or "").strip().lower()
    status_allows_view = (
        normalized_status in REGISTRAR_VIEW_EMR_STATUSES
        or (normalized_status == "in_visit" and normalized_payment_status == "paid")
    )
    return (
        visit_id is not None
        and status_allows_view
        and bool(
            _registrar_user_role_names(user)
            & REGISTRAR_DOCTOR_SECONDARY_ACTION_ROLES
        )
    )


def _registrar_can_schedule_next(
    user: User | None,
    *,
    queue_status: str | None,
    patient_id: int | None,
) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        patient_id is not None
        and normalized_status in REGISTRAR_SCHEDULE_NEXT_STATUSES
        and bool(
            _registrar_user_role_names(user)
            & REGISTRAR_DOCTOR_SECONDARY_ACTION_ROLES
        )
    )


def _registrar_available_actions(
    *,
    user: User | None,
    payment_status: str | None,
    queue_status: str | None,
    visit_id: int | None = None,
    patient_id: int | None = None,
) -> list[str]:
    actions: list[str] = []
    if _registrar_can_mark_paid(user, payment_status):
        actions.append("mark_paid")
    if _registrar_can_start_visit(user, queue_status):
        actions.append("start_visit")
    if _registrar_can_print_ticket(
        user,
        payment_status=payment_status,
        queue_status=queue_status,
    ):
        actions.append("print_ticket")
    if _registrar_can_complete(user, queue_status):
        actions.append("complete")
    if _registrar_can_cancel(user, queue_status):
        actions.append("cancel")
    if _registrar_can_view_emr(
        user,
        payment_status=payment_status,
        queue_status=queue_status,
        visit_id=visit_id,
    ):
        actions.append("view_emr")
    if _registrar_can_schedule_next(
        user,
        queue_status=queue_status,
        patient_id=patient_id,
    ):
        actions.append("schedule_next")
    return actions


REGISTRATION_DISCOUNT_MODES = {"none", "repeat", "benefit", "all_free"}


def _normalize_registration_discount_mode(raw_value: str | None) -> str:
    """Registrar payloads expose registration type only, never payment markers."""
    normalized = str(raw_value or "none").strip().lower()
    if normalized in REGISTRATION_DISCOUNT_MODES:
        return normalized
    return "none"


def _serialize_registrar_datetime(value: Any) -> str | None:
    """Serialize registrar timestamps without corrupting timezone semantics."""
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.isoformat()

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            return normalized
        if "T" in normalized:
            try:
                parsed = datetime.fromisoformat(normalized)
                return parsed.isoformat()
            except ValueError:
                return normalized
        return normalized

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return None

    return str(value)


def _is_newer_lab_report_instance(candidate: Any, current: Any | None) -> bool:
    if current is None:
        return True

    def sort_key(instance: Any) -> tuple[float, int]:
        created_at = getattr(instance, "created_at", None)
        if isinstance(created_at, datetime):
            timestamp = created_at.timestamp()
        else:
            timestamp = 0.0
        return (timestamp, getattr(instance, "id", 0) or 0)

    return sort_key(candidate) > sort_key(current)


def _lab_report_summary_for_registrar(service: Any, instance: Any) -> dict[str, Any]:
    sections = service.materialize_instance(instance)
    severity = service.summarize_instance_severity(sections)
    available_actions = service.instance_available_actions(instance)
    template = getattr(instance, "template", None)
    return {
        "id": instance.id,
        "status": instance.status,
        "template_id": instance.template_id,
        "template_version_id": instance.template_version_id,
        "template_name": getattr(template, "name", None),
        "created_at": _serialize_registrar_datetime(instance.created_at),
        "finalized_at": _serialize_registrar_datetime(instance.finalized_at),
        "printed_at": _serialize_registrar_datetime(instance.printed_at),
        "flagged_findings_count": severity["flagged_findings_count"],
        "critical_findings_count": severity["critical_findings_count"],
        "max_flag_severity": severity["max_flag_severity"],
        "available_actions": available_actions,
        **service.instance_action_flags(instance),
    }


def _latest_lab_report_summaries_by_visit(
    db: Session,
    visit_ids: set[int],
) -> dict[int, dict[str, Any]]:
    if not visit_ids:
        return {}

    from app.services.lab_reporting_service import LabReportingService

    service = LabReportingService(db)
    instances = service.list_instances(
        patient_id=None,
        visit_ids=sorted(visit_ids),
        status=None,
        limit=max(len(visit_ids) * 20, 500),
        offset=0,
    )
    latest_by_visit: dict[int, Any] = {}
    for instance in instances:
        visit_id = getattr(instance, "visit_id", None)
        if not visit_id:
            continue
        if _is_newer_lab_report_instance(instance, latest_by_visit.get(visit_id)):
            latest_by_visit[visit_id] = instance

    return {
        visit_id: _lab_report_summary_for_registrar(service, instance)
        for visit_id, instance in latest_by_visit.items()
    }


def _resolve_payment_truth(
    db: Session,
    *,
    visit_id: int | None = None,
    legacy_paid_at: datetime | None = None,
) -> tuple[str, str | None]:
    """Resolve payment status/method from payments, with a narrow legacy fallback."""
    if visit_id:
        try:
            from app.models.payment import Payment

            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )
            if payment:
                status = (
                    "paid"
                    if (
                        str(getattr(payment, "status", "") or "").lower() == "paid"
                        or getattr(payment, "paid_at", None)
                    )
                    else "pending"
                )
                method = getattr(payment, "method", None) or None
                return status, method
        except Exception:
            logger.debug(
                "registrar_integration: failed to resolve payment truth for visit",
                exc_info=True,
            )

    return ("paid", None) if legacy_paid_at else ("pending", None)


def _raise_registrar_internal_error(action: str, exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc

    logger.exception(
        "registrar_integration: unexpected error during %s (%s)",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )

# ===================== ОТДЕЛЕНИЯ ДЛЯ РЕГИСТРАТУРЫ =====================

