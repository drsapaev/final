from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, default="UZS"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # ✅ НОВЫЕ ПОЛЯ ДЛЯ КЛАССИФИКАЦИИ
    category_code: Mapped[Optional[str]] = mapped_column(
        String(1), nullable=True, index=True
    )  # K, D, C, L, S, O
    service_code: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, unique=True, index=True
    )  # K01, D02, C03, etc.
    
    # Новые поля для админ панели
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("service_categories.id"), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=30, nullable=True)
    doctor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("doctors.id"), nullable=True)
    
    # ✅ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    requires_doctor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    queue_tag: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    is_consultation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    allow_doctor_price_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Relationships
    category = relationship("ServiceCategory", back_populates="services")
    department = relationship("Department")
    doctor = relationship("Doctor", back_populates="services")
    price_overrides = relationship("DoctorPriceOverride", back_populates="service")


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, default="UZS"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
