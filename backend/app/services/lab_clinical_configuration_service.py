"""Versioned, clinic-owned clinical settings for laboratory result evaluation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lab import LabClinicalConfigurationVersion
from app.models.user import User
from app.services.audit_service import log_audit_event

CLINICAL_SECTIONS = (
    "method_instructions",
    "reference_intervals",
    "critical_values",
    "qc_rules",
)
DISPOSITION_SECTIONS = ("reference_intervals", "critical_values", "qc_rules")
CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
SECRET_KEYS = {"password", "secret", "token", "credential", "authorization", "privatekey"}


class ClinicalConfigurationError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _reject_sensitive_configuration(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(part in normalized for part in SECRET_KEYS) or normalized in {
                "patientid", "patientname", "dateofbirth", "mrn", "accessionid"
            }:
                raise ClinicalConfigurationError("sensitive_configuration_field_forbidden")
            _reject_sensitive_configuration(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_configuration(nested)


def _required_code(item: dict[str, Any], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not CODE.fullmatch(value):
        raise ClinicalConfigurationError("invalid_configuration_snapshot")
    return value


def _optional_text(item: dict[str, Any], name: str, *, max_length: int = 1000) -> None:
    value = item.get(name)
    if value is not None and (
        not isinstance(value, str) or len(value.strip()) > max_length
    ):
        raise ClinicalConfigurationError("invalid_configuration_snapshot")


def _finite_number(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return Decimal(str(value)).is_finite()
    except (InvalidOperation, ValueError):
        return False


def normalize_configuration_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Validate data-only clinical configuration; no clinic values are seeded."""
    if snapshot is None:
        snapshot = {}
    if not isinstance(snapshot, dict):
        raise ClinicalConfigurationError("invalid_configuration_snapshot")
    _reject_sensitive_configuration(snapshot)
    if set(snapshot) - {
        *CLINICAL_SECTIONS,
        "not_applicable_reasons",
    }:
        raise ClinicalConfigurationError("invalid_configuration_snapshot")
    normalized = {section: snapshot.get(section, []) for section in CLINICAL_SECTIONS}
    reasons = snapshot.get("not_applicable_reasons", {})
    if not isinstance(reasons, dict) or set(reasons) - set(DISPOSITION_SECTIONS):
        raise ClinicalConfigurationError("invalid_configuration_snapshot")
    normalized_reasons: dict[str, str] = {}
    for section, reason in reasons.items():
        if not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 1000:
            raise ClinicalConfigurationError("invalid_configuration_snapshot")
        normalized_reasons[section] = reason.strip()
    normalized["not_applicable_reasons"] = normalized_reasons

    allowed_fields = {
        "method_instructions": {
            "method_code", "method_version", "language_code", "instruction_text", "source_ref"
        },
        "reference_intervals": {
            "rule_code", "analyte_code", "method_code", "unit_code", "material_code",
            "sex", "age_min_months", "age_max_months", "low", "high", "warning_low",
            "warning_high", "critical_low", "critical_high", "text", "source_ref",
        },
        "critical_values": {
            "rule_code", "analyte_code", "method_code", "unit_code", "material_code",
            "sex", "age_min_months", "age_max_months", "direction", "threshold", "source_ref",
        },
        "qc_rules": {"rule_code", "method_code", "rule_type", "configuration", "source_ref"},
    }
    required_fields = {
        "method_instructions": {"method_code", "method_version", "instruction_text", "source_ref"},
        "reference_intervals": {"rule_code", "analyte_code", "method_code", "unit_code", "source_ref"},
        "critical_values": {"rule_code", "analyte_code", "method_code", "unit_code", "direction", "threshold", "source_ref"},
        "qc_rules": {"rule_code", "method_code", "rule_type", "configuration", "source_ref"},
    }

    for section in CLINICAL_SECTIONS:
        entries = normalized[section]
        if not isinstance(entries, list) or len(entries) > 1000:
            raise ClinicalConfigurationError("invalid_configuration_snapshot")
        seen_codes: set[str] = set()
        normalized_entries = []
        for raw in entries:
            if not isinstance(raw, dict) or set(raw) - allowed_fields[section]:
                raise ClinicalConfigurationError("invalid_configuration_snapshot")
            if not required_fields[section] <= set(raw):
                raise ClinicalConfigurationError("invalid_configuration_snapshot")
            item = dict(raw)
            code_field = "method_code" if section == "method_instructions" else "rule_code"
            code = _required_code(item, code_field)
            if section != "method_instructions":
                if code in seen_codes:
                    raise ClinicalConfigurationError("duplicate_clinical_rule_code")
                seen_codes.add(code)
            if section == "method_instructions":
                _required_code(item, "method_version")
                if not isinstance(item.get("instruction_text"), str) or not item["instruction_text"].strip():
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
                _optional_text(item, "instruction_text", max_length=10000)
            elif section == "reference_intervals":
                _required_code(item, "analyte_code")
                _required_code(item, "method_code")
                _required_code(item, "unit_code")
                _validate_conditions(item)
                bounds = [item.get(key) for key in ("low", "high", "warning_low", "warning_high", "critical_low", "critical_high")]
                if not any(value is not None for value in bounds) or any(
                    value is not None and not _finite_number(value) for value in bounds
                ):
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
                if item.get("low") is not None and item.get("high") is not None and item["low"] > item["high"]:
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
                if item.get("critical_low") is not None and item.get("low") is not None and item["critical_low"] > item["low"]:
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
                if item.get("critical_high") is not None and item.get("high") is not None and item["critical_high"] < item["high"]:
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
                _optional_text(item, "text", max_length=500)
            elif section == "critical_values":
                _required_code(item, "analyte_code")
                _required_code(item, "method_code")
                _required_code(item, "unit_code")
                _validate_conditions(item)
                if item.get("direction") not in {"below", "above"} or not _finite_number(item.get("threshold")):
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
            else:
                _required_code(item, "method_code")
                _required_code(item, "rule_type")
                if not isinstance(item.get("configuration"), dict):
                    raise ClinicalConfigurationError("invalid_configuration_snapshot")
                try:
                    json.dumps(item["configuration"], allow_nan=False)
                except (TypeError, ValueError) as exc:
                    raise ClinicalConfigurationError("invalid_configuration_snapshot") from exc

            if "language_code" in item:
                _required_code(item, "language_code")
            for source_name in ("source_ref", "material_code", "sex"):
                _optional_text(item, source_name, max_length=300)
            source_ref = item.get("source_ref")
            if not isinstance(source_ref, str) or not source_ref.strip():
                raise ClinicalConfigurationError("clinical_source_reference_required")
            if section != "method_instructions" and not CODE.fullmatch(str(item.get("unit_code", ""))):
                raise ClinicalConfigurationError("invalid_configuration_snapshot")
            normalized_entries.append(item)
        normalized[section] = normalized_entries

    try:
        serialized = json.dumps(normalized, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ClinicalConfigurationError("invalid_configuration_snapshot") from exc
    if len(serialized.encode("utf-8")) > 2_000_000:
        raise ClinicalConfigurationError("configuration_snapshot_too_large", 413)
    return normalized


def _validate_conditions(item: dict[str, Any]) -> None:
    minimum = item.get("age_min_months")
    maximum = item.get("age_max_months")
    if (minimum is not None and (type(minimum) is not int or minimum < 0)) or (
        maximum is not None and (type(maximum) is not int or maximum < 0)
    ):
        raise ClinicalConfigurationError("invalid_configuration_snapshot")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ClinicalConfigurationError("invalid_configuration_snapshot")
    _optional_text(item, "sex", max_length=32)
    _optional_text(item, "material_code", max_length=64)


def _validate_assignee(db: Session, user_id: int | None) -> User | None:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None or user.role != "Lab":
        raise ClinicalConfigurationError("assigned_lab_physician_role_required", 422)
    if not user.is_active:
        raise ClinicalConfigurationError("assigned_lab_physician_must_be_active", 422)
    return user


def _validate_assignments(
    db: Session, primary_user_id: int | None, substitute_user_id: int | None
) -> None:
    if primary_user_id is not None and substitute_user_id == primary_user_id:
        raise ClinicalConfigurationError("substitute_must_differ_from_primary")
    _validate_assignee(db, primary_user_id)
    _validate_assignee(db, substitute_user_id)


def _audit(
    db: Session,
    actor: User,
    version: LabClinicalConfigurationVersion,
    action: str,
    reason_code: str,
    *,
    extra_data: dict[str, Any] | None = None,
) -> None:
    log_audit_event(
        db,
        event_type=f"LAB_CLINICAL_CONFIGURATION_{action.upper()}",
        actor_user_id=actor.id,
        actor_role=actor.role,
        resource_type="lab_clinical_configuration_version",
        resource_id=str(version.id),
        action=action,
        outcome="success",
        reason_code={"code": reason_code},
        extra_data=extra_data,
    )


def list_versions(db: Session) -> list[LabClinicalConfigurationVersion]:
    return list(
        db.scalars(
            select(LabClinicalConfigurationVersion).order_by(
                LabClinicalConfigurationVersion.version_no.desc()
            )
        ).all()
    )


def _get_locked_version(
    db: Session, version_id: int
) -> LabClinicalConfigurationVersion | None:
    return db.scalar(
        select(LabClinicalConfigurationVersion)
        .where(LabClinicalConfigurationVersion.id == version_id)
        .with_for_update()
    )


def get_current_approved_configuration(
    db: Session,
) -> LabClinicalConfigurationVersion | None:
    return db.scalar(
        select(LabClinicalConfigurationVersion).where(
            LabClinicalConfigurationVersion.status == "APPROVED"
        )
    )


def create_draft(
    db: Session,
    *,
    configuration_snapshot: dict[str, Any],
    primary_lab_physician_user_id: int | None,
    substitute_lab_physician_user_id: int | None,
    actor: User,
) -> LabClinicalConfigurationVersion:
    _validate_assignments(db, primary_lab_physician_user_id, substitute_lab_physician_user_id)
    snapshot = normalize_configuration_snapshot(configuration_snapshot)
    current_version = db.scalar(select(func.max(LabClinicalConfigurationVersion.version_no))) or 0
    version = LabClinicalConfigurationVersion(
        version_no=current_version + 1,
        status="DRAFT",
        configuration_schema_version=1,
        configuration_snapshot=snapshot,
        primary_lab_physician_user_id=primary_lab_physician_user_id,
        substitute_lab_physician_user_id=substitute_lab_physician_user_id,
        created_by_user_id=actor.id,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ClinicalConfigurationError("configuration_version_conflict", 409) from exc
    _audit(db, actor, version, "created", "draft_created")
    db.commit()
    db.refresh(version)
    return version


def update_draft(
    db: Session,
    *,
    version_id: int,
    configuration_snapshot: dict[str, Any],
    primary_lab_physician_user_id: int | None,
    substitute_lab_physician_user_id: int | None,
    actor: User,
) -> LabClinicalConfigurationVersion:
    version = _get_locked_version(db, version_id)
    if version is None:
        raise ClinicalConfigurationError("configuration_version_not_found", 404)
    if version.status != "DRAFT":
        raise ClinicalConfigurationError("configuration_version_not_draft", 409)
    _validate_assignments(db, primary_lab_physician_user_id, substitute_lab_physician_user_id)
    version.configuration_snapshot = normalize_configuration_snapshot(configuration_snapshot)
    version.primary_lab_physician_user_id = primary_lab_physician_user_id
    version.substitute_lab_physician_user_id = substitute_lab_physician_user_id
    version.updated_at = datetime.now(UTC)
    _audit(db, actor, version, "updated", "draft_updated")
    db.commit()
    db.refresh(version)
    return version


def submit_for_approval(
    db: Session, *, version_id: int, actor: User
) -> LabClinicalConfigurationVersion:
    version = _get_locked_version(db, version_id)
    if version is None:
        raise ClinicalConfigurationError("configuration_version_not_found", 404)
    if version.status != "DRAFT":
        raise ClinicalConfigurationError("configuration_version_not_draft", 409)
    _validate_assignments(
        db,
        version.primary_lab_physician_user_id,
        version.substitute_lab_physician_user_id,
    )
    snapshot = normalize_configuration_snapshot(version.configuration_snapshot)
    if not snapshot["method_instructions"]:
        raise ClinicalConfigurationError("method_instructions_required_for_approval", 422)
    for section in DISPOSITION_SECTIONS:
        has_entries = bool(snapshot[section])
        has_reason = section in snapshot["not_applicable_reasons"]
        if has_entries == has_reason:
            raise ClinicalConfigurationError("clinical_section_disposition_required", 422)
    if version.primary_lab_physician_user_id is None:
        raise ClinicalConfigurationError("primary_lab_physician_required", 422)
    version.configuration_snapshot = snapshot
    version.status = "PENDING_APPROVAL"
    version.updated_at = datetime.now(UTC)
    _audit(db, actor, version, "submitted", "configuration_submitted_for_review")
    db.commit()
    db.refresh(version)
    return version


def approve_version(
    db: Session, *, version_id: int, actor: User
) -> LabClinicalConfigurationVersion:
    version = db.scalar(
        select(LabClinicalConfigurationVersion)
        .where(LabClinicalConfigurationVersion.id == version_id)
        .with_for_update()
    )
    if version is None:
        raise ClinicalConfigurationError("configuration_version_not_found", 404)
    if version.status != "PENDING_APPROVAL":
        raise ClinicalConfigurationError("configuration_version_not_pending", 409)
    _validate_assignments(
        db,
        version.primary_lab_physician_user_id,
        version.substitute_lab_physician_user_id,
    )
    if not actor.is_active or actor.role != "Lab":
        raise ClinicalConfigurationError("lab_physician_approval_required", 403)
    if actor.id == version.primary_lab_physician_user_id:
        assignment = "primary"
    elif actor.id == version.substitute_lab_physician_user_id:
        assignment = "substitute"
    else:
        raise ClinicalConfigurationError("assigned_lab_physician_approval_required", 403)

    approved_at = datetime.now(UTC)
    current_versions = db.scalars(
        select(LabClinicalConfigurationVersion)
        .where(LabClinicalConfigurationVersion.status == "APPROVED")
        .with_for_update()
    ).all()
    for previous in current_versions:
        previous.status = "ARCHIVED"
        previous.archived_at = approved_at
    version.status = "APPROVED"
    version.approved_by_user_id = actor.id
    version.approved_role_code = actor.role
    version.approval_authority_snapshot = {
        "actor_user_id": actor.id,
        "actor_role_code": actor.role,
        "assignment": assignment,
        "assigned_primary_user_id": version.primary_lab_physician_user_id,
        "assigned_substitute_user_id": version.substitute_lab_physician_user_id,
        "account_active_at_approval": True,
    }
    version.approved_at = approved_at
    _audit(
        db,
        actor,
        version,
        "approved",
        "assigned_lab_physician_approved_configuration",
        extra_data={"assignment": assignment, "version_no": version.version_no},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ClinicalConfigurationError("configuration_approval_conflict", 409) from exc
    db.refresh(version)
    return version
