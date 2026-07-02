from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.clinic import Doctor
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit


class DoctorPriceOverride(Base):
    """
    Модель для хранения изменений цен врачами (дерматолог-косметолог, стоматолог)
    """

    __tablename__ = "doctor_price_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Связи
    visit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("visits.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # ✅ SECURITY: SET NULL to preserve override record
    doctor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # ✅ SECURITY: SET NULL to preserve override record
    service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # ✅ SECURITY: SET NULL to preserve override record

    # Цены
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Обоснование изменения
    reason: Mapped[str] = mapped_column(String(255), nullable=False)  # Краткая причина
    details: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Подробное описание

    # Статус и одобрение
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending, approved, rejected

    # Кто и когда одобрил/отклонил (регистратура)
    approved_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Уведомления
    notification_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Связи
    visit: Mapped[Visit] = relationship("Visit", back_populates="price_overrides")
    doctor: Mapped[Doctor] = relationship("Doctor", back_populates="price_overrides")
    service: Mapped[Service] = relationship(
        "Service", back_populates="price_overrides"
    )
    approved_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[approved_by]
    )
