"""Review mixin for PatientOnboardingService. Split from patient_onboarding_service.py."""
from __future__ import annotations

from app.services.patient_onboarding._base import *  # noqa: F401, F403
from app.services.patient_onboarding._base import PatientOnboardingServiceMixinBase
from app.services.patient_onboarding._base import (  # noqa: F401
    _as_aware_utc,
    _clean_text,
    _decode_candidate_id,
    _default_review_message,
    _mask_name,
    _mask_phone,
    _patient_ref,
    _request_payload,
    _safe_note,
    _safe_note_hash,
    _utc_now,
)
from app.services.patient_service import PatientService  # noqa: F401


class ReviewMixin(PatientOnboardingServiceMixinBase):
    """Review methods."""

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
        for action, _count in (
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


