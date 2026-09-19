"""A+ stage 1 — lab_results lineage columns for the managed projection.

Owner decision C → A+ (recorded verbatim in
.ai-factory/plans/lab-results-lineage-decision.md):

- ``source_root_instance_id`` — stable identity of the blank revision
  chain (the root blank id; ``revise()`` chains via
  ``lab_report_instances.supersedes_instance_id``);
- ``source_instance_id`` — the concrete finalized version that produced
  the current value.

Managed projection key: ``(source_root_instance_id, test_code)`` —
NOT ``(order_id, test_code)`` (the #3235 overwrite defect) and NOT
``(source_instance_id, test_code)`` (each revision gets a new instance
id, so that key would create one legacy row per revision instead of
updating the chain's current projection).

Constraints per the contract:
- both columns are nullable FKs to ``lab_report_instances.id`` with NO
  cascade: deleting a source blank must never cascade-delete projection
  rows (RESTRICT — blanks are corrected via revise(), never deleted);
- historical rows keep NULL in both columns — this migration performs
  NO backfill and NO heuristic attribution (order_id + test_code
  matching is the exact mistake that caused the #3235 P1);
- uniqueness of ``(source_root_instance_id, test_code)`` applies ONLY to
  managed rows (partial unique index ``WHERE source_root_instance_id IS
  NOT NULL AND test_code IS NOT NULL``); rows without lineage are never
  restricted by the new key;
- source/root values are assigned by the server only (A+ runtime PR);
  nothing here exposes them to clients.

SAFETY: additive-only DDL (two nullable columns, two FKs, two indexes);
no existing row is modified, no row is deleted or merged. Production/
staging application is NOT part of this change: merging the PR does not
authorize running this migration against a live database.

RLS: lab_results is an EXISTING table whose RLS was enabled by 0046;
additive columns do not change the RLS state. The migration test asserts
``relrowsecurity`` stays enabled after the upgrade.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0070_lab_results_lineage"
down_revision = "0069_sentinel_pair_retirement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lab_results",
        sa.Column("source_root_instance_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lab_results",
        sa.Column("source_instance_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_lab_results_source_root_instance",
        "lab_results",
        "lab_report_instances",
        ["source_root_instance_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_lab_results_source_instance",
        "lab_results",
        "lab_report_instances",
        ["source_instance_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_lab_results_lineage_root_code",
        "lab_results",
        ["source_root_instance_id", "test_code"],
        unique=True,
        postgresql_where=sa.text(
            "source_root_instance_id IS NOT NULL AND test_code IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_lab_results_source_instance_id",
        "lab_results",
        ["source_instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lab_results_source_instance_id", table_name="lab_results")
    op.drop_index("uq_lab_results_lineage_root_code", table_name="lab_results")
    op.drop_constraint(
        "fk_lab_results_source_instance", "lab_results", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_lab_results_source_root_instance", "lab_results", type_="foreignkey"
    )
    op.drop_column("lab_results", "source_instance_id")
    op.drop_column("lab_results", "source_root_instance_id")
