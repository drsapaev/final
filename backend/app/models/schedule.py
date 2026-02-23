from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.department import Department


class ScheduleTemplate(Base):
    """
    Шаблон расписания приёма.
    Поля:
      - department: отделение (опционально)
      - doctor_id: ID врача (опционально)
      - weekday: 0..6 (Пн..Вс)
      - start_time, end_time: "HH:MM"
      - room: кабинет (опционально)
      - capacity_per_hour: вместимость записей на час (опц.)
      - active: активен/нет
    """

    __tablename__ = "schedule_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    department_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    doctor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # ✅ SECURITY: SET NULL to preserve schedule if doctor deleted
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    room: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capacity_per_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    department: Mapped[Department | None] = relationship(
        back_populates="schedules"
    )
