"""
Reason Codes — M5.4 (Epic M5 — Enterprise Security).

Provides structured reason context for audit log entries.
Instead of just "doctor opened patient", logs:
  "doctor opened patient because consultation #5832"

Usage:
    from app.services.reason_codes import ReasonCode

    log_audit_event(
        db=db,
        event_type="DOCTOR_OPEN_EMR",
        action="view",
        reason_code=ReasonCode.consultation(5832).to_dict(),
    )
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReasonCode:
    """Structured reason for an audit event (M5.4).

    Attributes:
        context: What triggered the action (consultation, appointment, emergency, etc.)
        id: ID of the triggering entity (e.g. consultation_id)
        note: Optional human-readable note
    """
    context: str
    id: int | str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON storage in AuditLog.reason_code."""
        result: dict[str, Any] = {"context": self.context}
        if self.id is not None:
            result["id"] = self.id
        if self.note:
            result["note"] = self.note
        return result

    # ─── Factory methods for common reason contexts ────────────────────────

    @classmethod
    def consultation(cls, consultation_id: int) -> "ReasonCode":
        """Action performed in context of a consultation."""
        return cls(context="consultation", id=consultation_id)

    @classmethod
    def appointment(cls, appointment_id: int) -> "ReasonCode":
        """Action performed in context of an appointment."""
        return cls(context="appointment", id=appointment_id)

    @classmethod
    def visit(cls, visit_id: int) -> "ReasonCode":
        """Action performed in context of a visit."""
        return cls(context="visit", id=visit_id)

    @classmethod
    def emergency(cls, note: str | None = None) -> "ReasonCode":
        """Action performed in emergency context."""
        return cls(context="emergency", note=note)

    @classmethod
    def scheduled_report(cls, report_name: str) -> "ReasonCode":
        """Action performed for a scheduled report."""
        return cls(context="scheduled_report", note=report_name)

    @classmethod
    def user_request(cls, user_id: int) -> "ReasonCode":
        """Action performed at user's explicit request."""
        return cls(context="user_request", id=user_id)

    @classmethod
    def system(cls, note: str | None = None) -> "ReasonCode":
        """Action performed by system (automated)."""
        return cls(context="system", note=note)


# ─── Reason context registry (for admin UI) ────────────────────────────────

REASON_CONTEXTS: list[dict[str, str]] = [
    {"value": "consultation", "label": "Консультация"},
    {"value": "appointment", "label": "Запись на приём"},
    {"value": "visit", "label": "Визит"},
    {"value": "emergency", "label": "Экстренный случай"},
    {"value": "scheduled_report", "label": "Запланированный отчёт"},
    {"value": "user_request", "label": "По запросу пользователя"},
    {"value": "system", "label": "Системная операция"},
]
