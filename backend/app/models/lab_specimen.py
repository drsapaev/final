"""Physical specimen identity and append-only custody history."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class LabSpecimenRejectionReasonCode(StrEnum):
    LABEL_MISMATCH = "label_mismatch"
    CONTAINER_MISMATCH = "container_mismatch"
    INSUFFICIENT_QUANTITY = "insufficient_quantity"
    SPECIMEN_QUALITY = "specimen_quality"
    TRANSPORT_ISSUE = "transport_issue"
    OTHER = "other"


_REJECTION_CODES_SQL = ", ".join(
    repr(code.value) for code in LabSpecimenRejectionReasonCode
)


class LabSpecimen(Base):
    __tablename__ = "lab_specimens"
    __table_args__ = (
        UniqueConstraint("id", "order_id", name="uq_lab_specimens_id_order"),
        UniqueConstraint("barcode", name="uq_lab_specimens_barcode"),
        UniqueConstraint(
            "order_id", "create_request_id", name="uq_lab_specimens_create_request"
        ),
        UniqueConstraint("replaces_specimen_id", name="uq_lab_specimens_replacement"),
        ForeignKeyConstraint(
            ["parent_specimen_id", "order_id"],
            ["lab_specimens.id", "lab_specimens.order_id"],
            name="fk_lab_specimens_parent_order",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["replaces_specimen_id", "order_id"],
            ["lab_specimens.id", "lab_specimens.order_id"],
            name="fk_lab_specimens_replacement_order",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "parent_specimen_id IS NULL OR replaces_specimen_id IS NULL",
            name="ck_lab_specimens_single_origin",
        ),
        CheckConstraint(
            "(parent_specimen_id IS NULL OR parent_specimen_id <> id) AND "
            "(replaces_specimen_id IS NULL OR replaces_specimen_id <> id)",
            name="ck_lab_specimens_no_self_reference",
        ),
        CheckConstraint(
            "status IN ('expected', 'collected', 'received', 'accepted', 'held', 'rejected')",
            name="ck_lab_specimens_status",
        ),
        CheckConstraint("revision > 0", name="ck_lab_specimens_revision"),
        Index("ix_lab_specimens_order_status", "order_id", "status"),
        Index("ix_lab_specimens_parent", "parent_specimen_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="RESTRICT"), nullable=False
    )
    barcode: Mapped[str] = mapped_column(String(24), nullable=False)
    material_code: Mapped[str] = mapped_column(String(32), nullable=False)
    container_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_specimen_id: Mapped[int | None] = mapped_column(Integer)
    replaces_specimen_id: Mapped[int | None] = mapped_column(Integer)
    create_request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    latest_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LabSpecimenAssignment(Base):
    __tablename__ = "lab_specimen_assignments"
    __table_args__ = (
        UniqueConstraint(
            "specimen_id", "visit_service_id", name="uq_lab_specimen_visit_service"
        ),
        UniqueConstraint(
            "specimen_id", "report_instance_id", name="uq_lab_specimen_report"
        ),
        CheckConstraint(
            "(visit_service_id IS NULL) <> (report_instance_id IS NULL)",
            name="ck_lab_specimen_assignment_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specimen_id: Mapped[int] = mapped_column(
        ForeignKey("lab_specimens.id", ondelete="RESTRICT"), nullable=False
    )
    visit_service_id: Mapped[int | None] = mapped_column(
        ForeignKey("visit_services.id", ondelete="RESTRICT"), index=True
    )
    report_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("lab_report_instances.id", ondelete="RESTRICT"), index=True
    )


class LabSpecimenEvent(Base):
    __tablename__ = "lab_specimen_events"
    __table_args__ = (
        UniqueConstraint(
            "specimen_id", "revision", name="uq_lab_specimen_event_revision"
        ),
        UniqueConstraint(
            "specimen_id", "request_id", name="uq_lab_specimen_event_request"
        ),
        CheckConstraint("revision > 0", name="ck_lab_specimen_event_revision"),
        CheckConstraint(
            f"reason_code IS NULL OR (action = 'reject' AND reason_code IN ({_REJECTION_CODES_SQL}))",
            name="ck_lab_specimen_event_rejection_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    specimen_id: Mapped[int] = mapped_column(
        ForeignKey("lab_specimens.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    resulting_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(300))
    reason_code: Mapped[str | None] = mapped_column(String(32))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    visit_service_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list
    )
    report_instance_ids: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list
    )
