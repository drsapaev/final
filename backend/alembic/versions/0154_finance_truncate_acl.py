"""Limit table-wide deletion privileges on financial and audit relations."""

import sqlalchemy as sa
from alembic import op

revision = "0154_finance_truncate_acl"
down_revision = "0153_visit_start_appointment"
branch_labels = None
depends_on = None

_GATEWAY_ROLES = ("anon", "authenticated", "service_role")
_RELATIONS = (
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
    "provider_reconciliation_conflicts",
    "provider_reconciliation_events",
    "refund_requests",
    "service_audit_logs",
    "service_packages",
    "visit_invitation_price_approval_auth",
)


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return
    if context.dialect.name != "postgresql" or context.as_sql:
        raise RuntimeError(
            "Finance privilege checks require an online PostgreSQL catalog"
        )

    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted financial schema required")

    connection = op.get_bind()
    activation_privilege = (
        "SET" if connection.dialect.server_version_info >= (16,) else "MEMBER"
    )
    roles = tuple(
        connection.scalars(
            sa.text("""
            SELECT rolname FROM pg_catalog.pg_roles
            WHERE rolname IN :gateway_roles
            ORDER BY rolname
        """).bindparams(sa.bindparam("gateway_roles", expanding=True)),
            {"gateway_roles": _GATEWAY_ROLES},
        )
    )
    preparer = context.dialect.identifier_preparer
    qualified_schema = preparer.quote_schema(schema)
    targets = ", ".join(
        f"{qualified_schema}.{preparer.quote_identifier(relation)}"
        for relation in _RELATIONS
    )
    grantees = ", ".join(("PUBLIC", *map(preparer.quote_identifier, roles)))
    op.execute(f"REVOKE TRUNCATE ON TABLE {targets} FROM {grantees} RESTRICT")

    remaining = connection.scalar(
        sa.text("""
            WITH finance AS (
                SELECT c.oid, c.relacl, c.relowner
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema AND c.relname IN :relations
            ), gateway_access AS (
                SELECT DISTINCT reachable.oid
                FROM pg_catalog.pg_roles gateway
                JOIN pg_catalog.pg_roles reachable
                  ON reachable.oid = gateway.oid
                  OR pg_catalog.pg_has_role(
                      gateway.oid, reachable.oid, :activation_privilege
                  )
                WHERE gateway.rolname IN :roles
            )
            SELECT EXISTS (
                SELECT 1 FROM finance
                CROSS JOIN LATERAL pg_catalog.aclexplode(
                    COALESCE(relacl, pg_catalog.acldefault('r', relowner))
                ) a
                WHERE a.grantee = 0 AND a.privilege_type = 'TRUNCATE'
            ) OR EXISTS (
                SELECT 1 FROM finance CROSS JOIN gateway_access AS g
                WHERE pg_catalog.has_table_privilege(g.oid, finance.oid, 'TRUNCATE')
                   OR pg_catalog.pg_has_role(g.oid, finance.relowner, 'USAGE')
            )
        """).bindparams(
            sa.bindparam("relations", expanding=True),
            sa.bindparam("roles", type_=sa.String(), expanding=True),
        ),
        {
            "schema": schema,
            "relations": _RELATIONS,
            "roles": roles,
            "activation_privilege": activation_privilege,
        },
    )
    if remaining is not False:
        raise RuntimeError(
            "Remaining financial TRUNCATE privileges require role reconciliation"
        )


def downgrade() -> None:
    """Keep destructive privileges revoked during application rollbacks."""
