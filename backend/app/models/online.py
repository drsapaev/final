from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base  # Base декларативной модели


# ============================================================================
# DEPRECATED: OnlineDay model is legacy department-based queue system
# ============================================================================
#
# ⚠️ WARNING: This model is DEPRECATED and should not be used for new features.
#
# Current Usage:
#   - Used only by appointments endpoint (/api/v1/appointments)
#   - Used by services/online_queue.py for simple ticket issuing
#
# Migration Path:
#   - New queue features should use DailyQueue (specialist-based) instead
#   - DailyQueue is the official SSOT for queue system
#   - Plan to migrate appointments endpoint to DailyQueue in future
#
# Key Differences:
#   - OnlineDay: department-based (string), uses Settings table for counters
#   - DailyQueue: specialist-based (FK to doctors), uses queue_entries table
#
# DO NOT:
#   - Add new features to this model
#   - Create new endpoints using OnlineDay
#   - Reference this model in new code
#
# SEE ALSO:
#   - app/models/online_queue.py (DailyQueue - preferred)
#   - docs/QUEUE_SYSTEM_ARCHITECTURE.md (migration guide)
# ============================================================================

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
