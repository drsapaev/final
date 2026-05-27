from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.patient import PatientCreate


PatientOnboardingStatus = Literal[
    "pending_review",
    "linked_existing",
    "created_patient",
    "needs_more_info",
    "rejected",
    "cancelled",
    "expired",
]


class PatientOnboardingAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    init_data: str | None = Field(default=None, alias="initData")
    entry_token: str | None = Field(default=None, alias="entryToken")
    section: str | None = None


class PatientOnboardingSubmitRequest(PatientOnboardingAuthRequest):
    language_code: str | None = Field(default=None, alias="languageCode", max_length=16)
    contact_phone: str | None = Field(default=None, alias="contactPhone", max_length=32)
    contact_name: str | None = Field(default=None, alias="contactName", max_length=256)
    desired_service: str | None = Field(
        default=None, alias="desiredService", max_length=128
    )
    desired_branch: str | None = Field(
        default=None, alias="desiredBranch", max_length=128
    )
    desired_doctor_id: int | None = Field(default=None, alias="desiredDoctorId", ge=1)
    desired_date: date | None = Field(default=None, alias="desiredDate")
    desired_time: str | None = Field(default=None, alias="desiredTime", max_length=8)
    note: str | None = Field(default=None, max_length=1000)


class PatientOnboardingRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    status: PatientOnboardingStatus
    language_code: str = Field(alias="languageCode")
    contact_phone: str | None = Field(default=None, alias="contactPhone")
    contact_name: str | None = Field(default=None, alias="contactName")
    desired_service: str | None = Field(default=None, alias="desiredService")
    desired_branch: str | None = Field(default=None, alias="desiredBranch")
    desired_doctor_id: int | None = Field(default=None, alias="desiredDoctorId")
    desired_date: date | None = Field(default=None, alias="desiredDate")
    desired_time: str | None = Field(default=None, alias="desiredTime")
    note: str | None = None
    review_message: str | None = Field(default=None, alias="reviewMessage")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    reviewed_at: datetime | None = Field(default=None, alias="reviewedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")


class PatientOnboardingSubmitResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request: PatientOnboardingRequestOut
    created: bool
    message_key: str = Field(alias="messageKey")
    safe_next_action: str = Field(alias="safeNextAction")


class PatientOnboardingStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request: PatientOnboardingRequestOut | None = None
    message_key: str = Field(alias="messageKey")
    safe_next_action: str = Field(alias="safeNextAction")


class RegistrarOnboardingRequestOut(PatientOnboardingRequestOut):
    telegram_user_id: int | None = Field(default=None, alias="telegramUserId")
    telegram_chat_id: int = Field(alias="telegramChatId")
    reviewed_by_user_id: int | None = Field(default=None, alias="reviewedByUserId")
    resolved_patient_id: int | None = Field(default=None, alias="resolvedPatientId")


class RegistrarOnboardingListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[RegistrarOnboardingRequestOut]
    total: int


class RegistrarLinkExistingPatientRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    patient_id: int = Field(alias="patientId", ge=1)
    review_message: str | None = Field(default=None, alias="reviewMessage", max_length=512)


class RegistrarCreatePatientFromOnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    patient: PatientCreate
    review_message: str | None = Field(default=None, alias="reviewMessage", max_length=512)


class RegistrarReviewMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    review_message: str | None = Field(default=None, alias="reviewMessage", max_length=512)


class RegistrarOnboardingActionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request: RegistrarOnboardingRequestOut
    message_key: str = Field(alias="messageKey")
