"""Pydantic schemas for notification/Telegram/Email/SMS endpoints.

P0-6 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `request: dict[str, Any]` or
individual `dict[str, Any]` body parameters with no validation, allowing
template injection, recipient spoofing, mass-assignment, and schema
drift. These schemas enforce explicit field types and constraints.

Backward-compatibility notes:
- Endpoints that previously took individual query params (e.g.
  `appointment_id: int, channels: list[str], template_data: dict | None`)
  keep their signatures — only the `dict[str, Any] | None` body param
  is replaced with a typed model.
- For endpoints where the entire body was a dict, the dict is replaced
  with a Pydantic model and the handler accesses fields via attributes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# =============================================================================
# SHARED COMPONENTS
# =============================================================================


class TemplateDataBase(BaseModel):
    """Base for optional template data passed to notification services.

    Template data is intentionally a permissive dict (the email/SMS
    service fills placeholders from it). We cap the size to prevent
    memory abuse and require string keys.
    """

    model_config = {"extra": "allow"}  # allow arbitrary template variables

    @field_validator("*", mode="before")
    @classmethod
    def _reject_large_values(cls, v: Any) -> Any:
        # Reject strings > 100KB to prevent memory abuse
        if isinstance(v, str) and len(v) > 100_000:
            raise ValueError("template_data string values must be ≤ 100KB")
        return v


class RecipientData(BaseModel):
    """Recipient for bulk email/SMS."""

    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    name: str | None = Field(None, max_length=200)
    metadata: dict[str, Any] | None = None

    @field_validator("phone")
    @classmethod
    def _strip_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        return v


# =============================================================================
# telegram_bot.py
# =============================================================================


class SetWebhookRequest(BaseModel):
    """Request body for POST /telegram/bot/set-webhook."""

    webhook_url: str = Field(..., min_length=1, max_length=2000, description="Telegram webhook URL")

    @field_validator("webhook_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("webhook_url must not be empty")
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("webhook_url must start with http:// or https://")
        return v


class SendTelegramNotificationRequest(BaseModel):
    """Request body for POST /telegram/bot/send-notification."""

    user_id: int = Field(..., ge=1, description="Telegram user/chat ID")
    message: str = Field(..., min_length=1, max_length=4096, description="Message text (Telegram limit 4096 chars)")

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class AppointmentData(BaseModel):
    """Appointment data for reminders."""

    appointment_id: int | None = None
    id: int | None = None
    patient_name: str | None = Field(None, max_length=200)
    doctor_name: str | None = Field(None, max_length=200)
    specialty: str | None = Field(None, max_length=200)
    date: str | None = Field(None, max_length=50)
    time: str | None = Field(None, max_length=50)
    cabinet: str | None = Field(None, max_length=100)

    model_config = {"extra": "allow"}


class SendAppointmentReminderRequest(BaseModel):
    """Request body for POST /telegram/bot/send-appointment-reminder."""

    user_id: int = Field(..., ge=1, description="Telegram user/chat ID")
    appointment: AppointmentData = Field(..., description="Appointment details for the reminder")


class LabResultsData(BaseModel):
    """Lab results data for notifications."""

    lab_results_id: int | None = None
    lab_result_id: int | None = None
    id: int | None = None
    patient_name: str | None = Field(None, max_length=200)
    test_type: str | None = Field(None, max_length=200)
    collection_date: str | None = Field(None, max_length=50)
    has_abnormalities: bool | None = None

    model_config = {"extra": "allow"}


class SendLabNotificationRequest(BaseModel):
    """Request body for POST /telegram/bot/send-lab-notification."""

    user_id: int = Field(..., ge=1, description="Telegram user/chat ID")
    results: LabResultsData = Field(..., description="Lab results details")


# =============================================================================
# telegram_integration.py
# =============================================================================


class SendTelegramIntegrationNotificationRequest(BaseModel):
    """Request body for POST /telegram/send-notification (integration)."""

    chat_id: int = Field(..., ge=1, description="Telegram chat ID")
    template_key: str = Field(..., min_length=1, max_length=100, description="Template identifier")
    data: dict[str, Any] = Field(default_factory=dict, description="Template placeholder values")
    language: Literal["ru", "uz", "en"] = Field("ru", description="Template language")

    @field_validator("data")
    @classmethod
    def _validate_data_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > 50:
            raise ValueError("data must not contain more than 50 keys")
        for key, val in v.items():
            if not isinstance(key, str):
                raise ValueError("data keys must be strings")
            if isinstance(val, str) and len(val) > 10_000:
                raise ValueError("data string values must be ≤ 10000 chars")
        return v


class SendAppointmentReminderIntegrationRequest(BaseModel):
    """Request body for POST /telegram/appointment-reminder."""

    patient_phone: str = Field(..., min_length=3, max_length=30, description="Patient phone number")
    appointment_data: AppointmentData = Field(..., description="Appointment details")

    @field_validator("patient_phone")
    @classmethod
    def _strip_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("patient_phone must not be empty")
        return v


class SendLabResultsNotificationRequest(BaseModel):
    """Request body for POST /telegram/lab-results-notification."""

    patient_phone: str = Field(..., min_length=3, max_length=30, description="Patient phone number")
    lab_data: LabResultsData = Field(..., description="Lab results details")

    @field_validator("patient_phone")
    @classmethod
    def _strip_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("patient_phone must not be empty")
        return v


class QrData(BaseModel):
    """QR code data for queue notifications."""

    token: str | None = Field(None, max_length=200)
    doctor_name: str | None = Field(None, max_length=200)
    specialty: str | None = Field(None, max_length=200)
    date: str | None = Field(None, max_length=50)
    time_window: str | None = Field(None, max_length=50)

    model_config = {"extra": "allow"}


class SendQrCodeRequest(BaseModel):
    """Request body for POST /telegram/send-qr-code."""

    patient_phone: str = Field(..., min_length=3, max_length=30, description="Patient phone number")
    qr_data: QrData = Field(..., description="QR code data for queue")

    @field_validator("patient_phone")
    @classmethod
    def _strip_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("patient_phone must not be empty")
        return v


# =============================================================================
# telegram_notifications.py
# =============================================================================


class PaymentData(BaseModel):
    """Payment data for confirmation notifications."""

    payment_id: int | None = None
    id: int | None = None
    amount: int | float | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    payment_date: str | None = Field(None, max_length=50)
    payment_method: str | None = Field(None, max_length=100)
    patient_name: str | None = Field(None, max_length=200)

    model_config = {"extra": "allow"}


class SendPaymentConfirmationRequest(BaseModel):
    """Request body for POST /telegram/send-payment-confirmation.

    Note: `patient_id` is a query param, `payment_data` is the body.
    """

    payment_data: PaymentData = Field(..., description="Payment details")


# =============================================================================
# email_sms_enhanced.py
# =============================================================================


class SendAppointmentReminderEnhancedRequest(BaseModel):
    """Request body for POST /email-sms/send-appointment-reminder-enhanced.

    Note: `appointment_id` and `channels` are query params; only
    `template_data` is a body param. We wrap it in a model so Pydantic
    validates the size and shape.
    """

    template_data: TemplateDataBase | None = None


class SendLabResultsEnhancedRequest(BaseModel):
    """Request body for POST /email-sms/send-lab-results-enhanced."""

    template_data: TemplateDataBase | None = None


class SendPaymentConfirmationEnhancedRequest(BaseModel):
    """Request body for POST /email-sms/send-payment-confirmation-enhanced."""

    payment_data: PaymentData = Field(..., description="Payment details")
    template_data: TemplateDataBase | None = None


class SendBulkEmailRequest(BaseModel):
    """Request body for POST /email-sms/send-bulk-email."""

    recipients: list[RecipientData] = Field(..., min_length=1, max_length=1000, description="Email recipients (max 1000)")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject")
    template_name: str | None = Field(None, max_length=200)
    template_data: TemplateDataBase | None = None
    html_content: str | None = Field(None, max_length=1_000_000, description="Raw HTML content (max 1MB)")
    text_content: str | None = Field(None, max_length=1_000_000, description="Plain text content (max 1MB)")

    @field_validator("subject")
    @classmethod
    def _strip_subject(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("subject must not be empty")
        return v


class SendBulkSmsRequest(BaseModel):
    """Request body for POST /email-sms/send-bulk-sms."""

    recipients: list[RecipientData] = Field(..., min_length=1, max_length=1000, description="SMS recipients (max 1000)")
    message: str | None = Field(None, max_length=1000, description="SMS message text (max 1000 chars)")
    template_name: str | None = Field(None, max_length=200)
    template_data: TemplateDataBase | None = None

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v if v else None


class SendCustomEmailRequest(BaseModel):
    """Request body for POST /email-sms/send-custom-email."""

    to_email: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    template_name: str | None = Field(None, max_length=200)
    template_data: TemplateDataBase | None = None
    html_content: str | None = Field(None, max_length=1_000_000)
    text_content: str | None = Field(None, max_length=1_000_000)
    attachments: list[dict[str, Any]] | None = Field(None, max_length=20)
    priority: Literal["normal", "high"] = "normal"

    @field_validator("subject")
    @classmethod
    def _strip_subject(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("subject must not be empty")
        return v

    @field_validator("attachments")
    @classmethod
    def _validate_attachments(cls, v: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if v is None:
            return None
        for att in v:
            if not isinstance(att, dict):
                raise ValueError("each attachment must be an object")
            if "filename" not in att or not isinstance(att["filename"], str):
                raise ValueError("attachment.filename is required and must be a string")
            if len(att["filename"]) > 255:
                raise ValueError("attachment.filename too long (max 255 chars)")
        return v


class SendCustomSmsRequest(BaseModel):
    """Request body for POST /email-sms/send-custom-sms."""

    phone: str = Field(..., min_length=3, max_length=30)
    message: str | None = Field(None, max_length=1000)
    template_name: str | None = Field(None, max_length=200)
    template_data: TemplateDataBase | None = None
    sender: str | None = Field(None, max_length=50)
    priority: Literal["normal", "high"] = "normal"

    @field_validator("phone")
    @classmethod
    def _strip_phone(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("phone must not be empty")
        return v

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v if v else None


# =============================================================================
# notifications.py
# =============================================================================


class SendSystemAlertRequest(BaseModel):
    """Request body for POST /notifications/send-system-alert.

    Note: `alert_type` and `message` are query params; `details` is the
    optional body. We wrap it to enforce size limits.
    """

    details: TemplateDataBase | None = None


class UpdateNotificationPolicyRequest(BaseModel):
    """Request body for PUT /notifications/settings/{user_id}/policy.

    The notifications endpoint already has a `_normalize_notification_
    policy_payload` helper that validates the policy shape (muted_until,
    snooze_until, dnd, event_controls, family_controls, channel_controls).
    We wrap it in a Pydantic model to enforce the top-level shape and
    reject unknown top-level keys early.
    """

    muted_until: datetime | None = None
    snooze_until: datetime | None = None
    dnd: dict[str, Any] | None = None
    event_controls: dict[str, Any] | None = None
    family_controls: dict[str, Any] | None = None
    channel_controls: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


# =============================================================================
# admin_telegram/_settings.py
# =============================================================================


class UpdateTelegramSettingsRequest(BaseModel):
    """Request body for PUT /admin/telegram/settings.

    Telegram settings are stored as a free-form dict in the clinic_settings
    table (category="telegram"). We enforce known keys + types here.
    Unknown keys are forbidden to prevent setting arbitrary clinic settings
    via this endpoint.
    """

    bot_token: str | None = Field(None, max_length=500)
    webhook_url: str | None = Field(None, max_length=2000)
    admin_chat_ids: list[int] | None = Field(None, max_length=100)
    notifications_enabled: bool | None = None
    appointment_reminders: bool | None = None
    lab_results_notifications: bool | None = None
    payment_notifications: bool | None = None
    default_language: Literal["ru", "uz", "en"] | None = None
    supported_languages: list[str] | None = Field(None, max_length=20)
    bot_username: str | None = Field(None, max_length=200)
    bot_name: str | None = Field(None, max_length=200)

    model_config = {"extra": "forbid"}


# =============================================================================
# telegram_webhook_enhanced.py
# =============================================================================


class TestWebhookRequest(BaseModel):
    """Request body for POST /telegram/webhook/test.

    The enhanced webhook processes arbitrary Telegram Update objects.
    We can't fully validate the Telegram Update schema here (it's huge
    and varies by update type), but we enforce that it's a dict and
    cap its size to prevent memory abuse.
    """

    update_id: int | None = None
    message: dict[str, Any] | None = None
    edited_message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None
    inline_query: dict[str, Any] | None = None
    chosen_inline_result: dict[str, Any] | None = None
    channel_post: dict[str, Any] | None = None
    edited_channel_post: dict[str, Any] | None = None
    poll: dict[str, Any] | None = None
    poll_answer: dict[str, Any] | None = None

    model_config = {"extra": "allow"}

    @field_validator("*")
    @classmethod
    def _reject_huge_dicts(cls, v: Any) -> Any:
        if isinstance(v, dict) and len(v) > 100:
            raise ValueError("nested objects must not contain more than 100 keys")
        return v


# =============================================================================
# telegram_webhook/_routes.py
# =============================================================================


class TelegramWebhookUpdateRequest(BaseModel):
    """Request body for POST /telegram/webhook.

    Telegram Update objects are extremely polymorphic. We validate
    top-level structure and cap nested sizes to prevent memory abuse.
    Full validation happens via aiogram's Update.model_validate().
    """

    update_id: int | None = None
    message: dict[str, Any] | None = None
    edited_message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None
    inline_query: dict[str, Any] | None = None
    chosen_inline_result: dict[str, Any] | None = None
    channel_post: dict[str, Any] | None = None
    edited_channel_post: dict[str, Any] | None = None
    poll: dict[str, Any] | None = None
    poll_answer: dict[str, Any] | None = None

    model_config = {"extra": "allow"}

    @field_validator("*")
    @classmethod
    def _reject_huge_dicts(cls, v: Any) -> Any:
        if isinstance(v, dict) and len(v) > 100:
            raise ValueError("nested objects must not contain more than 100 keys")
        return v


class SendMessageRequest(BaseModel):
    """Request body for POST /telegram/send-message.

    Note: `chat_id`, `message`, `parse_mode` are query params; only
    `reply_markup` is the body. We wrap it in a model.
    """

    reply_markup: dict[str, Any] | None = Field(
        None,
        description="Telegram inline keyboard markup (optional)",
    )

    @field_validator("reply_markup")
    @classmethod
    def _validate_reply_markup_size(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        if len(v) > 50:
            raise ValueError("reply_markup must not contain more than 50 keys")
        return v


__all__ = [
    # Shared
    "TemplateDataBase",
    "RecipientData",
    "AppointmentData",
    "LabResultsData",
    "PaymentData",
    "QrData",
    # telegram_bot.py
    "SetWebhookRequest",
    "SendTelegramNotificationRequest",
    "SendAppointmentReminderRequest",
    "SendLabNotificationRequest",
    # telegram_integration.py
    "SendTelegramIntegrationNotificationRequest",
    "SendAppointmentReminderIntegrationRequest",
    "SendLabResultsNotificationRequest",
    "SendQrCodeRequest",
    # telegram_notifications.py
    "SendPaymentConfirmationRequest",
    # email_sms_enhanced.py
    "SendAppointmentReminderEnhancedRequest",
    "SendLabResultsEnhancedRequest",
    "SendPaymentConfirmationEnhancedRequest",
    "SendBulkEmailRequest",
    "SendBulkSmsRequest",
    "SendCustomEmailRequest",
    "SendCustomSmsRequest",
    # notifications.py
    "SendSystemAlertRequest",
    "UpdateNotificationPolicyRequest",
    # admin_telegram/_settings.py
    "UpdateTelegramSettingsRequest",
    # telegram_webhook_enhanced.py + telegram_webhook/_routes.py
    "TestWebhookRequest",
    "TelegramWebhookUpdateRequest",
    "SendMessageRequest",
]
