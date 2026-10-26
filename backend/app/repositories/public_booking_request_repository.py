"""Persistence queries for public booking requests."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.clinic import ClinicSettings, Doctor
from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
)


class PublicBookingRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def lock_settings(self, key: str) -> ClinicSettings | None:
        return (
            self.db.query(ClinicSettings)
            .filter(ClinicSettings.key == key)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def create(self, request: PublicBookingRequest) -> PublicBookingRequest:
        self.db.add(request)
        self.db.flush()
        return request

    def get_event_by_idempotency_key_hash(
        self, key_hash: str
    ) -> PublicBookingRequestEvent | None:
        return (
            self.db.query(PublicBookingRequestEvent)
            .options(
                joinedload(PublicBookingRequestEvent.request).options(
                    joinedload(PublicBookingRequest.service),
                    joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                    selectinload(PublicBookingRequest.events),
                ),
            )
            .filter(PublicBookingRequestEvent.idempotency_key_hash == key_hash)
            .first()
        )

    def get_for_patient(
        self, *, request_id: UUID, patient_id: int, lock: bool = False
    ) -> PublicBookingRequest | None:
        query = (
            self.db.query(PublicBookingRequest)
            .options(
                joinedload(PublicBookingRequest.service),
                joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                selectinload(PublicBookingRequest.events),
            )
            .filter(
                PublicBookingRequest.id == request_id,
                PublicBookingRequest.patient_id == patient_id,
            )
        )
        if lock:
            query = query.populate_existing().with_for_update(of=PublicBookingRequest)
        return query.first()

    def list_for_patient(
        self, *, patient_id: int, limit: int = 100, offset: int = 0
    ) -> list[PublicBookingRequest]:
        return list(
            self.db.query(PublicBookingRequest)
            .options(
                joinedload(PublicBookingRequest.service),
                joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                selectinload(PublicBookingRequest.events),
            )
            .filter(PublicBookingRequest.patient_id == patient_id)
            .order_by(PublicBookingRequest.created_at.desc(), PublicBookingRequest.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_for_staff(
        self, *, request_id: UUID, lock: bool = False
    ) -> PublicBookingRequest | None:
        query = (
            self.db.query(PublicBookingRequest)
            .options(
                joinedload(PublicBookingRequest.patient),
                joinedload(PublicBookingRequest.service),
                joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
                selectinload(PublicBookingRequest.events),
            )
            .filter(PublicBookingRequest.id == request_id)
        )
        if lock:
            query = query.populate_existing().with_for_update(of=PublicBookingRequest)
        return query.first()

    def list_for_staff(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[PublicBookingRequest]:
        query = self.db.query(PublicBookingRequest).options(
            joinedload(PublicBookingRequest.patient),
            joinedload(PublicBookingRequest.service),
            joinedload(PublicBookingRequest.doctor).joinedload(Doctor.user),
            selectinload(PublicBookingRequest.events),
        )
        if status is not None:
            query = query.filter(PublicBookingRequest.status == status)
        return list(
            query.order_by(
                PublicBookingRequest.created_at.asc(), PublicBookingRequest.id
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
