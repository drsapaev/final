from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.clinic import Doctor
    from app.models.doctor_price_override import DoctorPriceOverride
    from app.models.patient import Patient
    from app.models.payment_invoice import PaymentInvoiceVisit


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        Index("uq_visits_allfree_identity", "id", "patient_id", "allfree_encounter_identity", unique=True),
        UniqueConstraint("id", "patient_id", name="uq_visits_id_patient"),
        UniqueConstraint("id", "patient_id", "encounter_id", name="uq_visits_id_patient_encounter"),
        CheckConstraint("encounter_id IS NULL OR patient_id IS NOT NULL", name="ck_visits_encounter_patient_present"),
        CheckConstraint(
            "started_appointment_id IS NULL OR started_appointment_checked",
            name="ck_visits_started_appointment_checked",
        ),
        Index(
            "uq_visits_started_appointment", "started_appointment_id", unique=True,
            postgresql_where=text("started_appointment_id IS NOT NULL"),
            sqlite_where=text("started_appointment_id IS NOT NULL"),
        ),
        ForeignKeyConstraint(
            ["encounter_id", "patient_id"], ["encounters.id", "encounters.patient_id"],
            name="fk_visits_encounter_patient", deferrable=True, initially="DEFERRED",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ✅ SECURITY: patient_id is NOT NULL, so we can't use SET NULL
    # Patient deletion should be prevented if visits exist, or use soft delete
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "patients.id", ondelete="RESTRICT"
        ),  # Prevent deletion if visits exist
        nullable=False,
        index=True,
    )
    encounter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("encounters.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    allfree_encounter_identity: Mapped[str | None] = mapped_column(
        String(24),
        Computed("CASE WHEN encounter_id IS NULL THEN 'N' ELSE 'I' || CAST(encounter_id AS TEXT) END", persisted=True),
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open"
    )  # open|closed|canceled
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=lambda: datetime.now(UTC)
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
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # ✅ SECURITY: SET NULL to preserve visit if doctor deleted
    visit_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    visit_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # A checked NULL is known absence, including when a captured row was deleted.
    # Unchecked visits predate this observation or started on another surface.
    started_appointment_checked: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), nullable=False,
    )
    started_appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "appointments.id", ondelete="SET NULL",
            name="fk_visits_started_appointment", use_alter=True,
        ),
        nullable=True,
    )
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

    # Narrow clinical identity fence; does not change on ordinary confirmation.
    price_context_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")

    # Server-owned generation binds Telegram actions to this clinical context.
    confirmation_context_epoch: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )

    # Historical completed visits are intentionally unknown until a
    # completion workflow records a consultation snapshot. The generation
    # fences that snapshot against subsequent clinical context mutations.
    repeat_evidence_generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    repeat_proof_generation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repeat_proof_consultation: Mapped[bool | None] = mapped_column(nullable=True)
    repeat_proof_doctor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    repeat_assigned_doctor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    repeat_assigned_owner_generation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # ✅ Идемпотентность reminder-пайплайна (arq job send_visit_reminder):
    # штампуется воркером после успешной отправки напоминания; повторные
    # запуски job'а (arq retry / повторный enqueue) видят NOT NULL и
    # пропускают отправку. Канонический путь записи — только воркер
    # (app/tasks/worker.py), схема — миграция 0060.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ✅ Lease (короткоживущий claim) того же job'а: ставится ДО dispatch,
    # чтобы две конкурирующие доставки не отправили дважды, и снимается
    # после успешной записи reminder_sent_at (или при неудаче). Lease старше
    # LEASE_TTL воркера — след умершего процесса и подлежит перев claim'у.
    # Схема — миграция 0060.
    reminder_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ✅ Поколение расписания (Codex round 7): инкрементируется каждым
    # путём, меняющим расписание; входит в schedule_version джоба, делая
    # версии неповторяющимися (цикл A→B→A не коллидирует с retained
    # результатом arq). Схема — миграция 0060.
    reminder_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

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
    __table_args__ = (
        Index("uq_visit_services_allfree_identity", "id", "visit_id", "service_id", unique=True),
        CheckConstraint(
            "duration_minutes_snapshot IS NULL OR duration_minutes_snapshot > 0",
            name="ck_visit_services_duration_snapshot_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("visits.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes_snapshot: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    price_line_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")

    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
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
