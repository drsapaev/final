"""Non-reserving public booking request lifecycle."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud.appointment import appointment as appointment_crud
from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
    PublicBookingRequestNotificationOutbox,
)
from app.repositories.public_booking_availability_repository import (
    PublicBookingAvailabilityRepository,
)
from app.repositories.public_booking_request_repository import (
    PublicBookingRequestRepository,
)
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.repositories.services_api_repository import ServicesApiRepository
from app.schemas.appointment import PatientPortalAppointmentCreate
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
from app.services.appointment_booking_routing import (
    resolve_doctor_routing_department,
)
from app.services.appointment_eligibility import ensure_doctor_eligible_for_appointment
from app.services.appointment_slot_guard import (
    lock_department_for_booking,
    lock_doctor_for_slot_reservation,
)
from app.services.public_booking_availability_service import (
    PublicBookingAvailabilityService,
)
from app.services.public_booking_calendar_settings import (
    PUBLIC_BOOKING_CALENDAR_KEY_PREFIX,
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
    """Own request state changes and atomically confirm requests as appointments."""

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
            self._enqueue_registrar_notification(
                request=request,
                event_type="public_booking_request_submitted",
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
        self._enqueue_registrar_notification(
            request=request,
            event_type="public_booking_request_resubmitted",
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

    def confirm_for_staff(
        self,
        *,
        request_id: UUID,
        actor_user_id: int,
        expected_version: int,
    ) -> PublicBookingRequestPatientOut:
        """Confirm a still-available request as one ordinary appointment.

        Existing requests remain processable after booking mode is changed or
        disabled. The current allowlist and catalog eligibility still apply;
        the slot calculation rechecks the current doctor schedule, holiday
        calendar, and all appointment/visit occupancy under the same doctor
        row lock used by appointment writers.
        """
        request = self.repository.get_for_staff(request_id=request_id, lock=True)
        if request is None:
            raise PublicBookingRequestError(404, "booking_request_not_found")
        self._require_version(request, expected_version)
        self._require_state(request, {PublicBookingRequestStatus.PENDING.value})

        settings = self._locked_request_settings()
        self.repository.lock_settings(
            f"{PUBLIC_BOOKING_CALENDAR_KEY_PREFIX}{request.appointment_date.year:04d}"
        )
        confirmation_settings = self._settings_for_existing_request(
            settings=settings,
            service_id=request.service_id,
            doctor_id=request.doctor_id,
        )

        doctor = lock_doctor_for_slot_reservation(self.db, request.doctor_id)
        if doctor is None:
            raise PublicBookingRequestError(409, "booking_request_unavailable")
        try:
            ensure_doctor_eligible_for_appointment(self.db, request.doctor_id)
            department = resolve_doctor_routing_department(doctor, None)
            department = lock_department_for_booking(self.db, department)
        except HTTPException as exc:
            raise PublicBookingRequestError(409, "booking_request_unavailable") from exc
        if department is None:
            raise PublicBookingRequestError(409, "booking_request_unavailable")

        service = ServicesApiRepository(self.db).get_service_for_update(
            request.service_id
        )
        if service is None or not service.slug:
            raise PublicBookingRequestError(409, "booking_request_unavailable")

        snapshot = self.availability_service.public_availability_for_day(
            service_slug=service.slug,
            doctor_slug=request.doctor.slug,
            target_date=request.appointment_date,
            settings=confirmation_settings,
        )
        if snapshot.slots is None:
            raise PublicBookingRequestError(409, "booking_request_unavailable")
        if request.appointment_time not in snapshot.slots:
            request.status = PublicBookingRequestStatus.NEEDS_NEW_TIME.value
            request.version += 1
            self._add_event(
                request=request,
                actor_user_id=actor_user_id,
                event_type="confirmation_slot_unavailable",
                from_status=PublicBookingRequestStatus.PENDING.value,
                to_status=request.status,
                previous_date=request.appointment_date,
                previous_time=request.appointment_time,
            )
            self.db.commit()
            stored = self.repository.get_for_staff(request_id=request.id)
            assert stored is not None
            return self._staff_out(stored)

        appointment_in = PatientPortalAppointmentCreate(
            patient_id=request.patient_id,
            doctor_id=request.doctor_id,
            # Appointment.department is an ORM relationship; persist only the
            # server-resolved FK, matching the patient portal writer.
            department_id=department.id,
            appointment_date=request.appointment_date,
            appointment_time=request.appointment_time.strftime("%H:%M"),
            service_ids=[request.service_id],
        )
        try:
            appointment = appointment_crud.create(
                db=self.db,
                obj_in=appointment_in,
                commit=False,
            )
            request.appointment_id = int(appointment.id)
            request.status = PublicBookingRequestStatus.CONFIRMED.value
            request.version += 1
            self._add_event(
                request=request,
                actor_user_id=actor_user_id,
                event_type="confirmed",
                from_status=PublicBookingRequestStatus.PENDING.value,
                to_status=request.status,
                previous_date=request.appointment_date,
                previous_time=request.appointment_time,
            )
            self.db.commit()
        except HTTPException as exc:
            self.db.rollback()
            raise PublicBookingRequestError(409, "booking_request_unavailable") from exc
        except Exception:
            self.db.rollback()
            raise

        stored = self.repository.get_for_staff(request_id=request.id)
        assert stored is not None
        return self._staff_out(stored)

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

    @staticmethod
    def _settings_for_existing_request(
        *,
        settings: PublicBookingSettingsOut,
        service_id: int,
        doctor_id: int,
    ) -> PublicBookingSettingsOut:
        """Apply new-request admission settings to an already-submitted request.

        The owner approved honoring submitted requests after the channel is
        disabled or its mode changes. Only the existing pair is needed from
        the current allowlist; current public/catalog eligibility is checked
        again by availability and exact-service appointment creation.
        """
        eligible_service_ids = {
            option.id for option in settings.services if option.eligible
        }
        eligible_doctor_ids = {
            option.id for option in settings.doctors if option.eligible
        }
        if (
            service_id not in settings.service_ids
            or doctor_id not in settings.doctor_ids
            or service_id not in eligible_service_ids
            or doctor_id not in eligible_doctor_ids
        ):
            raise PublicBookingRequestError(409, "booking_request_unavailable")
        return settings.model_copy(
            update={
                "is_enabled": True,
                "is_ready": True,
                # The request passed the horizon at submission. A later admin
                # change to that admission setting must not invalidate it.
                "booking_horizon_days": 365,
            }
        )

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

    def _enqueue_registrar_notification(
        self, *, request: PublicBookingRequest, event_type: str
    ) -> None:
        """Persist the inbox delivery intent in the request's transaction."""
        self.db.add(
            PublicBookingRequestNotificationOutbox(
                request_id=request.id,
                request_version=request.version,
                event_type=event_type,
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
            appointment_id=request.appointment_id,
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
            appointment_id=request.appointment_id,
            status=request.status,
            settings_version=request.settings_version,
            version=request.version,
            created_at=request.created_at,
            updated_at=request.updated_at,
            history=cls._history(request),
        )
