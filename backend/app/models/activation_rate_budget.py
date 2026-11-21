"""Short-lived shared counters for server activation admission."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ActivationRateBudget(Base):
    __tablename__ = "activation_rate_budgets"
    __table_args__ = (
        CheckConstraint("attempts >= 1", name="ck_activation_rate_budget_attempts"),
        Index("ix_activation_rate_budget_expiry", "expires_at"),
    )

    scope: Mapped[str] = mapped_column(String(72), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
