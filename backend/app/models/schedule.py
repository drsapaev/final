from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


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
    department: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    doctor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    room: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    capacity_per_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
