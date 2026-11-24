from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
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
    __table_args__ = (
        CheckConstraint(
            "(requester_type IS NULL AND requester_user_id IS NULL AND requester_user_id_snapshot IS NULL AND requester_auth_epoch IS NULL) OR "
            "(requester_type IS NOT NULL AND requester_type IN ('doctor','admin') AND requester_user_id_snapshot IS NOT NULL AND requester_user_id_snapshot > 0 AND "
            "requester_auth_epoch IS NOT NULL AND requester_auth_epoch >= 0 AND (requester_user_id IS NULL OR requester_user_id = requester_user_id_snapshot))",
            name="ck_doctor_price_requester_binding",
        ),
        CheckConstraint(
            "(requester_user_id_snapshot IS NULL OR typeof(requester_user_id_snapshot)='integer') AND (requester_auth_epoch IS NULL OR typeof(requester_auth_epoch)='integer')",
            name="ck_doctor_price_requester_integer_sqlite",
        ).ddl_if(dialect="sqlite"),
    )

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

    # New requests bind to one concrete association and the context in which
    # it was requested. NULLs on legacy/deleted data are deliberately unknown;
    # approval consumers must fail closed and must not infer a binding.
    target_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_visit_service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("visit_services.id", ondelete="SET NULL"), nullable=True
    )
    visit_context_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    doctor_owner_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    doctor_owner_generation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Nullable for all legacy requests; approval must require exact snapshots.
    price_context_generation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_line_generation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_owner_generation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    doctor_user_auth_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requester_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    requester_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requester_user_id_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requester_auth_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Цены
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # DERMAPRICE-BE-002 (audit #3892, group 15): фактическая цена услуги В
    # ВИЗИТЕ на момент создания запроса (VisitService.price — может отличаться
    # от каталожной после скидок/переопределений). original_price сохраняет
    # прежнюю семантику «неизменяемая каталожная ссылка»; NULL у исторических
    # строк — заполняется только новыми запросами.
    visit_price_before: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment=(
            "DERMAPRICE-BE-002: цена VisitService на момент создания запроса "
            "(дополнительная к каталожной original_price)"
        ),
    )

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
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
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
