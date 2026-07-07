"""Service for managing service audit logs."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy.orm import Session

from app.models.service import Service
from app.models.service_audit import ServiceAuditLog


class ServiceAuditService:
    """Handles audit logging for service changes."""

    def __init__(self, db: Session):
        self.db = db

    def log_service_change(
        self,
        *,
        service_id: int,
        action: str,
        user_id: int | None = None,
        changes: dict[str, dict[str, Any]] | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        comment: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ServiceAuditLog:
        """
        Log a service change.

        Args:
            service_id: ID of the service
            action: Type of action ('create', 'update', 'delete', 'activate', 'deactivate')
            user_id: ID of user who made the change
            changes: Dict of changed fields with old/new values
            old_values: Full snapshot of old values
            new_values: Full snapshot of new values
            comment: Optional comment/reason for change
            ip_address: IP address of the user
            user_agent: User agent string

        Returns:
            Created audit log entry
        """
        audit_log = ServiceAuditLog(
            service_id=service_id,
            user_id=user_id,
            action=action,
            changes=changes,
            old_values=old_values,
            new_values=new_values,
            comment=comment,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )

        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)

        return audit_log

    def log_service_creation(
        self,
        *,
        service: Service,
        user_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ServiceAuditLog:
        """Log service creation."""
        new_values = self._service_to_dict(service)

        return self.log_service_change(
            service_id=service.id,
            action="create",
            user_id=user_id,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_service_update(
        self,
        *,
        service_id: int,
        old_service: Service,
        new_service: Service,
        user_id: int | None = None,
        comment: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ServiceAuditLog:
        """Log service update with field-level changes."""
        old_values = self._service_to_dict(old_service)
        new_values = self._service_to_dict(new_service)

        # Calculate changes
        changes = self._calculate_changes(old_values, new_values)

        # Determine action based on changes
        action = "update"
        if "active" in changes:
            if changes["active"]["new"] and not changes["active"]["old"]:
                action = "activate"
            elif not changes["active"]["new"] and changes["active"]["old"]:
                action = "deactivate"

        return self.log_service_change(
            service_id=service_id,
            action=action,
            user_id=user_id,
            changes=changes,
            old_values=old_values,
            new_values=new_values,
            comment=comment,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_service_deletion(
        self,
        *,
        service: Service,
        user_id: int | None = None,
        comment: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ServiceAuditLog:
        """Log service deletion."""
        old_values = self._service_to_dict(service)

        return self.log_service_change(
            service_id=service.id,
            action="delete",
            user_id=user_id,
            old_values=old_values,
            comment=comment,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def get_service_history(
        self,
        *,
        service_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ServiceAuditLog]:
        """Get audit history for a service."""
        return (
            self.db.query(ServiceAuditLog)
            .filter(ServiceAuditLog.service_id == service_id)
            .order_by(ServiceAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_user_service_changes(
        self,
        *,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ServiceAuditLog]:
        """Get all service changes made by a user."""
        return (
            self.db.query(ServiceAuditLog)
            .filter(ServiceAuditLog.user_id == user_id)
            .order_by(ServiceAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_recent_changes(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ServiceAuditLog]:
        """Get recent service changes across all services."""
        return (
            self.db.query(ServiceAuditLog)
            .order_by(ServiceAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def _service_to_dict(self, service: Service) -> dict[str, Any]:
        """Convert service to dictionary for audit logging."""
        return {
            "id": service.id,
            "code": service.code,
            "service_code": service.service_code,
            "name": service.name,
            "category_id": service.category_id,
            "category_code": service.category_code,
            "price": float(service.price) if service.price else None,
            "currency": service.currency,
            "duration_minutes": service.duration_minutes,
            "doctor_id": service.doctor_id,
            "department_key": service.department_key,
            "queue_tag": service.queue_tag,
            "requires_doctor": service.requires_doctor,
            "is_consultation": service.is_consultation,
            "allow_doctor_price_override": service.allow_doctor_price_override,
            "active": service.active,
        }

    def _calculate_changes(
        self,
        old_values: dict[str, Any],
        new_values: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Calculate field-level changes between old and new values."""
        changes = {}

        # Important fields to track
        tracked_fields = [
            "code",
            "service_code",
            "name",
            "category_id",
            "category_code",
            "price",
            "currency",
            "duration_minutes",
            "doctor_id",
            "department_key",
            "queue_tag",
            "requires_doctor",
            "is_consultation",
            "allow_doctor_price_override",
            "active",
        ]

        for field in tracked_fields:
            old_val = old_values.get(field)
            new_val = new_values.get(field)

            if old_val != new_val:
                changes[field] = {
                    "old": old_val,
                    "new": new_val,
                }

        return changes
