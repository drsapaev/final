"""Guard stored refund and deposit amounts without rewriting legacy evidence."""

from alembic import op

revision = "0150_refund_deposit_amounts"
down_revision = "0149_payment_visit_amount"
branch_labels = None
depends_on = None

_MAX_AMOUNT = "9999999999.99"
_DEPOSIT_CHECKS = (
    ("patient_deposits", "ck_patient_deposits_balance_range", "balance"),
    ("deposit_transactions", "ck_deposit_transactions_amount_range", "amount"),
    (
        "deposit_transactions",
        "ck_deposit_transactions_balance_range",
        "balance_after",
    ),
)
_TRIGGER = "trg_refund_request_amounts"
_FUNCTION = "enforce_refund_request_amounts"


def _postgres_schema() -> str | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported refund money checks dialect")
    schema = (
        context.opts.get("version_table_schema") or context.dialect.default_schema_name
    )
    if not schema:
        raise RuntimeError("Trusted application schema required")
    return schema


def upgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    for table, constraint, column in _DEPOSIT_CHECKS:
        op.create_check_constraint(
            constraint,
            table,
            f"{column} BETWEEN 0 AND {_MAX_AMOUNT}",
            schema=schema,
            postgresql_not_valid=True,
        )

    quoted = op.get_context().dialect.identifier_preparer.quote_schema(schema)
    op.execute(f"""
        CREATE FUNCTION {quoted}.{_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog AS $guard$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                -- An operator can close an old non-paying request while
                -- retaining its original monetary evidence.
                IF (
                    (OLD.status = 'pending' AND NEW.status IN ('rejected', 'cancelled'))
                    OR (OLD.status = 'approved' AND OLD.refund_type = 'deposit'
                        AND NEW.status = 'rejected')
                )
                   AND (NEW.original_amount, NEW.refund_amount, NEW.commission_amount)
                       IS NOT DISTINCT FROM
                       (OLD.original_amount, OLD.refund_amount, OLD.commission_amount)
                THEN
                    RETURN NEW;
                END IF;
            END IF;

            IF (NEW.original_amount BETWEEN 0 AND {_MAX_AMOUNT}
                AND NEW.refund_amount BETWEEN 0 AND NEW.original_amount
                AND NEW.commission_amount BETWEEN 0 AND {_MAX_AMOUNT}) IS NOT TRUE
            THEN
                RAISE EXCEPTION 'invalid refund request amounts' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $guard$
    """)
    op.execute(f"REVOKE ALL ON FUNCTION {quoted}.{_FUNCTION}() FROM PUBLIC")
    op.execute(f"""
        CREATE TRIGGER {_TRIGGER}
        BEFORE INSERT OR UPDATE OF original_amount, refund_amount, commission_amount, status
        ON {quoted}.refund_requests
        FOR EACH ROW EXECUTE FUNCTION {quoted}.{_FUNCTION}()
    """)


def downgrade() -> None:
    schema = _postgres_schema()
    if schema is None:
        return

    quoted = op.get_context().dialect.identifier_preparer.quote_schema(schema)
    op.execute(f"DROP TRIGGER {_TRIGGER} ON {quoted}.refund_requests")
    op.execute(f"DROP FUNCTION {quoted}.{_FUNCTION}()")
    for table, constraint, _ in reversed(_DEPOSIT_CHECKS):
        op.drop_constraint(constraint, table, type_="check", schema=schema)
