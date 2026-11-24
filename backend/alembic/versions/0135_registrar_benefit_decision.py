"""Approve one exact registrar benefit under the financial and quota locks."""

import hashlib

from alembic import op

revision = "0135_registrar_benefit_decision"
down_revision = "0134_registrar_cart_origin"
branch_labels = None
depends_on = None

_DECISION = "approve_registrar_benefit(integer,integer,integer,bigint,text)"
_LEGACY = "legacy_benefit_cents(double precision)"


def _schemas() -> tuple[str, str, str, str, str]:
    context = op.get_context()
    schema = context.opts.get("version_table_schema") or context.dialect.default_schema_name
    if not schema:
        raise RuntimeError("Trusted application schema required")
    private = "clinic_internal_" + hashlib.sha256(b"clinic-capability-schema-v1\0" + schema.encode()).hexdigest()[:32]
    quote = context.dialect.identifier_preparer.quote_identifier
    delimiter = "$registrar_benefit$"
    while delimiter in schema:
        delimiter = delimiter[:-1] + "_x$"
    return schema.replace("'", "''"), private, quote(schema), quote(private), delimiter


def _legacy_usage(private: str, tag: str) -> None:
    # Mirrors float.as_integer_ratio() in calculate_quota_usage. Decimal text
    # could undercharge 0.1, whose stored binary value is just above 10 cents.
    op.execute(f"""
      CREATE FUNCTION {private}.legacy_benefit_cents(amount double precision) RETURNS numeric
      LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog AS {tag}
      DECLARE encoded bytea; exponent_bits integer; significand bigint; denominator numeric;
      BEGIN
        IF amount<0 OR amount>'9999999999.99'::double precision THEN
          RAISE EXCEPTION 'Invalid legacy benefit usage';
        END IF;
        encoded := pg_catalog.float8send(amount);
        exponent_bits := (pg_catalog.get_byte(encoded,0)&127)*16+(pg_catalog.get_byte(encoded,1)>>4);
        significand := (pg_catalog.get_byte(encoded,1)::bigint&15)<<48;
        FOR idx IN 2..7 LOOP
          significand := significand | (pg_catalog.get_byte(encoded,idx)::bigint<<(8*(7-idx)));
        END LOOP;
        IF significand=0 AND exponent_bits=0 THEN RETURN 0; END IF;
        IF exponent_bits<>0 THEN significand := significand+4503599627370496; END IF;
        denominator := pg_catalog.power(2::numeric,CASE WHEN exponent_bits=0 THEN 1074 ELSE 1075-exponent_bits END);
        RETURN pg_catalog.div(significand::numeric*100+denominator-1,denominator);
      END {tag}
    """)


