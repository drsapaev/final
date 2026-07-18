from __future__ import annotations

import csv  # noqa: F401
import hashlib  # noqa: F401
import hmac  # noqa: F401
import io  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
from datetime import UTC, datetime, timedelta  # noqa: F401
from difflib import SequenceMatcher  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import HTTPException, Request, status  # noqa: F401
from sqlalchemy import or_  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.crud import audit as crud_audit  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.patient import Patient  # noqa: F401
from app.models.telegram_config import (  # noqa: F401
    PatientOnboardingRequest,
    TelegramUser,
)
from app.models.user import User  # noqa: F401
from app.models.visit import Visit  # noqa: F401
from app.schemas.patient_onboarding import (  # noqa: F401
    OnboardingAnalyticsSummaryResponse,
    OnboardingMatchReasons,
    OnboardingPatientCandidate,
    OnboardingPatientSearchRequest,
    OnboardingSearchResponse,
    PatientOnboardingSubmitRequest,
    RegistrarPatientCreateDecisionRequest,
    RegistrarPatientLinkDecisionRequest,
)
from app.services.patient_service import PatientService  # noqa: F401

ONBOARDING_ACTIVE_STATUSES = {"pending_review", "needs_more_info"}
ONBOARDING_REQUEST_TTL_DAYS = 14
DUPLICATE_BLOCK_SCORE_THRESHOLD = 0.85
SAFE_NOTE_MAX_LENGTH = 512
MAX_SEARCH_CANDIDATES = 40
MAX_AUDIT_TRAIL_ITEMS = 12

NEEDS_MORE_INFO_REASON_CODES = frozenset(
    {"wrong_contact", "patient_unreachable", "duplicate_suspected", "other"}
)
REJECT_REASON_CODES = frozenset(
    {
        "wrong_contact",
        "patient_unreachable",
        "duplicate_suspected",
        "invalid_identity",
        "not_clinic_patient",
        "other",
    }
)
SEARCH_AUDIT_ACTION = "registrar_onboarding_duplicate_search"
REVIEWED_AUDIT_ACTION = "registrar_onboarding_reviewed"
SAFE_NOTE_BLOCK_PATTERNS = (
    r"\bpma_[a-z0-9_]+\b",
    r"\bpmo_[a-z0-9_]+\b",
    r"\bentry[_-]?token\b",
    r"\bpayment[_-]?id\b",
    r"\binvoice[_-]?id\b",
    r"\bdiagnos",
    r"\bdiagnoz",
    r"\bsymptom",
    r"\bsimptom",
    r"\blab\b",
    r"\bemr\b",
)


def _normalize_phone(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _phone_matches(search_digits: str, candidate_phone: str | None) -> bool:
    candidate_digits = _normalize_phone(candidate_phone)
    if not search_digits or not candidate_digits:
        return False
    return search_digits == candidate_digits or candidate_digits.endswith(search_digits)


def _mask_phone(value: str | None) -> str | None:
    digits = _normalize_phone(value)
    if not digits:
        return None
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{digits[:2]}*****{digits[-2:]}"


def _safe_name_part(value: str | None, fallback: str = "—") -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    return cleaned or fallback


def _mask_name(value: str | None) -> str:
    name = _safe_name_part(value, fallback="")
    if not name:
        return "Patient"
    parts = [part for part in name.split(" ") if part]
    return " ".join(
        part[:1] + ("****" if len(part) > 1 else "") for part in parts[:2]
    )


def _candidate_secret() -> str:
    return os.getenv("PATIENT_ONBOARDING_CANDIDATE_SALT", "offline-safe")


def _candidate_mask() -> int:
    return int(hashlib.sha256(_candidate_secret().encode("utf-8")).hexdigest()[:8], 16)


def _encode_candidate_id(request_id: int, patient_id: int) -> str:
    obfuscated_patient_id = int(patient_id) ^ _candidate_mask()
    payload = f"{int(request_id)}:{obfuscated_patient_id}"
    signature = hmac.new(
        _candidate_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"cand_{obfuscated_patient_id:x}_{signature}"


def _decode_candidate_id(request_id: int, candidate_id: str) -> int | None:
    token = str(candidate_id or "").strip()
    if not token.startswith("cand_"):
        return None
    body = token[len("cand_") :]
    try:
        obfuscated_hex, provided_signature = body.split("_", 1)
        obfuscated_patient_id = int(obfuscated_hex, 16)
    except (TypeError, ValueError):
        return None
    payload = f"{int(request_id)}:{obfuscated_patient_id}"
    expected_signature = hmac.new(
        _candidate_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None
    return int(obfuscated_patient_id ^ _candidate_mask())


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clean_text(value: str | None, *, max_length: int) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


def _normalize_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _name_similarity(a: str | None, b: str | None) -> float:
    a_value = _normalize_name(a)
    b_value = _normalize_name(b)
    if not a_value or not b_value:
        return 0.0
    return round(SequenceMatcher(None, a_value, b_value).ratio(), 3)


def _safe_note(value: str | None) -> str | None:
    cleaned = _clean_text(value, max_length=SAFE_NOTE_MAX_LENGTH)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    for pattern in SAFE_NOTE_BLOCK_PATTERNS:
        if re.search(pattern, lowered):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"reason": "unsafe_staff_note"},
            )
    return cleaned


def _safe_note_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _patient_ref(patient_id: int | None) -> str | None:
    if not patient_id:
        return None
    return hashlib.sha256(f"patient:{int(patient_id)}".encode()).hexdigest()[:12]


def _request_payload(row: PatientOnboardingRequest) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "status": row.status,
        "languageCode": row.language_code,
        "contactPhone": row.contact_phone,
        "contactName": row.contact_name,
        "desiredService": row.desired_service,
        "desiredBranch": row.desired_branch,
        "desiredDoctorId": row.desired_doctor_id,
        "desiredDate": row.desired_date,
        "desiredTime": row.desired_time,
        "note": row.note,
        "reviewMessage": row.review_message,
        "createdAt": row.created_at,
        "reviewedAt": row.reviewed_at,
        "expiresAt": row.expires_at,
    }


def _default_review_message(action: str, reason_code: str | None) -> str | None:
    if action == "needs_more_info":
        defaults = {
            "wrong_contact": "Please check your contact details and submit the request again.",
            "patient_unreachable": "We could not reach you. Please update your request or contact the clinic.",
            "duplicate_suspected": "We need a quick clarification before linking your request.",
            "other": "The registrar needs a few more safe details before continuing.",
        }
        return defaults.get(reason_code or "", defaults["other"])
    if action == "reject":
        defaults = {
            "wrong_contact": "The contact details could not be confirmed. Please contact the clinic.",
            "patient_unreachable": "We could not complete the review. Please contact the clinic.",
            "duplicate_suspected": "This request could not be completed automatically. Please contact the clinic.",
            "invalid_identity": "We could not confirm the request details. Please contact the clinic.",
            "not_clinic_patient": "The request could not be linked to a clinic patient record. Please contact the clinic.",
            "other": "The request could not be completed. Please contact the clinic.",
        }
        return defaults.get(reason_code or "", defaults["other"])
    if action == "linked_existing":
        return "The registrar linked your Telegram account to your patient record."
    if action == "created_patient":
        return "The registrar created your patient record and linked your Telegram account."
    return None



class PatientOnboardingServiceMixinBase:
    """Type-hint anchor."""
















































