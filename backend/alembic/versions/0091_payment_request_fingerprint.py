"""RETRO-FIN-001 (retrospective audit of merged fix PRs #3803–#3919).

``_replay_payment_client_request`` searched only by
``client_request_id`` + ``endpoint``: a key REUSED with a different
payment intent (different visit, patient, amount or method) replayed the
ORIGINAL operation's stored success (HTTP 200) without charging the new
intent — an apparent payment success unrelated to the submitted request
(and without a request-owner check on the replay path).

Schema anchor introduced here:

* ``payment_client_requests.request_fingerprint`` — nullable String(64),
  SHA-256 of the canonical intent fingerprint (endpoint + patient/visit
  allocation + amount + method) computed server-side on every keyed
  create. The replay path compares it BEFORE replaying: a mismatched key
  is rejected with 409 (``client_request_id_intent_mismatch``) without
  charging; byte-equivalent duplicates keep the winner-replay contract
  of issue 3859. NULL on historical anchors — their replay stays
  key+endpoint-scoped exactly as before (additive, back-compatible).

RLS is enabled per the public-schema guardrail (2026-09-02 Supabase
incident; enforced by ops/scripts/check_public_rls.py in CI).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0091_payment_request_fingerprint"
down_revision = "0090_payment_client_request"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_client_requests",
        sa.Column(
            "request_fingerprint",
            sa.String(length=64),
            nullable=True,
            comment=(
                "RETRO-FIN-001: SHA-256 канонического fingerprint intent'а "
                "(эндпоинт + пациент/визиты + сумма + метод); реплей ключа с "
                "другим intent отклоняется 409"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("payment_client_requests", "request_fingerprint")
