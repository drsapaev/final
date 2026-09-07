"""QD-2C runtime switch: resource-axis routing for doctorless tags.

CRUD layer (pure model lookups): safe to import from services,
repositories and the crud layer itself — no context-boundary edge
(the routing policy itself lives in the callers; this module only
answers "which registry row / which tag queue").

Stage C of the QD-2 staged rollout (QueueResource architecture FINAL,
2026-09-07). Stages A (0058: registry + dual-owner columns) and B (0059:
lab/ecg seeds + backfill) landed; this module is the shared resolver the
runtime paths use to PREFER the resource axis for a doctorless tag.

The switch is deliberately CONDITIONAL on live registry data:

- ``resolve_tag_resource`` returns an ACTIVE ``queue_resources`` row for
  the EXACT tag only. No registry row (an empty test database, the CI
  ``alembic upgrade head`` chain, ``general``/``stomatology`` and every
  doctor specialty tag, alias spellings like ``laboratory``) → ``None``
  → every caller keeps its legacy synthetic-Doctor path byte-identical.
- ``find_active_tag_queue`` is the tag-first unification lookup: the
  queue for a registry tag is found by ``(day, queue_tag, active)``
  regardless of owner — this is what makes the dual-ownership bridge
  (specialist_id AND queue_resource_id both set, the 0059 backfill
  shape) and the post-switch resource-owned rows (specialist NULL) the
  SAME queue to every runtime path, instead of forking a parallel
  per-doctor queue like the pre-QD-2 code did.
- The registry is read via the ``QueueResource`` model (stage A); the
  tag match is exact — never prefix, never alias inference (the 0059
  seed-gate contract).

NOT in scope (later stages, per the ADR stage table): the XOR
uniqueness contract (QD-2D) and retiring the synthetic User+Doctor
pairs (QD-2E) — the legacy fallback paths here keep working until E.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, QueueResource


def resolve_tag_resource(db: Session, queue_tag: str | None) -> QueueResource | None:
    """Active registry row for the exact queue_tag, or None.

    The single gate of the QD-2C runtime switch: a tag routes onto the
    resource axis ONLY when the seeded registry proves it doctorless.
    Exact-tag match only — ``laboratory`` must NOT resolve the ``lab``
    resource (the 0059 alias-skip contract).
    """
    if not queue_tag:
        return None
    return (
        db.query(QueueResource)
        .filter(
            QueueResource.queue_tag == queue_tag,
            QueueResource.active.is_(True),
        )
        .order_by(QueueResource.id.asc())
        .first()
    )


def find_active_tag_queue(db: Session, day: date, queue_tag: str) -> DailyQueue | None:
    """The active queue for (day, queue_tag), whatever its owner.

    Tag-first unification: for a registry tag there is exactly one
    routing surface per day — a bridged row (both owners, written by
    the 0059 backfill or the morning pre-create), a resource-owned row
    (specialist NULL, written after the switch) or, on a not-yet-seeded
    installation, the legacy synthetic-owned row. Deterministic order
    (id) mirrors the 0059 backfill contract.
    """
    return (
        db.query(DailyQueue)
        .filter(
            DailyQueue.day == day,
            DailyQueue.queue_tag == queue_tag,
            DailyQueue.active.is_(True),
        )
        .order_by(DailyQueue.id.asc())
        .first()
    )


def resource_queue_defaults(resource: QueueResource) -> dict:
    """Creation defaults transferred from the registry row.

    Mirrors what the pre-QD-2 paths read from the synthetic Doctor
    (max_online_per_day) — the seed transferred the LIVE synthetic
    values in 0059, so the caps are the values production uses today.
    """
    return {
        "max_online_entries": resource.max_online_per_day,
    }
