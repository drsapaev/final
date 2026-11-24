"""Immutable, idempotent receipts for laboratory result imports."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class LabImportReceipt(Base):
    __tablename__ = "lab_import_receipts"
    __table_args__ = (
        UniqueConstraint("source", "message_id", name="uq_lab_import_source_message"),
        Index("ix_lab_import_report", "report_instance_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_instance_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_instances.id", ondelete="RESTRICT")
    )
    specimen_id: Mapped[int] = mapped_column(
        ForeignKey("lab_specimens.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    source: Mapped[str] = mapped_column(String(24))
    message_id: Mapped[str] = mapped_column(String(64))
    payload_digest: Mapped[str] = mapped_column(String(64))
    field_keys: Mapped[list[str]] = mapped_column(JSON)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at_token: Mapped[str] = mapped_column(String(64))
