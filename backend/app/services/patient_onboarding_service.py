from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.crud import audit as crud_audit
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.telegram_config import PatientOnboardingRequest, TelegramUser
from app.models.user import User
from app.schemas.patient_onboarding import (
    PatientOnboardingSubmitRequest,
    RegistrarCreatePatientFromOnboardingRequest,
)
from app.services.patient_service import PatientService


ONBOARDING_ACTIVE_STATUSES = {"pending_review", "needs_more_info"}
ONBOARDING_FINAL_STATUSES = {
    "linked_existing",
    "created_patient",
    "rejected",
    "cancelled",
    "expired",
}
ONBOARDING_REQUEST_TTL_DAYS = 14


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_text(value: str | None, *, max_length: int) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


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


def _registrar_request_payload(row: PatientOnboardingRequest) -> dict[str, Any]:
    payload = _request_payload(row)
    payload.update(
        {
            "telegramUserId": row.telegram_user_id,
            "telegramChatId": int(row.telegram_chat_id),
            "reviewedByUserId": row.reviewed_by_user_id,
            "resolvedPatientId": row.resolved_patient_id,
        }
    )
    return payload


class PatientOnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _record_audit(
        self,
        *,
        action: str,
        row: PatientOnboardingRequest,
        actor_user_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        audit_payload = {
            "status": row.status,
            "telegram_user_id": row.telegram_user_id,
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

    def latest_for_telegram_user(
        self, telegram_user: TelegramUser
    ) -> PatientOnboardingRequest | None:
        row = (
            self.db.query(PatientOnboardingRequest)
            .filter(PatientOnboardingRequest.telegram_chat_id == int(telegram_user.chat_id))
            .order_by(PatientOnboardingRequest.created_at.desc(), PatientOnboardingRequest.id.desc())
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
        row = (
            existing
            if existing is not None and existing.status in ONBOARDING_ACTIVE_STATUSES
            else None
        )
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

    def own_status_response(
        self, telegram_user: TelegramUser
    ) -> dict[str, Any]:
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

    def submit_response(
        self, row: PatientOnboardingRequest, *, created: bool
    ) -> dict[str, Any]:
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
        return {
            "items": [_registrar_request_payload(self._refresh_expired(row)) for row in rows],
            "total": total,
        }

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

    def link_existing_patient(
        self,
        *,
        request_id: int,
        patient_id: int,
        actor: User,
        review_message: str | None = None,
    ) -> dict[str, Any]:
        row = self._get_reviewable(request_id)
        patient = self.db.query(Patient).filter(Patient.id == int(patient_id)).first()
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
        row.review_message = _clean_text(review_message, max_length=512)
        row.updated_at = _utc_now()
        self._record_audit(
            action="patient_onboarding_linked_existing",
            row=row,
            actor_user_id=int(actor.id),
            payload={"resolved_patient_id": int(patient.id)},
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": _registrar_request_payload(row),
            "messageKey": "patient_onboarding_linked_existing",
        }

    def create_patient_from_request(
        self,
        *,
        request: Request,
        request_id: int,
        payload: RegistrarCreatePatientFromOnboardingRequest,
        actor: User,
    ) -> dict[str, Any]:
        row = self._get_reviewable(request_id)
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
        row.review_message = _clean_text(payload.review_message, max_length=512)
        row.updated_at = _utc_now()
        self._record_audit(
            action="patient_onboarding_created_patient",
            row=row,
            actor_user_id=int(actor.id),
            payload={"resolved_patient_id": int(patient.id)},
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": _registrar_request_payload(row),
            "messageKey": "patient_onboarding_created_patient",
        }

    def request_more_info(
        self,
        *,
        request_id: int,
        actor: User,
        review_message: str | None,
    ) -> dict[str, Any]:
        row = self._get_reviewable(request_id)
        row.status = "needs_more_info"
        row.reviewed_by_user_id = int(actor.id)
        row.reviewed_at = _utc_now()
        row.review_message = _clean_text(review_message, max_length=512)
        row.updated_at = _utc_now()
        self._record_audit(
            action="patient_onboarding_needs_more_info",
            row=row,
            actor_user_id=int(actor.id),
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": _registrar_request_payload(row),
            "messageKey": "patient_onboarding_needs_more_info",
        }

    def reject(
        self,
        *,
        request_id: int,
        actor: User,
        review_message: str | None,
    ) -> dict[str, Any]:
        row = self._get_reviewable(request_id)
        row.status = "rejected"
        row.reviewed_by_user_id = int(actor.id)
        row.reviewed_at = _utc_now()
        row.review_message = _clean_text(review_message, max_length=512)
        row.updated_at = _utc_now()
        self._record_audit(
            action="patient_onboarding_rejected",
            row=row,
            actor_user_id=int(actor.id),
        )
        self.db.commit()
        self.db.refresh(row)
        return {
            "request": _registrar_request_payload(row),
            "messageKey": "patient_onboarding_rejected",
        }
