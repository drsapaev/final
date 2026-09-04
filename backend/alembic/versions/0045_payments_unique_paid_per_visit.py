"""H-4 fix: NO-OP migration. Row-level lock is used instead of a unique index.

Launch Blockers Audit fix H-4: prevent double-payment race condition.

DESIGN DECISION (revised after code investigation)
--------------------------------------------------
The original version of this migration created a partial UNIQUE INDEX:

    CREATE UNIQUE INDEX uq_payments_one_paid_per_visit
    ON payments (visit_id)
    WHERE status IN ('paid', 'completed')

Investigation of the actual cashier flow revealed that this index
would **break legitimate partial-payment workflows**:

1. ``_cashier_paid_amounts_by_visit_id`` (``cashier/_helpers.py``)
   explicitly **sums** all ``paid``/``completed`` payments per visit.
   This function only makes sense if multiple payments per visit are
   expected.

2. ``create_payment`` (``cashier/_payments.py:665``) computes
   ``remaining_debt = total_cost - paid_amount`` and only rejects
   when ``remaining_debt <= 0 AND payment_amount > 0`` (i.e. the
   visit is already fully paid). This is the partial-payment
   contract: a patient can pay 5000 of 10000, then return later
   to pay the remaining 5000.

3. The overpayment check (``cashier/_payments.py:685``) explicitly
   allows ``payment_amount > remaining_debt`` as an "advance /
   deposit" scenario, logging a WARNING for audit.

A unique index on ``visit_id`` alone would reject the second
5000 payment with IntegrityError, breaking the partial-payment
contract and the advance-payment feature.

CORRECT FIX
-----------
Instead of a DB-level unique constraint, the race condition is
closed by acquiring a **row-level lock** on the visit row at the
start of ``create_payment``:

    visit = (
        db.query(Visit)
        .filter(Visit.id == payment_data.visit_id)
        .with_for_update()
        .first()
    )

This serializes concurrent payment attempts on the same visit:
- Request A acquires the lock, reads ``paid_amount = 0``,
  creates the payment, commits.
- Request B blocks on the lock until A commits, then reads
  ``paid_amount = 10000``, the application-level check fires,
  and B gets HTTP 400 ``"Все услуги уже оплачены"``.

This pattern is already used elsewhere in the codebase:
- ``billing_service_pkg/_payments.py:412`` uses ``with_for_update()``
  on the Payment row for status updates.
- ``repositories/provider_webhook_repository.py:61-117`` uses
  ``with_for_update()`` on Payment rows for webhook processing.

WHY KEEP THE MIGRATION FILE?
----------------------------
This file is kept as a **no-op** (upgrade and downgrade do nothing)
for two reasons:

1. **Audit trail.** Anyone running ``alembic upgrade head`` against
   a database that previously had the bad version of this migration
   (revision ``0045_payments_unique_paid_per_visit``) will see the
   revision in the history and can read this docstring to understand
   why no index was created.

2. **Rollback safety.** If the bad version was already applied to a
   database, the downgrade of THIS version is a no-op, but the
   downgrade of the PREVIOUS version (which created the index) will
   correctly drop it. The previous version's downgrade is preserved
   in git history.

If the bad index was already applied to a production database,
run this SQL manually to drop it before upgrading:

    DROP INDEX IF EXISTS uq_payments_one_paid_per_visit;

Then run ``alembic upgrade head`` to mark this revision as applied.

The actual code fix (``with_for_update()`` on the visit query) is
in ``app/api/v1/endpoints/cashier/_payments.py``.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0044_audit_logs.
revision = "0045_payments_lock"
down_revision = "0044_audit_logs"
branch_labels = None
depends_on = None

# Index name from the original (revised) version of this migration.
# Kept here so operators can drop it manually if the bad version was
# already applied. See module docstring for details.
LEGACY_INDEX_NAME = "uq_payments_one_paid_per_visit"


def upgrade() -> None:
    # Defensive cleanup: if a previous version of this migration
    # created the index, drop it now. This is a no-op on databases
    # that never had the index.
    #
    # We use op.execute() with IF EXISTS so this is safe to run on
    # any database state. PostgreSQL supports DROP INDEX IF EXISTS.
    op.execute(sa.text(f"DROP INDEX IF EXISTS {LEGACY_INDEX_NAME}"))


def downgrade() -> None:
    # No-op: we never want to recreate the bad index.
    # If you need to restore the index (e.g. for testing the original
    # H-4 design), see the git history of this file for the original
    # CREATE UNIQUE INDEX statement.
    pass
