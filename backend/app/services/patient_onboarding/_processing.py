"""Processing mixin for PatientOnboardingService. Split from patient_onboarding_service.py."""
from __future__ import annotations

from app.services.patient_onboarding._base import *  # noqa: F401, F403
from app.services.patient_onboarding._base import PatientOnboardingServiceMixinBase
from app.services.patient_onboarding._base import (  # noqa: F401
    _request_payload,
    _utc_now,
)


class ProcessingMixin(PatientOnboardingServiceMixinBase):
    """Processing methods."""

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


