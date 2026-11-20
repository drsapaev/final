"""Keep a visit deposit payment, its debit and the balance in one transaction."""

from alembic import op

revision = "0142_deposit_visit_payment"
down_revision = "0141_confirmation_finance"
branch_labels = None
depends_on = None

_PAYMENT = "guard_visit_deposit_payment"
_TRANSACTION = "apply_visit_deposit_transaction"
_LINK = "guard_visit_deposit_payment_link"
_VERIFY_PAYMENT = "trg_verify_visit_deposit_payment"
_LOCK_PAYMENT = "trg_keep_visit_deposit_payment"
_APPLY_TRANSACTION = "trg_apply_visit_deposit_transaction"
_GUARD_PAYOUT = "trg_guard_visit_deposit_payout"
_GUARD_ALLOCATION = "trg_guard_visit_deposit_allocation"
_PAYMENT_EVIDENCE = (
    "id", "visit_id", "amount", "currency", "method", "status", "client_request_id",
    "provider", "provider_payment_id", "provider_transaction_id", "refunded_amount", "paid_at", "created_at",
)


def _postgres_target() -> tuple[str, str] | None:
    context = op.get_context()
    if context.dialect.name == "sqlite":
        return None
    if context.dialect.name != "postgresql":
        raise RuntimeError("Unsupported visit deposit dialect")
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    quoted = context.dialect.identifier_preparer.quote_schema(schema)
    delimiter = "$visit_deposit$"
    while delimiter in quoted:
        delimiter = delimiter[:-1] + "_x$"
    return quoted, delimiter


