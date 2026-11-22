"""Admin use case for explicitly repairing QueueProfile parent conflicts.

The only supported repair in this slice clears an explicit Department claim
so the existing QueueProfile.key-to-Department own-key convention applies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.specialties import DENTAL_FAMILY_SPELLINGS, expand_queue_tags
from app.crud.clinic import clinic_today
from app.crud.queue_owner_invariant import lock_profile_binding_scopes
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.queue_direction_public_address import QueueDirectionPublicAddress
from app.models.queue_profile import QueueProfile
from app.models.service import Service
from app.services.queue_profile_availability import (
    load_queue_profile_availability,
    normalize_department_key,
    resolve_queue_profile_availability,
)
from app.services.queue_service import queue_service

PARENT_REPAIR_REASON = "resolve_parent_conflict_to_own_key"


class QueueProfileParentRepairError(Exception):
    """Domain failure mapped to a typed HTTP response by the API endpoint."""

    def __init__(
        self,
        reason: Literal[
            "profile_not_found",
            "parent_repair_stale",
            "parent_repair_not_applicable",
            "parent_repair_confirmation_required",
        ],
        message: str,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class _ProposedProfile:
    id: int
    key: str
    department_key: None
    is_active: bool
    show_on_qr_page: bool
    queue_tags: tuple[str, ...]


def canonical_profile_tags(tags: list[str] | None, profile_key: str) -> list[str]:
    """Return the same effective profile tags used by existing T10 guards."""
    tag_list = [tag for tag in (tags or []) if tag]
    if not tag_list:
        return expand_queue_tags([profile_key])
    key_is_dental = (profile_key or "").strip().lower() in DENTAL_FAMILY_SPELLINGS
    tags_are_dental = any(
        (tag or "").strip().lower() in DENTAL_FAMILY_SPELLINGS for tag in tag_list
    )
    if key_is_dental and not tags_are_dental:
        tag_list.append(profile_key)
    return expand_queue_tags(tag_list)


def queue_profile_link_counts(db: Session, profile: Any) -> dict[str, int]:
    """Count the same significant QueueProfile links used by T10 lifecycle guards."""
    tags = canonical_profile_tags(profile.queue_tags, profile.key)
    usage_tags = list(tags)
    if profile.key and profile.key not in usage_tags:
        usage_tags.append(profile.key)

    active_public_addresses = (
        db.query(QueueDirectionPublicAddress)
        .filter(
            QueueDirectionPublicAddress.queue_profile_id == profile.id,
            QueueDirectionPublicAddress.retired_at.is_(None),
        )
        .count()
    )
    services = (
        db.query(Service).filter(Service.queue_tag.in_(usage_tags)).count()
        if usage_tags
        else 0
    )
    daily_queues = (
        db.query(DailyQueue).filter(DailyQueue.queue_tag.in_(usage_tags)).count()
        if usage_tags
        else 0
    )
    entries_total = 0
    entries_waiting = 0
    if daily_queues:
        queue_ids = [
            row.id
            for row in db.query(DailyQueue.id)
            .filter(DailyQueue.queue_tag.in_(usage_tags))
            .all()
        ]
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id.in_(queue_ids)
        )
        entries_total = entries.count()
        entries_waiting = entries.filter(OnlineQueueEntry.status == "waiting").count()

    if tags:
        active_doctors = (
            db.query(Doctor)
            .filter(
                Doctor.active.is_(True),
                func.lower(func.trim(Doctor.specialty)).in_(
                    {tag.strip().lower() for tag in tags}
                ),
            )
            .count()
        )
        active_queue_resources = (
            db.query(QueueResource)
            .filter(
                QueueResource.active.is_(True),
                QueueResource.queue_tag.in_(tags),
            )
            .count()
        )
    else:
        active_doctors = 0
        active_queue_resources = 0

    department_key = normalize_department_key(profile.department_key)
    department_services = (
        db.query(Service).filter(Service.department_key == department_key).count()
        if department_key
        else 0
    )
    return {
        "services": services,
        "department_services": department_services,
        "active_doctors": active_doctors,
        "active_queue_resources": active_queue_resources,
        "daily_queues": daily_queues,
        "entries_waiting": entries_waiting,
        "entries_total": entries_total,
        "active_public_addresses": active_public_addresses,
    }


def _service_parent_scope_ids(db: Session, department_key: str | None) -> set[int]:
    normalized = normalize_department_key(department_key)
    if normalized is None:
        return set()
    return {
        int(row.id)
        for row in db.query(Service.id)
        .filter(Service.department_key == normalized)
        .all()
    }


def _parent_references(
    profile: QueueProfile,
    departments_by_key: dict[str, Department],
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    candidates = (
        ("profile_key", profile.key),
        ("department_key", profile.department_key),
    )
    seen: set[tuple[str, str]] = set()
    for source, raw_key in candidates:
        key = normalize_department_key(raw_key)
        if key is None or (source, key) in seen:
            continue
        seen.add((source, key))
        department = departments_by_key.get(key)
        references.append(
            {
                "source": source,
                "department_key": key,
                "department_name_ru": department.name_ru if department else None,
                "exists": department is not None,
                "active": bool(department.active) if department else None,
            }
        )
    return references


def _public_effect_after_repair(
    db: Session,
    profile: QueueProfile,
    *,
    has_active_public_address: bool,
) -> tuple[bool, bool]:
    """Evaluate the canonical public catalog with a non-persisted profile copy.

    The canonical selector reads every configured profile to detect competing
    targets. Replace only this profile in that in-memory candidate set so the
    preview models the proposed binding without dirtying an ORM entity or
    writing anything in a read-only endpoint.
    """
    profiles = db.query(QueueProfile).all()
    proposed_profile = _ProposedProfile(
        id=int(profile.id),
        key=profile.key,
        department_key=None,
        is_active=bool(profile.is_active),
        show_on_qr_page=bool(profile.show_on_qr_page),
        queue_tags=tuple(profile.queue_tags or ()),
    )
    candidates = [proposed_profile if row.id == profile.id else row for row in profiles]
    availability_by_profile = load_queue_profile_availability(db, candidates)
    published = [row for row in candidates if bool(row.show_on_qr_page)]
    bookable = queue_service.public_qr_catalog_bookable_profiles(
        db,
        published,
        day=clinic_today(db),
        availability_by_profile=availability_by_profile,
        candidate_profiles=candidates,
    )
    target_is_bookable = any(row.key == profile.key for row in bookable)
    # A permanent route is usable only if the canonical selector accepts the
    # profile AND an active saved address already exists. Preview never
    # provisions, retires, or otherwise changes that address.
    return target_is_bookable, target_is_bookable and has_active_public_address


def _fingerprint(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_preview(db: Session, profile: QueueProfile) -> dict[str, Any]:
    current_availability = load_queue_profile_availability(db, [profile])[profile]
    parent_keys = {
        key
        for key in (
            normalize_department_key(profile.key),
            normalize_department_key(profile.department_key),
        )
        if key
    }
    departments = (
        db.query(Department)
        .filter(Department.key.in_(sorted(parent_keys)))
        .order_by(Department.id.asc())
        .populate_existing()
        .all()
        if parent_keys
        else []
    )
    departments_by_key = {department.key: department for department in departments}
    target = departments_by_key.get(profile.key)
    can_apply = (
        "parent_conflict" in current_availability.reason_codes and target is not None
    )
    blocker_code = (
        None
        if can_apply
        else (
            "own_key_department_missing"
            if "parent_conflict" in current_availability.reason_codes
            else "parent_conflict_absent"
        )
    )
    proposed_availability = (
        resolve_queue_profile_availability(
            _ProposedProfile(
                id=int(profile.id),
                key=profile.key,
                department_key=None,
                is_active=bool(profile.is_active),
                show_on_qr_page=bool(profile.show_on_qr_page),
                queue_tags=tuple(profile.queue_tags or ()),
            ),
            {target.key: target},
        )
        if target is not None
        else None
    )

    links = queue_profile_link_counts(db, profile)
    old_service_ids = _service_parent_scope_ids(db, profile.department_key)
    proposed_service_ids = _service_parent_scope_ids(db, profile.key)
    removed_service_ids = old_service_ids - proposed_service_ids
    added_service_ids = proposed_service_ids - old_service_ids
    service_fingerprint = _fingerprint(
        {
            "current": sorted(old_service_ids),
            "proposed": sorted(proposed_service_ids),
        }
    )
    qr_bookable, permanent_address_bookable = (
        _public_effect_after_repair(
            db,
            profile,
            has_active_public_address=links["active_public_addresses"] > 0,
        )
        if can_apply
        else (False, False)
    )
    parent_references = _parent_references(profile, departments_by_key)
    result = {
        "success": True,
        "profile_id": int(profile.id),
        "profile_key": profile.key,
        "current_department_key": profile.department_key,
        "current_availability_state": current_availability.state,
        "current_reason_codes": list(current_availability.reason_codes),
        "parent_references": parent_references,
        "target": (
            {
                "department_key": target.key,
                "department_name_ru": target.name_ru,
                "active": bool(target.active),
            }
            if target is not None
            else None
        ),
        "proposed_availability_state": (
            proposed_availability.state if proposed_availability else None
        ),
        "proposed_reason_codes": (
            list(proposed_availability.reason_codes) if proposed_availability else []
        ),
        "links": links,
        "services_removed_from_parent_scope": len(removed_service_ids),
        "services_added_to_parent_scope": len(added_service_ids),
        "service_scope_confirmation_required": bool(
            removed_service_ids or added_service_ids
        ),
        "qr_catalog_would_be_bookable": qr_bookable,
        "permanent_address_would_be_bookable": permanent_address_bookable,
        "public_access_confirmation_required": (
            qr_bookable or permanent_address_bookable
        ),
        "can_apply": can_apply,
        "blocker_code": blocker_code,
        "preview_token": None,
    }
    if can_apply and target is not None and proposed_availability is not None:
        token_snapshot = {
            "profile_id": result["profile_id"],
            "profile_key": profile.key,
            "updated_at": (
                profile.updated_at.isoformat() if profile.updated_at else None
            ),
            "current_department_key": profile.department_key,
            "is_active": bool(profile.is_active),
            "show_on_qr_page": bool(profile.show_on_qr_page),
            "target": {
                "id": int(target.id),
                "key": target.key,
                "name_ru": target.name_ru,
                "active": bool(target.active),
            },
            "current_availability": {
                "state": current_availability.state,
                "reasons": list(current_availability.reason_codes),
            },
            "proposed_availability": {
                "state": proposed_availability.state,
                "reasons": list(proposed_availability.reason_codes),
            },
            "parent_references": parent_references,
            "links": links,
            "service_fingerprint": service_fingerprint,
            "services_removed": sorted(removed_service_ids),
            "services_added": sorted(added_service_ids),
            "qr_catalog_would_be_bookable": qr_bookable,
            "permanent_address_would_be_bookable": permanent_address_bookable,
        }
        result["preview_token"] = _fingerprint(token_snapshot)
    return result


def preview_queue_profile_parent_repair(
    db: Session, profile_key: str
) -> dict[str, Any]:
    profile = (
        db.query(QueueProfile)
        .filter(QueueProfile.key == profile_key)
        .populate_existing()
        .first()
    )
    if profile is None:
        raise QueueProfileParentRepairError(
            "profile_not_found", "Профиль очереди не найден."
        )
    return _build_preview(db, profile)


def _write_parent_repair_audit(
    db: Session,
    *,
    profile: QueueProfile,
    actor_user_id: int,
    actor_role: str,
    request_id: str | None,
    old_department_key: str | None,
    preview: dict[str, Any],
) -> AuditLog:
    entry = AuditLog(
        action="update",
        entity_type="queue_profile",
        entity_id=int(profile.id),
        actor_user_id=actor_user_id,
        event_type="QUEUE_PROFILE_PARENT_REPAIR",
        actor_role=actor_role,
        actor_type="staff",
        resource_type="queue_profile",
        resource_id=str(profile.id),
        outcome="success",
        reason_code={"code": PARENT_REPAIR_REASON},
        session_id=request_id,
        payload={
            "profile_key": profile.key,
            "old_department_key": old_department_key,
            "new_department_key": None,
            "target_department_key": profile.key,
            "reason_code": PARENT_REPAIR_REASON,
            "preview_fingerprint": preview["preview_token"],
            "links": preview["links"],
            "services_removed_from_parent_scope": (
                preview["services_removed_from_parent_scope"]
            ),
            "services_added_to_parent_scope": (
                preview["services_added_to_parent_scope"]
            ),
            "qr_catalog_would_be_bookable": (preview["qr_catalog_would_be_bookable"]),
            "permanent_address_would_be_bookable": (
                preview["permanent_address_would_be_bookable"]
            ),
        },
    )
    db.add(entry)
    db.flush()
    return entry


def apply_queue_profile_parent_repair(
    db: Session,
    *,
    profile_key: str,
    target_department_key: str,
    preview_token: str,
    confirm_target: bool,
    confirm_service_scope_change: bool,
    confirm_public_access: bool,
    reason_code: str,
    actor_user_id: int,
    actor_role: str,
    request_id: str | None,
) -> dict[str, Any]:
    candidate = (
        db.query(QueueProfile)
        .filter(QueueProfile.key == profile_key)
        .populate_existing()
        .first()
    )
    if candidate is None:
        raise QueueProfileParentRepairError(
            "profile_not_found", "Профиль очереди не найден."
        )
    old_department_key = candidate.department_key
    old_tags = canonical_profile_tags(candidate.queue_tags, candidate.key)
    lock_profile_binding_scopes(
        db,
        queue_tags=[*old_tags, candidate.key],
        department_keys=[old_department_key, candidate.key],
    )
    profile = (
        db.query(QueueProfile)
        .filter(QueueProfile.key == profile_key)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if profile is None:
        raise QueueProfileParentRepairError(
            "profile_not_found", "Профиль очереди не найден."
        )
    if (
        profile.department_key != old_department_key
        or profile.key != candidate.key
        or canonical_profile_tags(profile.queue_tags, profile.key) != old_tags
    ):
        raise QueueProfileParentRepairError(
            "parent_repair_stale",
            "Привязка направления изменилась. Обновите preview и повторите.",
        )

    department_keys = sorted(
        {
            key
            for key in (
                normalize_department_key(profile.key),
                normalize_department_key(profile.department_key),
            )
            if key
        }
    )
    locked_departments = (
        db.query(Department)
        .filter(Department.key.in_(department_keys))
        .order_by(Department.id.asc())
        .with_for_update()
        .populate_existing()
        .all()
        if department_keys
        else []
    )
    departments_by_key = {
        department.key: department for department in locked_departments
    }

    if target_department_key != profile.key:
        raise QueueProfileParentRepairError(
            "parent_repair_not_applicable",
            "Можно выбрать только отделение, чей ключ совпадает с ключом профиля.",
        )
    target = departments_by_key.get(profile.key)
    current_availability = load_queue_profile_availability(db, [profile])[profile]
    if (
        profile.department_key is None
        and target is not None
        and "parent_conflict" not in current_availability.reason_codes
    ):
        previous_audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.event_type == "QUEUE_PROFILE_PARENT_REPAIR",
                AuditLog.resource_type == "queue_profile",
                AuditLog.resource_id == str(profile.id),
                AuditLog.outcome == "success",
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
        if (
            previous_audit is not None
            and isinstance(previous_audit.payload, dict)
            and previous_audit.payload.get("preview_fingerprint") == preview_token
            and target_department_key == profile.key
            and confirm_target
            and reason_code == PARENT_REPAIR_REASON
        ):
            return {
                "result": "already_applied",
                "profile_id": int(profile.id),
                "profile_key": profile.key,
                "department_key": None,
                "audit_event_id": int(previous_audit.id),
            }
        raise QueueProfileParentRepairError(
            "parent_repair_stale",
            "Конфликт уже изменился. Обновите preview перед повтором.",
        )

    if target is None or "parent_conflict" not in current_availability.reason_codes:
        raise QueueProfileParentRepairError(
            "parent_repair_not_applicable",
            "Текущую привязку нельзя исправить по правилу ключа профиля.",
        )
    preview = _build_preview(db, profile)
    if not preview["can_apply"] or preview["preview_token"] != preview_token:
        raise QueueProfileParentRepairError(
            "parent_repair_stale",
            "Состояние профиля или связанных настроек изменилось. Обновите preview.",
        )
    if not confirm_target or reason_code != PARENT_REPAIR_REASON:
        raise QueueProfileParentRepairError(
            "parent_repair_confirmation_required",
            "Подтвердите отделение и основание исправления.",
        )
    if (
        preview["service_scope_confirmation_required"]
        and not confirm_service_scope_change
    ) or (preview["public_access_confirmation_required"] and not confirm_public_access):
        raise QueueProfileParentRepairError(
            "parent_repair_confirmation_required",
            "Подтвердите изменение области услуг и доступности записи.",
        )

    profile.department_key = None
    db.flush()
    audit_entry = _write_parent_repair_audit(
        db,
        profile=profile,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        request_id=request_id,
        old_department_key=old_department_key,
        preview=preview,
    )
    return {
        "result": "applied",
        "profile_id": int(profile.id),
        "profile_key": profile.key,
        "department_key": None,
        "audit_event_id": int(audit_entry.id),
    }
