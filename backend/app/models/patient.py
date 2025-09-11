from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, name="gender"
    )  # M|F|X

    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    doc_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Связь с пользователем
    user: Mapped[Optional["User"]] = relationship("User", back_populates="patient")

    def short_name(self) -> str:
        mid = f" {self.middle_name}" if self.middle_name else ""
        return f"{self.last_name} {self.first_name}{mid}".strip()
