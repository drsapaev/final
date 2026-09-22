"""Corrective follow-up (owner verdict on merged #3355 + #3358 runtime):
service_executions routing snapshot — the immutable execution-to-station
binding (P1: active executions must not become unfinishable when the
Service catalog is re-tagged mid-flight).

Columns (all NULLABLE, additive-only):
- queue_resource_id — the station (QueueResource.id) the attempt's D3
  gate passed for at start. A plain value, NOT a live FK: the snapshot
  is a historical fact, and a registry-row deletion must not orphan or
  block execution history (audit outranks the registry row — the same
  rationale 0072 applied to visit_service_id is NOT repeated here
  deliberately: NO ACTION would forbid deleting a station with history,
  plain value keeps the deletion legal while the history stays);
- routing_queue_tag_snapshot — resource.queue_tag captured at start
  (audit axis; pairs with queue_resource_id as the station identity
  proof);
- routing_service_id — the visit_service.service_id the attempt was
  validated for (binds the routing proof to the exact billed line; a
  hand-repointed execution.visit_service_id no longer matches and the
  terminal path fails closed — the codex round-1 cross-station guard
  survives the catalog-mutation immunity).

BACKFILL (owner verdict round-2 P2 on PR #3367): every IN_PROGRESS row
existing at upgrade time gets its snapshot reconstructed from the same
chain the runtime uses (``_execution_station_resource``) — entry ->
queue -> the queue's owner resource, else the registry row for the
queue's tag (lowest id) — and the visit_service's service line. The
reconstruction is DELIBERATELY corroborated by the CURRENT catalog
before it is written: only rows whose resolved station's tag still
equals the service's queue_tag and whose line still requires no doctor
are backfilled. A blanket backfill would silently authorize rows the
legacy D3 re-check refuses today (hand-applied cross-station rows, or
rows a pre-upgrade re-tag already stranded) — no widening of
authorization is acceptable in an upgrade. Rows that stay NULL keep the
exact pre-0073 legacy current-catalog D3 re-check on their terminal
paths.

Rollout discipline (the residual rolling-deployment window): the
backfill covers rows existing at upgrade time only. Rows written by
pre-upgrade workers AFTER the upgrade (a rolling deployment) are born
NULL; catalog re-tags therefore stay frozen until the old version is
fully replaced and the born-NULL attempts have drained (the formal
rollout barrier — enforcement lives on the catalog surface, outside
this PR's scope, documented in the model docstring).

No index: every snapshot consumer resolves by the service_executions
PRIMARY KEY or an already-batched IN-load.

SAFETY: additive-only DDL (three new nullable columns) + a guarded
UPDATE scoped to status = 'in_progress' AND NULL snapshots (no terminal
row is rewritten). Production/staging application is NOT part of this
change; merging the PR does not authorize running it against a live
database (separate release GO per the NURSE-V2 migration discipline).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0073_execution_routing_snapshot"
down_revision = "0072_service_executions"
branch_labels = None
depends_on = None


# The in_progress lifecycle is minutes-hours, so the candidate set at
# upgrade time is a handful of rows: per-row resolution (3 small queries
# max per row) mirrors the runtime chain resolution line-by-line and
# stays dialect-portable, at the cost nobody pays twice.
_CANDIDATE_ROWS_SQL = sa.text(
    "SELECT se.id AS execution_id, "
    "       se.queue_entry_id AS entry_id, "
    "       se.visit_service_id AS visit_service_id "
    "FROM service_executions se "
    "WHERE se.status = 'in_progress' "
    "  AND se.queue_resource_id IS NULL "
    "  AND se.routing_queue_tag_snapshot IS NULL "
    "  AND se.routing_service_id IS NULL"
)

_QUEUE_AXIS_SQL = sa.text(
    "SELECT q.queue_resource_id AS owner_resource_id, "
    "       q.queue_tag AS queue_tag "
    "FROM queue_entries e "
    "JOIN daily_queues q ON q.id = e.queue_id "
    "WHERE e.id = :entry_id"
)

_RESOURCE_BY_ID_SQL = sa.text(
    "SELECT r.id AS resource_id, r.queue_tag AS resource_tag "
    "FROM queue_resources r WHERE r.id = :resource_id"
)

# Mirrors the runtime tag-axis fallback (``_execution_station_resource``):
# the registry row for the exact tag, lowest id for determinism.
_RESOURCE_BY_TAG_SQL = sa.text(
    "SELECT r.id AS resource_id, r.queue_tag AS resource_tag "
    "FROM queue_resources r "
    "WHERE r.queue_tag = :queue_tag "
    "ORDER BY r.id ASC "
    "LIMIT 1"
)

_SERVICE_LINE_SQL = sa.text(
    "SELECT s.id AS service_id, s.queue_tag AS service_tag, "
    "       s.requires_doctor AS requires_doctor "
    "FROM visit_services vs "
    "JOIN services s ON s.id = vs.service_id "
    "WHERE vs.id = :visit_service_id"
)

_BACKFILL_ROW_SQL = sa.text(
    "UPDATE service_executions "
    "SET queue_resource_id = :resource_id, "
    "    routing_queue_tag_snapshot = :resource_tag, "
    "    routing_service_id = :service_id "
    "WHERE id = :execution_id"
)


def _resolve_row(bind, execution_id: int, entry_id, visit_service_id) -> bool:
    """Reconstruct + corroborate one row's snapshot. True when written."""
    resource_id = resource_tag = service_id = None
    if entry_id is not None:
        queue_axis = bind.execute(_QUEUE_AXIS_SQL, {"entry_id": entry_id}).first()
        if queue_axis is not None:
            owner_resource_id, queue_tag = queue_axis
            resource_row = None
            if owner_resource_id is not None:
                resource_row = bind.execute(
                    _RESOURCE_BY_ID_SQL, {"resource_id": owner_resource_id}
                ).first()
            elif queue_tag is not None:
                resource_row = bind.execute(
                    _RESOURCE_BY_TAG_SQL, {"queue_tag": queue_tag}
                ).first()
            if resource_row is not None:
                resource_id, resource_tag = resource_row
    if visit_service_id is not None:
        line = bind.execute(
            _SERVICE_LINE_SQL, {"visit_service_id": visit_service_id}
        ).first()
        if line is not None:
            service_id, service_tag, requires_doctor = line
            # The D3 corroboration: the snapshot is only written when the
            # CURRENT catalog still proves the routing the legacy re-check
            # would demand (queue_tag match + requires_doctor=false).
            # Everything else keeps the legacy path — identical refusal,
            # zero widened authorization.
            if (
                resource_id is not None
                and service_tag == resource_tag
                and not bool(requires_doctor)
            ):
                bind.execute(
                    _BACKFILL_ROW_SQL,
                    {
                        "resource_id": resource_id,
                        "resource_tag": resource_tag,
                        "service_id": service_id,
                        "execution_id": execution_id,
                    },
                )
                return True
    return False


def upgrade() -> None:
    op.add_column(
        "service_executions",
        sa.Column("queue_resource_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "service_executions",
        sa.Column("routing_queue_tag_snapshot", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "service_executions",
        sa.Column("routing_service_id", sa.Integer(), nullable=True),
    )
    _backfill_in_progress_snapshots()


def _backfill_in_progress_snapshots() -> None:
    """The owner-verdict P2 backfill (see the module docstring)."""
    bind = op.get_bind()
    candidates = bind.execute(_CANDIDATE_ROWS_SQL).fetchall()
    for execution_id, entry_id, visit_service_id in candidates:
        _resolve_row(bind, execution_id, entry_id, visit_service_id)


def downgrade() -> None:
    op.drop_column("service_executions", "routing_service_id")
    op.drop_column("service_executions", "routing_queue_tag_snapshot")
    op.drop_column("service_executions", "queue_resource_id")