def _decision(app: str, private: str, tag: str) -> None:
    op.execute(f"""
      CREATE FUNCTION {private}.approve_registrar_benefit(
        p_invoice integer, p_assignment integer, p_actor integer, p_auth_epoch bigint, p_timezone text
      ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog SET row_security=off SET extra_float_digits=3 AS {tag}
      DECLARE invoice {app}.payment_invoices%ROWTYPE; applicant {app}.patient_benefits%ROWTYPE;
        policy {app}.benefits%ROWTYPE; actor_role text; patient integer; origin integer; members integer[];
        approved_at timestamptz; clinic_now timestamp; month_start date; approval_year integer;
        per_cent numeric; cap_single numeric; cap_month numeric; cap_year numeric;
        used_month numeric; used_year numeric; legacy_used numeric;
        gross_cents numeric; discount_cents numeric; numerator numeric; rem numeric; approval integer;
        written_members integer; written_total numeric;
      BEGIN
        IF p_invoice IS NULL OR p_invoice<=0 OR p_assignment IS NULL OR p_assignment<=0
          OR p_actor IS NULL OR p_actor<=0 OR p_auth_epoch IS NULL OR p_auth_epoch<0
          OR p_timezone IS NULL OR length(p_timezone)>64 OR NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_timezone_names WHERE name=p_timezone
          ) OR pg_catalog.current_setting('transaction_isolation')<>'read committed'
          OR pg_catalog.current_setting('session_replication_role')<>'origin' THEN
          RAISE EXCEPTION 'Invalid registrar benefit context';
        END IF;
        SELECT CASE WHEN u.is_superuser THEN 'superadmin' ELSE pg_catalog.lower(pg_catalog.btrim(u.role)) END
          INTO actor_role FROM {app}.users u WHERE u.id=p_actor AND u.is_active IS TRUE AND u.auth_epoch=p_auth_epoch
            AND (u.is_superuser IS TRUE OR pg_catalog.lower(pg_catalog.btrim(u.role)) IN ('admin','superadmin'))
          FOR NO KEY UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Registrar benefit actor unavailable'; END IF;

        SELECT i.patient_id,i.registrar_encounter_id_snapshot INTO patient,origin
          FROM {app}.payment_invoices i WHERE i.id=p_invoice;
        IF patient IS NULL OR origin IS NULL THEN RAISE EXCEPTION 'Registrar origin required'; END IF;
        PERFORM p.id FROM {app}.patients p WHERE p.id=patient AND p.is_deleted IS NOT TRUE FOR NO KEY UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Registrar patient unavailable'; END IF;
        SELECT ARRAY(SELECT v.id FROM {app}.visits v WHERE v.encounter_id=origin ORDER BY v.id FOR UPDATE) INTO members;
        PERFORM e.id FROM {app}.encounters e WHERE e.id=origin FOR UPDATE;
        SELECT * INTO invoice FROM {app}.payment_invoices i WHERE i.id=p_invoice FOR UPDATE;
        IF NOT FOUND OR invoice.patient_id IS DISTINCT FROM patient
          OR invoice.registrar_encounter_id_snapshot IS DISTINCT FROM origin OR invoice.status IS DISTINCT FROM 'pending'
          OR invoice.provider IS NOT NULL OR invoice.provider_payment_id IS NOT NULL
          OR invoice.provider_transaction_id IS NOT NULL OR invoice.payment_url IS NOT NULL
          OR invoice.provider_data IS NOT NULL OR invoice.currency IS NULL OR invoice.currency !~ '^[A-Z]{{3}}$'
          OR NOT EXISTS (SELECT 1 FROM {app}.encounters e WHERE e.id=origin AND e.patient_id=patient
              AND e.generation=invoice.registrar_encounter_generation_snapshot AND e.provenance='new')
          OR pg_catalog.cardinality(members)=0
          OR members IS DISTINCT FROM ARRAY(SELECT v.id FROM {app}.visits v WHERE v.encounter_id=origin ORDER BY v.id)
          OR members IS DISTINCT FROM ARRAY(SELECT l.visit_id FROM {app}.payment_invoice_visits l WHERE l.invoice_id=p_invoice ORDER BY l.visit_id)
          OR EXISTS (SELECT 1 FROM {app}.payment_invoice_visits l WHERE l.visit_id=ANY(members) AND l.invoice_id<>p_invoice)
          OR EXISTS (SELECT 1 FROM {app}.visits v WHERE v.id=ANY(members) AND
            (v.patient_id IS DISTINCT FROM patient OR v.discount_mode IS DISTINCT FROM 'none' OR v.status IS DISTINCT FROM 'confirmed'))
          OR EXISTS (SELECT 1 FROM {app}.encounter_benefit_applications a WHERE a.encounter_id=origin)
          OR EXISTS (SELECT 1 FROM {app}.all_free_requests r WHERE r.visit_id=ANY(members) AND r.status IN ('pending','approved'))
        THEN RAISE EXCEPTION 'Registrar benefit requires a current unused invoice'; END IF;

        -- The application also holds the shared reconciliation fence and has
        -- proved RLS-complete financial closure before entering this writer.
        IF EXISTS (SELECT 1 FROM {app}.payments p WHERE p.visit_id=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.payment_visits p WHERE p.visit_id=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.payment_webhooks p WHERE p.visit_id=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.payment_transactions p WHERE p.visit_id=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.invoices p WHERE p.visit_id=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.provider_active_visit_reservations p WHERE p.visit_id=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.provider_attempt_visits p WHERE p.visit_id_snapshot=ANY(members))
          OR EXISTS (SELECT 1 FROM {app}.provider_reconciliation_events r WHERE r.invoice_id_snapshot=p_invoice OR r.target_kind='unmatched')
        THEN RAISE EXCEPTION 'Registrar benefit requires financial reconciliation'; END IF;

        SELECT * INTO applicant FROM {app}.patient_benefits a
          WHERE a.id=p_assignment AND a.patient_id=patient AND a.is_active IS TRUE AND a.verified IS TRUE FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Registrar benefit assignment unavailable'; END IF;
        SELECT * INTO policy FROM {app}.benefits b WHERE b.id=applicant.benefit_id AND b.is_active IS TRUE FOR SHARE;
        IF NOT FOUND OR policy.applies_to_services IS NOT TRUE
          OR policy.age_min IS NOT NULL OR policy.age_max IS NOT NULL
          OR (policy.requires_document IS DISTINCT FROM false AND
             (applicant.verification_date IS NULL OR COALESCE(pg_catalog.btrim(applicant.document_number),'')=''))
        THEN RAISE EXCEPTION 'Registrar benefit eligibility unavailable'; END IF;

        INSERT INTO {app}.encounter_benefit_quota_anchors(patient_id,benefit_id) VALUES (patient,policy.id)
          ON CONFLICT (patient_id,benefit_id) DO NOTHING;
        PERFORM a.patient_id FROM {app}.encounter_benefit_quota_anchors a
          WHERE a.patient_id=patient AND a.benefit_id=policy.id FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Registrar benefit quota unavailable'; END IF;
        approved_at := pg_catalog.clock_timestamp();
        clinic_now := approved_at AT TIME ZONE p_timezone;
        month_start := pg_catalog.date_trunc('month',clinic_now)::date;
        approval_year := EXTRACT(year FROM clinic_now)::integer;
        IF (applicant.document_expiry_date IS NOT NULL AND applicant.document_expiry_date<clinic_now)
          OR (applicant.document_issued_date IS NOT NULL AND applicant.document_issued_date>clinic_now)
        THEN RAISE EXCEPTION 'Registrar benefit document is outside its validity'; END IF;

        per_cent := policy.discount_percentage::text::numeric;
        cap_single := policy.max_discount_amount::text::numeric;
        cap_month := policy.monthly_limit::text::numeric;
        cap_year := policy.yearly_limit::text::numeric;
        IF per_cent IS NULL OR per_cent<=0 OR per_cent>100 OR per_cent<>pg_catalog.trunc(per_cent,4)
          OR EXISTS (SELECT 1 FROM pg_catalog.unnest(ARRAY[cap_single,cap_month,cap_year]) c(value)
            WHERE value<0 OR value>9999999999.99 OR value<>pg_catalog.trunc(value,2))
        THEN RAISE EXCEPTION 'Registrar benefit policy requires reconciliation'; END IF;

        IF EXISTS (SELECT 1 FROM {app}.benefit_applications b JOIN {app}.patient_benefits a ON a.id=b.patient_benefit_id
           WHERE a.patient_id=patient AND (a.benefit_id=policy.id OR b.benefit_id=policy.id)
             AND (a.benefit_id IS DISTINCT FROM b.benefit_id OR b.benefit_amount IS NULL))
          OR EXISTS (SELECT 1 FROM {app}.encounter_benefit_applications a
            WHERE a.patient_id_snapshot=patient AND a.benefit_id_snapshot=policy.id
              AND (NOT pg_catalog.isfinite(a.period_month) OR EXTRACT(day FROM a.period_month)<>1
                OR EXTRACT(year FROM a.period_month)<>a.period_year OR pg_catalog.btrim(a.period_timezone)=''))
        THEN RAISE EXCEPTION 'Registrar benefit history requires reconciliation'; END IF;
        SELECT COALESCE(sum({private}.legacy_benefit_cents(b.benefit_amount)),0) INTO legacy_used
          FROM {app}.benefit_applications b JOIN {app}.patient_benefits a ON a.id=b.patient_benefit_id
          WHERE a.patient_id=patient AND a.benefit_id=policy.id;
        SELECT legacy_used+COALESCE(sum(a.benefit_total*100) FILTER (
          WHERE a.period_timezone<>p_timezone OR a.period_month=month_start),0),
          legacy_used+COALESCE(sum(a.benefit_total*100) FILTER (
          WHERE a.period_timezone<>p_timezone OR a.period_year=approval_year),0)
          INTO used_month,used_year FROM {app}.encounter_benefit_applications a
          WHERE a.patient_id_snapshot=patient AND a.benefit_id_snapshot=policy.id;
        IF used_month>999999999999 OR used_year>999999999999 THEN
          RAISE EXCEPTION 'Registrar benefit history is beyond supported amounts';
        END IF;

        IF EXISTS (SELECT 1 FROM {app}.visit_services s WHERE s.visit_id=ANY(members) AND
              (s.service_id IS NULL OR s.service_id<=0 OR s.qty IS NULL OR s.qty<=0 OR s.price IS NULL
                OR s.price<0 OR s.price>9999999999.99 OR s.currency IS DISTINCT FROM invoice.currency))
          OR EXISTS (SELECT 1 FROM {app}.payment_invoice_visits l WHERE l.invoice_id=p_invoice AND
              l.visit_amount IS DISTINCT FROM (SELECT sum(s.qty*s.price) FROM {app}.visit_services s WHERE s.visit_id=l.visit_id))
        THEN RAISE EXCEPTION 'Registrar benefit lines require reconciliation'; END IF;
        SELECT COALESCE(sum(s.price*s.qty*100),0) INTO gross_cents
          FROM {app}.visit_services s WHERE s.visit_id=ANY(members);
        IF gross_cents=0 OR gross_cents>999999999999 OR gross_cents IS DISTINCT FROM invoice.total_amount*100 THEN
          RAISE EXCEPTION 'Registrar benefit total requires reconciliation';
        END IF;

        -- Round once to cents, half-even, then cap and apportion by largest remainder.
        numerator := gross_cents*per_cent*10000;
        discount_cents := pg_catalog.div(numerator,1000000);
        rem := pg_catalog.mod(numerator,1000000);
        IF rem>500000 OR (rem=500000 AND pg_catalog.mod(discount_cents,2)=1) THEN
          discount_cents := discount_cents+1;
        END IF;
        discount_cents := LEAST(discount_cents,cap_single*100,
          CASE WHEN cap_month IS NOT NULL THEN GREATEST(cap_month*100-used_month,0) END,
          CASE WHEN cap_year IS NOT NULL THEN GREATEST(cap_year*100-used_year,0) END);
        IF discount_cents<=0 THEN RAISE EXCEPTION 'Registrar benefit quota exhausted'; END IF;

        INSERT INTO {app}.encounter_benefit_applications (
          encounter_id,patient_id,patient_id_snapshot,patient_benefit_id,patient_benefit_id_snapshot,
          benefit_id,benefit_id_snapshot,approved_by_user_id,approved_by_user_id_snapshot,approved_by_role_snapshot,
          approved_at,period_timezone,period_month,period_year,encounter_generation,percentage,
          max_discount,monthly_limit,yearly_limit,monthly_used_before,yearly_used_before,gross_total,benefit_total,net_total
        ) VALUES (
          origin,patient,patient,p_assignment,p_assignment,policy.id,policy.id,p_actor,p_actor,actor_role,
          approved_at,p_timezone,month_start,approval_year,invoice.registrar_encounter_generation_snapshot,per_cent,
          cap_single,cap_month,cap_year,used_month/100,used_year/100,gross_cents/100,discount_cents/100,
          (gross_cents-discount_cents)/100
        ) RETURNING id INTO approval;
        INSERT INTO {app}.encounter_benefit_visit_snapshots
          (application_id,visit_id,encounter_id,patient_id,visit_id_snapshot,visit_context_epoch)
          SELECT approval,v.id,origin,patient,v.id,v.confirmation_context_epoch FROM {app}.visits v WHERE v.id=ANY(members);

        WITH shares AS (
          SELECT s.id,s.visit_id,s.service_id,s.qty,s.price,s.price*s.qty*100 AS gross,
            pg_catalog.div(discount_cents*s.price*s.qty*100,gross_cents) AS share,
            pg_catalog.mod(discount_cents*s.price*s.qty*100,gross_cents) AS remainder
          FROM {app}.visit_services s WHERE s.visit_id=ANY(members)
        ), apportioned AS (
          SELECT *,share+CASE WHEN row_number() OVER (ORDER BY remainder DESC,id)<=discount_cents-sum(share) OVER ()
                              THEN 1 ELSE 0 END AS cut FROM shares
        )
        INSERT INTO {app}.encounter_benefit_allocations (
          application_id,visit_id,visit_id_snapshot,visit_service_id,visit_service_id_snapshot,service_id_snapshot,
          visit_context_epoch,quantity,unit_price,gross_amount,benefit_amount,net_amount
        ) SELECT approval,s.visit_id,s.visit_id,s.id,s.id,s.service_id,v.confirmation_context_epoch,s.qty,s.price,
            s.gross/100,s.cut/100,(s.gross-s.cut)/100
          FROM apportioned s JOIN {app}.visits v ON v.id=s.visit_id;

        UPDATE {app}.payment_invoice_visits l SET visit_amount=net.amount
          FROM (SELECT a.visit_id,sum(a.net_amount) AS amount FROM {app}.encounter_benefit_allocations a
                WHERE a.application_id=approval GROUP BY a.visit_id) net
          WHERE l.invoice_id=p_invoice AND l.visit_id=net.visit_id;
        GET DIAGNOSTICS written_members = ROW_COUNT;
        IF written_members<>pg_catalog.cardinality(members) THEN
          RAISE EXCEPTION 'Registrar benefit invoice links were not repriced';
        END IF;
        UPDATE {app}.payment_invoices SET total_amount=(gross_cents-discount_cents)/100,updated_at=approved_at
          WHERE id=p_invoice RETURNING total_amount INTO written_total;
        IF written_total IS DISTINCT FROM (gross_cents-discount_cents)/100 THEN
          RAISE EXCEPTION 'Registrar benefit invoice was not repriced';
        END IF;
        RETURN pg_catalog.jsonb_build_object('application_id',approval,'invoice_id',p_invoice,
          'gross_total',(gross_cents/100)::text,'benefit_total',(discount_cents/100)::text,
          'total_amount',((gross_cents-discount_cents)/100)::text);
      END {tag}
    """)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return
    if dialect != "postgresql":
        raise RuntimeError("Unsupported benefit decision dialect")
    schema, private_name, app, private, tag = _schemas()
    op.execute("SET LOCAL standard_conforming_strings=on")
    op.execute(f"""DO {tag} BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace a JOIN pg_catalog.pg_namespace p ON p.nspowner=a.nspowner
        WHERE a.nspname='{schema}' AND p.nspname='{private_name}')
        OR (SELECT count(*) FROM {private}.clinic_capability_namespace)<>1
        OR NOT EXISTS (SELECT 1 FROM {private}.clinic_capability_namespace
          WHERE id=1 AND format_version=1 AND application_schema='{schema}' AND private_schema='{private_name}') THEN
        RAISE EXCEPTION 'Registrar benefit capability namespace is invalid';
      END IF;
    END {tag}""")
    _legacy_usage(private, tag)
    _decision(app, private, tag)
    for signature in (_LEGACY, _DECISION):
        op.execute(f"REVOKE ALL ON FUNCTION {private}.{signature} FROM PUBLIC")
        op.execute(f"""DO {tag} DECLARE owner_name name; BEGIN
          SELECT r.rolname INTO STRICT owner_name FROM pg_catalog.pg_namespace n
            JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='{schema}';
          EXECUTE pg_catalog.format('ALTER FUNCTION %I.{signature} OWNER TO %I','{private_name}',owner_name);
        END {tag}""")


def downgrade() -> None:
    if op.get_context().dialect.name == "sqlite":
        return
    _, _, app, private, tag = _schemas()
    op.execute("SET LOCAL row_security=off")
    op.execute(f"LOCK TABLE {app}.encounter_benefit_applications IN ACCESS EXCLUSIVE MODE")
    op.execute(f"""DO {tag} BEGIN
      IF EXISTS (SELECT 1 FROM {app}.encounter_benefit_applications) THEN
        RAISE EXCEPTION 'Registrar benefit decisions prevent downgrade';
      END IF;
    END {tag}""")
    op.execute(f"DROP FUNCTION {private}.{_DECISION}")
    op.execute(f"DROP FUNCTION {private}.{_LEGACY}")
