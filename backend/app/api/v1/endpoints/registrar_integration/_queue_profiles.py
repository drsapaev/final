from __future__ import annotations

from typing import Any, Literal

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa
from app.api.v1.endpoints.registrar_integration._helpers import (
    _raise_registrar_internal_error,
)  # noqa: F401
from app.core.specialties import (
    DENTAL_FAMILY_SPELLINGS,
    canonical_specialty,
    expand_queue_tags,
)
from app.schemas.misc_endpoints import ReorderQueueProfilesRequest


def _canonical_profile_tags(tags: list[str] | None, profile_key: str) -> list[str]:
    """D-1 (Codex round-6/7): the tags a QueueProfile write path persists.

    - omitted/empty tags fall back to ``[profile_key]``;
    - a dental-family key must always contribute to the expansion (unless
      the submitted tags already contain a family spelling), so family
      profiles stay canonical-covered even when the admin sets unrelated
      tags;
    - NON-dental profiles keep EXACTLY the tags the admin submitted — the
      key is never silently re-added after an explicit removal.
    """
    tag_list = [t for t in (tags or []) if t]
    if not tag_list:
        return expand_queue_tags([profile_key])
    key_is_family = (profile_key or "").strip().lower() in DENTAL_FAMILY_SPELLINGS
    tags_are_family = any(
        (t or "").strip().lower() in DENTAL_FAMILY_SPELLINGS for t in tag_list
    )
    if key_is_family and not tags_are_family:
        tag_list.append(profile_key)
    return expand_queue_tags(tag_list)


def _profile_binding_values_equal(
    field: str, left: Any, right: Any, profile_key: str
) -> bool:
    if field == "queue_tags":
        return _canonical_profile_tags(left, profile_key) == _canonical_profile_tags(
            right, profile_key
        )
    return left == right


@router.get("/queues/profiles", response_model=dict[str, Any])
def get_queue_profiles(
    active_only: bool = Query(True, description="Только активные профили"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "Cashier", "Lab")
    ),
):
    """
    Получить список профилей очередей для динамических вкладок.

    Каждый профиль определяет:
    - key: уникальный ключ (cardiology, ecg, dermatology и т.д.)
    - title/title_ru: названия для отображения
    - queue_tags: список queue_tag значений, которые относятся к этому профилю
    - icon/color: UI конфигурация

    Frontend использует queue_tags для фильтрации записей по вкладкам.

    SSOT: Вкладки определяются в БД, НЕ хардкодятся в frontend.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Пытаемся получить из БД
        query = db.query(QueueProfile)

        if active_only:
            query = query.filter(QueueProfile.is_active == True)

        profiles = query.order_by(QueueProfile.display_order).all()

        return {
            "success": True,
            "profiles": [
                {
                    "key": p.key,
                    "title": p.title,
                    "title_ru": p.title_ru,
                    "queue_tags": p.queue_tags or [],
                    "department_key": p.department_key,
                    "icon": p.icon,
                    "color": p.color,
                    "order": p.display_order,  # API returns as 'order' for frontend compatibility
                    "is_active": p.is_active,
                    "show_on_qr_page": getattr(
                        p, "show_on_qr_page", True
                    ),  # Handle missing column
                    # D-1: canonical clinic_settings segment this profile's
                    # start_number_*/max_per_day_* rows live under (the
                    # profile key itself may be a legacy machinery value —
                    # e.g. "stomatology" — while settings rows are stored
                    # under the canonical "dentistry" after migration 0049).
                    "settings_key": canonical_specialty(p.key),
                }
                for p in profiles
            ],
            "source": "database",
        }

    except Exception as e:
        _raise_registrar_internal_error("fetch_queue_profiles", e)


@router.get("/queues/profiles/public", response_model=dict[str, Any])
def get_queue_profiles_public(
    db: Session = Depends(get_db),
):
    """
    ⭐ PUBLIC ENDPOINT: Получить список профилей для QR-страницы регистрации.

    Не требует авторизации - используется пациентами при самостоятельной регистрации.
    Возвращает только профили с is_active=True И show_on_qr_page=True.

    Используется на странице /queue/join для выбора специальности.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Получаем только активные профили, которые видны на QR странице
        profiles = (
            db.query(QueueProfile)
            .filter(
                QueueProfile.is_active == True, QueueProfile.show_on_qr_page == True
            )
            .order_by(QueueProfile.display_order)
            .all()
        )

        return {
            "success": True,
            "specialists": [
                {
                    "id": p.id,
                    "specialty": p.key,
                    "specialty_display": p.title_ru or p.title,
                    "icon": _get_emoji_for_key(p.key),
                    "color": p.color or "#6b7280",
                }
                for p in profiles
            ],
            "source": "database",
        }

    except Exception as e:
        _raise_registrar_internal_error("fetch_public_queue_profiles", e)


