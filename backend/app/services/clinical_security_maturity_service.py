from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.emr_v2 import EMRAuditLog, EMRRevision
from app.models.message import Message
from app.models.user_profile import UserAuditLog
from app.services.encryption_service import AES256Encryption

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionTarget:
    table_name: str
    model: type
    timestamp_field: str
    retention_days: int
    hard_delete_allowed: bool


@dataclass(frozen=True)
class BreakGlassPolicy:
    enabled: bool
    max_minutes: int
    reason_min_length: int
    require_ticket: bool
    allowed_roles: tuple[str, ...]


class ClinicalSecurityMaturityService:
    """
    Baseline controls for PHI lifecycle governance:
    - Retention inventory
    - Encryption posture check
    - PHI access reporting from audit logs
    - Break-glass policy validation
    """

    _PHI_RESOURCE_TYPES = {
        "patient",
        "patients",
        "visit",
        "visits",
        "emr",
        "emr_record",
        "emr_records",
        "payment",
        "payments",
        "billing",
        "lab",
        "lab_result",
        "lab_results",
    }

    def __init__(
        self,
        db: Session,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self._now = now_provider or datetime.utcnow

    def _retention_targets(self) -> list[RetentionTarget]:
        return [
            RetentionTarget(
                table_name="emr_revisions",
                model=EMRRevision,
                timestamp_field="created_at",
                retention_days=settings.PHI_RETENTION_DAYS,
                hard_delete_allowed=False,
            ),
            RetentionTarget(
                table_name="emr_audit_logs",
                model=EMRAuditLog,
                timestamp_field="timestamp",
                retention_days=settings.PHI_RETENTION_DAYS,
                hard_delete_allowed=False,
            ),
            RetentionTarget(
                table_name="user_audit_logs",
                model=UserAuditLog,
                timestamp_field="created_at",
                retention_days=settings.PHI_RETENTION_DAYS,
                hard_delete_allowed=False,
            ),
            RetentionTarget(
                table_name="messages",
                model=Message,
                timestamp_field="created_at",
                retention_days=settings.PHI_RETENTION_DAYS,
                hard_delete_allowed=True,
            ),
        ]

    def build_retention_inventory(self, as_of: datetime | None = None) -> dict[str, Any]:
        now = as_of or self._now()
        inventory: list[dict[str, Any]] = []
        overdue_total = 0

        for target in self._retention_targets():
            cutoff = now - timedelta(days=target.retention_days)
            details = self._read_retention_target(target=target, cutoff=cutoff)
            inventory.append(details)
            if isinstance(details.get("overdue_records"), int):
                overdue_total += details["overdue_records"]

        return {
            "generated_at": now.isoformat(),
            "retention_days": settings.PHI_RETENTION_DAYS,
            "targets_checked": len(inventory),
            "total_overdue_records": overdue_total,
            "targets": inventory,
        }

    def _read_retention_target(
        self,
        target: RetentionTarget,
        cutoff: datetime,
    ) -> dict[str, Any]:
        timestamp_column = getattr(target.model, target.timestamp_field)
        try:
            total = self.db.query(target.model).count()
            overdue = (
                self.db.query(target.model)
                .filter(timestamp_column < cutoff)
                .count()
            )
            oldest = self.db.query(func.min(timestamp_column)).scalar()
            newest = self.db.query(func.max(timestamp_column)).scalar()
        except SQLAlchemyError as exc:  # pragma: no cover - defensive for drifted envs
            logger.warning(
                "Unable to inspect retention target %s: %s",
                target.table_name,
                exc,
            )
            return {
                "table_name": target.table_name,
                "retention_days": target.retention_days,
                "hard_delete_allowed": target.hard_delete_allowed,
                "error": str(exc),
            }

        return {
            "table_name": target.table_name,
            "retention_days": target.retention_days,
            "hard_delete_allowed": target.hard_delete_allowed,
            "cutoff_date": cutoff.isoformat(),
            "total_records": total,
            "overdue_records": overdue,
            "oldest_record_at": oldest.isoformat() if oldest else None,
            "newest_record_at": newest.isoformat() if newest else None,
        }

    def evaluate_encryption_posture(self) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []
        smoke_tests: dict[str, bool] = {}

        message_key = settings.MESSAGE_ENCRYPTION_KEY
        app_encryption_key = settings.ENCRYPTION_KEY

        if not message_key:
            issues.append("MESSAGE_ENCRYPTION_KEY is not configured.")
        else:
            smoke_tests["message_encryption_roundtrip"] = self._encryption_roundtrip_ok(
                key=message_key
            )
            if not smoke_tests["message_encryption_roundtrip"]:
                issues.append("Message encryption key failed roundtrip check.")

        if not app_encryption_key:
            warnings.append("ENCRYPTION_KEY is not configured for sensitive app secrets.")
        else:
            smoke_tests["app_encryption_roundtrip"] = self._encryption_roundtrip_ok(
                key=app_encryption_key
            )
            if not smoke_tests["app_encryption_roundtrip"]:
                issues.append("ENCRYPTION_KEY failed roundtrip check.")

        return {
            "generated_at": self._now().isoformat(),
            "algorithm": "AES-256-GCM",
            "message_key_configured": bool(message_key),
            "app_encryption_key_configured": bool(app_encryption_key),
            "encryption_ready": not issues,
            "issues": issues,
            "warnings": warnings,
            "smoke_tests": smoke_tests,
        }

    def _encryption_roundtrip_ok(self, key: str) -> bool:
        try:
            probe = "clinical-security-probe"
            crypto = AES256Encryption(key=key)
            encrypted = crypto.encrypt(probe)
            decrypted = crypto.decrypt(encrypted)
            return decrypted == probe
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Encryption roundtrip failed: %s", exc)
            return False

    def build_phi_access_report(
        self,
        days: int = 30,
        top_users_limit: int = 10,
    ) -> dict[str, Any]:
        if days <= 0:
            raise ValueError("days must be > 0")
        if top_users_limit <= 0:
            raise ValueError("top_users_limit must be > 0")

        now = self._now()
        since = now - timedelta(days=days)

        emr_action_rows = (
            self.db.query(EMRAuditLog.action, func.count(EMRAuditLog.id))
            .filter(EMRAuditLog.timestamp >= since)
            .group_by(EMRAuditLog.action)
            .all()
        )
        user_action_rows = (
            self.db.query(UserAuditLog.action, func.count(UserAuditLog.id))
            .filter(UserAuditLog.created_at >= since)
            .filter(UserAuditLog.resource_type.in_(self._PHI_RESOURCE_TYPES))
            .group_by(UserAuditLog.action)
            .all()
        )

        action_breakdown: dict[str, int] = {}
        for action, count in emr_action_rows:
            action_breakdown[action] = action_breakdown.get(action, 0) + int(count)
        for action, count in user_action_rows:
            key = f"user_audit:{action.lower()}"
            action_breakdown[key] = action_breakdown.get(key, 0) + int(count)

        emr_events = sum(int(count) for _, count in emr_action_rows)
        user_phi_events = sum(int(count) for _, count in user_action_rows)

        per_user_counts: dict[int, int] = {}
        emr_users = (
            self.db.query(EMRAuditLog.user_id, func.count(EMRAuditLog.id).label("events"))
            .filter(EMRAuditLog.timestamp >= since)
            .group_by(EMRAuditLog.user_id)
            .all()
        )
        user_audit_users = (
            self.db.query(UserAuditLog.user_id, func.count(UserAuditLog.id).label("events"))
            .filter(UserAuditLog.created_at >= since)
            .filter(UserAuditLog.resource_type.in_(self._PHI_RESOURCE_TYPES))
            .filter(UserAuditLog.user_id.isnot(None))
            .group_by(UserAuditLog.user_id)
            .all()
        )

        for user_id, events in emr_users:
            per_user_counts[int(user_id)] = per_user_counts.get(int(user_id), 0) + int(events)
        for user_id, events in user_audit_users:
            per_user_counts[int(user_id)] = per_user_counts.get(int(user_id), 0) + int(events)

        top_users = sorted(
            (
                {"user_id": user_id, "events": events}
                for user_id, events in per_user_counts.items()
            ),
            key=lambda row: row["events"],
            reverse=True,
        )[:top_users_limit]

        return {
            "generated_at": now.isoformat(),
            "window_days": days,
            "since": since.isoformat(),
            "emr_events": emr_events,
            "user_audit_phi_events": user_phi_events,
            "total_phi_events": emr_events + user_phi_events,
            "unique_users": len(per_user_counts),
            "action_breakdown": dict(sorted(action_breakdown.items(), key=lambda kv: kv[0])),
            "top_users": top_users,
        }

    def get_break_glass_policy(self) -> BreakGlassPolicy:
        roles = tuple(
            role.strip()
            for role in settings.BREAK_GLASS_ALLOWED_ROLES.split(",")
            if role.strip()
        )
        return BreakGlassPolicy(
            enabled=settings.BREAK_GLASS_ENABLED,
            max_minutes=settings.BREAK_GLASS_MAX_MINUTES,
            reason_min_length=settings.BREAK_GLASS_REASON_MIN_LENGTH,
            require_ticket=settings.BREAK_GLASS_REQUIRE_TICKET,
            allowed_roles=roles,
        )

    def validate_break_glass_policy(
        self,
        policy: BreakGlassPolicy | None = None,
    ) -> dict[str, Any]:
        effective = policy or self.get_break_glass_policy()
        errors: list[str] = []
        warnings: list[str] = []

        if effective.max_minutes > 240:
            errors.append(
                "BREAK_GLASS_MAX_MINUTES exceeds 240 minutes; emergency scope is too broad."
            )
        if effective.reason_min_length < 20:
            errors.append(
                "BREAK_GLASS_REASON_MIN_LENGTH must be at least 20 characters."
            )
        if effective.enabled and not effective.allowed_roles:
            errors.append("Break-glass is enabled but no allowed roles are configured.")
        if effective.enabled and not effective.require_ticket:
            warnings.append(
                "Break-glass without ticket requirement weakens incident traceability."
            )
        if not effective.enabled:
            warnings.append(
                "Break-glass is disabled; verify there is an operational fallback for emergencies."
            )

        return {
            "generated_at": self._now().isoformat(),
            "compliant": not errors,
            "errors": errors,
            "warnings": warnings,
            "effective_policy": {
                "enabled": effective.enabled,
                "max_minutes": effective.max_minutes,
                "reason_min_length": effective.reason_min_length,
                "require_ticket": effective.require_ticket,
                "allowed_roles": list(effective.allowed_roles),
            },
        }
