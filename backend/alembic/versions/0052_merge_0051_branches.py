"""Merge the two 0051 branches into a single head.

Parallel PRs landed two revisions chained after 0050_enable_rls_sweep:
- 0051_salary_tables_adoption (#3008, main)
- 0051_medical_specialty_catalog (#3010, this branch)

Neither applied revision is edited (guardrail); this empty merge revision
declares both as parents so `alembic upgrade head` is unambiguous again.
"""

revision = "0052_merge_0051_branches"
down_revision = ("0051_salary_tables_adoption", "0051_medical_specialty_catalog")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
