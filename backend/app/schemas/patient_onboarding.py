from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

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


class OnboardingPatientSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    phone: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=256)
    birth_date: date | None = Field(default=None, alias="birthDate")
    branch: str | None = Field(default=None, max_length=128, alias="branch")
    doctor_id: int | None = Field(default=None, alias="doctorId", ge=1)
    preferred_date_from: date | None = Field(default=None, alias="preferredDateFrom")
    preferred_date_to: date | None = Field(default=None, alias="preferredDateTo")


class OnboardingMatchReasons(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_match: bool = False
    name_similarity: float = 0.0
    dob_match: bool = False
    recent_visit_match: bool = False


class OnboardingPatientCandidate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    candidate_id: str = Field(alias="candidateId")
    patient_id_hash: str | None = Field(default=None, alias="patientIdHash", max_length=64)
    masked_phone: str | None = Field(default=None, alias="maskedPhone", max_length=32)
    masked_name: str | None = Field(default=None, alias="maskedName", max_length=256)
    dob_year: int | None = Field(default=None, alias="dobYear", ge=1900, le=2100)
    dob_month: int | None = Field(default=None, alias="dobMonth", ge=1, le=12)
    recent_visit_summary: str | None = Field(default=None, alias="recentVisitSummary", max_length=180)
    branch: str | None = Field(default=None, max_length=128)
    last_seen_at: str | None = Field(default=None, alias="lastSeenAt")
    match_score: float = Field(ge=0.0, le=1.0, alias="matchScore")
    match_reasons: OnboardingMatchReasons = Field(alias="matchReasons")
    risk_level: Literal["low", "medium", "high"] = "low"


class OnboardingSearchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: int = Field(alias="requestId")
    candidates: list[OnboardingPatientCandidate] = Field(default_factory=list)
    reviewed: bool = False
    high_confidence_candidate_exists: bool = Field(
        default=False,
        alias="highConfidenceCandidateExists",
    )
    top_risk_level: Literal["low", "medium", "high"] = Field(
        default="low", alias="topRiskLevel"
    )


class OnboardingNeedsMoreInfoReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal[
        "wrong_contact",
        "patient_unreachable",
        "duplicate_suspected",
        "other",
    ]


class OnboardingRejectedReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal[
        "wrong_contact",
        "patient_unreachable",
        "duplicate_suspected",
        "invalid_identity",
        "not_clinic_patient",
        "other",
    ]


class RegistrarOnboardingActionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    action: Literal["link_existing", "create_new", "request_more_info", "reject"] = "link_existing"
    candidate_id: str | None = Field(default=None, alias="candidateId")
    reason_code: str | None = Field(default=None, alias="reasonCode", max_length=64)
    safe_note: str | None = Field(default=None, alias="safeNote", max_length=512)
    confirm_create_despite_duplicates: bool = Field(default=False, alias="confirmCreateDespiteDuplicates")


class RegistrarPatientLinkDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    candidate_id: str = Field(alias="candidateId")
    reason_code: str | None = Field(default=None, alias="reasonCode", max_length=64)
    safe_note: str | None = Field(default=None, alias="safeNote", max_length=512)


class RegistrarPatientCreateDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    patient: PatientCreate
    review_candidate_id: str | None = Field(default=None, alias="reviewCandidateId")
    confirm_create_despite_duplicates: bool = Field(default=False, alias="confirmCreateDespiteDuplicates")
    reason_code: str | None = Field(default=None, alias="reasonCode", max_length=64)
    safe_note: str | None = Field(default=None, alias="safeNote", max_length=512)


class RegistrarOnboardingReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason_code: str | None = Field(default=None, alias="reasonCode", max_length=64)
    safe_note: str | None = Field(default=None, alias="safeNote", max_length=512)


class OnboardingAuditTrailItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    action: str
    reviewer: str | None = None
    reviewer_role: str | None = Field(default=None, alias="reviewerRole")
    timestamp: datetime | None = None
    reason_code: str | None = Field(default=None, alias="reasonCode")


class OnboardingNotificationPreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str
    body: str
    cta_label: str = Field(alias="ctaLabel")


class OnboardingAnalyticsFunnel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    started: int = 0
    opened: int = 0
    submitted: int = 0
    pending_review: int = Field(default=0, alias="pendingReview")
    needs_more_info: int = Field(default=0, alias="needsMoreInfo")
    linked_existing: int = Field(default=0, alias="linkedExisting")
    created_patient: int = Field(default=0, alias="createdPatient")
    rejected: int = 0
    expired: int = 0


class OnboardingAnalyticsDashboard(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    pending_requests: int = Field(default=0, alias="pendingRequests")
    overdue_requests: int = Field(default=0, alias="overdueRequests")
    today_submitted: int = Field(default=0, alias="todaySubmitted")
    linked_or_created_today: int = Field(default=0, alias="linkedOrCreatedToday")
    average_review_time_minutes: float = Field(default=0.0, alias="averageReviewTimeMinutes")
    average_pending_time_minutes: float = Field(default=0.0, alias="averagePendingTimeMinutes")
    conversion_rate: float = Field(default=0.0, alias="conversionRate")
    rejection_rate: float = Field(default=0.0, alias="rejectionRate")
    needs_more_info_rate: float = Field(default=0.0, alias="needsMoreInfoRate")


class OnboardingAnalyticsSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    funnel: OnboardingAnalyticsFunnel
    dashboard: OnboardingAnalyticsDashboard
    generated_at: datetime = Field(alias="generatedAt")


class RegistrarOnboardingRequestOut(PatientOnboardingRequestOut):
    telegram_user_id: int | None = Field(default=None, alias="telegramUserId")
    telegram_chat_id: int = Field(alias="telegramChatId")
    reviewed_by_user_id: int | None = Field(default=None, alias="reviewedByUserId")
    resolved_patient_id: int | None = Field(default=None, alias="resolvedPatientId")
    duplicate_review_snapshot: dict[str, Any] | None = Field(
        default=None,
        alias="duplicateReviewSnapshot",
    )
    has_duplicate_review: bool = Field(default=False, alias="hasDuplicateReview")
    last_reviewed_at: datetime | None = Field(default=None, alias="lastReviewedAt")
    audit_trail: list[OnboardingAuditTrailItem] = Field(
        default_factory=list,
        alias="auditTrail",
    )
    notification_preview: OnboardingNotificationPreview | None = Field(
        default=None,
        alias="notificationPreview",
    )


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
