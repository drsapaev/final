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

import sqlalchemy as sa
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


def lock_registry_tag_creation(db: Session, queue_tag: str, day: date) -> None:
    """Serialize the first creation of a registry-tag queue (QD-2C).

    query-then-insert with no unique constraint until QD-2D: two
    concurrent first-arrival writers (batch create, visit
    confirmation, GQL joinQueue) could both observe no active
    (day, tag) queue and insert two resource queues, splitting
    patients across the tag's routing surface. The PostgreSQL
    advisory transaction lock (same key the GQL joinQueue mutation
    takes: ``daily_queue:tag:{tag}:{day}``) serializes the
    check-then-insert window; SQLite (tests) has no advisory locks
    and skips — the sequential no-duplicate pins cover that path.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
            {"k": f"daily_queue:tag:{queue_tag}:{day.isoformat()}"},
        )


def resource_start_number(db: Session, daily_queue: DailyQueue) -> int | None:
    """The registry row's start_number_online for a resource queue.

    QD-2C numbering SSOT: a resource-owned (or bridged) queue floors
    its ticket sequence at ``QueueResource.start_number_online`` (the
    LIVE synthetic values 0059 transferred). ``None`` for doctor
    queues — the caller keeps its doctor/settings floor.
    """
    if not daily_queue.queue_resource_id:
        return None
    resource = db.get(QueueResource, daily_queue.queue_resource_id)
    if resource is None or not resource.start_number_online:
        return None
    return int(resource.start_number_online)


def resolve_registry_tag_queue_for_specialist(
    db: Session, day: date, specialist_id: int | None, queue_tag: str | None
) -> DailyQueue | None:
    """Resource-axis fallback for the STAFF queue identity (QD-2C).

    The staff command surfaces (REST ``POST /qr_queue/{specialist_id}/
    call-next``, GQL ``callNextPatient``, ``staff_call_next_patient``)
    address a queue by the DOCTOR id. A registry tag's queue may be
    resource-owned (specialist NULL) — created by the morning
    pre-create or any post-switch writer — and the doctor-keyed
    lookup finds nothing. The legacy identity still names the tag:
    the synthetic Doctor's specialty (or the explicit queue_tag) IS
    the routing tag, and when that tag has an active registry row the
    (day, tag) queue is the one routing surface (ADR-001 stage C).

    Returns the tag queue only when the tag is registry-backed;
    doctor-tag lookups keep the per-doctor PR-26 contract untouched.
    """
    tag = queue_tag
    if tag is None and specialist_id is not None:
        from app.models.clinic import Doctor

        doctor = db.get(Doctor, specialist_id)
        if doctor is None:
            return None
        tag = doctor.specialty
    if not tag:
        return None
    # Codex round-3 P1: deactivation-proof — an existing resource-owned
    # queue stays the surface even if the registry row was deactivated
    return tag_routes_to_resource(db, tag, day)


def tag_routes_to_resource(db: Session, queue_tag: str, day: date) -> DailyQueue | None:
    """The (day, tag) routing surface — deactivation-proof (QD-2C,
    Codex round-3 P1).

    An operator deactivating a registry row mid-day must not make the
    day's routing surface vanish: patients already waiting on the
    resource-owned queue would disappear from every specialist-keyed
    surface while new arrivals fork a parallel legacy queue. The rule:

    - an existing ACTIVE queue for (day, tag) that carries
      ``queue_resource_id`` IS the surface regardless of the registry
      flag (the resource axis stays routable until the queue closes);
    - otherwise an ACTIVE registry row makes the (day, tag) queue the
      surface whatever its owner (the stage-C switch);
    - otherwise the tag is legacy doctor routing (None) — a
      deactivated tag without a live resource queue creates nothing
      on the resource axis.

    Returns the queue (or None); creation of NEW resource queues is
    the caller's decision and still requires the ACTIVE registry row
    (``resolve_tag_resource``).
    """
    queue = find_active_tag_queue(db, day, queue_tag)
    if queue is not None and queue.queue_resource_id is not None:
        return queue
    if resolve_tag_resource(db, queue_tag) is None:
        return None
    return queue
