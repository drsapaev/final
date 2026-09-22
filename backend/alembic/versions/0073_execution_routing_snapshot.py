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

NO backfill: rows written before this migration keep NULL snapshots and
their terminal paths keep the legacy CURRENT-catalog D3 re-check
(transitional window — the execution lifecycle is minutes-hours, the
migration applies at rest; documented in the model docstring). No index:
every snapshot consumer resolves by the service_executions PRIMARY KEY
or an already-batched IN-load.

SAFETY: additive-only DDL (two/three new nullable columns, no existing
row touched, no data rewrite). Production/staging application is NOT
part of this change; merging the PR does not authorize running it
against a live database (separate release GO per the NURSE-V2 migration
discipline).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0073_execution_routing_snapshot"
down_revision = "0072_service_executions"
branch_labels = None
depends_on = None


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


def downgrade() -> None:
    op.drop_column("service_executions", "routing_service_id")
    op.drop_column("service_executions", "routing_queue_tag_snapshot")
    op.drop_column("service_executions", "queue_resource_id")
