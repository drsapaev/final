from __future__ import annotations

import csv
import hashlib
import hmac
import io
import os
import re
from datetime import UTC, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.crud import audit as crud_audit
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.telegram_config import PatientOnboardingRequest, TelegramUser
from app.models.user import User
from app.models.visit import Visit
from app.schemas.patient_onboarding import (
    OnboardingAnalyticsSummaryResponse,
    OnboardingMatchReasons,
    OnboardingPatientCandidate,
    OnboardingPatientSearchRequest,
    OnboardingSearchResponse,
    PatientOnboardingSubmitRequest,
    RegistrarPatientCreateDecisionRequest,
    RegistrarPatientLinkDecisionRequest,
)
from app.services.patient_service import PatientService

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


class PatientOnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _request_signature(row: PatientOnboardingRequest) -> str:
        return hashlib.sha256(
            f"req:{int(row.id)}:{int(row.telegram_chat_id)}".encode()
        ).hexdigest()[:16]

    def _validate_audit_actor(self, actor: User) -> None:
        if getattr(actor, "is_superuser", False):
            return
        if actor.role not in {"Admin", "Registrar"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": "action_forbidden"},
            )

    def _record_audit(
        self,
        *,
        action: str,
        row: PatientOnboardingRequest,
        actor_user_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        audit_payload = {
            "request_signature": self._request_signature(row),
            "status": row.status,
            "has_contact_phone": bool(row.contact_phone),
            "has_contact_name": bool(row.contact_name),
            **(payload or {}),
        }
        crud_audit.log(
            self.db,
            action=action,
            entity_type="patient_onboarding_request",
            entity_id=int(row.id),
            actor_user_id=actor_user_id,
            payload=audit_payload,
        )

    def _refresh_expired(self, row: PatientOnboardingRequest) -> PatientOnboardingRequest:
        if (
            row.status in ONBOARDING_ACTIVE_STATUSES
            and row.expires_at is not None
            and _as_aware_utc(row.expires_at) < _utc_now()
        ):
            row.status = "expired"
            row.reviewed_at = _utc_now()
            row.updated_at = _utc_now()
            self._record_audit(action="patient_onboarding_expired", row=row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def _patient_name(self, patient: Patient) -> str:
        return " ".join(
            part
            for part in (
                _safe_name_part(patient.last_name, ""),
                _safe_name_part(patient.first_name, ""),
                _safe_name_part(patient.middle_name, ""),
            )
            if part
        ).strip()

    def _staff_display_name(self, actor_user_id: int | None) -> tuple[str | None, str | None]:
        if not actor_user_id:
            return None, None
        user = self.db.query(User).filter(User.id == int(actor_user_id)).first()
        if user is None:
            return None, None
        label = _mask_name(user.full_name or user.username or user.role)
        return label, user.role

    def _last_visit_for_patient(self, patient_id: int) -> Visit | None:
        return (
            self.db.query(Visit)
            .filter(Visit.patient_id == int(patient_id))
            .order_by(Visit.created_at.desc(), Visit.id.desc())
            .first()
        )

    def _candidate_for_patient(
        self,
        request_row: PatientOnboardingRequest,
        patient: Patient,
        *,
        search_input: OnboardingPatientSearchRequest,
    ) -> OnboardingPatientCandidate:
        patient_name = self._patient_name(patient)
        candidate_token = _encode_candidate_id(int(request_row.id), int(patient.id))
        search_phone = _normalize_phone(search_input.phone or request_row.contact_phone or "")
        patient_phone = _normalize_phone(patient.phone or "")
        last_visit = self._last_visit_for_patient(int(patient.id))
        recent_visit_match = False
        last_seen = None
        recent_visit_summary = None
        branch_label = None
        if last_visit is not None:
            last_seen_at = _as_aware_utc(last_visit.created_at)
            if last_seen_at is not None:
                last_seen = last_seen_at.isoformat()
                recent_visit_match = (_utc_now() - last_seen_at).days <= 180
            safe_visit_date = last_visit.visit_date.isoformat() if last_visit.visit_date else None
            branch_label = _clean_text(last_visit.department, max_length=64)
            recent_visit_summary = " | ".join(
                value
                for value in (
                    f"Seen {safe_visit_date}" if safe_visit_date else None,
                    branch_label,
                    f"status={last_visit.status}" if last_visit.status else None,
                )
                if value
            ) or None

        phone_match = _phone_matches(search_phone, patient_phone)
        dob_match = bool(
            search_input.birth_date is not None
            and patient.birth_date is not None
            and search_input.birth_date == patient.birth_date
        )
        name_similarity = _name_similarity(
            search_input.name or request_row.contact_name,
            patient_name,
        )
        score = round(
            (0.60 if phone_match else 0.0)
            + (0.20 * name_similarity)
            + (0.15 if dob_match else 0.0)
            + (0.05 if recent_visit_match else 0.0),
            3,
        )
        score = min(1.0, max(0.0, score))
        if score >= DUPLICATE_BLOCK_SCORE_THRESHOLD:
            risk_level = "high"
        elif score >= 0.65:
            risk_level = "medium"
        else:
            risk_level = "low"

        reasons = OnboardingMatchReasons(
            phone_match=phone_match,
            name_similarity=name_similarity,
            dob_match=dob_match,
            recent_visit_match=recent_visit_match,
        )
        return OnboardingPatientCandidate(
            candidate_id=candidate_token,
            patient_id_hash=_patient_ref(int(patient.id)),
            masked_phone=_mask_phone(patient.phone),
            masked_name=_mask_name(patient_name),
            dob_year=patient.birth_date.year if patient.birth_date else None,
            dob_month=patient.birth_date.month if patient.birth_date else None,
            recent_visit_summary=recent_visit_summary,
            branch=branch_label or search_input.branch or request_row.desired_branch,
            last_seen_at=last_seen,
            match_score=score,
            match_reasons=reasons,
            risk_level=risk_level,
        )

    def search_candidates(
        self,
        request_row: PatientOnboardingRequest,
        search_payload: OnboardingPatientSearchRequest,
    ) -> OnboardingSearchResponse:
        phone = _normalize_phone(search_payload.phone or request_row.contact_phone or "")
        name = search_payload.name or request_row.contact_name
        birth_date = search_payload.birth_date

        query = self.db.query(Patient).filter(Patient.is_deleted.is_not(True))
        exact_phone_rows: list[Patient] = []
        if phone:
            phone_rows = (
                self.db.query(Patient)
                .filter(
                    Patient.is_deleted.is_not(True),
                    Patient.phone.is_not(None),
                )
                .order_by(Patient.last_name.asc(), Patient.first_name.asc())
                .all()
            )
            exact_phone_rows = [
                patient for patient in phone_rows if _phone_matches(phone, patient.phone)
            ]
            query = query.filter(Patient.phone.is_not(None))
        name_parts = [
            part.strip().lower()
            for part in re.split(r"\s+", str(name or "").strip())
            if part.strip()
        ]
        if name_parts:
            like_filters = []
            for part in name_parts:
                like_filters.extend(
                    [
                        Patient.first_name.ilike(f"%{part}%"),
                        Patient.last_name.ilike(f"%{part}%"),
                        Patient.middle_name.ilike(f"%{part}%"),
                    ]
                )
            query = query.filter(or_(*like_filters))
        if birth_date is not None:
            query = query.filter(Patient.birth_date == birth_date)

        candidate_rows = (
            query.order_by(Patient.last_name.asc(), Patient.first_name.asc())
            .limit(MAX_SEARCH_CANDIDATES)
            .all()
        )
        if exact_phone_rows:
            seen_ids = {int(patient.id) for patient in exact_phone_rows}
            candidate_rows = exact_phone_rows + [
                patient
                for patient in candidate_rows
                if int(patient.id) not in seen_ids
            ]
            candidate_rows = candidate_rows[:MAX_SEARCH_CANDIDATES]
        candidates = [
            self._candidate_for_patient(
                request_row,
                patient,
                search_input=search_payload,
            )
            for patient in candidate_rows
        ]
        candidates.sort(
            key=lambda item: (item.match_score, item.risk_level == "high"),
            reverse=True,
        )
        top = candidates[0] if candidates else None
        return OnboardingSearchResponse(
            request_id=int(request_row.id),
            candidates=candidates,
            reviewed=bool(phone or name_parts or birth_date or search_payload.branch),
            high_confidence_candidate_exists=any(
                candidate.match_score >= DUPLICATE_BLOCK_SCORE_THRESHOLD
                for candidate in candidates
            ),
            top_risk_level=top.risk_level if top is not None else "low",
        )

    def _duplicate_search_payload(
        self,
        response: OnboardingSearchResponse,
        *,
        search_payload: OnboardingPatientSearchRequest,
    ) -> dict[str, Any]:
        return {
            "reason_code": "duplicate_search",
            "searched_at": _utc_now().isoformat(),
            "candidate_count": len(response.candidates),
            "top_risk_level": response.top_risk_level,
            "high_confidence_candidate_exists": response.high_confidence_candidate_exists,
            "query": {
                "has_phone": bool(search_payload.phone),
                "has_name": bool(search_payload.name),
                "has_birth_date": bool(search_payload.birth_date),
                "has_branch": bool(search_payload.branch),
                "has_doctor": bool(search_payload.doctor_id),
                "has_preferred_date": bool(
                    search_payload.preferred_date_from or search_payload.preferred_date_to
                ),
            },
            "top_candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "masked_name": candidate.masked_name,
                    "masked_phone": candidate.masked_phone,
                    "dob_year": candidate.dob_year,
                    "dob_month": candidate.dob_month,
                    "recent_visit_summary": candidate.recent_visit_summary,
                    "branch": candidate.branch,
                    "match_score": candidate.match_score,
                    "risk_level": candidate.risk_level,
                    "match_reasons": candidate.match_reasons.model_dump(mode="json"),
                }
                for candidate in response.candidates[:5]
            ],
        }

    def _latest_duplicate_review_log(
        self,
        request_id: int,
    ) -> AuditLog | None:
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "patient_onboarding_request",
                AuditLog.entity_id == int(request_id),
                AuditLog.action == SEARCH_AUDIT_ACTION,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .first()
        )

    def _safe_duplicate_review_snapshot(
        self,
        row: PatientOnboardingRequest,
    ) -> dict[str, Any] | None:
        log_row = self._latest_duplicate_review_log(int(row.id))
        if log_row is None or not isinstance(log_row.payload, dict):
            return None
        reviewed_at = _as_aware_utc(log_row.created_at)
        request_updated_at = _as_aware_utc(row.updated_at or row.created_at)
        if (
            reviewed_at is not None
            and request_updated_at is not None
            and reviewed_at < request_updated_at
        ):
            return None
        payload = log_row.payload
        return {
            "searchedAt": payload.get("searched_at"),
            "candidateCount": payload.get("candidate_count", 0),
            "topRiskLevel": payload.get("top_risk_level", "low"),
            "highConfidenceCandidateExists": bool(
                payload.get("high_confidence_candidate_exists", False)
            ),
            "topCandidates": payload.get("top_candidates") or [],
        }

    def _build_audit_trail(self, request_id: int) -> list[dict[str, Any]]:
        rows = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "patient_onboarding_request",
                AuditLog.entity_id == int(request_id),
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(MAX_AUDIT_TRAIL_ITEMS)
            .all()
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = row.payload if isinstance(row.payload, dict) else {}
            reviewer, reviewer_role = self._staff_display_name(row.actor_user_id)
            items.append(
                {
                    "action": row.action,
                    "reviewer": reviewer,
                    "reviewerRole": reviewer_role,
                    "timestamp": row.created_at,
                    "reasonCode": payload.get("reason_code"),
                }
            )
        return items

    def _notification_preview(self, row: PatientOnboardingRequest) -> dict[str, Any]:
        messages = {
            "pending_review": {
                "title": "Request received",
                "body": "The registrar will review your request before protected sections open.",
                "ctaLabel": "Open Mini App",
            },
            "needs_more_info": {
                "title": "More information requested",
                "body": "The registrar needs a few safe details before continuing.",
                "ctaLabel": "Update request",
            },
            "linked_existing": {
                "title": "Request approved",
                "body": "Your Telegram account is linked. Open the protected patient cabinet.",
                "ctaLabel": "Open cabinet",
            },
            "created_patient": {
                "title": "Patient profile ready",
                "body": "A clinic staff member created and linked your patient profile.",
                "ctaLabel": "Open cabinet",
            },
            "rejected": {
                "title": "Request requires clinic support",
                "body": "Please contact the clinic to continue safely.",
                "ctaLabel": "Contact clinic",
            },
            "expired": {
                "title": "Request expired",
                "body": "Open Mini App from Telegram and submit a fresh request.",
                "ctaLabel": "Submit again",
            },
        }
        return messages.get(
            row.status,
            {
                "title": "Request update",
                "body": "Open Mini App from Telegram to continue safely.",
                "ctaLabel": "Open Mini App",
            },
        )

    def _registrar_request_payload(self, row: PatientOnboardingRequest) -> dict[str, Any]:
        duplicate_snapshot = self._safe_duplicate_review_snapshot(row)
        return {
            **_request_payload(row),
            "telegramUserId": row.telegram_user_id,
            "telegramChatId": int(row.telegram_chat_id),
            "reviewedByUserId": row.reviewed_by_user_id,
            "resolvedPatientId": None,
            "duplicateReviewSnapshot": duplicate_snapshot,
            "hasDuplicateReview": duplicate_snapshot is not None,
            "lastReviewedAt": (
                duplicate_snapshot.get("searchedAt")
                if duplicate_snapshot is not None
                else row.reviewed_at
            ),
            "auditTrail": self._build_audit_trail(int(row.id)),
            "notificationPreview": self._notification_preview(row),
        }

    def latest_for_telegram_user(
        self,
        telegram_user: TelegramUser,
    ) -> PatientOnboardingRequest | None:
        row = (
            self.db.query(PatientOnboardingRequest)
            .filter(PatientOnboardingRequest.telegram_chat_id == int(telegram_user.chat_id))
            .order_by(
                PatientOnboardingRequest.created_at.desc(),
                PatientOnboardingRequest.id.desc(),
            )
            .first()
        )
        if row is None:
            return None
        return self._refresh_expired(row)

    def submit(
        self,
        *,
        telegram_user: TelegramUser,
        payload: PatientOnboardingSubmitRequest,
    ) -> tuple[PatientOnboardingRequest, bool]:
        if getattr(telegram_user, "patient_id", None):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "linked_patient_already_exists"},
            )

        desired_doctor_id = payload.desired_doctor_id
        if desired_doctor_id is not None:
            doctor = self.db.query(Doctor).filter(Doctor.id == desired_doctor_id).first()
            if doctor is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"reason": "desired_doctor_not_found"},
                )

        existing = self.latest_for_telegram_user(telegram_user)
        row = existing if existing is not None and existing.status in ONBOARDING_ACTIVE_STATUSES else None
        created = row is None
        if row is None:
            row = PatientOnboardingRequest(
                telegram_user_id=getattr(telegram_user, "id", None),
                telegram_chat_id=int(telegram_user.chat_id),
                status="pending_review",
                expires_at=_utc_now() + timedelta(days=ONBOARDING_REQUEST_TTL_DAYS),
            )
            self.db.add(row)

        row.language_code = _clean_text(payload.language_code, max_length=16) or getattr(
            telegram_user, "language_code", "ru"
        )
        row.contact_phone = _clean_text(payload.contact_phone, max_length=32)
        row.contact_name = _clean_text(payload.contact_name, max_length=256) or _clean_text(
            " ".join(
                part
                for part in (
                    getattr(telegram_user, "first_name", None),
                    getattr(telegram_user, "last_name", None),
                )
                if part
            ),
            max_length=256,
        )
        row.desired_service = _clean_text(payload.desired_service, max_length=128)
        row.desired_branch = _clean_text(payload.desired_branch, max_length=128)
        row.desired_doctor_id = desired_doctor_id
        row.desired_date = payload.desired_date
        row.desired_time = _clean_text(payload.desired_time, max_length=8)
        row.note = _clean_text(payload.note, max_length=1000)
        row.status = "pending_review"
        row.review_message = None
        row.reviewed_by_user_id = None
        row.resolved_patient_id = None
        row.reviewed_at = None
        row.updated_at = _utc_now()

        self.db.flush()
        self._record_audit(
            action="patient_onboarding_submitted",
            row=row,
            payload={"created": created},
        )
        self.db.commit()
        self.db.refresh(row)
        return row, created

    def own_status_response(self, telegram_user: TelegramUser) -> dict[str, Any]:
        row = self.latest_for_telegram_user(telegram_user)
        if row is None:
            return {
                "request": None,
                "messageKey": "patient_onboarding_not_found",
                "safeNextAction": "submit_onboarding_request",
            }
        return {
            "request": _request_payload(row),
            "messageKey": f"patient_onboarding_{row.status}",
            "safeNextAction": self.safe_next_action(row),
        }

    @staticmethod
    def safe_next_action(row: PatientOnboardingRequest) -> str:
        if row.status == "needs_more_info":
            return "submit_more_info"
        if row.status in {"linked_existing", "created_patient"}:
            return "open_protected_patient_cabinet"
        if row.status in {"rejected", "cancelled", "expired"}:
            return "contact_registrar_or_submit_new_request"
        return "wait_for_registrar_review"

    def submit_response(self, row: PatientOnboardingRequest, *, created: bool) -> dict[str, Any]:
        return {
            "request": _request_payload(row),
            "created": created,
            "messageKey": "patient_onboarding_submitted",
            "safeNextAction": self.safe_next_action(row),
        }

    def list_pending(
        self,
        *,
        status_filter: str = "pending_review",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        query = self.db.query(PatientOnboardingRequest)
        if status_filter:
            query = query.filter(PatientOnboardingRequest.status == status_filter)
        total = query.count()
        rows = (
            query.order_by(
                PatientOnboardingRequest.created_at.asc(),
                PatientOnboardingRequest.id.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = [self._registrar_request_payload(self._refresh_expired(row)) for row in rows]
        return {"items": items, "total": total}

    def analytics_summary(self) -> dict[str, Any]:
        now = _utc_now()
        start_of_day = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)

        rows = self.db.query(PatientOnboardingRequest).all()
        refreshed_rows = [self._refresh_expired(row) for row in rows]
        status_counts = {
            "pending_review": 0,
            "needs_more_info": 0,
            "linked_existing": 0,
            "created_patient": 0,
            "rejected": 0,
            "expired": 0,
        }
        review_durations: list[float] = []
        pending_durations: list[float] = []
        today_submitted = 0
        linked_or_created_today = 0
        overdue_requests = 0

        for row in refreshed_rows:
            if row.status in status_counts:
                status_counts[row.status] += 1
            created_at = _as_aware_utc(row.created_at)
            reviewed_at = _as_aware_utc(row.reviewed_at)
            if created_at is not None and created_at >= start_of_day:
                today_submitted += 1
            if created_at is not None and row.status in ONBOARDING_ACTIVE_STATUSES:
                pending_minutes = (now - created_at).total_seconds() / 60
                pending_durations.append(pending_minutes)
                if pending_minutes >= 240:
                    overdue_requests += 1
            if created_at is not None and reviewed_at is not None:
                review_durations.append((reviewed_at - created_at).total_seconds() / 60)
                if row.status in {"linked_existing", "created_patient"} and reviewed_at >= start_of_day:
                    linked_or_created_today += 1

        submitted_total = len(refreshed_rows)
        linked_total = status_counts["linked_existing"] + status_counts["created_patient"]
        rejected_total = status_counts["rejected"]
        needs_more_info_total = status_counts["needs_more_info"]

        telemetry_actions = {
            "patient_onboarding_started",
            "patient_onboarding_opened",
        }
        telemetry_counts = dict.fromkeys(telemetry_actions, 0)
        for action, count in (
            self.db.query(AuditLog.action, AuditLog.id)
            .filter(
                AuditLog.entity_type == "telegram_onboarding_telemetry",
                AuditLog.action.in_(tuple(telemetry_actions)),
            )
            .all()
        ):
            telemetry_counts[str(action)] = telemetry_counts.get(str(action), 0) + 1

        conversion_rate = round((linked_total / submitted_total) * 100, 1) if submitted_total else 0.0
        rejection_rate = round((rejected_total / submitted_total) * 100, 1) if submitted_total else 0.0
        needs_more_info_rate = round((needs_more_info_total / submitted_total) * 100, 1) if submitted_total else 0.0
        average_review_time = round(sum(review_durations) / len(review_durations), 1) if review_durations else 0.0
        average_pending_time = round(sum(pending_durations) / len(pending_durations), 1) if pending_durations else 0.0

        return OnboardingAnalyticsSummaryResponse(
            funnel={
                "started": telemetry_counts.get("patient_onboarding_started", 0),
                "opened": telemetry_counts.get("patient_onboarding_opened", 0),
                "submitted": submitted_total,
                "pendingReview": status_counts["pending_review"],
                "needsMoreInfo": needs_more_info_total,
                "linkedExisting": status_counts["linked_existing"],
                "createdPatient": status_counts["created_patient"],
                "rejected": rejected_total,
                "expired": status_counts["expired"],
            },
            dashboard={
                "pendingRequests": status_counts["pending_review"],
                "overdueRequests": overdue_requests,
                "todaySubmitted": today_submitted,
                "linkedOrCreatedToday": linked_or_created_today,
                "averageReviewTimeMinutes": average_review_time,
                "averagePendingTimeMinutes": average_pending_time,
                "conversionRate": conversion_rate,
                "rejectionRate": rejection_rate,
                "needsMoreInfoRate": needs_more_info_rate,
            },
            generatedAt=now,
        ).model_dump(by_alias=True)

    def export_requests_csv(self, *, status_filter: str = "") -> str:
        query = self.db.query(PatientOnboardingRequest)
        if status_filter:
            query = query.filter(PatientOnboardingRequest.status == status_filter)
        rows = query.order_by(
            PatientOnboardingRequest.created_at.desc(),
            PatientOnboardingRequest.id.desc(),
        ).all()

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "request_id",
                "status",
                "created_at",
                "reviewed_at",
                "contact_name_masked",
                "contact_phone_masked",
                "desired_service",
                "desired_branch",
                "desired_date",
                "desired_time",
                "reviewed_by",
                "reviewer_role",
                "reason_code",
            ],
        )
        writer.writeheader()
        for row in rows:
            row = self._refresh_expired(row)
            audit_trail = self._build_audit_trail(int(row.id))
            latest_audit = audit_trail[0] if audit_trail else {}
            reviewed_by, reviewer_role = self._staff_display_name(row.reviewed_by_user_id)
            writer.writerow(
                {
                    "request_id": int(row.id),
                    "status": row.status,
                    "created_at": _as_aware_utc(row.created_at).isoformat() if row.created_at else "",
                    "reviewed_at": _as_aware_utc(row.reviewed_at).isoformat() if row.reviewed_at else "",
                    "contact_name_masked": _mask_name(row.contact_name),
                    "contact_phone_masked": _mask_phone(row.contact_phone) or "",
                    "desired_service": row.desired_service or "",
                    "desired_branch": row.desired_branch or "",
                    "desired_date": row.desired_date.isoformat() if row.desired_date else "",
                    "desired_time": row.desired_time or "",
                    "reviewed_by": reviewed_by or "",
                    "reviewer_role": reviewer_role or "",
                    "reason_code": latest_audit.get("reasonCode") or "",
                }
            )
        return output.getvalue()

    def _get_reviewable(self, request_id: int) -> PatientOnboardingRequest:
        row = (
            self.db.query(PatientOnboardingRequest)
            .filter(PatientOnboardingRequest.id == int(request_id))
            .first()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"reason": "onboarding_request_not_found"},
            )
        row = self._refresh_expired(row)
        if row.status not in ONBOARDING_ACTIVE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "onboarding_request_not_reviewable"},
            )
        return row

    def search_candidates_for_request(
        self,
        *,
        request_id: int,
        actor: User,
        search_payload: OnboardingPatientSearchRequest,
    ) -> dict[str, Any]:
        self._validate_audit_actor(actor)
        row = self._get_reviewable(request_id)
        response = self.search_candidates(row, search_payload)
        audit_payload = self._duplicate_search_payload(response, search_payload=search_payload)
        self._record_audit(
            action=SEARCH_AUDIT_ACTION,
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self.db.commit()
        return response.model_dump(by_alias=True)

    def _require_duplicate_review(
        self,
        row: PatientOnboardingRequest,
    ) -> dict[str, Any]:
        snapshot = self._safe_duplicate_review_snapshot(row)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "duplicate_review_required"},
            )
        return snapshot

    def _resolve_candidate_patient(
        self,
        request_row: PatientOnboardingRequest,
        candidate_id: str,
    ) -> Patient | None:
        patient_id = _decode_candidate_id(int(request_row.id), candidate_id)
        if patient_id is None:
            return None
        return (
            self.db.query(Patient)
            .filter(Patient.id == int(patient_id), Patient.is_deleted.is_not(True))
            .first()
        )

    def link_existing_patient(
        self,
        *,
        request_id: int,
        payload: RegistrarPatientLinkDecisionRequest,
        actor: User,
    ) -> dict[str, Any]:
        self._validate_audit_actor(actor)
        row = self._get_reviewable(request_id)
        safe_note = _safe_note(payload.safe_note)
        snapshot = self._require_duplicate_review(row)
        candidate_ids = {
            str(item.get("candidate_id"))
            for item in snapshot.get("topCandidates") or []
            if item.get("candidate_id")
        }
        if payload.candidate_id not in candidate_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "candidate_review_required"},
            )
        patient = self._resolve_candidate_patient(row, payload.candidate_id)
        if patient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"reason": "patient_not_found"},
            )
        telegram_user = (
            self.db.query(TelegramUser)
            .filter(TelegramUser.id == row.telegram_user_id)
            .first()
        )
        if telegram_user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "telegram_user_not_found"},
            )
        telegram_user.patient_id = int(patient.id)
        row.status = "linked_existing"
        row.resolved_patient_id = int(patient.id)
        row.reviewed_by_user_id = int(actor.id)
        row.reviewed_at = _utc_now()
        row.review_message = safe_note or _default_review_message(
            "linked_existing",
            payload.reason_code,
        )
        row.updated_at = _utc_now()
        audit_payload = {
            "reason_code": payload.reason_code,
            "candidate_id": payload.candidate_id,
            "candidate_match_confirmed": True,
            "resolved_patient_ref": _patient_ref(int(patient.id)),
            "note_hash": _safe_note_hash(safe_note),
        }
        self._record_audit(
            action=REVIEWED_AUDIT_ACTION,
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self._record_audit(
            action="patient_onboarding_linked_existing",
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": self._registrar_request_payload(row),
            "messageKey": "patient_onboarding_linked_existing",
        }

    def create_patient_from_request(
        self,
        *,
        request: Request,
        request_id: int,
        payload: RegistrarPatientCreateDecisionRequest,
        actor: User,
    ) -> dict[str, Any]:
        self._validate_audit_actor(actor)
        row = self._get_reviewable(request_id)
        safe_note = _safe_note(payload.safe_note)
        snapshot = self._require_duplicate_review(row)
        top_candidates = snapshot.get("topCandidates") or []
        high_confidence_exists = bool(snapshot.get("highConfidenceCandidateExists"))
        if high_confidence_exists and not payload.confirm_create_despite_duplicates:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": "duplicate_review_override_required"},
            )
        if high_confidence_exists and not _clean_text(payload.reason_code, max_length=64):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"reason": "duplicate_override_reason_required"},
            )
        if payload.review_candidate_id:
            candidate_ids = {
                str(item.get("candidate_id"))
                for item in top_candidates
                if item.get("candidate_id")
            }
            if payload.review_candidate_id not in candidate_ids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"reason": "candidate_review_required"},
                )

        patient = PatientService(self.db).create_patient(
            request=request,
            patient_in=payload.patient,
            current_user=actor,
        )
        telegram_user = (
            self.db.query(TelegramUser)
            .filter(TelegramUser.id == row.telegram_user_id)
            .first()
        )
        if telegram_user is not None:
            telegram_user.patient_id = int(patient.id)
        row.status = "created_patient"
        row.resolved_patient_id = int(patient.id)
        row.reviewed_by_user_id = int(actor.id)
        row.reviewed_at = _utc_now()
        row.review_message = safe_note or _default_review_message(
            "created_patient",
            payload.reason_code,
        )
        row.updated_at = _utc_now()
        audit_payload = {
            "reason_code": payload.reason_code,
            "review_candidate_id": payload.review_candidate_id,
            "confirm_create_despite_duplicates": payload.confirm_create_despite_duplicates,
            "high_confidence_duplicate_present": high_confidence_exists,
            "resolved_patient_ref": _patient_ref(int(patient.id)),
            "note_hash": _safe_note_hash(safe_note),
        }
        self._record_audit(
            action=REVIEWED_AUDIT_ACTION,
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self._record_audit(
            action="patient_onboarding_created_patient",
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": self._registrar_request_payload(row),
            "messageKey": "patient_onboarding_created_patient",
        }

    def request_more_info(
        self,
        *,
        request_id: int,
        actor: User,
        reason_code: str | None,
        safe_note: str | None,
    ) -> dict[str, Any]:
        self._validate_audit_actor(actor)
        if reason_code not in NEEDS_MORE_INFO_REASON_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"reason": "needs_more_info_reason_invalid"},
            )
        row = self._get_reviewable(request_id)
        note = _safe_note(safe_note)
        row.status = "needs_more_info"
        row.reviewed_by_user_id = int(actor.id)
        row.reviewed_at = _utc_now()
        row.review_message = note or _default_review_message("needs_more_info", reason_code)
        row.updated_at = _utc_now()
        audit_payload = {
            "reason_code": reason_code,
            "note_hash": _safe_note_hash(note),
        }
        self._record_audit(
            action=REVIEWED_AUDIT_ACTION,
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self._record_audit(
            action="patient_onboarding_needs_more_info",
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": self._registrar_request_payload(row),
            "messageKey": "patient_onboarding_needs_more_info",
        }

    def reject(
        self,
        *,
        request_id: int,
        actor: User,
        reason_code: str | None,
        safe_note: str | None,
    ) -> dict[str, Any]:
        self._validate_audit_actor(actor)
        if reason_code not in REJECT_REASON_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"reason": "rejected_reason_invalid"},
            )
        row = self._get_reviewable(request_id)
        note = _safe_note(safe_note)
        row.status = "rejected"
        row.reviewed_by_user_id = int(actor.id)
        row.reviewed_at = _utc_now()
        row.review_message = note or _default_review_message("reject", reason_code)
        row.updated_at = _utc_now()
        audit_payload = {
            "reason_code": reason_code,
            "note_hash": _safe_note_hash(note),
        }
        self._record_audit(
            action=REVIEWED_AUDIT_ACTION,
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self._record_audit(
            action="patient_onboarding_rejected",
            row=row,
            actor_user_id=int(actor.id),
            payload=audit_payload,
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": self._registrar_request_payload(row),
            "messageKey": "patient_onboarding_rejected",
        }
