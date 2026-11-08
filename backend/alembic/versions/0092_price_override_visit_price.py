"""DERMAPRICE-BE-002 (audit #3892, group 15) — truthful price reference.

``original_price`` on ``doctor_price_overrides`` records the CATALOGUE
price (``Service.price``), not the visit's actual ``VisitService.price``
which may differ after discounts/overrides. The registrar's pending-review
payload computed ``price_difference`` from the catalogue reference, so the
reviewer could not see the change relative to what the visit is actually
billed at.

Schema anchor introduced here:

* ``doctor_price_overrides.visit_price_before`` — nullable Numeric(12,2),
  captured server-side at creation time from the visit-service row (the
  DERMAPRICE-BE-001 membership guard guarantees the row exists).
  ``original_price`` KEEPS its immutable catalogue-reference semantics
  (audit: «do not silently redefine existing audit semantics»); the new
  field is additive truth for financial decision-making. NULL on
  historical rows — populated only by new override requests.

RLS is enabled per the public-schema guardrail (2026-09-02 Supabase
incident; enforced by ops/scripts/check_public_rls.py in CI).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0092_price_override_visit_price"
down_revision = "0091_payment_request_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "doctor_price_overrides",
        sa.Column(
            "visit_price_before",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment=(
                "DERMAPRICE-BE-002: цена VisitService на момент создания "
                "запроса (дополнительная к каталожной original_price)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("doctor_price_overrides", "visit_price_before")
