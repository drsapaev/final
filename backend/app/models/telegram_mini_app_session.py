"""Patient-only Telegram sessions, independent of staff UserSession."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class TelegramMiniAppSession(Base):
    __tablename__ = "telegram_mini_app_sessions"
    __table_args__ = (
        UniqueConstraint("init_data_hash", name="uq_tg_mini_session_init_data"),
        UniqueConstraint("refresh_token_hash", name="uq_tg_mini_session_refresh"),
        CheckConstraint("expires_at > created_at", name="ck_tg_mini_session_expiry"),
        CheckConstraint(
            "patient_link_epoch >= 0", name="ck_tg_mini_session_link_epoch"
        ),
        Index(
            "ix_tg_mini_sessions_patient_active",
            "patient_id",
            "revoked_at",
            "expires_at",
        ),
        Index("ix_tg_mini_sessions_telegram_user", "telegram_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("telegram_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_link_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    init_data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    device_label: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
