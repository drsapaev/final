"""Non-reserving patient requests for the public booking flow."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PublicBookingRequest(Base):
    """A patient's requested time; it never occupies the appointment calendar."""

    __tablename__ = "public_booking_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'needs_new_time', 'confirmed', 'rejected', 'withdrawn')",
            name="ck_public_booking_requests_status",
        ),
        CheckConstraint("version > 0", name="ck_public_booking_requests_version"),
        CheckConstraint(
            "settings_version >= 0",
            name="ck_public_booking_requests_settings_version",
        ),
        Index(
            "ix_public_booking_requests_patient_created",
            "patient_id",
            "created_at",
        ),
        Index(
            "ix_public_booking_requests_status_created",
            "status",
            "created_at",
        ),
        Index(
            "uq_public_booking_requests_active_slot",
            "patient_id",
            "service_id",
            "doctor_id",
            "appointment_date",
            "appointment_time",
            unique=True,
            postgresql_where=text("status IN ('pending', 'needs_new_time')"),
            sqlite_where=text("status IN ('pending', 'needs_new_time')"),
        ),
        Index(
            "uq_public_booking_requests_appointment_id",
            "appointment_id",
            unique=True,
            postgresql_where=text("appointment_id IS NOT NULL"),
            sqlite_where=text("appointment_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    doctor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    appointment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("appointments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default=text("'pending'")
    )
    settings_version: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient = relationship("Patient", foreign_keys=[patient_id])
    service = relationship("Service", foreign_keys=[service_id])
    doctor = relationship("Doctor", foreign_keys=[doctor_id])
    appointment = relationship("Appointment", foreign_keys=[appointment_id])
    events = relationship(
        "PublicBookingRequestEvent",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="PublicBookingRequestEvent.id",
    )


class PublicBookingRequestEvent(Base):
    """Append-only state and selected-time history for a booking request."""

    __tablename__ = "public_booking_request_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('submitted', 'resubmitted', 'staff_requested_new_time', "
            "'confirmation_slot_unavailable', 'confirmed', 'rejected', 'withdrawn')",
            name="ck_public_booking_request_events_type",
        ),
        CheckConstraint(
            "(idempotency_key_hash IS NULL) = (payload_hash IS NULL)",
            name="ck_public_booking_request_events_idempotency_pair",
        ),
        Index("ix_public_booking_request_events_request_id", "request_id", "id"),
        UniqueConstraint(
            "idempotency_key_hash",
            name="uq_public_booking_request_events_idempotency_key_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("public_booking_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_appointment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    previous_appointment_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    requested_appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    request = relationship("PublicBookingRequest", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_user_id])