def _get_emoji_for_key(key: str) -> str:
    """Helper to get emoji icon for profile key"""
    emoji_map = {
        "cardiology": "❤️",
        "ecg": "📊",
        "dermatology": "✨",
        "stomatology": "🦷",
        "lab": "🔬",
        "laboratory": "🔬",
        "procedures": "💉",
        "cosmetology": "💄",
        "general": "👥",
    }
    return emoji_map.get(key, "👨‍⚕️")


def _profile_link_counts(db: Session, profile: Any) -> dict[str, int]:
    """RQ-12.b (D-02, owner decision 2026-09-15): significant-link counts
    for a QueueProfile, computed from live tables at call time.

    This function is the single SSOT for BOTH the impact preview and the
    hard-delete guard: the delete endpoint re-computes these numbers in
    the same transaction that would commit the delete, so a previously
    rendered preview can never authorize a destructive action (stale
    preview protection, ACCEPTANCE S-10). Significant links are:

    - services whose queue_tag is owned by this profile (a delete would
      orphan or silently untag them);
    - daily queues (ANY day — historical rows included) whose queue_tag
      is owned by this profile: their entries are the profile's real
      usage history and possibly still-waiting patients;
    - waiting entries under those queues (must remain serviceable by
      staff regardless of the profile's active state);
    - active permanent public addresses linked to this profile.
    """
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.queue_direction_public_address import QueueDirectionPublicAddress
    from app.models.service import Service

    # Runtime routing expands dental-family aliases even for legacy rows
    # seeded before the canonical profile writer. Count links against that
    # same effective tag set so a legacy alias is not mistaken for an
    # unused binding.
    tags = _canonical_profile_tags(profile.queue_tags, profile.key)
    services = 0
    daily_queues = 0
    entries_waiting = 0
    entries_total = 0
    active_public_addresses = (
        db.query(QueueDirectionPublicAddress)
        .filter(
            QueueDirectionPublicAddress.queue_profile_id == profile.id,
            QueueDirectionPublicAddress.retired_at.is_(None),
        )
        .count()
    )
    if tags:
        services = db.query(Service).filter(Service.queue_tag.in_(tags)).count()
        daily_queues = (
            db.query(DailyQueue).filter(DailyQueue.queue_tag.in_(tags)).count()
        )
        if daily_queues:
            queue_ids = [
                row.id
                for row in db.query(DailyQueue.id)
                .filter(DailyQueue.queue_tag.in_(tags))
                .all()
            ]
            entries_q = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id.in_(queue_ids)
            )
            entries_total = entries_q.count()
            entries_waiting = entries_q.filter(
                OnlineQueueEntry.status == "waiting"
            ).count()
    return {
        "services": services,
        "daily_queues": daily_queues,
        "entries_waiting": entries_waiting,
        "entries_total": entries_total,
        "active_public_addresses": active_public_addresses,
    }


