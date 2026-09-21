"""RQ-16.b — direction QR-entry methods (contract/API slice).

DIRECTION_CONTRACT.md §6.2 (derived from D-01/D-03 APPROVED, E-039):
the server EXPLICITLY enumerates the supported QR-entry methods of a
direction — session QR (the short-lived protected session path,
join/start -> join/complete; printed QR stays short-lived, RQ-11 TTL
honesty), permanent address and view-only overview (D-01 §4: an
overview never creates its own numbering). Clients must read this
surface, never guess.

RQ-16.d (owner decision 2026-09-17, E-055 §8): the
``permanent_address`` flag became DYNAMIC per-direction — True only
when the direction has a provisioned active registry address AND the
canonical eligibility probe passes. Unprovisioned directions keep
reporting False (no backfill, E-055 §3). The RQ-16.d runtime lives on
the same surface:

- ``POST /admin/directions/{profile_key}/public-address/provision``
  (Admin-only): generates the opaque public code ONCE (E-055 §3 — no
  admin-typed slugs, no backfill), idempotent re-provision, collision
  retry loop (E-055 §11). The ``clinic`` sentinel key is refused — a
  direction token with department == "clinic" would be
  indistinguishable from a legacy clinic-wide token and the session
  binding could not be enforced.
- ``POST /public/{public_code}/start-session`` (anonymous,
  rate-limited): ONE canonical resolve/start operation (E-055 §9) —
  registry lookup -> QueueProfile -> the SAME visibility contract as QR
  (single anonymous 404 refusal for unknown/archived/hidden/deleted/
  retired, S-15) -> eligibility probe -> a direction-scoped short-lived
  QueueToken mint (bounded by the SAME 5..15 min TTL contract as every
  QR token, RQ-11) -> the EXISTING ``start_join_session`` (15-minute
  QueueJoinSession) -> the existing join/complete flow. No join rule is
  copied here; ``/queue/join/:token`` stays the canonical session path.
  The internal minted token is NOT returned (the session_token drives
  the flow) — no second credential is handed out.

Refusal rules (S-15): an archived (is_active=False), hidden
(show_on_qr_page=False), tombstoned (hard-deleted profile) or unknown
code returns 404 with the SAME anonymous detail — archived directions
block new joins and must not leak existence. Fail-closed: no
INITIAL_QUEUE_PROFILES fallback fabricates directions here.

§6.1: visibility/normalization semantics are CONSUMED from the
queue_svc resolver helpers (``_normalize_qr_specialty_key`` /
``_is_qr_visible_profile`` — the same classmethods the RQ-14.b
canonical resolver and the join path use); no rule is duplicated here.
Read-only aside from the provision operation and the session/token
rows it legitimately creates (the same rows the printed-QR path
creates).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import (
    BaseModel,
    Depends,
    Field,
    QRQueueService,
    Session,
    User,
    get_db,
    queue_service,
    require_roles,
    router,
)
from app.core.rate_limiter import RATE_LIMITS, limiter
from app.models.queue_direction_public_address import (
    QueueDirectionPublicAddress,
    normalize_public_code,
)
from app.services.queue_svc import QueueBusinessService


class DirectionEntryMethod(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """The contract methods space (DIRECTION_CONTRACT.md §6.2)."""

    SESSION_QR = "session_qr"
    PERMANENT_ADDRESS = "permanent_address"
    VIEW_ONLY = "view_only"


class DirectionEntryMethodSupport(BaseModel):
    """One method with its honest support flag for this direction."""

    method: DirectionEntryMethod
    supported: bool


class DirectionEntryMethodsResponse(BaseModel):
    """Explicit entry-methods enumeration for one QR-visible direction."""

    direction_key: str = Field(
        ..., description="Canonical QR-visible profile key (normalized)"
    )
    profile_id: int = Field(..., description="QueueProfile.id — a separate id space (D-01)")
    title: str = Field(..., description="Public display title (title_ru preferred)")
    entry_methods: list[DirectionEntryMethodSupport] = Field(
        ...,
        description=(
            "The WHOLE methods space, always fully present: every contract "
            "method carries an honest supported flag; clients must not "
            "infer methods absent from this enumeration"
        ),
    )


class PublicAddressProvisionResponse(BaseModel):
    """Result of the Admin provision/enable of a permanent address."""

    profile_id: int = Field(..., description="QueueProfile.id — a separate id space (D-01)")
    direction_key: str = Field(..., description="Canonical profile key the address is bound to")
    public_code: str = Field(
        ...,
        description=(
            "Opaque random 12-char lowercase public code (E-055 §2) — a "
            "PUBLIC identifier, never a secret and never derived from the "
            "direction title or key"
        ),
    )
    url_path: str = Field(..., description="The permanent frontend route: /q/<public_code>")
    created: bool = Field(
        ...,
        description=(
            "True when a NEW code was generated now; False when the "
            "direction already had its one active address (E-055 §3: "
            "generated ONCE, re-provision returns the SAME address)"
        ),
    )
    provisioned_at: str | None = Field(None, description="Address creation timestamp (ISO-8601)")


class PublicDirectionAddressInfo(BaseModel):
    """The direction a permanent-address session is scoped to."""

    profile_id: int = Field(..., description="QueueProfile.id — a separate id space (D-01)")
    key: str = Field(..., description="Canonical direction key")
    title: str = Field(..., description="Public display title (title_ru preferred)")
    public_code: str = Field(..., description="The canonical lowercase public code of the address")


class PublicDirectionStartResponse(BaseModel):
    """Short-lived session opened through the permanent public address.

    The ``session_token`` drives the EXISTING QueueJoin flow
    (``/queue/join/:token`` semantics preserved); the internal
    direction-scoped QR token is deliberately NOT returned.
    """

    session_token: str
    expires_at: str
    permanent_address: bool = Field(
        ..., description="Always True on this surface (the address is permanent)"
    )
    direction: PublicDirectionAddressInfo
    queue_info: dict[str, Any] = Field(
        ...,
        description=(
            "The same token-info shape the session-QR flow consumes, with "
            "selectable_specialists narrowed to this direction's eligible "
            "owners (RQ-09.b eligibility contract)"
        ),
    )


_REFUSAL_DETAIL = "Направление недоступно"

# RQ-16.d mint TTL request: bounded by the SAME 5..15 minute contract as
# every QR token (RQ-11 TTL honesty) — the minted token is a short-lived
# session-scoping primitive, never a permanent credential.
_PUBLIC_ADDRESS_TOKEN_TTL_HOURS = 1


def _anonymous_refusal() -> HTTPException:
    """Single anonymous refusal — unknown/archived/hidden/deleted/retired
    are indistinguishable (S-15)."""
    return HTTPException(status_code=404, detail=_REFUSAL_DETAIL)


def _load_active_address(
    db: Session, profile_id: int
) -> QueueDirectionPublicAddress | None:
    """The one active (retired_at IS NULL) registry row of the profile."""
    return (
        db.query(QueueDirectionPublicAddress)
        .filter(
            QueueDirectionPublicAddress.queue_profile_id == profile_id,
            QueueDirectionPublicAddress.retired_at.is_(None),
        )
        .first()
    )


@router.get(
    "/directions/{profile_key}/entry-methods",
    response_model=DirectionEntryMethodsResponse,
    summary="Поддерживаемые способы QR-входа направления (RQ-16.b/RQ-16.d)",
)
def get_direction_entry_methods(
    profile_key: str,
    db: Session = Depends(get_db),
) -> DirectionEntryMethodsResponse:
    """Read-only contract surface: explicitly enumerate the QR-entry
    methods the server supports for the direction addressed by its
    QR-visible profile key. ``permanent_address`` is dynamic per
    direction since RQ-16.d (E-055 §8)."""
    from app.models.queue_profile import QueueProfile

    normalized = QueueBusinessService._normalize_qr_specialty_key(profile_key)
    if not normalized:
        raise _anonymous_refusal()

    profile = (
        db.query(QueueProfile).filter(QueueProfile.key == normalized).first()
    )
    if profile is None or not QueueBusinessService._is_qr_visible_profile(profile):
        raise _anonymous_refusal()

    # RQ-16.d (E-055 §8): honest per-direction flag — provisioned active
    # address AND canonical eligibility/resolution allows booking. A
    # direction without a provisioned address never claims support (no
    # backfill, E-055 §3).
    permanent_supported = _load_active_address(db, profile.id) is not None and (
        queue_service.direction_resolves_to_bookable_surface(db, profile)
    )

    return DirectionEntryMethodsResponse(
        direction_key=normalized,
        profile_id=profile.id,
        title=profile.title_ru or profile.title or normalized,
        entry_methods=[
            DirectionEntryMethodSupport(method=method, supported=supported)
            for method, supported in (
                (DirectionEntryMethod.SESSION_QR, True),
                (DirectionEntryMethod.PERMANENT_ADDRESS, permanent_supported),
                (DirectionEntryMethod.VIEW_ONLY, True),
            )
        ],
    )


@router.post(
    "/admin/directions/{profile_key}/public-address/provision",
    response_model=PublicAddressProvisionResponse,
    summary="Provision постоянного публичного адреса направления (RQ-16.d)",
    responses={
        400: {"description": "Зарезервированный ключ направления или исчерпаны попытки генерации"},
        401: {"description": "Требуется аутентификация"},
        403: {"description": "Только роль Admin"},
        404: {"description": "Направление не найдено"},
    },
)
def provision_public_address(
    profile_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> PublicAddressProvisionResponse:
    """Admin provision/enable of the permanent public address (E-055 §3):
    the server generates the opaque code ONCE and persists it forever.
    Idempotent — a re-provision returns the SAME address (created=False);
    archive/reactivate cycles never regenerate (E-055 §7). Manual address
    editing and rotation are out of scope (E-055 §6)."""
    from app.models.queue_profile import QueueProfile

    normalized = QueueBusinessService._normalize_qr_specialty_key(profile_key)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Направление не найдено"
        )
    if normalized in QueueBusinessService.PUBLIC_ADDRESS_FORBIDDEN_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Ключ зарезервирован для общего QR клиники и не может быть "
                "публичным адресом направления"
            ),
        )

    profile = (
        db.query(QueueProfile).filter(QueueProfile.key == normalized).first()
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Направление не найдено"
        )

    try:
        row, created = queue_service.provision_public_address(db, profile=profile)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    provisioned_at: str | None = None
    if isinstance(row.created_at, datetime):
        provisioned_at = row.created_at.isoformat()
    return PublicAddressProvisionResponse(
        profile_id=profile.id,
        direction_key=profile.key,
        public_code=row.public_code,
        url_path=f"/q/{row.public_code}",
        created=created,
        provisioned_at=provisioned_at,
    )


def _direction_selectable_specialists(
    profile, selectable: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Narrow the clinic-wide selection to THIS direction's eligible
    owners (consumed from the RQ-09 selection SSOT — no new eligibility
    rule is invented here)."""
    if not selectable:
        return []
    keys = set()
    normalized_key = QueueBusinessService._normalize_qr_specialty_key(profile.key)
    if normalized_key:
        keys.add(normalized_key)
    for tag in profile.queue_tags or []:
        normalized_tag = QueueBusinessService._normalize_qr_specialty_key(tag)
        if normalized_tag:
            keys.add(normalized_tag)
    return [card for card in selectable if card.get("specialty") in keys]


