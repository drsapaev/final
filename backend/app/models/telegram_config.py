"""
Модели для конфигурации Telegram в админ панели
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class TelegramConfig(Base):
    """Конфигурация Telegram бота"""

    __tablename__ = "telegram_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_token: Mapped[str | None] = mapped_column(String(500), nullable=True)  # TG-AUDIT-28 P1: encrypted (Fernet)
    webhook_url: Mapped[str | None] = mapped_column(String(300), nullable=True)  # URL вебхука
    webhook_secret: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Секрет для верификации

    # Настройки бота
    bot_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bot_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Чаты администраторов
    admin_chat_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)  # [123456, 789012]

    # Настройки уведомлений
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lab_results_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payment_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Языки
    default_language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)
    supported_languages: Mapped[list[str]] = mapped_column(
        JSON, default=["ru", "uz", "en"], nullable=False
    )

    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )




    @property
    def decrypted_bot_token(self) -> str | None:
        """TG-AUDIT-28 P1: decrypt bot_token on read."""
        if not self.bot_token:
            return None
        from app.core.config import settings
        if not settings.ENCRYPTION_KEY:
            return self.bot_token  # plaintext fallback (dev/test)
        try:
            if self.bot_token.startswith("gAAAAA"):
                from cryptography.fernet import Fernet
                cipher = Fernet(settings.ENCRYPTION_KEY.encode())
                return cipher.decrypt(self.bot_token.encode()).decode()
            return self.bot_token  # not encrypted yet (migration period)
        except Exception:
            return self.bot_token

    def set_bot_token(self, value: str | None) -> None:
        """TG-AUDIT-28 P1: encrypt bot_token on write."""
        if not value:
            self.bot_token = None
            return
        from app.core.config import settings
        if not settings.ENCRYPTION_KEY:
            self.bot_token = value  # plaintext fallback (dev/test)
            return
        from cryptography.fernet import Fernet
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        self.bot_token = cipher.encrypt(value.encode()).decode()


class TelegramTemplate(Base):
    """Шаблоны сообщений Telegram"""

    __tablename__ = "telegram_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_key: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # appointment_reminder, lab_ready
    template_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # notification, reminder, broadcast
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)

    # Контент шаблона
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Заголовок (если нужен)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)  # Jinja2 шаблон сообщения

    # Настройки отправки
    parse_mode: Mapped[str] = mapped_column(
        String(20), default="HTML", nullable=False
    )  # HTML, Markdown, None
    disable_web_page_preview: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Кнопки (inline keyboard)
    inline_buttons: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )  # [{"text": "Подтвердить", "callback_data": "confirm"}]

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramUser(Base):
    """Связка пользователей с Telegram"""

    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve Telegram link
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve Telegram link

    # Telegram данные
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language_code: Mapped[str] = mapped_column(String(16), default="ru", nullable=False)

    # Настройки уведомлений
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lab_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Статус
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Заблокировал бота
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patient: Mapped[Patient | None] = relationship("Patient", foreign_keys=[patient_id])
    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])


class TelegramStaffLinkToken(Base):
    """Hash-only storage shape for one-time staff Telegram link tokens."""

    __tablename__ = "telegram_staff_link_tokens"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_telegram_staff_link_tokens_expires_after_created",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR consumed_at <= expires_at",
            name="ck_telegram_staff_link_tokens_consumed_before_expiry",
        ),
        Index(
            "ix_telegram_staff_link_tokens_staff_user_id",
            "staff_user_id",
        ),
        Index(
            "ix_telegram_staff_link_tokens_telegram_chat_id",
            "telegram_chat_id",
        ),
        Index(
            "ix_telegram_staff_link_tokens_unconsumed_expires",
            "expires_at",
            postgresql_where=text("consumed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(
        String(96), unique=True, nullable=False, index=True
    )
    staff_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    issued_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    staff_user: Mapped[User] = relationship("User", foreign_keys=[staff_user_id])
    issued_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[issued_by_user_id]
    )


class TelegramStaffConfirmationToken(Base):
    """Hash-only storage shape for one-time staff action confirmation tokens."""

    __tablename__ = "telegram_staff_confirmation_tokens"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_telegram_staff_confirmation_tokens_expires_after_created",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR consumed_at <= expires_at",
            name="ck_telegram_staff_confirmation_tokens_consumed_before_expiry",
        ),
        CheckConstraint(
            "operation_key <> ''",
            name="ck_telegram_staff_confirmation_tokens_operation_not_empty",
        ),
        CheckConstraint(
            "action_payload_hash <> ''",
            name="ck_telegram_staff_confirmation_tokens_payload_hash_not_empty",
        ),
        Index(
            "ix_telegram_staff_confirmation_tokens_staff_user_id",
            "staff_user_id",
        ),
        Index(
            "ix_telegram_staff_confirmation_tokens_telegram_chat_id",
            "telegram_chat_id",
        ),
        Index(
            "ix_telegram_staff_confirmation_tokens_operation_key",
            "operation_key",
        ),
        Index(
            "ix_telegram_staff_confirmation_tokens_unconsumed_expires",
            "expires_at",
            postgresql_where=text("consumed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(
        String(96), unique=True, nullable=False, index=True
    )
    staff_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    operation_key: Mapped[str] = mapped_column(String(96), nullable=False)
    command_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_payload_hash: Mapped[str] = mapped_column(String(96), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_reference_hash: Mapped[str | None] = mapped_column(
        String(96), nullable=True
    )
    idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(96), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    staff_user: Mapped[User] = relationship("User", foreign_keys=[staff_user_id])


class TelegramPatientFormSubmission(Base):
    """Protected Telegram Mini App patient form submission."""

    __tablename__ = "telegram_patient_form_submissions"
    __table_args__ = (
        CheckConstraint(
            "form_id <> ''",
            name="ck_telegram_patient_form_submissions_form_id_not_empty",
        ),
        CheckConstraint(
            "schema_version > 0",
            name="ck_telegram_patient_form_submissions_schema_version_positive",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted')",
            name="ck_telegram_patient_form_submissions_status_allowed",
        ),
        CheckConstraint(
            "source <> ''",
            name="ck_telegram_patient_form_submissions_source_not_empty",
        ),
        UniqueConstraint(
            "patient_id",
            "form_id",
            name="uq_telegram_patient_form_submissions_patient_form",
        ),
        Index(
            "ix_telegram_patient_form_submissions_patient_id",
            "patient_id",
        ),
        Index(
            "ix_telegram_patient_form_submissions_telegram_user_id",
            "telegram_user_id",
        ),
        Index(
            "ix_telegram_patient_form_submissions_chat_id",
            "telegram_chat_id",
        ),
        Index(
            "ix_telegram_patient_form_submissions_patient_status",
            "patient_id",
            "status",
        ),
        Index(
            "ix_telegram_patient_form_submissions_updated_at",
            "updated_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("telegram_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    form_id: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), default="telegram_mini_app", nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient: Mapped[Patient] = relationship("Patient", foreign_keys=[patient_id])
    telegram_user: Mapped[TelegramUser | None] = relationship(
        "TelegramUser", foreign_keys=[telegram_user_id]
    )


class PatientOnboardingRequest(Base):
    """REQUEST_REVIEW storage for unlinked Telegram/Mini App appointment requests."""

    __tablename__ = "patient_onboarding_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'pending_review', "
            "'linked_existing', "
            "'created_patient', "
            "'needs_more_info', "
            "'rejected', "
            "'cancelled', "
            "'expired'"
            ")",
            name="ck_patient_onboarding_requests_status_allowed",
        ),
        CheckConstraint(
            "desired_time IS NULL OR desired_time <> ''",
            name="ck_patient_onboarding_requests_desired_time_not_empty",
        ),
        Index(
            "ix_patient_onboarding_requests_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_patient_onboarding_requests_telegram_user_status",
            "telegram_user_id",
            "status",
        ),
        Index(
            "ix_patient_onboarding_requests_telegram_chat_id",
            "telegram_chat_id",
        ),
        Index(
            "ix_patient_onboarding_requests_expires_at",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("telegram_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending_review", nullable=False
    )
    language_code: Mapped[str] = mapped_column(
        String(16), default="ru", nullable=False
    )
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    desired_service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    desired_branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    desired_doctor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
    )
    desired_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    desired_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    telegram_user: Mapped[TelegramUser | None] = relationship(
        "TelegramUser", foreign_keys=[telegram_user_id]
    )
    reviewed_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[reviewed_by_user_id]
    )
    resolved_patient: Mapped[Patient | None] = relationship(
        "Patient", foreign_keys=[resolved_patient_id]
    )


class TelegramMessage(Base):
    """Лог отправленных сообщений"""

    __tablename__ = "telegram_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ID сообщения в Telegram

    # Тип и контент
    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # reminder, notification, broadcast
    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус доставки
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, sent, delivered, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Метаданные
    sent_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve message log
    related_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # appointment, visit, payment
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sent_by: Mapped[User | None] = relationship("User", foreign_keys=[sent_by_user_id])