@router.get(
    "/queues/profiles/{profile_key}/impact-preview", response_model=dict[str, Any]
)
def get_queue_profile_impact_preview(
    profile_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """RQ-12.b (D-02): server-side impact preview of what a lifecycle
    action on this profile would touch.

    Read-only: this endpoint never mutates anything and its report is
    informational only — the delete endpoint re-verifies the same links
    at execution time, so a stale preview cannot authorize destruction
    (ACCEPTANCE S-10: "повторить со stale preview").
    """
    try:
        from app.models.queue_profile import QueueProfile

        profile = db.query(QueueProfile).filter(QueueProfile.key == profile_key).first()
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile '{profile_key}' not found"
            )

        counts = _profile_link_counts(db, profile)
        can_hard_delete = all(v == 0 for v in counts.values())

        return {
            "success": True,
            "profile": {
                "key": profile.key,
                "title": profile.title,
                "is_active": profile.is_active,
            },
            "links": counts,
            "can_hard_delete": can_hard_delete,
            # D-02: a used tab is archived (is_active=False), never
            # silently destroyed; deletion is only for linkless profiles.
            "recommendation": "delete" if can_hard_delete else "archive",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error building impact preview for {profile_key}: {e}")
        db.rollback()
        _raise_registrar_internal_error("queue profile impact preview", e)


# ===================== QUEUE PROFILE CRUD (ADMIN) =====================


class QueueProfileCreate(BaseModel):
    """Schema for creating a new QueueProfile"""

    key: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Unique key (e.g., 'cardiology')",
    )
    title: str = Field(..., min_length=1, max_length=100, description="English title")
    title_ru: str | None = Field(None, max_length=100, description="Russian title")
    queue_tags: list[str] = Field(
        default=[], description="List of queue_tag values for this profile"
    )
    department_key: str | None = Field(None, max_length=50)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    show_on_qr_page: bool = Field(
        default=True, description="Show this profile on QR join page"
    )
    icon: str | None = Field(
        None, max_length=50, description="Lucide icon name (e.g., 'Heart')"
    )
    color: str | None = Field(
        None, max_length=20, description="Hex color (e.g., '#E53E3E')"
    )


class QueueProfileUpdate(BaseModel):
    """Schema for updating an existing QueueProfile"""

    title: str | None = Field(None, max_length=100)
    title_ru: str | None = Field(None, max_length=100)
    queue_tags: list[str] | None = None
    department_key: str | None = Field(None, max_length=50)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None
    show_on_qr_page: bool | None = Field(
        None, description="Show this profile on QR join page"
    )
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=20)


class QueueProfileBindingSnapshot(BaseModel):
    queue_tags: list[str]
    department_key: str | None


class QueueProfileLinkCounts(BaseModel):
    services: int
    daily_queues: int
    entries_waiting: int
    entries_total: int
    active_public_addresses: int


class QueueProfileImpactIdentity(BaseModel):
    key: str


class QueueProfileUpdateImpactPreview(BaseModel):
    success: bool
    profile: QueueProfileImpactIdentity
    current: QueueProfileBindingSnapshot
    proposed: QueueProfileBindingSnapshot
    links: QueueProfileLinkCounts
    changed_binding_fields: list[Literal["queue_tags", "department_key"]]
    blocked_fields: list[Literal["queue_tags", "department_key"]]
    can_update: bool


class QueueProfileBindingConflictDetail(BaseModel):
    reason: Literal["profile_binding_change_blocked"]
    blocked_fields: list[Literal["queue_tags", "department_key"]]
    links: QueueProfileLinkCounts
    message: str


class QueueProfileBindingConflictResponse(BaseModel):
    detail: QueueProfileBindingConflictDetail


