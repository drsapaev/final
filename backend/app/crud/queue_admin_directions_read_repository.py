"""Bulk, side-effect-free database reads for queue setup directions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.specialties import expand_queue_tags
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, QueueResource
from app.models.queue_direction_public_address import QueueDirectionPublicAddress
from app.models.queue_profile import QueueProfile
from app.models.service import Service
from app.models.user import User
from app.services.queue_svc._core import qr_doctor_owner_eligibility_filters


@dataclass(frozen=True)
class QueueAdminDirectionsSnapshot:
    profiles: list[QueueProfile]
    services: list[Service]
    resources: list[QueueResource]
    doctors: list[Doctor]
    daily_queues: list[DailyQueue]
    profiles_with_permanent_address: set[int]


def load_queue_admin_directions_snapshot(
    db: Session, *, day: date
) -> QueueAdminDirectionsSnapshot:
    """Load all catalog facts in bounded queries; never creates missing rows."""
    profiles = (
        db.query(QueueProfile)
        .order_by(QueueProfile.display_order, QueueProfile.id)
        .all()
    )
    services = db.query(Service).order_by(Service.id).all()
    resources = db.query(QueueResource).order_by(QueueResource.id).all()
    daily_queues = (
        db.query(DailyQueue)
        .filter(DailyQueue.day == day, DailyQueue.active.is_(True))
        .order_by(DailyQueue.id)
        .all()
    )

    route_tags: set[str] = set()
    for profile in profiles:
        profile_key = str(profile.key or "").strip()
        profile_tags = list(profile.queue_tags or [])
        if not profile_tags and profile_key:
            profile_tags = [profile_key]
        route_tags.update(tag for tag in expand_queue_tags(profile_tags) if tag)

    service_doctor_ids = {
        int(service.doctor_id)
        for service in services
        if service.active and service.doctor_id is not None
    }
    doctor_conditions = []
    if route_tags:
        doctor_conditions.append(Doctor.specialty.in_(sorted(route_tags)))
    if service_doctor_ids:
        doctor_conditions.append(Doctor.id.in_(sorted(service_doctor_ids)))
    doctors: list[Doctor] = []
    if doctor_conditions:
        doctors = (
            db.query(Doctor)
            .join(User, Doctor.user_id == User.id)
            .filter(
                Doctor.active.is_(True),
                Doctor.specialty.isnot(None),
                func.trim(Doctor.specialty) != "",
                func.lower(func.trim(Doctor.specialty)) != "general",
                or_(*doctor_conditions),
                *qr_doctor_owner_eligibility_filters(),
            )
            .options(joinedload(Doctor.user).joinedload(User.profile))
            .order_by(Doctor.id)
            .all()
        )

    profile_ids = [int(profile.id) for profile in profiles]
    profiles_with_permanent_address: set[int] = set()
    if profile_ids:
        profiles_with_permanent_address = {
            int(row[0])
            for row in (
                db.query(QueueDirectionPublicAddress.queue_profile_id)
                .filter(
                    QueueDirectionPublicAddress.queue_profile_id.in_(profile_ids),
                    QueueDirectionPublicAddress.retired_at.is_(None),
                )
                .distinct()
                .all()
            )
            if row[0] is not None
        }

    return QueueAdminDirectionsSnapshot(
        profiles=profiles,
        services=services,
        resources=resources,
        doctors=doctors,
        daily_queues=daily_queues,
        profiles_with_permanent_address=profiles_with_permanent_address,
    )
