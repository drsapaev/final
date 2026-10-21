"""Read model for the Admin queue-directions setup screen."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.specialties import expand_queue_tags
from app.crud.clinic import clinic_today
from app.crud.queue_admin_directions_read_repository import (
    QueueAdminDirectionsSnapshot,
    load_queue_admin_directions_snapshot,
)
from app.models.online_queue import DailyQueue, QueueResource
from app.models.queue_profile import QueueProfile
from app.models.service import Service
from app.schemas.admin_queue_directions import (
    AdminDirectionAction,
    AdminDirectionBookingTarget,
    AdminDirectionDailyQueueReference,
    AdminDirectionPrecreateTag,
    AdminDirectionProfile,
    AdminDirectionReason,
    AdminQueueDirection,
    AdminQueueDirectionsResponse,
    AdminUnattachedCatalog,
    AdminUnattachedResource,
    AdminUnattachedService,
)
from app.services.queue_profile_availability import load_queue_profile_availability
from app.services.queue_service import queue_service


@dataclass(frozen=True, eq=False)
class _PublicationCandidate:
    """Read-only in-memory profile with the explicit publish intent applied."""

    key: str
    queue_tags: list[str]
    is_active: bool
    show_on_qr_page: bool
    department_key: str | None


def _profile_route_tags(profile: QueueProfile) -> set[str]:
    values = list(profile.queue_tags or [])
    if not values and profile.key:
        values = [profile.key]
    return {tag for tag in expand_queue_tags(values) if tag}


def _current_queue_owner(
    queue: DailyQueue,
) -> tuple[str, int | None]:
    resource_id = getattr(queue, "queue_resource_id", None)
    doctor_id = getattr(queue, "specialist_id", None)
    if resource_id is not None and doctor_id is None:
        return "resource", int(resource_id)
    if doctor_id is not None and resource_id is None:
        return "doctor", int(doctor_id)
    return "unresolved", None


def _profile_to_dto(profile: QueueProfile) -> AdminDirectionProfile:
    return AdminDirectionProfile(
        id=int(profile.id),
        key=profile.key,
        title=profile.title,
        title_ru=profile.title_ru,
        queue_tags=list(profile.queue_tags or []),
        department_key=profile.department_key,
        is_active=bool(profile.is_active),
        show_on_qr_page=bool(profile.show_on_qr_page),
        display_order=int(profile.display_order),
        icon=profile.icon,
        color=profile.color,
    )


def _precreate_by_tag(
    queue_tags: set[str],
    snapshot: QueueAdminDirectionsSnapshot,
    *,
    eligible_doctor_ids: set[int],
) -> list[AdminDirectionPrecreateTag]:
    active_services_by_tag: dict[str, list[Service]] = defaultdict(list)
    for service in snapshot.services:
        tag = (service.queue_tag or "").strip()
        if service.active and tag:
            active_services_by_tag[tag].append(service)

    active_resource_by_tag = {
        resource.queue_tag: resource
        for resource in snapshot.resources
        if resource.active
    }
    service_doctor_ids_by_tag: dict[str, set[int]] = defaultdict(set)
    for tag, services in active_services_by_tag.items():
        for service in services:
            if service.doctor_id is not None:
                service_doctor_ids_by_tag[tag].add(int(service.doctor_id))

    queue_ids_by_owner_tag: dict[tuple[str, int, str], list[int]] = defaultdict(list)
    for queue in snapshot.daily_queues:
        owner_type, owner_id = _current_queue_owner(queue)
        if owner_id is not None:
            queue_ids_by_owner_tag[(owner_type, owner_id, queue.queue_tag)].append(
                int(queue.id)
            )

    result: list[AdminDirectionPrecreateTag] = []
    for tag in sorted(queue_tags):
        active_services = active_services_by_tag.get(tag, [])
        owner_type: str | None = None
        owner_id: int | None = None
        reasons: list[str] = []

        if not active_services:
            reasons.append("no_active_service")
        elif tag in active_resource_by_tag:
            resource = active_resource_by_tag[tag]
            owner_type, owner_id = "resource", int(resource.id)
            reasons.append("active_resource_owner")
        else:
            service_owners = service_doctor_ids_by_tag.get(tag, set())
            if not service_owners:
                reasons.append("no_explicit_service_owner")
            elif len(service_owners) > 1:
                reasons.append("multiple_active_service_owners")
            else:
                candidate_id = next(iter(service_owners))
                if candidate_id not in eligible_doctor_ids:
                    reasons.append("ineligible_service_owner")
                else:
                    owner_type, owner_id = "doctor", candidate_id
                    reasons.append("single_active_service_owner")

        queue_ids = (
            queue_ids_by_owner_tag.get((owner_type, owner_id, tag), [])
            if owner_type is not None and owner_id is not None
            else []
        )
        # This flag reports policy feasibility; state separately reports
        # whether this owner's queue for the selected day already exists.
        can_precreate = owner_type is not None and bool(active_services)
        if can_precreate and queue_ids:
            state = "already_exists"
        elif can_precreate:
            state = "eligible"
        else:
            state = "blocked"
        if queue_ids:
            reasons.append("active_queue_exists")
        result.append(
            AdminDirectionPrecreateTag(
                queue_tag=tag,
                state=state,
                can_precreate=can_precreate,
                active_service_count=len(active_services),
                owner_type=owner_type,
                owner_id=owner_id,
                existing_daily_queue_ids=queue_ids,
                reason_codes=reasons,
            )
        )
    return result


def _configuration_reasons(
    profile: QueueProfile,
    availability,
    *,
    mode: str,
    owner_conflict: str | None,
    public_available: bool,
    publish_candidate_available: bool,
) -> list[AdminDirectionReason]:
    reasons: list[AdminDirectionReason] = []
    if not profile.is_active:
        reasons.append(
            AdminDirectionReason(
                code="manual_archived",
                severity="warning",
                subject_type="queue_profile",
                subject_key=profile.key,
            )
        )
    if availability.state == "conflict":
        for code in availability.reason_codes:
            reasons.append(
                AdminDirectionReason(
                    code=code,
                    severity="error",
                    subject_type="department",
                    subject_key=availability.parent_department_key,
                )
            )
    elif availability.state == "unavailable":
        for code in availability.reason_codes:
            reasons.append(
                AdminDirectionReason(
                    code=code,
                    severity="warning",
                    subject_type="department",
                    subject_key=availability.parent_department_key,
                )
            )
    if mode == "unresolved":
        code = owner_conflict or "no_bookable_owner"
        reasons.append(
            AdminDirectionReason(
                code=code,
                severity="error" if owner_conflict else "warning",
                subject_type="queue_profile",
                subject_key=profile.key,
            )
        )
    elif mode == "overview" and profile.show_on_qr_page:
        reasons.append(
            AdminDirectionReason(
                code="overview_must_remain_internal",
                severity="error",
                subject_type="queue_profile",
                subject_key=profile.key,
            )
        )
    elif mode == "booking" and not profile.show_on_qr_page:
        reasons.append(
            AdminDirectionReason(
                code="not_published",
                severity="info",
                subject_type="queue_profile",
                subject_key=profile.key,
            )
        )
    if (
        mode == "booking"
        and profile.is_active
        and profile.show_on_qr_page
        and availability.is_available
        and not public_available
    ):
        reasons.append(
            AdminDirectionReason(
                code="public_target_not_selectable",
                severity="error",
                subject_type="queue_profile",
                subject_key=profile.key,
            )
        )
    elif (
        mode == "booking"
        and profile.is_active
        and availability.is_available
        and not profile.show_on_qr_page
        and not publish_candidate_available
    ):
        reasons.append(
            AdminDirectionReason(
                code="publish_target_not_selectable",
                severity="error",
                subject_type="queue_profile",
                subject_key=profile.key,
            )
        )
    return reasons


def _configuration_state(
    profile: QueueProfile,
    availability,
    *,
    mode: str,
    reasons: list[AdminDirectionReason],
    public_available: bool,
) -> str:
    codes = {reason.code for reason in reasons}
    if {
        "parent_conflict",
        "parent_missing",
        "publish_target_not_selectable",
    } & codes:
        return "conflict"
    if mode == "overview" and profile.show_on_qr_page:
        return "conflict"
    if "public_target_not_selectable" in codes:
        return "conflict"
    if not profile.is_active or not availability.is_available:
        return "unavailable"
    if mode == "unresolved" or (mode == "booking" and not profile.show_on_qr_page):
        return "incomplete"
    if mode == "booking" and profile.show_on_qr_page and not public_available:
        return "incomplete"
    return "ready"


def _allowed_actions(
    profile: QueueProfile,
    availability,
    *,
    mode: str,
    public_available: bool,
    publish_candidate_available: bool,
    has_address: bool,
) -> list[AdminDirectionAction]:
    if not profile.is_active:
        return [
            AdminDirectionAction(
                kind="restore_profile",
                entity_type="queue_profile",
                entity_id=int(profile.id),
                entity_key=profile.key,
            )
        ]
    if availability.state != "available":
        action = AdminDirectionAction(
            kind="review_configuration",
            entity_type="department",
            entity_key=availability.parent_department_key or profile.department_key,
        )
        return [action]
    if mode == "unresolved":
        return [
            AdminDirectionAction(
                kind="configure_ownership",
                entity_type="queue_tag",
                entity_key=tag,
            )
            for tag in sorted(_profile_route_tags(profile))
        ]
    if mode == "overview":
        if profile.show_on_qr_page:
            return [
                AdminDirectionAction(
                    kind="review_configuration",
                    entity_type="queue_profile",
                    entity_id=int(profile.id),
                    entity_key=profile.key,
                )
            ]
        return []
    if not profile.show_on_qr_page:
        if not publish_candidate_available:
            return [
                AdminDirectionAction(
                    kind="review_configuration",
                    entity_type="queue_profile",
                    entity_id=int(profile.id),
                    entity_key=profile.key,
                )
            ]
        return [
            AdminDirectionAction(
                kind="publish_profile",
                entity_type="queue_profile",
                entity_id=int(profile.id),
                entity_key=profile.key,
            )
        ]
    if not public_available:
        return [
            AdminDirectionAction(
                kind="review_configuration",
                entity_type="queue_profile",
                entity_id=int(profile.id),
                entity_key=profile.key,
            )
        ]
    if not has_address:
        return [
            AdminDirectionAction(
                kind="provision_permanent_address",
                entity_type="queue_profile",
                entity_id=int(profile.id),
                entity_key=profile.key,
            )
        ]
    return []


def build_admin_queue_directions(
    db: Session, *, requested_day: date | None = None
) -> AdminQueueDirectionsResponse:
    """Build real Admin setup facts using the queue domain's read policies."""
    clinic_day = clinic_today(db)
    view_day = requested_day or clinic_day
    snapshot = load_queue_admin_directions_snapshot(db, day=view_day)
    profiles = snapshot.profiles
    availability_by_profile = load_queue_profile_availability(db, profiles)

    owner_scope_by_profile, eligible_doctor_specialties = (
        queue_service._qr_profile_owner_scopes_for_catalog(db, profiles, day=clinic_day)
    )
    resource_route_tags = {
        resource.queue_tag for resource in snapshot.resources if resource.active
    }
    if view_day == clinic_day:
        resource_route_tags.update(
            queue.queue_tag
            for queue in snapshot.daily_queues
            if queue.queue_resource_id is not None
        )
    else:
        resource_route_tags.update(
            row[0]
            for row in (
                db.query(DailyQueue.queue_tag)
                .filter(
                    DailyQueue.day == clinic_day,
                    DailyQueue.active.is_(True),
                    DailyQueue.queue_resource_id.isnot(None),
                )
                .all()
            )
            if row[0]
        )

    published_profiles = [
        profile for profile in profiles if profile.is_active and profile.show_on_qr_page
    ]
    public_profiles = queue_service.public_qr_catalog_bookable_profiles(
        db,
        published_profiles,
        day=clinic_day,
        availability_by_profile=availability_by_profile,
        candidate_profiles=profiles,
        owner_scope_by_profile=owner_scope_by_profile,
        eligible_doctor_specialties=eligible_doctor_specialties,
    )
    public_profile_keys = {profile.key for profile in public_profiles}

    # Evaluate whether publishing a hidden profile would be safe with the
    # canonical public-catalog policy. Use a plain in-memory proxy instead of
    # mutating an ORM row: this endpoint is strictly read-only, while the
    # publish command still revalidates under its own transaction.
    publishable_profile_keys: set[str] = set(public_profile_keys)
    for profile in profiles:
        if not profile.is_active or profile.show_on_qr_page:
            continue
        candidate = _PublicationCandidate(
            key=profile.key,
            queue_tags=list(profile.queue_tags or []),
            is_active=bool(profile.is_active),
            show_on_qr_page=True,
            department_key=profile.department_key,
        )
        availability_with_candidate = dict(availability_by_profile)
        availability_with_candidate[candidate] = availability_by_profile[profile]
        owner_scopes_with_candidate = dict(owner_scope_by_profile)
        owner_scopes_with_candidate[candidate] = owner_scope_by_profile.get(profile)
        if queue_service.public_qr_catalog_bookable_profiles(
            db,
            [candidate],
            day=clinic_day,
            availability_by_profile=availability_with_candidate,
            candidate_profiles=[*profiles, candidate],
            owner_scope_by_profile=owner_scopes_with_candidate,
            eligible_doctor_specialties=eligible_doctor_specialties,
        ):
            publishable_profile_keys.add(profile.key)

    eligible_doctors_by_id = {int(doctor.id): doctor for doctor in snapshot.doctors}
    eligible_doctor_ids = set(eligible_doctors_by_id)
    doctor_specialties_by_tag: dict[str, list] = defaultdict(list)
    for doctor in snapshot.doctors:
        if doctor.specialty:
            doctor_specialties_by_tag[doctor.specialty].append(doctor)

    resources_by_tag: dict[str, list[QueueResource]] = defaultdict(list)
    for resource in snapshot.resources:
        resources_by_tag[resource.queue_tag].append(resource)
    queues_by_owner_tag: dict[tuple[str, int, str], list[int]] = defaultdict(list)
    for queue in snapshot.daily_queues:
        owner_type, owner_id = _current_queue_owner(queue)
        if owner_id is not None:
            queues_by_owner_tag[(owner_type, owner_id, queue.queue_tag)].append(
                int(queue.id)
            )

    directions: list[AdminQueueDirection] = []
    covered_tags: set[str] = set()
    for profile in profiles:
        route_tags = _profile_route_tags(profile)
        covered_tags.update(route_tags)
        owner_scope, owner_conflict = (
            queue_service._qr_profile_owner_scope_from_targets(
                profile,
                resource_route_tags=resource_route_tags,
                eligible_doctor_specialties=eligible_doctor_specialties,
            )
        )
        mode = (
            "overview"
            if owner_conflict == "mixed_direction_targets"
            else (
                "booking"
                if owner_scope is not None and owner_conflict is None
                else "unresolved"
            )
        )
        availability = availability_by_profile[profile]
        public_available = profile.key in public_profile_keys
        configuration_reasons = _configuration_reasons(
            profile,
            availability,
            mode=mode,
            owner_conflict=owner_conflict,
            public_available=public_available,
            publish_candidate_available=profile.key in publishable_profile_keys,
        )
        state = _configuration_state(
            profile,
            availability,
            mode=mode,
            reasons=configuration_reasons,
            public_available=public_available,
        )

        targets: list[AdminDirectionBookingTarget] = []
        for tag in sorted(route_tags):
            for resource in resources_by_tag.get(tag, []):
                queue_ids = queues_by_owner_tag.get(
                    ("resource", int(resource.id), tag), []
                )
                if resource.active or queue_ids:
                    targets.append(
                        AdminDirectionBookingTarget(
                            owner_type="resource",
                            owner_id=int(resource.id),
                            queue_tag=tag,
                            label=resource.display_name,
                            is_active=bool(resource.active),
                            eligible_for_new_booking=bool(resource.active or queue_ids),
                            existing_daily_queue_ids=queue_ids,
                        )
                    )
            if tag not in resource_route_tags:
                for doctor in doctor_specialties_by_tag.get(tag, []):
                    queue_ids = queues_by_owner_tag.get(
                        ("doctor", int(doctor.id), tag), []
                    )
                    doctor_user = getattr(doctor, "user", None)
                    doctor_profile = getattr(doctor_user, "profile", None)
                    targets.append(
                        AdminDirectionBookingTarget(
                            owner_type="doctor",
                            owner_id=int(doctor.id),
                            queue_tag=tag,
                            label=(
                                getattr(doctor_profile, "full_name", None)
                                or getattr(doctor_user, "full_name", None)
                                or str(doctor.specialty)
                            ),
                            is_active=True,
                            eligible_for_new_booking=True,
                            existing_daily_queue_ids=queue_ids,
                        )
                    )
        targets.sort(
            key=lambda target: (target.queue_tag, target.owner_type, target.owner_id)
        )

        current_queues = [
            AdminDirectionDailyQueueReference(
                daily_queue_id=int(queue.id),
                queue_tag=queue.queue_tag,
                owner_type=_current_queue_owner(queue)[0],
                owner_id=_current_queue_owner(queue)[1],
            )
            for queue in snapshot.daily_queues
            if queue.queue_tag in route_tags
        ]
        has_address = int(profile.id) in snapshot.profiles_with_permanent_address
        directions.append(
            AdminQueueDirection(
                profile=_profile_to_dto(profile),
                resolved_mode=mode,
                configuration_state=state,
                configuration_reasons=configuration_reasons,
                effective_availability=availability.state,
                effective_availability_reasons=list(availability.reason_codes),
                booking_targets=targets,
                current_day_queues=current_queues,
                public_availability=public_available,
                permanent_address_exists=has_address,
                precreate_by_tag=_precreate_by_tag(
                    route_tags,
                    snapshot,
                    eligible_doctor_ids=eligible_doctor_ids,
                ),
                allowed_next_actions=_allowed_actions(
                    profile,
                    availability,
                    mode=mode,
                    public_available=public_available,
                    publish_candidate_available=profile.key in publishable_profile_keys,
                    has_address=has_address,
                ),
            )
        )

    all_catalog_tags = {
        (service.queue_tag or "").strip()
        for service in snapshot.services
        if (service.queue_tag or "").strip()
    }
    all_catalog_tags.update(
        resource.queue_tag for resource in snapshot.resources if resource.queue_tag
    )
    unattached_tags = sorted(tag for tag in all_catalog_tags if tag not in covered_tags)
    unattached_services = [
        AdminUnattachedService(
            service_id=int(service.id),
            name=service.name,
            code=service.service_code or service.code,
            queue_tag=service.queue_tag,
            active=bool(service.active),
        )
        for service in snapshot.services
        if not service.queue_tag or service.queue_tag.strip() not in covered_tags
    ]
    unattached_resources = [
        AdminUnattachedResource(
            resource_id=int(resource.id),
            queue_tag=resource.queue_tag,
            display_name=resource.display_name,
            active=bool(resource.active),
        )
        for resource in snapshot.resources
        if resource.queue_tag not in covered_tags
    ]

    return AdminQueueDirectionsResponse(
        as_of_day=view_day,
        directions=directions,
        unattached=AdminUnattachedCatalog(
            queue_tags=unattached_tags,
            services=unattached_services,
            resources=unattached_resources,
        ),
    )
