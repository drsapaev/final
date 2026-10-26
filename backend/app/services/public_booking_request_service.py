"""Non-reserving public booking request lifecycle."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
)
from app.repositories.public_booking_availability_repository import (
    PublicBookingAvailabilityRepository,
)
from app.repositories.public_booking_request_repository import (
    PublicBookingRequestRepository,
)
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.schemas.public_booking_request import (
    PublicBookingRequestEventOut,
    PublicBookingRequestOut,
    PublicBookingRequestPatientOut,
    PublicBookingRequestStatus,
)
from app.schemas.public_booking_settings import (
    PublicBookingMode,
    PublicBookingSettingsOut,
)
from app.services.public_booking_availability_service import (
    PublicBookingAvailabilityService,
)
from app.services.public_booking_calendar_settings import (
    PublicBookingCalendarSettingsService,
)
from app.services.public_booking_settings import (
    PUBLIC_BOOKING_SETTINGS_KEY,
    PublicBookingSettingsError,
    PublicBookingSettingsService,
)
from app.services.registrar_doctor_eligibility import (
    service_routes_to_resource_queue,
)

REQUEST_CREATION_LIMIT_PER_PATIENT = 5
REQUEST_CREATION_WINDOW = timedelta(minutes=1)


class PublicBookingRequestError(Exception):
    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class PublicBookingRequestService:
    """Own request state changes; never create or reserve appointments."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PublicBookingRequestRepository(db)
        self.settings_service = PublicBookingSettingsService(db)
        self.public_site_repository = PublicSiteReadRepository(db)
        self.availability_service = PublicBookingAvailabilityService(
            PublicBookingAvailabilityRepository(db),
            public_site_repository=self.public_site_repository,
            booking_settings_service=self.settings_service,
            calendar_settings_service=PublicBookingCalendarSettingsService(db),
            resource_queue_route_policy=lambda service, day: (
                service_routes_to_resource_queue(db, service, day)
            ),
        )

    def create_for_patient(
        self,
        *,
        patient_id: int,
        actor_user_id: int,
        service_slug: str,
        doctor_slug: str,
        appointment_date: date,
        appointment_time: time,
        expected_settings_version: int,
        idempotency_key: str,
        operation_scope: str,
    ) -> PublicBookingRequestOut:
        key_hash, payload_hash = self._idempotency_hashes(
            patient_id=patient_id,
            idempotency_key=idempotency_key,
            operation_scope=operation_scope,
            payload={
                "operation": "create",
                "service_slug": service_slug,
                "doctor_slug": doctor_slug,
                "appointment_date": appointment_date.isoformat(),
                "appointment_time": appointment_time.isoformat(timespec="minutes"),
                "expected_settings_version": expected_settings_version,
            },
        )
        replay = self._idempotent_request(
            key_hash=key_hash,
            payload_hash=payload_hash,
            patient_id=patient_id,
        )
        if replay is not None:
            return self._patient_out(replay)
        settings = self._locked_request_settings()
        # The settings row lock serializes concurrent first submissions that
        # use the same key; recheck after acquiring it before inserting.
        replay = self._idempotent_request(
            key_hash=key_hash,
            payload_hash=payload_hash,
            patient_id=patient_id,
        )
        if replay is not None:
            return self._patient_out(replay)
        self._require_request_settings(settings, expected_settings_version)
        self._require_request_creation_limit(patient_id)
        service_id, doctor_id = self._validate_slot(
            settings=settings,
            service_slug=service_slug,
            doctor_slug=doctor_slug,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
        )
        self._require_no_active_duplicate(
            patient_id=patient_id,
            service_id=service_id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
        )
        request = PublicBookingRequest(
            patient_id=patient_id,
            service_id=service_id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status=PublicBookingRequestStatus.PENDING.value,
            settings_version=settings.version,
            version=1,
        )
        try:
            self.repository.create(request)
            self._add_event(
                request=request,
                actor_user_id=actor_user_id,
                event_type="submitted",
                from_status=None,
                to_status=PublicBookingRequestStatus.PENDING.value,
                previous_date=None,
                previous_time=None,
                idempotency_key_hash=key_hash,
                payload_hash=payload_hash,
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if self.repository.has_active_request_for_slot(
                patient_id=patient_id,
                service_id=service_id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
            ):
                raise PublicBookingRequestError(
                    409, "booking_request_duplicate"
                ) from exc
            raise
        stored = self.repository.get_for_patient(
            request_id=request.id, patient_id=patient_id
        )
        assert stored is not None
        return self._patient_out(stored)

    def list_for_patient(
        self, *, patient_id: int, limit: int, offset: int
    ) -> list[PublicBookingRequestOut]:
        rows = self.repository.list_for_patient(
            patient_id=patient_id, limit=limit, offset=offset
        )
        return [self._patient_out(row) for row in rows]

    def withdraw_for_patient(
        self,
        *,
        request_id: UUID,
        patient_id: int,
        actor_user_id: int,
        expected_version: int,
    ) -> PublicBookingRequestOut:
        request = self.repository.get_for_patient(
            request_id=request_id, patient_id=patient_id, lock=True
        )
        if request is None:
            raise PublicBookingRequestError(404, "booking_request_not_found")
        self._require_version(request, expected_version)
        self._require_state(
            request,
            {
                PublicBookingRequestStatus.PENDING.value,
                PublicBookingRequestStatus.NEEDS_NEW_TIME.value,
            },
        )
        old_status = request.status
        request.status = PublicBookingRequestStatus.WITHDRAWN.value
        request.version += 1
        self._add_event(
            request=request,
            actor_user_id=actor_user_id,
            event_type="withdrawn",
            from_status=old_status,
            to_status=request.status,
            previous_date=request.appointment_date,
            previous_time=request.appointment_time,
        )
        self.db.commit()
        stored = self.repository.get_for_patient(
            request_id=request.id, patient_id=patient_id
        )
        assert stored is not None
        return self._patient_out(stored)

    def resubmit_for_patient(
        self,
        *,
        request_id: UUID,
        patient_id: int,
        actor_user_id: int,
        expected_version: int,
        appointment_date: date,
        appointment_time: time,
        expected_settings_version: int,
        idempotency_key: str,
        operation_scope: str,
    ) -> PublicBookingRequestOut:
        request = self.repository.get_for_patient(
            request_id=request_id, patient_id=patient_id, lock=True
        )
        if request is None:
            raise PublicBookingRequestError(404, "booking_request_not_found")
        key_hash, payload_hash = self._idempotency_hashes(
            patient_id=patient_id,
            idempotency_key=idempotency_key,
            operation_scope=operation_scope,
            payload={
                "operation": "resubmit",
                "request_id": str(request_id),
                "expected_version": expected_version,
                "service_slug": request.service.slug,
                "doctor_slug": request.doctor.slug,
                "appointment_date": appointment_date.isoformat(),
                "appointment_time": appointment_time.isoformat(timespec="minutes"),
                "expected_settings_version": expected_settings_version,
            },
        )
        replay = self._idempotent_request(
            key_hash=key_hash,
            payload_hash=payload_hash,
            patient_id=patient_id,
            request_id=request_id,
        )
        if replay is not None:
            return self._patient_out(replay)
        self._require_version(request, expected_version)
        self._require_state(request, {PublicBookingRequestStatus.NEEDS_NEW_TIME.value})
        if (
            appointment_date == request.appointment_date
            and appointment_time == request.appointment_time
        ):
            raise PublicBookingRequestError(409, "booking_time_unavailable")
        settings = self._locked_request_settings()
        replay = self._idempotent_request(
            key_hash=key_hash,
            payload_hash=payload_hash,
            patient_id=patient_id,
            request_id=request_id,
        )
        if replay is not None:
            return self._patient_out(replay)
        self._require_request_settings(settings, expected_settings_version)
        service_id, doctor_id = self._validate_slot(
            settings=settings,
            service_slug=request.service.slug,
            doctor_slug=request.doctor.slug,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
        )
        old_date = request.appointment_date
        old_time = request.appointment_time
        if service_id != request.service_id or doctor_id != request.doctor_id:
            raise PublicBookingRequestError(409, "booking_request_state_conflict")
        self._require_no_active_duplicate(
            patient_id=patient_id,
            service_id=service_id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            excluding_request_id=request.id,
        )
        request.appointment_date = appointment_date
        request.appointment_time = appointment_time
        request.settings_version = settings.version
        request.status = PublicBookingRequestStatus.PENDING.value
        request.version += 1
        self._add_event(
            request=request,
            actor_user_id=actor_user_id,
            event_type="resubmitted",
            from_status=PublicBookingRequestStatus.NEEDS_NEW_TIME.value,
            to_status=request.status,
            previous_date=old_date,
            previous_time=old_time,
            idempotency_key_hash=key_hash,
            payload_hash=payload_hash,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if self.repository.has_active_request_for_slot(
                patient_id=patient_id,
                service_id=service_id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                excluding_request_id=request_id,
            ):
                raise PublicBookingRequestError(
                    409, "booking_request_duplicate"
                ) from exc
            raise
        stored = self.repository.get_for_patient(
            request_id=request.id, patient_id=patient_id
        )
        assert stored is not None
        return self._patient_out(stored)

    def list_for_staff(
        self,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[PublicBookingRequestPatientOut]:
        rows = self.repository.list_for_staff(
            status=status_filter, limit=limit, offset=offset
        )
        return [self._staff_out(row) for row in rows]

    def request_new_time_for_staff(
        self,
        *,
        request_id: UUID,
        actor_user_id: int,
        expected_version: int,
    ) -> PublicBookingRequestPatientOut:
        request = self.repository.get_for_staff(request_id=request_id, lock=True)
        if request is None:
            raise PublicBookingRequestError(404, "booking_request_not_found")
        self._require_version(request, expected_version)
        self._require_state(request, {PublicBookingRequestStatus.PENDING.value})
        request.status = PublicBookingRequestStatus.NEEDS_NEW_TIME.value
        request.version += 1
        self._add_event(
            request=request,
            actor_user_id=actor_user_id,
            event_type="staff_requested_new_time",
            from_status=PublicBookingRequestStatus.PENDING.value,
            to_status=request.status,
            previous_date=request.appointment_date,
            previous_time=request.appointment_time,
        )
        self.db.commit()
        stored = self.repository.get_for_staff(request_id=request.id)
        assert stored is not None
        return self._staff_out(stored)

    def reject_for_staff(
        self,
        *,
        request_id: UUID,
        actor_user_id: int,
        expected_version: int,
    ) -> PublicBookingRequestPatientOut:
        request = self.repository.get_for_staff(request_id=request_id, lock=True)
        if request is None:
            raise PublicBookingRequestError(404, "booking_request_not_found")
        self._require_version(request, expected_version)
        self._require_state(
            request,
            {
                PublicBookingRequestStatus.PENDING.value,
                PublicBookingRequestStatus.NEEDS_NEW_TIME.value,
            },
        )
        old_status = request.status
        request.status = PublicBookingRequestStatus.REJECTED.value
        request.version += 1
        self._add_event(
            request=request,
            actor_user_id=actor_user_id,
            event_type="rejected",
            from_status=old_status,
            to_status=request.status,
            previous_date=request.appointment_date,
            previous_time=request.appointment_time,
        )
        self.db.commit()
        stored = self.repository.get_for_staff(request_id=request.id)
        assert stored is not None
        return self._staff_out(stored)

    def _locked_request_settings(self) -> PublicBookingSettingsOut:
        self.repository.lock_settings(PUBLIC_BOOKING_SETTINGS_KEY)
        try:
            settings = self.settings_service.get_settings()
        except PublicBookingSettingsError as exc:
            raise PublicBookingRequestError(503, "public_booking_unavailable") from exc

        return settings

    def _require_request_creation_limit(self, patient_id: int) -> None:
        created_since = datetime.now(UTC) - REQUEST_CREATION_WINDOW
        if (
            self.repository.count_patient_requests_since(
                patient_id=patient_id,
                created_since=created_since,
            )
            >= REQUEST_CREATION_LIMIT_PER_PATIENT
        ):
            raise PublicBookingRequestError(429, "booking_request_rate_limited")

    def _require_no_active_duplicate(
        self,
        *,
        patient_id: int,
        service_id: int,
        doctor_id: int,
        appointment_date: date,
        appointment_time: time,
        excluding_request_id: UUID | None = None,
    ) -> None:
        if self.repository.has_active_request_for_slot(
            patient_id=patient_id,
            service_id=service_id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            excluding_request_id=excluding_request_id,
        ):
            raise PublicBookingRequestError(409, "booking_request_duplicate")

    @staticmethod
    def _require_request_settings(
        settings: PublicBookingSettingsOut, expected_settings_version: int
    ) -> None:
        if settings.version != expected_settings_version:
            raise PublicBookingRequestError(409, "booking_settings_version_conflict")
        if not settings.is_enabled or not settings.is_ready:
            raise PublicBookingRequestError(409, "public_booking_unavailable")
        if settings.mode != PublicBookingMode.REGISTRAR_REQUEST:
            raise PublicBookingRequestError(409, "booking_mode_changed")

    @staticmethod
    def _idempotency_hashes(
        *,
        patient_id: int,
        idempotency_key: str,
        operation_scope: str,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        key_hash = hashlib.sha256(
            f"{patient_id}\0{operation_scope}\0{idempotency_key}".encode()
        ).hexdigest()
        payload_hash = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return key_hash, payload_hash

    def _idempotent_request(
        self,
        *,
        key_hash: str,
        payload_hash: str,
        patient_id: int,
        request_id: UUID | None = None,
    ) -> PublicBookingRequest | None:
        event = self.repository.get_event_by_idempotency_key_hash(key_hash)
        if event is None:
            return None
        request = event.request
        if (
            request.patient_id != patient_id
            or (request_id is not None and request.id != request_id)
            or event.payload_hash != payload_hash
        ):
            raise PublicBookingRequestError(409, "booking_request_idempotency_conflict")
        return request

    def _validate_slot(
        self,
        *,
        settings: PublicBookingSettingsOut,
        service_slug: str,
        doctor_slug: str,
        appointment_date: date,
        appointment_time: time,
    ) -> tuple[int, int]:
        snapshot = self.availability_service.public_availability_for_day(
            service_slug=service_slug,
            doctor_slug=doctor_slug,
            target_date=appointment_date,
            settings=settings,
        )
        if snapshot.slots is None:
            raise PublicBookingRequestError(404, "public_content_not_found")
        if appointment_time not in snapshot.slots:
            raise PublicBookingRequestError(409, "booking_time_unavailable")
        service = self.public_site_repository.get_public_service_by_slug(service_slug)
        doctor = self.public_site_repository.get_public_doctor_by_slug(doctor_slug)
        if service is None or doctor is None:
            raise PublicBookingRequestError(404, "public_content_not_found")
        return int(service.id), int(doctor.id)

    def _add_event(
        self,
        *,
        request: PublicBookingRequest,
        actor_user_id: int,
        event_type: str,
        from_status: str | None,
        to_status: str,
        previous_date: date | None,
        previous_time: time | None,
        idempotency_key_hash: str | None = None,
        payload_hash: str | None = None,
    ) -> None:
        self.db.add(
            PublicBookingRequestEvent(
                request_id=request.id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                previous_appointment_date=previous_date,
                previous_appointment_time=previous_time,
                requested_appointment_date=request.appointment_date,
                requested_appointment_time=request.appointment_time,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
        )

    @staticmethod
    def _require_version(request: PublicBookingRequest, expected: int) -> None:
        if request.version != expected:
            raise PublicBookingRequestError(409, "booking_request_version_conflict")

    @staticmethod
    def _require_state(request: PublicBookingRequest, allowed: set[str]) -> None:
        if request.status not in allowed:
            raise PublicBookingRequestError(409, "booking_request_state_conflict")

    @staticmethod
    def _history(request: PublicBookingRequest) -> list[PublicBookingRequestEventOut]:
        return [
            PublicBookingRequestEventOut(
                event_type=event.event_type,
                from_status=event.from_status,
                to_status=event.to_status,
                previous_appointment_date=event.previous_appointment_date,
                previous_appointment_time=event.previous_appointment_time,
                requested_appointment_date=event.requested_appointment_date,
                requested_appointment_time=event.requested_appointment_time,
                created_at=event.created_at,
            )
            for event in request.events
        ]

    @classmethod
    def _patient_out(cls, request: PublicBookingRequest) -> PublicBookingRequestOut:
        return PublicBookingRequestOut(
            id=request.id,
            service_slug=request.service.slug,
            doctor_slug=request.doctor.slug,
            appointment_date=request.appointment_date,
            appointment_time=request.appointment_time,
            status=request.status,
            settings_version=request.settings_version,
            version=request.version,
            created_at=request.created_at,
            updated_at=request.updated_at,
            history=cls._history(request),
        )

    @classmethod
    def _staff_out(
        cls, request: PublicBookingRequest
    ) -> PublicBookingRequestPatientOut:
        doctor_user = getattr(request.doctor, "user", None)
        doctor_name = getattr(doctor_user, "full_name", None) or "Врач"
        return PublicBookingRequestPatientOut(
            id=request.id,
            patient_id=request.patient_id,
            patient_display_name=request.patient.short_name(),
            service_name=request.service.name,
            doctor_display_name=doctor_name,
            service_slug=request.service.slug,
            doctor_slug=request.doctor.slug,
            appointment_date=request.appointment_date,
            appointment_time=request.appointment_time,
            status=request.status,
            settings_version=request.settings_version,
            version=request.version,
            created_at=request.created_at,
            updated_at=request.updated_at,
            history=cls._history(request),
        )
