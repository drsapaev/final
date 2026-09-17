"""RQ-16.b — direction QR-entry methods (contract/API slice).

DIRECTION_CONTRACT.md §6.2 (derived from D-01/D-03 APPROVED, E-039):
the server EXPLICITLY enumerates the supported QR-entry methods of a
direction — session QR (the short-lived protected session path,
join/start -> join/complete; printed QR stays short-lived, RQ-11 TTL
honesty), permanent address (NOT supported until RQ-16.c/.d — the slug
model and the address FORM are the OPEN POINT awaiting the owner, so the
server reports it as explicitly unsupported instead of omitting it) and
view-only overview (D-01 §4: an overview never creates its own
numbering). Clients must read this surface, never guess.

Refusal rules (S-15): an archived (is_active=False), hidden
(show_on_qr_page=False) or unknown key returns 404 with the SAME
anonymous detail — archived directions block new joins and must not leak
existence. Fail-closed: no INITIAL_QUEUE_PROFILES fallback fabricates
directions here (contrast: /queues/profiles/public keeps its legacy
fallbacks) — a fabricated direction would invite clients to build entry
paths that do not exist.

§6.1: visibility/normalization semantics are CONSUMED from the queue_svc
resolver helpers (``_normalize_qr_specialty_key`` / ``_is_qr_visible_profile``
— the same classmethods the RQ-14.b canonical resolver and the join path
use); no rule is duplicated here. The canonical queue tag / owner
resolution itself stays in the RQ-14.b resolver — this surface only
reports the methods space.

Read-only: no schema changes, no behavior change to any existing
surface. Explicit star-import lesson (47): the queue_svc class is
imported by name, so underscore classmethods are reachable.
"""

from __future__ import annotations

from enum import Enum

from fastapi import HTTPException

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import (
    BaseModel,
    Depends,
    Field,
    Session,
    get_db,
    router,
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


_REFUSAL_DETAIL = "Направление недоступно"

# Slice-honest support flags (DIRECTION_CONTRACT.md §6.2/§6.3, E-052):
# session QR is the supported protected path; the permanent address flips
# per-direction only when RQ-16.c/.d land the slug model; the overview is
# always available without booking and never creates numbering (D-01 §4).
_METHOD_SUPPORT: tuple[tuple[DirectionEntryMethod, bool], ...] = (
    (DirectionEntryMethod.SESSION_QR, True),
    (DirectionEntryMethod.PERMANENT_ADDRESS, False),
    (DirectionEntryMethod.VIEW_ONLY, True),
)


def _anonymous_refusal() -> HTTPException:
    """Single anonymous refusal — unknown/archived/hidden are indistinguishable (S-15)."""
    return HTTPException(status_code=404, detail=_REFUSAL_DETAIL)


@router.get(
    "/directions/{profile_key}/entry-methods",
    response_model=DirectionEntryMethodsResponse,
    summary="Поддерживаемые способы QR-входа направления (RQ-16.b)",
)
def get_direction_entry_methods(
    profile_key: str,
    db: Session = Depends(get_db),
) -> DirectionEntryMethodsResponse:
    """Read-only contract surface: explicitly enumerate the QR-entry
    methods the server supports for the direction addressed by its
    QR-visible profile key."""
    from app.models.queue_profile import QueueProfile

    normalized = QueueBusinessService._normalize_qr_specialty_key(profile_key)
    if not normalized:
        raise _anonymous_refusal()

    profile = (
        db.query(QueueProfile).filter(QueueProfile.key == normalized).first()
    )
    if profile is None or not QueueBusinessService._is_qr_visible_profile(profile):
        raise _anonymous_refusal()

    return DirectionEntryMethodsResponse(
        direction_key=normalized,
        profile_id=profile.id,
        title=profile.title_ru or profile.title or normalized,
        entry_methods=[
            DirectionEntryMethodSupport(method=method, supported=supported)
            for method, supported in _METHOD_SUPPORT
        ],
    )
