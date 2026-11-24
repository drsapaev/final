"""Remove gateway UPDATE on financial identity and generation sequences."""

import sqlalchemy as sa

from alembic import op

revision = "0163_financial_seq_update_acl"
down_revision = "0162_confirmation_sequence_owner"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_GENERATION_SEQUENCE = "encounter_financial_generation_seq"
# Frozen relation inventory from 0154, 0159 and the catalogue audit in 0160.
_FINANCIAL_TABLES = (
    "audit_logs",
    "benefit_applications",
    "benefits",
    "billing_rules",
    "billing_settings",
    "click_callback_receipts",
    "click_issued_attempts",
    "click_prepares",
    "click_receipt_key_versions",
    "click_receipt_reconciliation_links",
    "click_reconciliation_reviews",
    "deposit_transactions",
    "discount_applications",
    "discount_services",
    "discounts",
    "doctor_price_hmac_key_versions",
    "doctor_price_intent_keys",
    "doctor_price_intent_lines",
    "doctor_price_intents",
    "doctor_price_overrides",
    "dynamic_prices",
    "encounter_benefit_allocations",
    "encounter_benefit_applications",
    "encounter_benefit_events",
    "encounter_benefit_quota_anchors",
    "encounter_benefit_visit_snapshots",
    "finance_transactions",
    "invoice_items",
    "invoice_templates",
    "invoices",
    "kaspi_issued_payment_refs",
    "loyalty_point_transactions",
    "loyalty_programs",
    "package_purchases",
    "package_services",
    "patient_benefits",
    "patient_deposits",
    "patient_loyalty",
    "payment_client_requests",
    "payment_invoice_visits",
    "payment_invoices",
    "payment_providers",
    "payment_refund_claims",
    "payment_reminders",
    "payment_transactions",
    "payment_visits",
    "payment_webhooks",
    "payments",
    "price_history",
    "pricing_rule_services",
    "pricing_rules",
    "provider_active_visit_reservations",
    "provider_attempt_visits",
    "provider_attempts",
    "provider_reconciliation_conflicts",
    "provider_reconciliation_events",
    "refund_requests",
    "service_audit_logs",
    "service_packages",
    "services",
    "user_audit_logs",
    "visit_invitation_price_approval_auth",
)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Financial sequence privileges require an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted financial sequence schema required")

    connection = op.get_bind()
    sequences = connection.execute(
        sa.text("""
            SELECT seq.oid, seq.relname
            FROM pg_catalog.pg_class seq
            JOIN pg_catalog.pg_namespace ns ON ns.oid = seq.relnamespace
            WHERE ns.nspname = :schema AND seq.relkind = 'S'
              AND (seq.relname = :generation_sequence OR EXISTS (
                  SELECT 1
                  FROM pg_catalog.pg_depend dep
                  JOIN pg_catalog.pg_class target ON target.oid = dep.refobjid
                  WHERE dep.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
                    AND dep.refclassid = 'pg_catalog.pg_class'::pg_catalog.regclass
                    AND dep.objid = seq.oid AND dep.objsubid = 0 AND dep.refobjsubid > 0
                    AND dep.deptype IN ('a', 'i')
                    AND target.relnamespace = ns.oid AND target.relkind IN ('r', 'p')
                    AND target.relname IN :tables
              ))
            ORDER BY seq.relname
        """).bindparams(sa.bindparam("tables", expanding=True)),
        {
            "schema": schema,
            "generation_sequence": _GENERATION_SEQUENCE,
            "tables": _FINANCIAL_TABLES,
        },
    ).all()
    if not sequences:
        raise RuntimeError("Reviewed financial sequences are required")

    roles = tuple(
        connection.scalars(
            sa.text("""
                SELECT rolname FROM pg_catalog.pg_roles
                WHERE rolname IN :roles ORDER BY rolname
            """).bindparams(sa.bindparam("roles", expanding=True)),
            {"roles": _GATEWAY_ROLES},
        )
    )
    preparer = context.dialect.identifier_preparer
    quoted_schema = preparer.quote_schema(schema)
    sequences_sql = ", ".join(
        f"{quoted_schema}.{preparer.quote_identifier(name)}" for _, name in sequences
    )
    grantees = ", ".join(("PUBLIC", *map(preparer.quote_identifier, roles)))
    # UPDATE permits setval. USAGE continues to support ordinary nextval calls.
    op.execute(f"REVOKE UPDATE ON SEQUENCE {sequences_sql} FROM {grantees} RESTRICT")

    activation = "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    protected = connection.scalar(
        sa.text("""
            WITH targets AS (
                SELECT oid, relowner, relacl FROM pg_catalog.pg_class
                WHERE oid IN :sequences
            ), gateway_access AS (
                SELECT DISTINCT reachable.oid
                FROM pg_catalog.pg_roles gateway
                JOIN pg_catalog.pg_roles reachable
                  ON reachable.oid = gateway.oid
                  OR pg_catalog.pg_has_role(gateway.oid, reachable.oid, :activation)
                WHERE gateway.rolname IN :roles
            )
            SELECT NOT EXISTS (
                SELECT 1 FROM targets CROSS JOIN LATERAL pg_catalog.aclexplode(relacl) acl
                WHERE acl.grantee = 0 AND acl.privilege_type = 'UPDATE'
            ) AND NOT EXISTS (
                SELECT 1 FROM targets CROSS JOIN gateway_access gateway
                WHERE pg_catalog.has_sequence_privilege(gateway.oid, targets.oid, 'UPDATE')
                   OR pg_catalog.pg_has_role(gateway.oid, targets.relowner, 'USAGE')
            )
        """).bindparams(
            sa.bindparam("roles", type_=sa.String(), expanding=True),
            sa.bindparam("sequences", expanding=True),
        ),
        {
            "activation": activation,
            "roles": roles,
            "sequences": [oid for oid, _ in sequences],
        },
    )
    if protected is not True:
        raise RuntimeError(
            "Remaining financial sequence UPDATE privileges require role reconciliation"
        )


def downgrade() -> None:
    """Keep financial sequence mutation restricted during application rollbacks."""
