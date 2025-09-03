from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base  # Base декларативной модели


class OnlineDay(Base):
    __tablename__ = "online_days"
    __table_args__ = (
        UniqueConstraint("department", "date_str", name="uq_online_day_dep_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    department: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date_str: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # YYYY-MM-DD
    start_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