@router.post(
    "/public/{public_code}/start-session",
    response_model=PublicDirectionStartResponse,
    summary=(
        "Начало короткоживущей сессии по постоянному адресу направления "
        "(RQ-16.d, анонимный путь)"
    ),
    responses={
        400: {"description": "Честный отказ существующего сессионного контракта (окно записи и т.п.)"},
        404: {
            "description": (
                "Анонимный отказ (S-15): направление недоступно — "
                "unknown/archived/hidden/deleted/retired неразличимы"
            ),
            "content": {
                "application/json": {"example": {"detail": _REFUSAL_DETAIL}}
            },
        },
        429: {"description": "Rate limit превышен (анонимный путь)"},
    },
)
@limiter.limit(RATE_LIMITS["public_direction_start"])
def start_public_direction_session(
    request: Request,
    public_code: str,
    db: Session = Depends(get_db),
) -> PublicDirectionStartResponse:
    """ONE canonical anonymous resolve/start operation (E-055 §9):

    public_code -> registry -> QueueProfile -> visibility/eligibility ->
    anonymous rate limit -> short-lived session -> the existing
    QueueJoin session flow. No second join mechanism: every rule stays
    in the canonical resolver, and the minted direction-scoped token is
    bound to THIS direction for the session's whole short life.
    """
    code = normalize_public_code(public_code)
    if len(code) != 12:
        raise _anonymous_refusal()

    address = (
        db.query(QueueDirectionPublicAddress)
        .filter(
            QueueDirectionPublicAddress.public_code == code,
            QueueDirectionPublicAddress.retired_at.is_(None),
        )
        .first()
    )
    if address is None:
        raise _anonymous_refusal()

    profile = address.queue_profile
    if profile is None or not QueueBusinessService._is_qr_visible_profile(profile):
        # Tombstoned (hard-deleted), archived or hidden directions refuse
        # with the SAME anonymous response (S-15).
        raise _anonymous_refusal()

    if not queue_service.direction_resolves_to_bookable_surface(db, profile):
        # Fail-closed: a direction that resolves to NO bookable owner is a
        # dead entry — «мёртвых» поверхностей не появляется.
        raise _anonymous_refusal()

    # Mint the direction-scoped short-lived token (uncommitted): the
    # reserved-prefixed department carries the direction key so the join
    # path can enforce the session scope (legacy tokens never carry the
    # prefix). TTL is bounded by the shared RQ-11 contract.
    try:
        token_value, _token_meta = queue_service.assign_queue_token(
            db,
            specialist_id=None,
            department=(
                f"{QueueBusinessService.PUBLIC_ADDRESS_DEPARTMENT_PREFIX}"
                f"{profile.key}"
            ),
            generated_by_user_id=None,
            expires_hours=_PUBLIC_ADDRESS_TOKEN_TTL_HOURS,
            is_clinic_wide=True,
            commit=False,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    # The EXISTING session creation (15-minute QueueJoinSession, time
    # restrictions, TTL checks — all inherited unchanged).
    service = QRQueueService(db)
    try:
        result = service.start_join_session(
            token=token_value,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    info = dict(result.get("queue_info") or {})
    # The minted token is NOT a second credential — the session_token
    # drives the existing flow.
    info.pop("token", None)
    info["selectable_specialists"] = _direction_selectable_specialists(
        profile, info.get("selectable_specialists")
    )

    # RQ-18 follow-up (owner round-1 P1-1): the shared token-info builder
    # runs the clinic-wide branch for the minted is_clinic_wide token and
    # emits the CLINIC SENTINEL display fields («Клиника» /
    # «Все специалисты» / queue_length 0). A direction session must
    # present the DIRECTION the patient is joining — the routing decision
    # itself stays untouched in the join path. Live queue statistics are
    # deliberately NOT synthesized here: resolving the exact (tag, day)
    # surface at start time would duplicate the join-path routing
    # resolution (drift hazard); the real numbers arrive with the
    # join-time result (entries[].queue_length / estimated_wait_time).
    _direction_title = profile.title_ru or profile.title or profile.key
    info["department_name"] = _direction_title
    info["specialist_name"] = None
    info["queue_length"] = None

    return PublicDirectionStartResponse(
        session_token=result["session_token"],
        expires_at=result["expires_at"],
        permanent_address=True,
        direction=PublicDirectionAddressInfo(
            profile_id=profile.id,
            key=profile.key,
            title=profile.title_ru or profile.title or profile.key,
            public_code=address.public_code,
        ),
        queue_info=info,
    )