def upgrade() -> None:
    target = _postgres_target()
    if target is None:
        return
    schema, delimiter = target
    old_fields = ",".join(f"OLD.{field}" for field in _PAYMENT_EVIDENCE)
    new_fields = ",".join(f"NEW.{field}" for field in _PAYMENT_EVIDENCE)
    op.execute(f"""
      CREATE FUNCTION {schema}.{_PAYMENT}() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS {delimiter}
      BEGIN
        IF TG_OP='UPDATE' THEN
          IF ROW({old_fields}) IS DISTINCT FROM ROW({new_fields}) THEN
            RAISE EXCEPTION 'visit deposit payment evidence is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END IF;
        IF NEW.status<>'paid' OR NEW.paid_at IS NULL OR NEW.currency<>'UZS'
            OR NEW.amount<=0 OR COALESCE(NEW.refunded_amount,0)<>0
            OR NEW.provider IS NOT NULL OR NEW.provider_payment_id IS NOT NULL
            OR NEW.provider_transaction_id IS NOT NULL OR NEW.client_request_id IS NULL
            OR NEW.client_request_id !~ '^[0-9a-f]{{8}}(-[0-9a-f]{{4}}){{3}}-[0-9a-f]{{12}}$' THEN
          RAISE EXCEPTION 'visit deposit payment requires a debit receipt' USING ERRCODE='23514';
        END IF;
        IF NOT EXISTS (
          SELECT 1 FROM {schema}.deposit_transactions d
          WHERE d.client_request_id=CAST(NEW.client_request_id AS uuid)
            AND d.payment_id=NEW.id AND d.visit_id=NEW.visit_id AND d.transaction_type='debit'
            AND d.amount=NEW.amount AND d.command_currency=NEW.currency AND d.command_is_active IS TRUE
        ) THEN
          RAISE EXCEPTION 'visit deposit payment requires a debit receipt' USING ERRCODE='23514';
        END IF;
        RETURN NULL;
      END {delimiter}
    """)
    op.execute(f"""
      CREATE FUNCTION {schema}.{_TRANSACTION}() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS {delimiter}
      DECLARE payment_method text; payment_key text; subject_id integer;
      BEGIN
        IF NEW.transaction_type='debit' THEN
          -- A restricted SELECT can hide old unpaired debits. Prove that
          -- the caller sees the entire receipt table before testing absence.
          IF pg_catalog.row_security_active(TG_RELID) AND (
            NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=TG_RELID
              AND p.polpermissive AND p.polcmd IN ('r','*') AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true'
              AND (0=ANY(p.polroles) OR (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=TG_RELID
              AND NOT p.polpermissive AND p.polcmd IN ('r','*') AND EXISTS (
                SELECT 1 FROM pg_catalog.unnest(p.polroles) AS subject(role_id)
                WHERE CASE WHEN subject.role_id=0 THEN true
                  ELSE pg_catalog.pg_has_role(CURRENT_USER,subject.role_id,'MEMBER') END))
          ) THEN
            RAISE EXCEPTION 'visit deposit ledger visibility unavailable' USING ERRCODE='42501';
          END IF;
          SELECT v.patient_id INTO subject_id FROM {schema}.payments p
          JOIN {schema}.visits v ON v.id=p.visit_id
          WHERE p.id=NEW.payment_id AND p.visit_id=NEW.visit_id AND p.amount=NEW.amount
            AND p.method='deposit' AND p.status='paid'
            AND COALESCE(p.refunded_amount,0)=0 AND p.currency='UZS' AND p.currency=NEW.command_currency
            AND p.client_request_id=CAST(NEW.client_request_id AS text)
          FOR SHARE OF v NOWAIT;
          IF subject_id IS NULL OR NEW.amount<=0 OR NEW.command_is_active IS NOT TRUE
              OR NEW.refund_request_id IS NOT NULL OR NEW.refund_currency_snapshot IS NOT NULL THEN
            RAISE EXCEPTION 'invalid visit deposit debit evidence' USING ERRCODE='23514';
          END IF;
          IF EXISTS (SELECT 1 FROM {schema}.deposit_transactions d WHERE d.visit_id=NEW.visit_id
            AND d.transaction_type='debit' AND d.payment_id IS NULL) THEN
            RAISE EXCEPTION 'unpaired historical visit deposit debit' USING ERRCODE='23514';
          END IF;
          UPDATE {schema}.patient_deposits SET balance=balance-NEW.amount,
            updated_at=pg_catalog.statement_timestamp()
            WHERE id=NEW.deposit_id AND patient_id=subject_id AND currency=NEW.command_currency
              AND is_active AND balance>=NEW.amount
            RETURNING balance INTO NEW.balance_after;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'invalid visit deposit balance' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END IF;

        SELECT p.method,p.client_request_id INTO payment_method,payment_key
          FROM {schema}.payments p WHERE p.id=NEW.payment_id;
        IF NOT FOUND OR (payment_method='deposit' AND NOT EXISTS (
          SELECT 1 FROM {schema}.deposit_transactions d
          WHERE d.payment_id=NEW.payment_id AND d.visit_id=NEW.visit_id AND d.deposit_id=NEW.deposit_id
            AND d.transaction_type='debit' AND d.amount=NEW.amount AND d.command_is_active IS TRUE
            AND d.command_currency=NEW.refund_currency_snapshot AND CAST(d.client_request_id AS text)=payment_key
        )) THEN
          RAISE EXCEPTION 'visit refund must match its deposit debit' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END {delimiter}
    """)
    op.execute(f"""
      CREATE FUNCTION {schema}.{_LINK}() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS {delimiter}
      DECLARE payment_method text;
      BEGIN
        SELECT p.method INTO payment_method FROM {schema}.payments p WHERE p.id=NEW.payment_id;
        IF NOT FOUND OR payment_method='deposit' THEN
          IF TG_TABLE_NAME='payment_visits' THEN
            RAISE EXCEPTION 'visit deposit payment has a single visit' USING ERRCODE='23514';
          END IF;
          RAISE EXCEPTION 'visit deposit payment requires a deposit refund' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END {delimiter}
    """)
    for function in (_PAYMENT, _TRANSACTION, _LINK):
        op.execute(f"REVOKE ALL ON FUNCTION {schema}.{function}() FROM PUBLIC")
    op.execute(f"""
      CREATE CONSTRAINT TRIGGER {_VERIFY_PAYMENT} AFTER INSERT ON {schema}.payments
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.method='deposit')
      EXECUTE FUNCTION {schema}.{_PAYMENT}()
    """)
    op.execute(f"""
      CREATE TRIGGER {_LOCK_PAYMENT} BEFORE UPDATE ON {schema}.payments FOR EACH ROW
      WHEN (OLD.method='deposit' OR NEW.method='deposit') EXECUTE FUNCTION {schema}.{_PAYMENT}()
    """)
    op.execute(f"""
      CREATE TRIGGER {_APPLY_TRANSACTION} BEFORE INSERT ON {schema}.deposit_transactions FOR EACH ROW
      WHEN ((NEW.transaction_type='debit' AND (NEW.visit_id IS NOT NULL OR NEW.payment_id IS NOT NULL))
        OR NEW.refund_currency_snapshot IS NOT NULL) EXECUTE FUNCTION {schema}.{_TRANSACTION}()
    """)
    op.execute(f"""
      CREATE TRIGGER {_GUARD_PAYOUT} BEFORE INSERT ON {schema}.refund_requests
      FOR EACH ROW EXECUTE FUNCTION {schema}.{_LINK}()
    """)
    op.execute(f"""
      CREATE TRIGGER {_GUARD_ALLOCATION} BEFORE INSERT OR UPDATE OF payment_id,visit_id,amount
      ON {schema}.payment_visits FOR EACH ROW EXECUTE FUNCTION {schema}.{_LINK}()
    """)


def downgrade() -> None:
    target = _postgres_target()
    if target is None:
        return
    schema, delimiter = target
    op.execute("SET LOCAL row_security=off")
    op.execute(f"""
      LOCK TABLE {schema}.payments, {schema}.deposit_transactions, {schema}.refund_requests,
        {schema}.payment_visits IN ACCESS EXCLUSIVE MODE
    """)
    op.execute(f"""DO {delimiter} BEGIN
      IF EXISTS (SELECT 1 FROM {schema}.payments WHERE method='deposit') THEN
        RAISE EXCEPTION 'visit deposit payment evidence prevents downgrade' USING ERRCODE='23514';
      END IF;
    END {delimiter}""")
    for table, trigger in (("payments", _VERIFY_PAYMENT), ("payments", _LOCK_PAYMENT),
                           ("deposit_transactions", _APPLY_TRANSACTION), ("refund_requests", _GUARD_PAYOUT),
                           ("payment_visits", _GUARD_ALLOCATION)):
        op.execute(f"DROP TRIGGER {trigger} ON {schema}.{table}")
    for function in (_LINK, _TRANSACTION, _PAYMENT):
        op.execute(f"DROP FUNCTION {schema}.{function}()")
