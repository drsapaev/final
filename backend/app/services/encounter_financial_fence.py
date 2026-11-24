"""Internal group snapshot and draft-invoice re-quote primitives.

This module is not an authorization boundary yet. Every encounter-membership,
invoice-link and financial writer must participate in the same lock protocol,
and the PostgreSQL runtime role needs verified complete RLS visibility before
an issuer or decision endpoint may rely on these primitives.

The caller owns User/Patient locks, transaction, rollback, authorization and
external effects. No helper below commits or contacts a provider.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.financial_capability_contract import financial_contract_is_valid
from app.models.all_free_request import AllFreeRequest, AllFreeRequestLine
from app.models.billing import Invoice
from app.models.encounter import Encounter
from app.models.encounter_benefit_ledger import (
    EncounterBenefitAllocation,
    EncounterBenefitApplication,
    EncounterBenefitEvent,
)
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.models.provider_attempt import (
    ProviderActiveVisitReservation,
    ProviderAttemptVisit,
)
from app.models.provider_reconciliation import ProviderReconciliationEvent
from app.models.visit import Visit, VisitService
from app.services.all_free_guard import lock_visit_without_pending
from app.services.money_input import MoneyInputError, parse_money


class FinancialFenceError(ValueError):
    """The group or financial state must be refreshed or reconciled."""


@dataclass(frozen=True)
class LockedFinancialGroup:
    session: Session
    transaction: object
    session_savepoint: object | None
    connection_savepoint: object | None
    encounter: Encounter
    visits: tuple[Visit, ...]
    invoices: tuple[PaymentInvoice, ...]
    links: tuple[PaymentInvoiceVisit, ...]
    pending_requests: tuple[AllFreeRequest, ...]
    gross_by_visit: Mapping[int, Decimal]
    baseline_links: tuple[tuple[int, Decimal], ...]
    baseline_invoices: tuple[tuple[int, Decimal], ...]


@dataclass(frozen=True)
class _PaymentPreflight:
    transaction: object
    session_savepoint: object | None
    connection_savepoint: object | None
    visit_ids: tuple[int, ...]
    contexts: tuple[tuple[int, int, int | None, int], ...]
    groups: tuple[tuple[int, int, tuple[int, ...]], ...]
    ungrouped: tuple[int, ...]
    invoice_ids: tuple[int, ...]
    invoice_links: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class LockedPaymentRecord:
    payment_id: int
    primary_visit_id: int
    visit_ids: tuple[int, ...]
    links: tuple[tuple[int, int], ...]


_PAYMENT_PREFLIGHT_KEY = object()
_CONTEXT_MODELS = (
    Visit, VisitService, Encounter, AllFreeRequest, AllFreeRequestLine,
    EncounterBenefitApplication, EncounterBenefitAllocation, EncounterBenefitEvent,
)


def _money(value: object) -> Decimal:
    try:
        return parse_money(value)
    except (MoneyInputError, TypeError, ValueError) as exc:
        raise FinancialFenceError("Некорректная денежная сумма") from exc


def _financial_private_schema(db: Session) -> str:
    from app.db.capability_namespace import capability_schema_name

    name = capability_schema_name(db.get_bind().dialect.default_schema_name)
    return db.get_bind().dialect.identifier_preparer.quote_schema(name)


def _financial_schema(db: Session) -> str:
    """Validate one configured database boundary before unqualified reads."""
    schema, owner, runtime = (settings.TRUSTED_DB_SCHEMA, settings.TRUSTED_DB_SCHEMA_OWNER,
                              settings.TRUSTED_DB_RUNTIME_ROLE)
    if (any(not isinstance(value, str) or not value or "\x00" in value or len(value.encode("utf-8")) > 63
            for value in (schema, owner, runtime))
        or schema in {"pg_catalog", "information_schema"}
        or db.get_bind().dialect.default_schema_name != schema):
        raise FinancialFenceError("Финансовая проверка недоступна")
    search_path, actual_temp = db.execute(text("""
      SELECT pg_catalog.current_schemas(true),
        (SELECT n.nspname FROM pg_catalog.pg_namespace n WHERE n.oid=pg_catalog.pg_my_temp_schema())
    """)).one()
    if list(search_path) not in (["pg_catalog", schema], ["pg_catalog", schema, actual_temp] if actual_temp else []):
        raise FinancialFenceError("Финансовая проверка недоступна")
    qualified = db.get_bind().dialect.identifier_preparer.quote_schema(schema)
    private = _financial_private_schema(db)
    from app.db.capability_namespace import capability_schema_name

    safe = db.execute(text("""
      SELECT NOT pg_catalog.has_schema_privilege(CURRENT_USER,n.oid,'CREATE')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
          WHERE a.privilege_type='CREATE' AND a.grantee<>n.nspowner)
        AND NOT a.rolsuper AND NOT a.rolbypassrls AND a.rolcanlogin AND CURRENT_USER=SESSION_USER
        AND NOT a.rolcreaterole AND NOT a.rolcreatedb AND NOT a.rolreplication
        AND (schema_owner.rolsuper OR NOT schema_owner.rolcanlogin)
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles member WHERE NOT member.rolsuper
          AND member.oid<>schema_owner.oid AND pg_catalog.pg_has_role(member.oid,schema_owner.oid,'MEMBER'))
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles member WHERE NOT member.rolsuper
          AND member.oid<>a.oid AND pg_catalog.pg_has_role(member.oid,a.oid,'MEMBER'))
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles inherited
          WHERE inherited.oid<>a.oid AND pg_catalog.pg_has_role(a.oid,inherited.oid,'MEMBER'))
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles elevated
          WHERE (elevated.rolsuper OR elevated.rolbypassrls OR elevated.rolcreaterole OR elevated.rolcreatedb OR elevated.rolreplication)
            AND pg_catalog.pg_has_role(a.oid,elevated.oid,'MEMBER'))
        AND pg_catalog.lower(a.rolname) NOT IN ('anon','authenticated','public')
        AND private_ns.nspowner=n.nspowner
        AND pg_catalog.has_schema_privilege(CURRENT_USER,private_ns.oid,'USAGE')
        AND NOT pg_catalog.has_schema_privilege(CURRENT_USER,private_ns.oid,'CREATE')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(private_ns.nspacl,pg_catalog.acldefault('n',private_ns.nspowner))) x
          WHERE (x.privilege_type='CREATE' AND x.grantee<>private_ns.nspowner) OR x.grantee=0)
      FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles a ON a.rolname=CURRENT_USER
        JOIN pg_catalog.pg_roles schema_owner ON schema_owner.oid=n.nspowner
        JOIN pg_catalog.pg_namespace private_ns ON private_ns.nspname=:private
      WHERE n.nspname=:schema AND schema_owner.rolname=:expected_owner AND a.rolname=:expected_runtime
    """), {"schema": schema, "private": capability_schema_name(schema),
            "expected_owner": owner, "expected_runtime": runtime}).scalar_one_or_none()
    if safe is not True:
        raise FinancialFenceError("Финансовая проверка недоступна")
    names = (f"{private}.financial_lock_rows(text,integer[])", f"{private}.financial_probe_group(integer)")
    integrity = db.execute(text("""
      SELECT count(*)=2 AND count(DISTINCT p.proowner)=1 AND COALESCE(bool_and(p.prosecdef AND p.prokind='f'
        AND p.proowner=owner.oid AND NOT owner.rolcanlogin AND NOT owner.rolsuper
        AND NOT owner.rolbypassrls AND NOT owner.rolcreaterole AND NOT owner.rolcreatedb
        AND NOT owner.rolreplication AND p.provolatile='v'
        AND pg_catalog.cardinality(p.proconfig)=2
        AND 'search_path=pg_catalog'=ANY(p.proconfig) AND 'row_security=on'=ANY(p.proconfig)
        AND pg_catalog.has_function_privilege(CURRENT_USER,p.oid,'EXECUTE')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          WHERE a.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
             OR (a.grantee<>p.proowner AND (a.privilege_type<>'EXECUTE' OR a.is_grantable)))
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles candidate WHERE NOT candidate.rolsuper
          AND candidate.oid<>owner.oid AND pg_catalog.pg_has_role(candidate.oid,owner.oid,'MEMBER'))
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles inherited WHERE inherited.oid<>owner.oid
          AND pg_catalog.pg_has_role(owner.oid,inherited.oid,'MEMBER'))
        AND NOT pg_catalog.pg_has_role(CURRENT_USER,owner.oid,'MEMBER')),false)
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
      WHERE p.oid IN (pg_catalog.to_regprocedure(:lock_function),pg_catalog.to_regprocedure(:probe_function))
    """), {"lock_function": names[0], "probe_function": names[1]}).scalar_one()
    if integrity is not True:
        raise FinancialFenceError("Финансовая проверка недоступна")
    try:
        backend_oid = db.execute(text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER")).scalar_one()
        if not financial_contract_is_valid(db, schema=schema, private=capability_schema_name(schema),
                                           quoted_schema=qualified, backend_oid=backend_oid):
            raise FinancialFenceError("Финансовая проверка недоступна")
    except SQLAlchemyError:
        raise FinancialFenceError("Финансовая проверка недоступна") from None
    return qualified


def _pg_lock_rows(db: Session, schema: str, kind: str, ids: list[int]) -> None:
    private = _financial_private_schema(db)
    actual = db.execute(text(f"SELECT {private}.financial_lock_rows(:kind, CAST(:ids AS integer[]))"),
                        {"kind": kind, "ids": ids}).scalar_one()
    if list(actual) != ids:
        raise FinancialFenceError("Состав обращения изменился")


def _require_clean_context(db: Session) -> None:
    if any(isinstance(obj, _CONTEXT_MODELS) for obj in (*db.new, *db.dirty, *db.deleted)):
        raise FinancialFenceError("Сначала завершите изменения обращения")


def _verify_complete_backend_reads(db: Session, schema: str) -> None:
    # A closure cannot safely be inferred from RLS-filtered Visit/link rows.
    # Hold table locks before inspecting policy catalog so policy DDL cannot
    # change the predicate between the proof and the later closure recheck.
    full_tables = ("visits", "encounters", "visit_services", "payment_invoices", "payment_invoice_visits")
    names = (*full_tables, "payments", "payment_visits", "provider_active_visit_reservations")
    db.execute(text("LOCK TABLE " + ", ".join(f"{schema}.{name}" for name in full_tables) + " IN ACCESS SHARE MODE"))
    # The column-only reads also hold table locks while RLS policies are checked.
    db.execute(text(f"SELECT id FROM {schema}.payments WHERE false"))
    db.execute(text(f"SELECT id FROM {schema}.payment_visits WHERE false"))
    db.execute(text(f"SELECT visit_id FROM {schema}.provider_active_visit_reservations WHERE false"))
    checked = db.execute(text("""
      SELECT count(*)=8 AND COALESCE(bool_and((CASE WHEN c.relname='payments' THEN
        pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'id','SELECT') AND pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'visit_id','SELECT')
          AND pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'status','SELECT')
          AND pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'provider_payment_id','SELECT')
        WHEN c.relname='payment_visits' THEN pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'id','SELECT')
          AND pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'payment_id','SELECT')
          AND pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'visit_id','SELECT')
        WHEN c.relname='provider_active_visit_reservations' THEN
          pg_catalog.has_column_privilege(CURRENT_USER,c.oid,'visit_id','SELECT')
        ELSE pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'SELECT') END) AND (
        NOT c.relrowsecurity OR (EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
          WHERE p.polrelid=c.oid AND p.polpermissive AND p.polcmd IN ('r','*')
            AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
            AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid AND NOT p.polpermissive
            AND p.polcmd IN ('r','*') AND EXISTS (SELECT 1 FROM pg_catalog.unnest(p.polroles) rid
              WHERE CASE WHEN rid=0 THEN true ELSE pg_catalog.pg_has_role(CURRENT_USER,rid,'MEMBER') END)))
      )),false)
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname=:schema AND c.relname=ANY(:tables) AND c.relkind IN ('r','p')
    """), {"schema": db.get_bind().dialect.default_schema_name, "tables": list(names)}).scalar_one()
    if checked is not True:
        raise FinancialFenceError("Финансовая проверка недоступна")


def acquire_reconciliation_mutex(db: Session, schema: str | None) -> bool:
    """Lock the durable-evidence mutex and return its verified pending state.

    Internal reconciliation callers must first lock and revalidate their
    complete Visit, Encounter and Invoice closure. A true result is evidence
    to reconcile, never permission for a financial mutation or checkout.
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        if not schema or schema != _financial_schema(db):
            raise FinancialFenceError("Сверка платежей временно недоступна")
    elif dialect != "sqlite" or schema is not None:
        raise FinancialFenceError("Сверка платежей временно недоступна")
    if schema:
        private = _financial_private_schema(db)
        function = f"{private}.reconciliation_pending_guard()"
        valid = db.execute(text("""
          SELECT p.prosecdef AND p.provolatile='v' AND p.prorettype='pg_catalog.bool'::pg_catalog.regtype
            AND p.prokind='f' AND pg_catalog.cardinality(p.proconfig)=2
            AND 'search_path=pg_catalog'=ANY(p.proconfig) AND 'row_security=on'=ANY(p.proconfig)
            AND NOT owner.rolcanlogin AND NOT owner.rolsuper AND NOT owner.rolbypassrls
            AND NOT owner.rolcreaterole AND NOT owner.rolcreatedb AND NOT owner.rolreplication
            AND pg_catalog.has_function_privilege(CURRENT_USER,p.oid,'EXECUTE')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
              WHERE a.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
                OR (a.grantee<>p.proowner AND (a.privilege_type<>'EXECUTE' OR a.is_grantable)))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles member WHERE NOT member.rolsuper
              AND member.oid<>owner.oid AND pg_catalog.pg_has_role(member.oid,owner.oid,'MEMBER'))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles inherited WHERE inherited.oid<>owner.oid
              AND pg_catalog.pg_has_role(owner.oid,inherited.oid,'MEMBER'))
          FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
          WHERE p.oid=pg_catalog.to_regprocedure(:function)
        """), {"function": function}).scalar_one_or_none()
        if valid is not True:
            raise FinancialFenceError("Сверка платежей временно недоступна")
        pending = db.execute(text(f"SELECT {private}.reconciliation_pending_guard()" )).scalar_one()
        if type(pending) is not bool:
            raise FinancialFenceError("Сверка платежей временно недоступна")
    else:
        updated = db.execute(text("UPDATE provider_reconciliation_mutex SET id=id WHERE id=1"))
        if updated.rowcount != 1:
            raise FinancialFenceError("Сверка платежей временно недоступна")
        pending = db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM provider_reconciliation_events)
              OR EXISTS(SELECT 1 FROM click_callback_receipts WHERE phase='complete')
        """)).scalar_one()
        if type(pending) is not int or pending not in (0, 1):
            raise FinancialFenceError("Сверка платежей временно недоступна")
        pending = bool(pending)
    return pending


def _pending_reconciliation(db: Session, schema: str | None) -> None:
    """After all invoice locks, deny checkout while evidence needs review."""
    pending = acquire_reconciliation_mutex(db, schema)
    if pending:
        raise FinancialFenceError("Платежи требуют операторской сверки")


def _discover_payment_closure(db: Session, requested: set[int]) -> tuple[list[int], list[int], list[int], list[tuple[int, int, int]]]:
    """Bounded transitive closure over encounter membership and invoice links."""
    visits = set(requested)
    encounters: set[int] = set()
    invoices: set[int] = set()
    for _ in range(64):
        before = (frozenset(visits), frozenset(encounters), frozenset(invoices))
        hints = db.query(Visit.id, Visit.encounter_id).filter(Visit.id.in_(visits)).all()
        if len(hints) != len(visits):
            raise FinancialFenceError("Состав обращения изменился")
        encounters.update(row.encounter_id for row in hints if row.encounter_id is not None)
        visits.update(row[0] for row in db.query(Visit.id).filter(Visit.encounter_id.in_(encounters)).all())
        invoices.update(row[0] for row in db.query(PaymentInvoiceVisit.invoice_id).filter(PaymentInvoiceVisit.visit_id.in_(visits)).all())
        visits.update(row[0] for row in db.query(PaymentInvoiceVisit.visit_id).filter(PaymentInvoiceVisit.invoice_id.in_(invoices)).all())
        if max(len(visits), len(encounters), len(invoices)) > 1000:
            raise FinancialFenceError("Обращение слишком велико для безопасной оплаты")
        if before == (frozenset(visits), frozenset(encounters), frozenset(invoices)):
            break
    else:
        raise FinancialFenceError("Состав счётов требует сверки")
    links = sorted((r.id, r.invoice_id, r.visit_id) for r in db.query(PaymentInvoiceVisit.id, PaymentInvoiceVisit.invoice_id, PaymentInvoiceVisit.visit_id)
                   .filter(PaymentInvoiceVisit.invoice_id.in_(invoices)).all())
    return sorted(visits), sorted(encounters), sorted(invoices), links


def _lock_full_financial_closure(db: Session, requested: set[int], schema: str | None):
    visits, encounters, invoices, links = _discover_payment_closure(db, requested)
    if schema:
        _pg_lock_rows(db, schema, "visit", visits)
        _pg_lock_rows(db, schema, "encounter", encounters)
        _pg_lock_rows(db, schema, "invoice", invoices)
    else:
        db.query(Visit.id).filter(Visit.id.in_(visits)).order_by(Visit.id).with_for_update().all()
        db.query(Encounter.id).filter(Encounter.id.in_(encounters)).order_by(Encounter.id).with_for_update().all()
        db.query(PaymentInvoice.id).filter(PaymentInvoice.id.in_(invoices)).order_by(PaymentInvoice.id).with_for_update().all()
    if _discover_payment_closure(db, requested) != (visits, encounters, invoices, links):
        raise FinancialFenceError("Состав счётов изменился")
    return visits, encounters, invoices, links


def _preflight_recheck(db: Session, marker: _PaymentPreflight, schema: str | None) -> None:
    # Locks acquired after a PG savepoint are released by rollback to it,
    # while the root SessionTransaction stays the same. Bind both SQLAlchemy
    # savepoint identities; a release or rollback invalidates the marker.
    if (marker.transaction is not db.get_transaction()
            or marker.session_savepoint is not db.get_nested_transaction()
            or marker.connection_savepoint is not db.connection().get_nested_transaction()
            or not marker.transaction.is_active
            or (marker.session_savepoint is not None and not marker.session_savepoint.is_active)
            or (marker.connection_savepoint is not None and not marker.connection_savepoint.is_active)):
        raise FinancialFenceError("Транзакция проверки завершилась")
    _require_clean_context(db)
    rows = (db.query(Visit.id, Visit.patient_id, Visit.encounter_id, Visit.confirmation_context_epoch)
            .filter(Visit.id.in_(marker.visit_ids)).order_by(Visit.id).all())
    if (tuple((r.id, r.patient_id, r.encounter_id, r.confirmation_context_epoch) for r in rows) != marker.contexts
            or any(r.encounter_id is not None for r in rows if r.id in marker.ungrouped)):
        raise FinancialFenceError("Контекст обращения изменился")
    visits, groups, invoices, links = _discover_payment_closure(db, set(marker.visit_ids))
    if (visits != list(marker.visit_ids) or groups != [group[0] for group in marker.groups]
            or invoices != list(marker.invoice_ids) or links != list(marker.invoice_links)):
        raise FinancialFenceError("Состав счётов изменился")
    # Mutex is acquired only after every Visit, Encounter and Invoice lock.
    _pending_reconciliation(db, schema)
    for encounter_id, generation, members in marker.groups:
        current = db.query(Encounter.generation).filter(Encounter.id == encounter_id).scalar()
        ids = tuple(row[0] for row in db.query(Visit.id).filter(Visit.encounter_id == encounter_id).order_by(Visit.id).all())
        if current != generation or ids != members:
            raise FinancialFenceError("Состав обращения изменился")
        if schema:
            probe = db.execute(text(f"SELECT {_financial_private_schema(db)}.financial_probe_group(:encounter)"),
                               {"encounter": encounter_id}).scalar_one()
            if not isinstance(probe, dict) or probe.get("members") != list(members) or not isinstance(probe.get("pending"), list):
                raise FinancialFenceError("Финансовая проверка недоступна")
            if probe["pending"]:
                raise FinancialFenceError("Есть заявка на бесплатные услуги")
        elif db.query(AllFreeRequest.id).filter(AllFreeRequest.visit_id.in_(members), AllFreeRequest.status == "pending").first():
            raise FinancialFenceError("Есть заявка на бесплатные услуги")
    for visit_id in marker.ungrouped:
        lock_visit_without_pending(db, visit_id)


def preflight_payment_groups(db: Session, visit_ids: list[int]) -> None:
    """Lock the union of groups before any payment mutation in this tx.

    This is a private application protocol, not a request flag. A marker is
    tied to this exact root transaction and cannot be extended after locks
    were acquired; callers must supply their complete batch up front.
    """
    if (not isinstance(visit_ids, list) or not visit_ids
            or any(type(value) is not int or value <= 0 for value in visit_ids)):
        raise FinancialFenceError("Некорректный список визитов")
    with db.no_autoflush:
        _require_clean_context(db)
        dialect = db.get_bind().dialect.name
        schema = None
        if dialect == "postgresql":
            db.execute(text("SET LOCAL lock_timeout='2s'"))
            if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
                raise FinancialFenceError("Проверка доступна только в READ COMMITTED")
            schema = _financial_schema(db)
            _verify_complete_backend_reads(db, schema)
        elif dialect == "sqlite":
            db.execute(text("UPDATE visits SET id=id WHERE 0"))
        else:
            raise FinancialFenceError("Неподдерживаемая база данных")
        existing = db.info.get(_PAYMENT_PREFLIGHT_KEY)
        requested = set(visit_ids)
        if isinstance(existing, _PaymentPreflight) and existing.transaction is db.get_transaction():
            if not requested.issubset(existing.visit_ids):
                raise FinancialFenceError("Все визиты нужно проверить до начала оплаты")
            _preflight_recheck(db, existing, schema)
            return
        all_ids, group_ids, invoice_ids, links = _lock_full_financial_closure(db, requested, schema)
        member_rows = (db.query(Visit.id, Visit.patient_id, Visit.encounter_id, Visit.confirmation_context_epoch)
                       .filter(Visit.id.in_(all_ids)).order_by(Visit.id).all())
        ungrouped = tuple(r.id for r in member_rows if r.encounter_id is None)
        invoice_rows = db.query(PaymentInvoice.id, PaymentInvoice.patient_id).filter(PaymentInvoice.id.in_(invoice_ids)).all()
        if len(invoice_rows) != len(invoice_ids):
            raise FinancialFenceError("Состав счётов изменился")
        patient_by_visit = {row.id: row.patient_id for row in member_rows}
        patient_by_invoice = {row.id: row.patient_id for row in invoice_rows}
        if any(patient_by_invoice.get(invoice_id) != patient_by_visit.get(link_visit_id)
               for _, invoice_id, link_visit_id in links):
            raise FinancialFenceError("Счёт не соответствует пациенту")
        encounters = db.query(Encounter).filter(Encounter.id.in_(group_ids)).order_by(Encounter.id).populate_existing().all()
        if len(encounters) != len(group_ids):
            raise FinancialFenceError("Состав обращения изменился")
        groups = []
        for encounter in encounters:
            members = tuple(sorted(r.id for r in member_rows if r.encounter_id == encounter.id))
            if (not members or encounter.patient_id is None
                    or any(r.patient_id != encounter.patient_id for r in member_rows if r.encounter_id == encounter.id)
                    or (encounter.provenance != "new" and not (encounter.provenance == "legacy_unresolved" and len(members) == 1))):
                raise FinancialFenceError("Состав обращения требует сверки")
            groups.append((encounter.id, encounter.generation, members))
        if len(member_rows) != len(all_ids) or any(type(r.confirmation_context_epoch) is not int or r.confirmation_context_epoch <= 0 for r in member_rows):
            raise FinancialFenceError("Контекст обращения требует сверки")
        marker = _PaymentPreflight(db.get_transaction(), db.get_nested_transaction(),
                                   db.connection().get_nested_transaction(), tuple(all_ids),
                                   tuple((r.id, r.patient_id, r.encounter_id, r.confirmation_context_epoch) for r in member_rows),
                                   tuple(groups), ungrouped, tuple(invoice_ids), tuple(links))
        _preflight_recheck(db, marker, schema)
        db.info[_PAYMENT_PREFLIGHT_KEY] = marker


def ensure_payment_preflight(db: Session, visit_id: int) -> None:
    """Revalidate or build the private transaction-bound group marker."""
    preflight_payment_groups(db, [visit_id])


def require_preflighted_payment_visits(db: Session, visit_id: int) -> tuple[int, ...]:
    """Revalidate an existing closure; never acquire it implicitly."""
    marker = db.info.get(_PAYMENT_PREFLIGHT_KEY)
    if (type(visit_id) is not int or visit_id < 1 or not isinstance(marker, _PaymentPreflight)
            or marker.transaction is not db.get_transaction() or visit_id not in marker.visit_ids):
        raise FinancialFenceError("Сначала проверьте всю группу оплаты")
    preflight_payment_groups(db, [visit_id])
    return marker.visit_ids


def _verify_payment_reference_fence(db: Session, schema: str) -> None:
    """Prove canonical nondeferred FK and both live 0118 writer triggers."""
    table_payment = f"{schema}.payments"
    table_links = f"{schema}.payment_visits"
    private = _financial_private_schema(db)
    trigger_function = f"{private}.financial_visit_reference_fence()"
    base_function = f"{private}.financial_probe_group(integer)"
    safe = db.execute(text("""
      SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint fk
        WHERE fk.contype='f' AND fk.conrelid=pg_catalog.to_regclass(:links)
          AND fk.confrelid=pg_catalog.to_regclass(:payment) AND fk.convalidated AND NOT fk.condeferrable
          AND fk.conkey=ARRAY[(SELECT attnum FROM pg_catalog.pg_attribute WHERE attrelid=fk.conrelid AND attname='payment_id')]::smallint[]
          AND fk.confkey=ARRAY[(SELECT attnum FROM pg_catalog.pg_attribute WHERE attrelid=fk.confrelid AND attname='id')]::smallint[])
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute a WHERE a.attrelid=pg_catalog.to_regclass(:links)
          AND a.attname IN ('payment_id','visit_id') AND NOT a.attnotnull)
        AND (SELECT count(*)=2 AND COALESCE(bool_and(t.tgenabled IN ('O','A') AND NOT t.tgisinternal
          AND t.tgtype=29 AND t.tgattr::text='' AND t.tgqual IS NULL
          AND p.oid=pg_catalog.to_regprocedure(:trigger_function) AND p.proowner=base.proowner
          AND p.prosecdef AND 'search_path=pg_catalog'=ANY(p.proconfig) AND 'row_security=on'=ANY(p.proconfig)),false)
          FROM (VALUES ('payments','trg_financial_payment'), ('payment_visits','trg_financial_payment_link')) AS expected(tab,trig)
          JOIN pg_catalog.pg_class c ON c.oid=CASE expected.tab WHEN 'payments' THEN pg_catalog.to_regclass(:payment) ELSE pg_catalog.to_regclass(:links) END
          JOIN pg_catalog.pg_trigger t ON t.tgrelid=c.oid AND t.tgname=expected.trig
          JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
          JOIN pg_catalog.pg_proc base ON base.oid=pg_catalog.to_regprocedure(:base_function))
        AND pg_catalog.current_setting('session_replication_role')='origin'
    """), {"payment": table_payment, "links": table_links, "trigger_function": trigger_function,
            "base_function": base_function}).scalar_one_or_none()
    if safe is not True:
        raise FinancialFenceError("Связи платежа требуют сверки")


def preflight_payment_record(db: Session, payment_id: int) -> LockedPaymentRecord:
    """Lock a payment's full Visit union before locking and rechecking Payment.

    This routine is for staff confirmation, not provider-debit settlement. A
    caller must authorize its actor before entering and must perform no external
    action before the transaction commits. Canonical Payment has a primary
    Visit; an unproven historical NULL is deliberately rejected.
    """
    if type(payment_id) is not int or payment_id <= 0:
        raise FinancialFenceError("Платёж не найден")
    with db.no_autoflush:
        _require_clean_context(db)
        schema = None
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL lock_timeout='2s'"))
            if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
                raise FinancialFenceError("Проверка доступна только в READ COMMITTED")
            schema = _financial_schema(db)
            _verify_complete_backend_reads(db, schema)
            _verify_payment_reference_fence(db, schema)
        elif db.get_bind().dialect.name == "sqlite":
            db.execute(text("UPDATE visits SET id=id WHERE 0"))
        else:
            raise FinancialFenceError("Неподдерживаемая база данных")
        reference = db.query(Payment.id, Payment.visit_id).filter(Payment.id == payment_id).first()
        if reference is None or type(reference.visit_id) is not int or reference.visit_id <= 0:
            raise FinancialFenceError("Платёж требует сверки визита")
        links = tuple((row.id, row.visit_id) for row in db.query(PaymentVisit.id, PaymentVisit.visit_id)
                      .filter(PaymentVisit.payment_id == payment_id).order_by(PaymentVisit.id).all())
        if any(type(link_id) is not int or type(visit_id) is not int or visit_id <= 0 for link_id, visit_id in links):
            raise FinancialFenceError("Связи платежа требуют сверки")
        ids = sorted({reference.visit_id, *(visit_id for _, visit_id in links)})
        preflight_payment_groups(db, ids)
        payment = (db.query(Payment.id, Payment.visit_id).filter(Payment.id == payment_id)
                   .with_for_update(nowait=True).first())
        actual_links = tuple((row.id, row.visit_id) for row in db.query(PaymentVisit.id, PaymentVisit.visit_id)
                             .filter(PaymentVisit.payment_id == payment_id).order_by(PaymentVisit.id).all())
        if payment is None or payment.visit_id != reference.visit_id or actual_links != links:
            raise FinancialFenceError("Связи платежа изменились")
        return LockedPaymentRecord(payment_id, reference.visit_id, tuple(ids), links)


def lock_group_without_pending(db: Session, visit_id: int) -> None:
    """Fence payment/confirmation without rejecting previous partial payments.

    Caller owns authorization, rollback and the remaining business checks. All
    membership writers must already obey 0118; provider callbacks require
    durable receipt before they may encounter this guard.
    """
    if type(visit_id) is not int or visit_id <= 0:
        raise FinancialFenceError("Визит не найден")
    if db.new or db.dirty or db.deleted:
        raise FinancialFenceError("Сначала сохраните изменения в транзакции")
    dialect = db.get_bind().dialect.name
    schema = None
    if dialect == "sqlite":
        db.execute(text("UPDATE visits SET id=id WHERE 0"))
    elif dialect == "postgresql":
        if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
            raise FinancialFenceError("Проверка доступна только в READ COMMITTED")
        schema = _financial_schema(db)
        _verify_complete_backend_reads(db, schema)
    else:
        raise FinancialFenceError("Неподдерживаемая база данных")
    hint = db.query(Visit.encounter_id, Visit.patient_id).filter(Visit.id == visit_id).first()
    if hint is None:
        raise FinancialFenceError("Визит не найден")
    if hint.encounter_id is None:
        # 0114 checks even nullable legacy request records under the locked
        # Visit; any membership writer must first lock this same Visit.
        lock_visit_without_pending(db, visit_id)
        current = db.query(Visit.encounter_id).filter(Visit.id == visit_id).first()
        if current is None or current.encounter_id is not None:
            raise FinancialFenceError("Состав обращения изменился")
        return
    ids = sorted(row[0] for row in db.query(Visit.id).filter(Visit.encounter_id == hint.encounter_id).all())
    if visit_id not in ids:
        raise FinancialFenceError("Состав обращения изменился")
    if schema:
        _pg_lock_rows(db, schema, "visit", ids)
        _pg_lock_rows(db, schema, "encounter", [hint.encounter_id])
    else:
        db.query(Visit.id).filter(Visit.id.in_(ids)).order_by(Visit.id).with_for_update().all()
    encounter_query = db.query(Encounter).filter(Encounter.id == hint.encounter_id)
    if not schema:
        encounter_query = encounter_query.with_for_update()
    encounter = encounter_query.populate_existing().first()
    visits = db.query(Visit).filter(Visit.id.in_(ids)).order_by(Visit.id).populate_existing().all()
    after = sorted(row[0] for row in db.query(Visit.id).filter(Visit.encounter_id == hint.encounter_id).all())
    if (encounter is None or encounter.patient_id != hint.patient_id or after != ids
            or len(visits) != len(ids) or any(v.patient_id != hint.patient_id or v.encounter_id != hint.encounter_id for v in visits)
            or (encounter.provenance != "new" and not (encounter.provenance == "legacy_unresolved" and len(ids) == 1))):
        raise FinancialFenceError("Состав обращения требует сверки")
    if schema:
        probe = db.execute(text(f"SELECT {_financial_private_schema(db)}.financial_probe_group(:encounter)"),
                           {"encounter": hint.encounter_id}).scalar_one()
        if not isinstance(probe, dict) or probe.get("members") != ids or not isinstance(probe.get("pending"), list):
            raise FinancialFenceError("Финансовая проверка недоступна")
        if probe["pending"]:
            raise FinancialFenceError("Есть заявка на бесплатные услуги")
    else:
        if db.query(AllFreeRequest.id).filter(AllFreeRequest.visit_id.in_(ids), AllFreeRequest.status == "pending").first():
            raise FinancialFenceError("Есть заявка на бесплатные услуги")


def lock_financial_group(
    db: Session, visit_id: int, *, allow_all_free_request_id: int | None = None,
    allow_sibling_pending_for_staging: bool = False,
) -> LockedFinancialGroup:
    """Lock sorted visits -> encounter -> invoices and validate fresh evidence.

    Must be called after locking/authorizing the actor and patient, and only
    after the database-wide writer, receipt and RLS prerequisites above have
    been installed. A repeated membership read is NOT a substitute for that
    writer fence. The nonowner backend proves direct visibility and compares
    its rows with a separately provisioned RLS-complete capability snapshot.
    """
    if type(visit_id) is not int or visit_id <= 0:
        raise FinancialFenceError("Визит не найден")
    if allow_all_free_request_id is not None and (
        type(allow_all_free_request_id) is not int or allow_all_free_request_id <= 0
    ):
        raise FinancialFenceError("Некорректная заявка")
    if type(allow_sibling_pending_for_staging) is not bool or (
        allow_sibling_pending_for_staging and allow_all_free_request_id is not None
    ):
        raise FinancialFenceError("Некорректный режим заявки")
    if db.new or db.dirty or db.deleted:
        raise FinancialFenceError("Сначала сохраните изменения в транзакции")

    dialect = db.get_bind().dialect.name
    schema = None
    if dialect == "sqlite":
        db.execute(text("UPDATE visits SET id=id WHERE 0"))
    elif dialect == "postgresql":
        if db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
            raise FinancialFenceError("Проверка доступна только в READ COMMITTED")
        schema = _financial_schema(db)
        _verify_complete_backend_reads(db, schema)
    else:
        raise FinancialFenceError("Неподдерживаемая база данных")

    hint = db.query(Visit.encounter_id, Visit.patient_id).filter(Visit.id == visit_id).first()
    if hint is None or hint.encounter_id is None or hint.patient_id is None:
        raise FinancialFenceError("Требуется сверка обращения")
    encounter_id, patient_id = hint
    all_ids, group_ids, invoice_ids, closure_links = _lock_full_financial_closure(db, {visit_id}, schema)
    all_visits = tuple(db.query(Visit).filter(Visit.id.in_(all_ids)).order_by(Visit.id).populate_existing().all())
    all_encounters = tuple(db.query(Encounter).filter(Encounter.id.in_(group_ids)).order_by(Encounter.id).populate_existing().all())
    if (len(all_visits) != len(all_ids) or len(all_encounters) != len(group_ids)
            or any(v.patient_id != patient_id or v.encounter_id is None for v in all_visits)
            or any(e.patient_id != patient_id or (e.provenance != "new" and not (
                e.provenance == "legacy_unresolved" and sum(v.encounter_id == e.id for v in all_visits) == 1
            )) for e in all_encounters)):
        raise FinancialFenceError("Состав связанных счетов требует сверки")
    ids = sorted(row[0] for row in db.query(Visit.id).filter(Visit.encounter_id == encounter_id).all())
    if visit_id not in ids:
        raise FinancialFenceError("Состав обращения изменился")
    visit_query = db.query(Visit).filter(Visit.id.in_(ids)).order_by(Visit.id)
    encounter_query = db.query(Encounter).filter(Encounter.id == encounter_id)
    visits = tuple(visit_query.populate_existing().all())
    encounter = encounter_query.populate_existing().first()
    after = sorted(row[0] for row in db.query(Visit.id).filter(Visit.encounter_id == encounter_id).all())
    if (encounter is None or encounter.patient_id != patient_id or encounter.provenance != "new"
            or after != ids or len(visits) != len(ids)
            or any(v.encounter_id != encounter_id or v.patient_id != patient_id for v in visits)):
        raise FinancialFenceError("Состав обращения изменился или требует сверки")

    # No child FOR UPDATE: a concurrent VisitService writer already owns the
    # child and its 0102 trigger locks the Visit, so reversing locks deadlocks.
    lines = (db.query(VisitService).filter(VisitService.visit_id.in_(all_ids))
             .order_by(VisitService.visit_id, VisitService.id).populate_existing().all())
    all_gross = {v.id: Decimal("0.00") for v in all_visits}
    seen = set()
    currencies = set()
    for line in lines:
        if type(line.qty) is not int or not 0 < line.qty <= 2147483647:
            raise FinancialFenceError("Количество услуг требует сверки")
        if not isinstance(line.currency, str) or not line.currency.strip():
            raise FinancialFenceError("Валюта услуги требует сверки")
        currencies.add(line.currency)
        seen.add(line.visit_id)
        all_gross[line.visit_id] += _money(line.price) * line.qty
        if all_gross[line.visit_id] > Decimal("9999999999.99"):
            raise FinancialFenceError("Стоимость услуг превышает допустимую")
    if seen != set(all_ids) or len(currencies) > 1:
        raise FinancialFenceError("Состав услуг требует сверки")
    gross = {visit_id: all_gross[visit_id] for visit_id in ids}

    if not schema:
        payment_ids = db.query(PaymentVisit.payment_id).filter(PaymentVisit.visit_id.in_(all_ids))
        payments = db.query(Payment.id).filter(or_(Payment.visit_id.in_(all_ids), Payment.id.in_(payment_ids))).first()
        if payments is not None:
            raise FinancialFenceError("Платежи требуют финансовой сверки")
        if (db.query(PaymentWebhook.id).filter(PaymentWebhook.visit_id.in_(all_ids)).first() is not None
                or db.query(PaymentTransaction.id).filter(PaymentTransaction.visit_id.in_(all_ids)).first() is not None
                or db.query(ProviderAttemptVisit.id).filter(ProviderAttemptVisit.visit_id_snapshot.in_(all_ids)).first() is not None):
            raise FinancialFenceError("История провайдера требует финансовой сверки")
        if db.query(ProviderActiveVisitReservation.visit_id).filter(
            ProviderActiveVisitReservation.visit_id.in_(all_ids)
        ).first() is not None:
            raise FinancialFenceError("Онлайн-оплата требует финансовой сверки")
        if db.query(Invoice.id).filter(Invoice.visit_id.in_(all_ids)).first() is not None:
            raise FinancialFenceError("Счёт биллинга требует финансовой сверки")

    invoice_query = db.query(PaymentInvoice).filter(PaymentInvoice.id.in_(invoice_ids)).order_by(PaymentInvoice.id)
    invoices = tuple(invoice_query.populate_existing().all())
    # A verified, unresolved external debit must not be lost behind an
    # approval. This mutex is after all relevant Invoice locks.
    _pending_reconciliation(db, schema)
    links = tuple(db.query(PaymentInvoiceVisit).filter(PaymentInvoiceVisit.invoice_id.in_(invoice_ids))
                  .order_by(PaymentInvoiceVisit.invoice_id, PaymentInvoiceVisit.visit_id,
                            PaymentInvoiceVisit.id).populate_existing().all())
    if sorted((link.id, link.invoice_id, link.visit_id) for link in links) != closure_links:
        raise FinancialFenceError("Состав счетов изменился")
    probe = None
    if schema:
        for group in all_encounters:
            current = db.execute(text(f"SELECT {_financial_private_schema(db)}.financial_probe_group(:encounter)"),
                                 {"encounter": group.id}).scalar_one()
            members = sorted(v.id for v in all_visits if v.encounter_id == group.id)
            group_invoice_ids = sorted({link.invoice_id for link in links if link.visit_id in members})
            if (not isinstance(current, dict) or current.get("members") != members
                    or current.get("lines") != sorted(line.id for line in lines if line.visit_id in members)
                    or current.get("invoices") != group_invoice_ids
                    or current.get("links") != sorted(link.id for link in links if link.invoice_id in group_invoice_ids)
                    or type(current.get("history")) is not bool):
                raise FinancialFenceError("Финансовая проверка недоступна")
            if current["history"]:
                raise FinancialFenceError("Платежи требуют финансовой сверки")
            if group.id == encounter_id:
                probe = current
    pending_query = db.query(AllFreeRequest).filter(AllFreeRequest.visit_id.in_(ids), AllFreeRequest.status == "pending").order_by(AllFreeRequest.id)
    if not schema:
        pending_query = pending_query.with_for_update()
    pending = tuple(pending_query.populate_existing().all())
    if schema:
        if not isinstance(probe, dict) or probe.get("pending") != [r.id for r in pending]:
            raise FinancialFenceError("Финансовая проверка недоступна")
    if (any(r.visit_id not in ids or r.encounter_id != encounter_id or r.patient_id != patient_id for r in pending)
            or len({r.visit_id for r in pending}) != len(pending)):
        raise FinancialFenceError("Заявки требуют сверки")
    selected = [r for r in pending if r.id == allow_all_free_request_id]
    if allow_all_free_request_id is not None and (len(selected) != 1 or selected[0].visit_id != visit_id):
        raise FinancialFenceError("Заявка не соответствует обращению")
    if allow_all_free_request_id is None and pending:
        if not allow_sibling_pending_for_staging or any(r.visit_id == visit_id for r in pending):
            raise FinancialFenceError("Есть заявка на бесплатные услуги")
    if len(invoices) != len(invoice_ids):
        raise FinancialFenceError("Состав счетов изменился")
    if not schema and db.query(ProviderReconciliationEvent.id).filter(
        or_(ProviderReconciliationEvent.invoice_id_snapshot.in_(invoice_ids),
            ProviderReconciliationEvent.target_kind == "unmatched")
    ).first() is not None:
        raise FinancialFenceError("Подтверждение оплаты требует сверки")
    linked_visits: set[int] = set()
    invoice_sums: dict[int, Decimal] = {invoice.id: Decimal("0.00") for invoice in invoices}
    for link in links:
        if (link.visit_id not in all_gross or link.visit_id in linked_visits
                or _money(link.visit_amount) != all_gross[link.visit_id]):
            raise FinancialFenceError("Распределение счёта изменилось")
        linked_visits.add(link.visit_id)
        invoice_sums[link.invoice_id] += _money(link.visit_amount)
    for invoice in invoices:
        if (invoice.patient_id != patient_id or invoice.currency != next(iter(currencies)) or invoice.status != "pending"
                or invoice.provider is not None or invoice.provider_payment_id is not None
                or invoice.provider_transaction_id is not None or invoice.payment_url is not None
                or invoice.provider_data is not None or _money(invoice.total_amount) != invoice_sums[invoice.id]):
            raise FinancialFenceError("Состояние счёта требует сверки")
    return LockedFinancialGroup(db, db.get_transaction(), db.get_nested_transaction(), db.connection().get_nested_transaction(),
                                encounter, visits, invoices, links, pending, MappingProxyType(gross),
                                tuple((link.id, _money(link.visit_amount)) for link in links),
                                tuple((invoice.id, _money(invoice.total_amount)) for invoice in invoices))


def _write_draft_requote(group: LockedFinancialGroup, amount_by_visit: dict[int, Decimal], *, discount_only: bool) -> None:
    db = group.session
    if (group.transaction is not db.get_transaction() or not group.transaction.is_active
            or group.session_savepoint is not db.get_nested_transaction()
            or group.connection_savepoint is not db.connection().get_nested_transaction()
            or (group.session_savepoint is not None and not group.session_savepoint.is_active)
            or (group.connection_savepoint is not None and not group.connection_savepoint.is_active)):
        raise FinancialFenceError("Транзакция расчёта завершилась")
    if (tuple((link.id, _money(link.visit_amount)) for link in group.links) != group.baseline_links
            or tuple((invoice.id, _money(invoice.total_amount)) for invoice in group.invoices) != group.baseline_invoices):
        raise FinancialFenceError("Счёт изменился после проверки")
    if set(amount_by_visit) != set(group.gross_by_visit):
        raise FinancialFenceError("Неполное распределение обращения")
    nets = {visit_id: _money(amount) for visit_id, amount in amount_by_visit.items()}
    if discount_only and any(nets[visit_id] > gross for visit_id, gross in group.gross_by_visit.items()):
        raise FinancialFenceError("Скидка превышает стоимость услуг")
    totals = {invoice.id: Decimal("0.00") for invoice in group.invoices}
    for link in group.links:
        totals[link.invoice_id] += nets.get(link.visit_id, _money(link.visit_amount))
        if totals[link.invoice_id] > Decimal("9999999999.99"):
            raise FinancialFenceError("Сумма счёта превышает допустимую")
    for link in group.links:
        if link.visit_id in nets:
            link.visit_amount = nets[link.visit_id]
    for invoice in group.invoices:
        invoice.total_amount = totals[invoice.id]


def requote_draft_invoices(group: LockedFinancialGroup, net_by_visit: dict[int, Decimal]) -> None:
    """Apply an aggregate discount, bounded by the locked baseline."""
    _write_draft_requote(group, net_by_visit, discount_only=True)


def requote_draft_invoice_prices(group: LockedFinancialGroup, repriced_by_visit: dict[int, Decimal]) -> None:
    """Apply server-calculated repricing, allowing a controlled increase.

    Existing benefits and approved All Free must be checked through the
    complete 0125 capability before this function becomes publicly reachable.
    """
    # Do not make this callable a bypass around an earlier benefit/all-free
    # decision: the reader checks complete RLS visibility and all linked groups.
    from app.services.encounter_benefit_net import (
        require_no_existing_financial_adjustment,
    )

    for visit in group.visits:
        require_no_existing_financial_adjustment(group.session, visit.id)
    _write_draft_requote(group, repriced_by_visit, discount_only=False)
