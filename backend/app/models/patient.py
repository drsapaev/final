from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    literal,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "birth_date_precision IN ('unknown', 'year_only', 'reported_exact')",
            name="ck_patient_birth_date_precision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True
    )  # ✅ SECURITY: SET NULL (patient can exist without user account)
    # Advances in the database when account ownership or deletion changes.
    notification_owner_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    last_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    middle_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # A migration trigger advances this generation on every date change;
    # zero or missing evidence is never a verified birth date.
    birth_date_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    birth_date_precision: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    sex: Mapped[str | None] = mapped_column(
        String(8), nullable=True, name="gender"
    )  # M|F|X

    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    doc_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # PR-1: Mobile API medical-domain fields (AUDIT_PR1_MOBILE_EXTENDED.md).
    # Backed by Alembic migration 0037_patient_medical_fields.
    emergency_contact: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # ✅ SOFT-DELETE: Безопасное удаление пациентов
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Связь с пользователем
    user: Mapped[User | None] = relationship("User", back_populates="patient", foreign_keys=[user_id])

    def short_name(self) -> str:
        """
        Возвращает короткое имя пациента в формате "Фамилия Имя [Отчество]".
        Гарантирует, что всегда возвращается непустая строка.
        """
        # ✅ ЗАЩИТА: Проверяем, что поля не пустые
        last_name = (self.last_name or "").strip()
        first_name = (self.first_name or "").strip()
        middle_name = (self.middle_name or "").strip() if self.middle_name else ""

        # Если оба поля пустые - это ошибка данных, но возвращаем fallback
        if not last_name and not first_name:
            return f"Пациент ID={self.id}" if self.id else "Неизвестный пациент"

        # Если одно из полей пустое - используем другое для обоих
        if not last_name and first_name:
            last_name = first_name
        elif last_name and not first_name:
            first_name = last_name

        # Формируем имя
        mid = f" {middle_name}" if middle_name else ""
        result = f"{last_name} {first_name}{mid}".strip()

        # Финальная проверка - если все еще пустое (не должно произойти)
        return (
            result
            if result
            else f"Пациент ID={self.id}" if self.id else "Неизвестный пациент"
        )

    @hybrid_property
    def full_name(self) -> str:
        return self.short_name()

    @full_name.expression
    def full_name(cls):  # type: ignore[no-redef]
        return func.trim(
            func.coalesce(cls.last_name, "")
            + literal(" ")
            + func.coalesce(cls.first_name, "")
            + literal(" ")
            + func.coalesce(cls.middle_name, "")
        )


class PatientBirthDateEvidence(Base):
    """A reviewed date is usable only while its patient generation matches.

    The schema alone does not establish the actor's authority or the accuracy
    of the reviewed record. It deliberately does not copy the date into audit.
    """

    __tablename__ = "patient_birth_date_evidence"
    __table_args__ = (
        UniqueConstraint("patient_id", "birth_date_generation", name="uq_patient_birth_evidence_generation"),
        CheckConstraint("patient_id_snapshot > 0 AND birth_date_generation > 0 AND actor_user_id_snapshot > 0", name="ck_patient_birth_evidence_identity"),
        CheckConstraint("patient_id IS NULL OR patient_id = patient_id_snapshot", name="ck_patient_birth_evidence_patient"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"))
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    birth_date_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
