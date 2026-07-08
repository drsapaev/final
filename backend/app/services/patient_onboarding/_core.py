"""Core mixin for PatientOnboardingService. Split from patient_onboarding_service.py."""
from __future__ import annotations
from app.services.patient_onboarding._base import *  # noqa: F401, F403
from app.services.patient_onboarding._base import PatientOnboardingServiceMixinBase


class CoreMixin(PatientOnboardingServiceMixinBase):
    """Core methods."""

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