@router.post(
    "/queues/profiles/{profile_key}/impact-preview",
    response_model=QueueProfileUpdateImpactPreview,
)
def preview_queue_profile_update(
    profile_key: str,
    profile_data: QueueProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Read-only impact preview for a proposed profile update.

    A preview is informational. The PUT handler re-reads usage immediately
    before applying any fields and never accepts a preview as authorization.
    """
    try:
        from app.models.queue_profile import QueueProfile

        profile = db.query(QueueProfile).filter(QueueProfile.key == profile_key).first()
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile '{profile_key}' not found"
            )

        proposed_update = profile_data.dict(exclude_unset=True)
        current = {
            "queue_tags": list(profile.queue_tags or []),
            "department_key": profile.department_key,
        }
        proposed = dict(current)
        if "queue_tags" in proposed_update:
            candidate_tags = _canonical_profile_tags(
                proposed_update["queue_tags"], profile.key
            )
            # Keep the legacy stored list visible for a semantically
            # unchanged proposal; preview should describe the actual no-op.
            proposed["queue_tags"] = (
                current["queue_tags"]
                if _profile_binding_values_equal(
                    "queue_tags", current["queue_tags"], candidate_tags, profile.key
                )
                else candidate_tags
            )
        if "department_key" in proposed_update:
            proposed["department_key"] = proposed_update["department_key"]

        changed_binding_fields = [
            field
            for field in ("queue_tags", "department_key")
            if not _profile_binding_values_equal(
                field, current[field], proposed[field], profile.key
            )
        ]
        links = _profile_link_counts(db, profile)
        blocked_fields = changed_binding_fields if any(links.values()) else []

        return {
            "success": True,
            "profile": QueueProfileImpactIdentity(key=profile.key),
            "current": current,
            "proposed": proposed,
            "links": links,
            "changed_binding_fields": changed_binding_fields,
            "blocked_fields": blocked_fields,
            "can_update": not blocked_fields,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing queue profile update for {profile_key}: {e}")
        db.rollback()
        _raise_registrar_internal_error("queue profile update preview", e)


@router.post("/queues/profiles", response_model=dict[str, Any])
def create_queue_profile(
    profile_data: QueueProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Create a new QueueProfile (admin only).

    SSOT: Tabs are defined in DB, not hardcoded in frontend.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Check if key already exists
        existing = (
            db.query(QueueProfile).filter(QueueProfile.key == profile_data.key).first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Profile with key '{profile_data.key}' already exists",
            )

        # Create new profile
        new_profile = QueueProfile(
            key=profile_data.key,
            title=profile_data.title,
            title_ru=profile_data.title_ru,
            # D-1 (Codex round-6 P1): a dental-family profile must never be
            # persisted with tags blind to the canonical spelling (see
            # _canonical_profile_tags for the exact contract).
            queue_tags=_canonical_profile_tags(
                profile_data.queue_tags, profile_data.key
            ),
            department_key=profile_data.department_key,
            display_order=profile_data.display_order,
            is_active=profile_data.is_active,
            show_on_qr_page=profile_data.show_on_qr_page,
            icon=profile_data.icon,
            color=profile_data.color,
        )

        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        logger.info(f"Created QueueProfile: {new_profile.key}")

        return {
            "success": True,
            "profile": {
                "id": new_profile.id,
                "key": new_profile.key,
                "title": new_profile.title,
                "title_ru": new_profile.title_ru,
                "queue_tags": new_profile.queue_tags or [],
                "department_key": new_profile.department_key,
                "order": new_profile.display_order,
                "is_active": new_profile.is_active,
                "show_on_qr_page": new_profile.show_on_qr_page,
                "icon": new_profile.icon,
                "color": new_profile.color,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating queue profile: {e}")
        db.rollback()
        _raise_registrar_internal_error("create queue profile", e)


@router.put(
    "/queues/profiles/{profile_key}",
    response_model=dict[str, Any],
    responses={
        409: {
            "model": QueueProfileBindingConflictResponse,
            "description": "Binding changes are blocked while the profile is in use.",
        }
    },
)
def update_queue_profile(
    profile_key: str,
    profile_data: QueueProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Update an existing QueueProfile by key (admin only).

    SSOT: Changes here reflect immediately in Registrar Panel tabs.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Find profile
        # Serialize binding edits with public-address provisioning. Both
        # operations lock this canonical row before checking dependencies.
        profile = (
            db.query(QueueProfile)
            .filter(QueueProfile.key == profile_key)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile '{profile_key}' not found"
            )

        # Update fields (only those provided)
        update_data = profile_data.dict(exclude_unset=True)
        if "queue_tags" in update_data:
            candidate_tags = _canonical_profile_tags(
                update_data["queue_tags"], profile.key
            )
            if _profile_binding_values_equal(
                "queue_tags", profile.queue_tags, candidate_tags, profile.key
            ):
                # The UI submits the full form, including unchanged tags.
                # Preserve older persisted spellings/order instead of
                # treating canonical expansion as a binding mutation.
                update_data.pop("queue_tags")
            else:
                update_data["queue_tags"] = candidate_tags

        current_bindings = {
            "queue_tags": list(profile.queue_tags or []),
            "department_key": profile.department_key,
        }
        changed_binding_fields = [
            field
            for field in ("queue_tags", "department_key")
            if field in update_data
            and not _profile_binding_values_equal(
                field, current_bindings[field], update_data[field], profile.key
            )
        ]
        if changed_binding_fields:
            # Recompute usage at command time. A preview is never authority
            # to change a binding after the profile has become used.
            links = _profile_link_counts(db, profile)
            if any(links.values()):
                logger.warning(
                    "QueueProfile binding update blocked: "
                    f"key={profile.key} fields={changed_binding_fields} links={links}"
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "reason": "profile_binding_change_blocked",
                        "blocked_fields": changed_binding_fields,
                        "links": links,
                        "message": (
                            "Связи используемого профиля менять нельзя. "
                            "Разрешены только отображаемые поля и архивирование."
                        ),
                    },
                )

        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)

        db.commit()
        db.refresh(profile)

        logger.info(f"Updated QueueProfile: {profile.key}")

        return {
            "success": True,
            "profile": {
                "id": profile.id,
                "key": profile.key,
                "title": profile.title,
                "title_ru": profile.title_ru,
                "queue_tags": profile.queue_tags or [],
                "department_key": profile.department_key,
                "order": profile.display_order,
                "is_active": profile.is_active,
                "icon": profile.icon,
                "color": profile.color,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating queue profile: {e}")
        db.rollback()
        _raise_registrar_internal_error("update queue profile", e)


@router.delete("/queues/profiles/{profile_key}", response_model=dict[str, Any])
def delete_queue_profile(
    profile_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Delete a QueueProfile by key (admin only).

    Warning: This will remove the tab from Registrar Panel.
    """
    try:
        from app.models.queue_profile import QueueProfile
        from app.models.service import Service

        # Find profile
        profile = db.query(QueueProfile).filter(QueueProfile.key == profile_key).first()
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile '{profile_key}' not found"
            )

        # RQ-12.b (D-02 owner decision 2026-09-15): hard delete is allowed
        # ONLY with proven absence of significant links — services on the
        # profile's tags, daily queues (historical rows included) and any
        # entries under them (waiting patients must stay serviceable via
        # archive, not be orphaned by deletion). The counts are computed
        # HERE, at execution time, from the same SSOT as the impact
        # preview — a previously rendered preview report is informational
        # and NEVER authorizes the delete (stale-preview protection, S-10).
        counts = _profile_link_counts(db, profile)
        if any(counts.values()):
            logger.warning(f"Delete of QueueProfile '{profile_key}' blocked: {counts}")
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": "profile_has_significant_links",
                    "links": counts,
                    "message": (
                        "Профиль используется: архивируйте его "
                        "(is_active=false) вместо удаления."
                    ),
                },
            )

        # PR-22: cascade cleanup — clear queue_tag from services that
        # matched this profile's tags. Without this, services keep
        # orphaned queue_tags that silently disappear from registrar.
        #
        # RQ-12.a (F-11 / ACCEPTANCE S-10): a tag that is STILL owned by
        # another (remaining) profile must keep its services — deleting
        # one profile must not silently untag services from the remaining
        # profile's tab. Compute the remaining owners' tags BEFORE the
        # delete; only exclusively-owned tags are cleaned.
        other_tags: set[str] = set()
        for other in (
            db.query(QueueProfile).filter(QueueProfile.key != profile_key).all()
        ):
            other_tags.update(other.queue_tags or [])

        tags_to_clean = [
            tag for tag in (profile.queue_tags or []) if tag not in other_tags
        ]
        services_cleaned = 0
        if tags_to_clean:
            services = (
                db.query(Service).filter(Service.queue_tag.in_(tags_to_clean)).all()
            )
            for svc in services:
                if svc.queue_tag in tags_to_clean:
                    svc.queue_tag = None
                    services_cleaned += 1

        db.delete(profile)
        db.commit()

        logger.info(
            f"Deleted QueueProfile: {profile_key} (cleaned {services_cleaned} services)"
        )

        return {
            "success": True,
            "message": f"Profile '{profile_key}' deleted successfully",
            "services_cleaned": services_cleaned,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting queue profile: {e}")
        db.rollback()
        _raise_registrar_internal_error("delete queue profile", e)


@router.post("/queues/profiles/reorder", response_model=dict[str, Any])
def reorder_queue_profiles(
    orders: ReorderQueueProfilesRequest,  # {"profile_key": new_order, ...}
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Batch update display_order for multiple profiles (admin only).

    Request body: {"cardiology": 1, "ecg": 2, "dermatology": 3, ...}
    """
    try:
        from app.models.queue_profile import QueueProfile

        updated = 0
        for key, order in orders.items():
            profile = db.query(QueueProfile).filter(QueueProfile.key == key).first()
            if profile:
                profile.display_order = order
                updated += 1

        db.commit()

        logger.info(f"Reordered {updated} QueueProfiles")

        return {
            "success": True,
            "updated": updated,
        }

    except Exception as e:
        logger.error(f"Error reordering queue profiles: {e}")
        db.rollback()
        _raise_registrar_internal_error("reorder queue profiles", e)


# ===================== СПРАВОЧНИК УСЛУГ (СТАРЫЙ) =====================
