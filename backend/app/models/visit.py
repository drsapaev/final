from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.clinic import Doctor
    from app.models.doctor_price_override import DoctorPriceOverride
    from app.models.patient import Patient
    from app.models.payment_invoice import PaymentInvoiceVisit


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ✅ SECURITY: patient_id is NOT NULL, so we can't use SET NULL
    # Patient deletion should be prevented if visits exist, or use soft delete
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="RESTRICT"),  # Prevent deletion if visits exist
        nullable=False,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )  # open|closed|canceled
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # ✅ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    discount_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", index=True
    )  # none|repeat|benefit|all_free
    approval_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", index=True
    )  # none|pending|approved|rejected
    doctor_price_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    doctor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True
    )  # ✅ SECURITY: SET NULL to preserve visit if doctor deleted
    visit_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    visit_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    department: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Department name/key
    department_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ✅ ПОЛЯ ДЛЯ ПОДТВЕРЖДЕНИЯ ВИЗИТОВ
    confirmation_token: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    confirmation_channel: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # phone|telegram|pwa
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # user_id, telegram_id, или phone

    # ✅ SSOT: Источник визита (единственный источник истины)
    # 'online' = QR/Telegram регистрация
    # 'desk' = Регистратура
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="desk", index=True
    )

    services: Mapped[list[VisitService]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )

    # Связь с изменениями цен врачами
    price_overrides: Mapped[list[DoctorPriceOverride]] = relationship(
        "DoctorPriceOverride", back_populates="visit", cascade="all, delete-orphan"
    )

    # Связь с корзиной через промежуточную таблицу
    invoices: Mapped[list[PaymentInvoiceVisit]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )

    # Связь с отделением (закомментирована из-за конфликта с department строковым полем)
    # department_obj: Mapped[Optional["Department"]] = relationship(back_populates="visits")

    # Связь с врачом
    doctor: Mapped[Doctor | None] = relationship(back_populates="visits")
    patient: Mapped[Patient | None] = relationship("Patient")


class VisitService(Base):
    __tablename__ = "visit_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("visits.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    visit: Mapped[Visit] = relationship(back_populates="services")

    def __init__(self, **kwargs: Any):
        # Backward compatibility for legacy payloads/tests.
        quantity = kwargs.pop("quantity", None)
        kwargs.pop("discount_amount", None)
        if quantity is not None and "qty" not in kwargs:
            kwargs["qty"] = quantity
        if not kwargs.get("name"):
            kwargs["name"] = "Услуга"
        super().__init__(**kwargs)

    @property
    def quantity(self) -> int:
        return self.qty

    @quantity.setter
    def quantity(self, value: int) -> None:
        self.qty = value
