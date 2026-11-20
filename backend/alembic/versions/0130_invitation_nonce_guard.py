"""Preserve one-time dispatch of an invitation across database transactions."""

from alembic import op

revision = "0130_invitation_nonce_guard"
down_revision = "0129_click_reconciliation"
branch_labels = None
depends_on = None


_POSTGRES_BODY = """
        BEGIN
          IF TG_OP='DELETE' THEN RAISE EXCEPTION 'invitation evidence is immutable'; END IF;
          IF ROW(NEW.visit_id_snapshot, NEW.patient_id_snapshot, NEW.owner_generation,
                 NEW.context_epoch, NEW.token_digest, NEW.channel, NEW.telegram_link_id,
                 NEW.telegram_link_epoch, NEW.issuer_actor_id, NEW.issuer_key_digest, NEW.issuer_fingerprint, NEW.created_at)
             IS DISTINCT FROM ROW(OLD.visit_id_snapshot, OLD.patient_id_snapshot, OLD.owner_generation,
                 OLD.context_epoch, OLD.token_digest, OLD.channel, OLD.telegram_link_id,
                 OLD.telegram_link_epoch, OLD.issuer_actor_id, OLD.issuer_key_digest, OLD.issuer_fingerprint, OLD.created_at)
             OR (NEW.visit_id IS DISTINCT FROM OLD.visit_id AND NEW.visit_id IS NOT NULL)
             OR (NEW.patient_id IS DISTINCT FROM OLD.patient_id AND NEW.patient_id IS NOT NULL)
             OR (NEW.state IS DISTINCT FROM OLD.state AND NOT
               ((OLD.state='pending' AND NEW.state IN ('unknown','sent','cancelled'))
                OR (OLD.state='unknown' AND NEW.state='sent'))){nonce_rules} THEN
            RAISE EXCEPTION 'invalid invitation transition';
          END IF;
          RETURN NEW;
        END
"""

# The worker and provisioning script check the exact PostgreSQL body.
_POSTGRES_NONCE_RULES = """
             OR (NEW.dispatch_nonce_digest IS DISTINCT FROM OLD.dispatch_nonce_digest AND NOT
               ((OLD.state='pending' AND NEW.state='unknown' AND OLD.dispatch_nonce_digest IS NULL AND NEW.dispatch_nonce_digest IS NOT NULL)
                OR (OLD.state='unknown' AND NEW.state='unknown' AND OLD.dispatch_nonce_digest IS NOT NULL AND NEW.dispatch_nonce_digest IS NULL)))
             OR (OLD.state='unknown' AND NEW.state='sent' AND OLD.dispatch_nonce_digest IS NOT NULL)"""


def _replace_postgres_guard(*, enforce_nonce: bool) -> None:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    qualified = context.dialect.identifier_preparer.quote_schema(schema)
    nonce_rules = _POSTGRES_NONCE_RULES if enforce_nonce else ""
    body = _POSTGRES_BODY.format(nonce_rules=nonce_rules)
    op.execute(f"""CREATE OR REPLACE FUNCTION {qualified}.protect_visit_invitation_delivery()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $invitation_guard${body}$invitation_guard$""")


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        _replace_postgres_guard(enforce_nonce=True)
    elif dialect == "sqlite":
        op.execute("""
        CREATE TRIGGER trg_protect_invitation_dispatch_nonce BEFORE UPDATE ON visit_invitation_deliveries
        WHEN (NEW.dispatch_nonce_digest IS NOT OLD.dispatch_nonce_digest AND NOT
               ((OLD.state='pending' AND NEW.state='unknown' AND OLD.dispatch_nonce_digest IS NULL AND NEW.dispatch_nonce_digest IS NOT NULL)
                OR (OLD.state='unknown' AND NEW.state='unknown' AND OLD.dispatch_nonce_digest IS NOT NULL AND NEW.dispatch_nonce_digest IS NULL)))
          OR (OLD.state='unknown' AND NEW.state='sent' AND OLD.dispatch_nonce_digest IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'invalid invitation transition'); END
        """)
    else:
        raise RuntimeError("Unsupported invitation delivery dialect")


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        _replace_postgres_guard(enforce_nonce=False)
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER trg_protect_invitation_dispatch_nonce")
    else:
        raise RuntimeError("Unsupported invitation delivery dialect")
