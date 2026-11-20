"""Validate complete benefit evidence and derive exact per-line net amounts.

The caller must authorize the selected Visit before calling. This read model
does not approve a benefit or guarantee a provider payment. PostgreSQL uses a
single STABLE capability statement; SQLite reserves its writer before reads.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from types import MappingProxyType

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.all_free_request import AllFreeRequest, AllFreeRequestLine
from app.models.encounter import Encounter
from app.models.encounter_benefit_ledger import (
    EncounterBenefitAllocation,
    EncounterBenefitApplication,
    EncounterBenefitEvent,
    EncounterBenefitVisitSnapshot,
)
from app.models.visit import Visit, VisitService
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_private_schema,
    _financial_schema,
)
from app.services.money_input import MoneyInputError, parse_money


class BenefitQuoteError(ValueError):
    """Stored benefit evidence is incomplete or its context has changed."""


@dataclass(frozen=True)
class BenefitVisitQuote:
    total: Decimal
    line_totals: Mapping[int, Decimal]
    has_benefit: bool = False
    patient_id: int | None = None
    encounter_id: int | None = None
    visit_context_epoch: int | None = None
    snapshot_digest: str | None = None
    currency: str | None = None


def _amount(value: object) -> Decimal:
    try:
        return parse_money(value)
    except (MoneyInputError, TypeError, ValueError) as exc:
        raise BenefitQuoteError("Льгота требует финансовой сверки") from exc


def _line_currency(lines: list, *, visit_id: int | None = None) -> str | None:
    known: set[str] = set()
    unknown = False
    for line in lines:
        if not isinstance(line, dict):
            raise BenefitQuoteError("Валюта услуг требует проверки")
        if visit_id is not None and line.get("visit") != visit_id:
            continue
        value = line.get("currency")
        if value is None or value == "":
            unknown = True
            continue
        if (type(value) is not str or len(value) != 3 or not value.isascii()
                or not value.isalpha() or not value.isupper()):
            raise BenefitQuoteError("Валюта услуг требует проверки")
        known.add(value)
    if len(known) > 1:
        raise BenefitQuoteError("Услуги в разных валютах требуют сверки")
    return next(iter(known)) if known and not unknown else None


def _snapshot_digest(snapshot: dict) -> str:
    """Bind validated evidence, without treating the digest as authority.

    Snapshot arrays are sets of database rows, so their order is canonicalized
    before hashing. The digest stays internal and must be signed by a caller
    that needs an authorization or review capability.
    """
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            items = [normalize(item) for item in value]
            return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise BenefitQuoteError("Стоимость услуг требует проверки")
            return format(value, "f")
        if value is None or type(value) in (str, int, bool):
            return value
        raise BenefitQuoteError("Стоимость услуг требует проверки")

    encoded = json.dumps(normalize(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(b"visit-financial-quote-v1\0" + encoded).hexdigest()


def _sqlite_snapshot(db: Session, visit_id: int) -> dict:
    # Reserve the single writer before multiple reads so they share a stable
    # clinical/financial snapshot. No application commit is performed here.
    db.execute(text("UPDATE visits SET id=id WHERE 0"))
    selected = db.query(Visit).filter(Visit.id == visit_id).populate_existing().first()
    if selected is None:
        return {"visible": True, "selected": None}
    encounter = (db.query(Encounter).filter(Encounter.id == selected.encounter_id).populate_existing().first()
                 if selected.encounter_id else None)
    visits = (db.query(Visit).filter(Visit.encounter_id == selected.encounter_id).order_by(Visit.id).populate_existing().all()
              if selected.encounter_id else [selected])
    visit_ids = [v.id for v in visits]
    lines = db.query(VisitService).filter(VisitService.visit_id.in_(visit_ids)).order_by(VisitService.id).populate_existing().all()
    apps = (db.query(EncounterBenefitApplication).filter(EncounterBenefitApplication.encounter_id == selected.encounter_id).populate_existing().all()
            if selected.encounter_id else [])
    ids = [a.id for a in apps]
    snapshots = db.query(EncounterBenefitVisitSnapshot).filter(EncounterBenefitVisitSnapshot.application_id.in_(ids)).populate_existing().all()
    allocations = db.query(EncounterBenefitAllocation).filter(EncounterBenefitAllocation.application_id.in_(ids)).populate_existing().all()
    events = db.query(EncounterBenefitEvent).filter(EncounterBenefitEvent.application_id.in_(ids)).populate_existing().all()
    approved_all_free = [r[0] for r in db.query(AllFreeRequest.id).filter(
        AllFreeRequest.visit_id.in_(visit_ids), AllFreeRequest.status == "approved"
    ).order_by(AllFreeRequest.id).all()]
    return {
        "visible": True,
        "selected": {"id": selected.id, "patient": selected.patient_id, "encounter": selected.encounter_id},
        "encounter": ({"id": encounter.id, "patient": encounter.patient_id, "generation": encounter.generation,
                       "provenance": encounter.provenance} if encounter else None),
        "visits": [{"id": v.id, "patient": v.patient_id, "encounter": v.encounter_id, "epoch": v.confirmation_context_epoch} for v in visits],
        "lines": [{"id": line.id, "visit": line.visit_id, "service": line.service_id, "qty": line.qty,
                   "price": line.price, "currency": line.currency} for line in lines],
        "applications": [{"id": a.id, "encounter": a.encounter_id, "patient": a.patient_id, "generation": a.encounter_generation,
                          "gross": a.gross_total, "discount": a.benefit_total, "net": a.net_total} for a in apps],
        "snapshots": [{"app": s.application_id, "visit": s.visit_id, "visit_snapshot": s.visit_id_snapshot,
                       "patient": s.patient_id, "encounter": s.encounter_id, "epoch": s.visit_context_epoch} for s in snapshots],
        "allocations": [{"app": a.application_id, "visit": a.visit_id, "visit_snapshot": a.visit_id_snapshot,
                         "line": a.visit_service_id, "line_snapshot": a.visit_service_id_snapshot, "service": a.service_id_snapshot,
                         "epoch": a.visit_context_epoch, "qty": a.quantity, "unit": a.unit_price, "gross": a.gross_amount,
                         "discount": a.benefit_amount, "net": a.net_amount} for a in allocations],
        "events": [{"app": e.application_id, "kind": e.event_type} for e in events],
        "approved_all_free": approved_all_free,
    }


def require_postgres_quote_capability(db: Session) -> str:
    """Prove the private quote function before a single-statement batch read."""
    try:
        _financial_schema(db)
    except FinancialFenceError as exc:
        raise BenefitQuoteError("Льгота временно недоступна") from exc
    private = _financial_private_schema(db)
    function = f"{private}.encounter_benefit_quote(integer)"
    lock_function = f"{private}.financial_probe_group(integer)"
    valid = db.execute(text("""
      SELECT p.prosecdef AND p.provolatile='s' AND p.prorettype='pg_catalog.jsonb'::pg_catalog.regtype
        AND p.proowner=base.proowner AND p.prokind='f' AND pg_catalog.cardinality(p.proconfig)=2
        AND 'search_path=pg_catalog'=ANY(p.proconfig) AND 'row_security=on'=ANY(p.proconfig)
        AND pg_catalog.has_function_privilege(CURRENT_USER,p.oid,'EXECUTE')
        AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          WHERE a.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER))
            OR (a.grantee<>p.proowner AND (a.privilege_type<>'EXECUTE' OR a.is_grantable)))
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_proc base ON base.oid=pg_catalog.to_regprocedure(:base)
      WHERE p.oid=pg_catalog.to_regprocedure(:function)
    """), {"base": lock_function, "function": function}).scalar_one_or_none()
    if valid is not True:
        raise BenefitQuoteError("Льгота временно недоступна")
    return private


def _read_snapshot(db: Session, visit_id: int) -> dict:
    if type(visit_id) is not int or visit_id <= 0:
        raise BenefitQuoteError("Визит не найден")
    with db.no_autoflush:
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            snapshot = _sqlite_snapshot(db, visit_id)
        elif dialect == "postgresql":
            private = require_postgres_quote_capability(db)
            snapshot = db.execute(text(f"SELECT {private}.encounter_benefit_quote(:visit_id)"), {"visit_id": visit_id}).scalar_one()
        else:
            raise BenefitQuoteError("Неподдерживаемая база данных")
    if not isinstance(snapshot, dict) or snapshot.get("visible") is not True:
        raise BenefitQuoteError("Льгота временно недоступна")
    return snapshot


def benefit_visit_quote(db: Session, visit_id: int) -> BenefitVisitQuote | None:
    """Return validated net quote or None if the group has no benefit.

    A NULL/missing live ID, partial historical evidence, status event, changed
    membership, epoch, quantity, price or allocation fails closed. None does
    not mean an authorization decision: payment writers still need the group
    preflight and independently verified provider settlement protocol.
    """
    quote = visit_financial_quote(db, visit_id)
    return quote if quote.has_benefit else None


def visit_financial_quote(db: Session, visit_id: int) -> BenefitVisitQuote:
    """Read exact aggregate line amounts from one complete visible snapshot.

    A proven absence of a benefit retains gross prices. The function never
    interprets a failed or filtered capability as absence of a decision.
    Unflushed changes are rejected, because they are not in the snapshot.
    """
    sensitive_models = (Visit, VisitService, Encounter, AllFreeRequest, AllFreeRequestLine, EncounterBenefitApplication,
                        EncounterBenefitAllocation, EncounterBenefitVisitSnapshot, EncounterBenefitEvent)
    if any(isinstance(obj, sensitive_models) for obj in (*db.new, *db.dirty, *db.deleted)):
        raise BenefitQuoteError("Сначала сохраните изменения обращения")
    snapshot = _read_snapshot(db, visit_id)
    return quote_from_financial_snapshot(snapshot, visit_id=visit_id)


def quote_from_financial_snapshot(snapshot: object, *, visit_id: int) -> BenefitVisitQuote:
    """Validate already captured evidence without performing any new reads."""
    if not isinstance(snapshot, dict) or snapshot.get("visible") is not True:
        raise BenefitQuoteError("Льгота временно недоступна")
    selected, members = snapshot.get("selected"), snapshot.get("visits")
    if not isinstance(selected, dict) or selected.get("id") != visit_id or not isinstance(members, list):
        raise BenefitQuoteError("Стоимость услуг требует проверки")
    current = [row for row in members if isinstance(row, dict) and row.get("id") == visit_id]
    if (len(current) != 1 or current[0].get("patient") != selected.get("patient")
            or current[0].get("encounter") != selected.get("encounter") or type(current[0].get("epoch")) is not int):
        raise BenefitQuoteError("Контекст визита изменился")
    identity = {"patient_id": selected.get("patient"), "encounter_id": selected.get("encounter"),
                "visit_context_epoch": current[0]["epoch"]}
    adjusted = validate_benefit_snapshot(snapshot, visit_id=visit_id)
    digest = _snapshot_digest(snapshot)
    rows = snapshot.get("lines")
    if not isinstance(rows, list):
        raise BenefitQuoteError("Стоимость услуг требует проверки")
    currency = _line_currency(rows, visit_id=visit_id)
    if adjusted is not None:
        group_currency = _line_currency(rows)
        if group_currency is None:
            raise BenefitQuoteError("Валюта льготного обращения требует сверки")
        # A Visit without its own lines still belongs to this one-currency
        # approved group; its exact total is zero in that currency.
        if not adjusted.line_totals:
            currency = group_currency
        return BenefitVisitQuote(adjusted.total, MappingProxyType(dict(adjusted.line_totals)), has_benefit=True,
                                 snapshot_digest=digest, currency=currency, **identity)
    totals: dict[int, Decimal] = {}
    with localcontext() as context:
        context.prec = 40  # Numeric(12,2) times an INTEGER and bounded sums.
        for row in rows:
            if not isinstance(row, dict):
                raise BenefitQuoteError("Стоимость услуг требует проверки")
            if row.get("visit") != visit_id:
                continue
            line_id, qty = row.get("id"), row.get("qty")
            if type(line_id) is not int or line_id <= 0 or line_id in totals or type(qty) is not int or not 0 < qty <= 2147483647:
                raise BenefitQuoteError("Состав услуг требует проверки")
            amount = _amount(row.get("price")) * qty
            if amount > Decimal("9999999999.99"):
                raise BenefitQuoteError("Стоимость услуг превышает допустимую сумму")
            totals[line_id] = amount
        total = sum(totals.values(), Decimal("0.00"))
    if total > Decimal("9999999999.99"):
        raise BenefitQuoteError("Стоимость услуг превышает допустимую сумму")
    return BenefitVisitQuote(total, MappingProxyType(totals), snapshot_digest=digest, currency=currency, **identity)


def require_no_existing_financial_adjustment(db: Session, visit_id: int) -> None:
    """Temporarily refuse repricing over an existing audited decision.

    An approved benefit/all-free decision requires explicit versioned admin
    reapproval before its price can change. This is an intermediate safe
    limitation, not the completed correction workflow.
    """
    decision_models = (Visit, Encounter, AllFreeRequest, AllFreeRequestLine, EncounterBenefitApplication,
                       EncounterBenefitAllocation, EncounterBenefitVisitSnapshot, EncounterBenefitEvent)
    if any(isinstance(obj, decision_models) for obj in (*db.new, *db.dirty, *db.deleted)):
        raise FinancialFenceError("Решение о льготе или бесплатных услугах изменяется")
    try:
        snapshot = _read_snapshot(db, visit_id)
    except BenefitQuoteError as exc:
        raise FinancialFenceError("Проверка прежнего решения недоступна") from exc
    if (not isinstance(snapshot.get("selected"), dict) or snapshot["selected"].get("id") != visit_id
            or not isinstance(snapshot.get("applications"), list)
            or not isinstance(snapshot.get("approved_all_free"), list)):
        raise FinancialFenceError("Проверка прежнего решения недоступна")
    if snapshot["applications"] or snapshot["approved_all_free"]:
        raise FinancialFenceError("Требуется повторное решение администратора по льготе или бесплатным услугам")


def validate_benefit_snapshot(snapshot: object, *, visit_id: int) -> BenefitVisitQuote | None:
    """Validate every group epoch/line allocation and return one Visit net."""
    with localcontext() as context:
        context.prec = 40
        return _validate_benefit_snapshot(snapshot, visit_id=visit_id)


def _validate_benefit_snapshot(snapshot: object, *, visit_id: int) -> BenefitVisitQuote | None:
    if not isinstance(snapshot, dict) or snapshot.get("visible") is not True:
        raise BenefitQuoteError("Льгота временно недоступна")
    selected = snapshot.get("selected")
    if not isinstance(selected, dict) or selected.get("id") != visit_id:
        raise BenefitQuoteError("Визит не найден")
    apps = snapshot.get("applications")
    if not isinstance(apps, list) or len(apps) > 1:
        raise BenefitQuoteError("Льгота требует сверки")
    if not apps:
        return None
    app = apps[0]
    encounter = snapshot.get("encounter")
    visits, lines = snapshot.get("visits"), snapshot.get("lines")
    snapshots, allocations, events = snapshot.get("snapshots"), snapshot.get("allocations"), snapshot.get("events")
    if (not isinstance(app, dict) or not isinstance(encounter, dict)
            or not all(isinstance(value, list) for value in (visits, lines, snapshots, allocations, events))
            or events or not visits or not allocations
            or encounter.get("provenance") != "new" or encounter.get("id") != selected.get("encounter")
            or encounter.get("patient") != selected.get("patient") or app.get("encounter") != encounter.get("id")
            or app.get("patient") != selected.get("patient") or app.get("generation") != encounter.get("generation")):
        raise BenefitQuoteError("Контекст льготы требует сверки")
    visit_by_id = {row.get("id"): row for row in visits if isinstance(row, dict)}
    if (len(visit_by_id) != len(visits) or visit_id not in visit_by_id
            or any(row.get("patient") != selected.get("patient") or row.get("encounter") != encounter.get("id")
                   or type(row.get("epoch")) is not int or row["epoch"] <= 0 for row in visit_by_id.values())):
        raise BenefitQuoteError("Состав обращения изменился")
    evidence_by_visit = {row.get("visit"): row for row in snapshots if isinstance(row, dict)}
    if (len(evidence_by_visit) != len(snapshots) or set(evidence_by_visit) != set(visit_by_id)
            or any(row.get("app") != app.get("id") or row.get("visit") != row.get("visit_snapshot")
                   or row.get("patient") != selected.get("patient") or row.get("encounter") != encounter.get("id")
                   or row.get("epoch") != visit_by_id[row["visit"]]["epoch"] for row in evidence_by_visit.values())):
        raise BenefitQuoteError("Состав или контекст обращения изменился")
    line_by_id = {row.get("id"): row for row in lines if isinstance(row, dict)}
    if len(line_by_id) != len(lines):
        raise BenefitQuoteError("Состав услуг требует сверки")
    gross_by_line: dict[int, Decimal] = {}
    for line_id, row in line_by_id.items():
        if (type(line_id) is not int or line_id <= 0 or row.get("visit") not in visit_by_id
                or type(row.get("qty")) is not int or not 0 < row["qty"] <= 2147483647):
            raise BenefitQuoteError("Состав услуг требует сверки")
        gross = _amount(row.get("price")) * row["qty"]
        if gross > Decimal("9999999999.99"):
            raise BenefitQuoteError("Стоимость услуг превышает допустимую")
        gross_by_line[line_id] = gross
    discounts: dict[int, Decimal] = {}
    sums = {"gross": Decimal("0.00"), "discount": Decimal("0.00"), "net": Decimal("0.00")}
    for allocation in allocations:
        if not isinstance(allocation, dict):
            raise BenefitQuoteError("Распределение льготы требует сверки")
        line_id = allocation.get("line")
        row = line_by_id.get(line_id)
        if (row is None or line_id in discounts or allocation.get("app") != app.get("id")
                or allocation.get("line_snapshot") != line_id or allocation.get("visit") != row["visit"]
                or allocation.get("visit_snapshot") != row["visit"] or allocation.get("service") != row.get("service")
                or allocation.get("epoch") != visit_by_id[row["visit"]]["epoch"]
                or allocation.get("qty") != row["qty"] or _amount(allocation.get("unit")) != _amount(row["price"])):
            raise BenefitQuoteError("Распределение льготы изменилось")
        gross, discount, net = (_amount(allocation.get(key)) for key in ("gross", "discount", "net"))
        if gross != gross_by_line[line_id] or discount > gross or net != gross - discount:
            raise BenefitQuoteError("Распределение льготы требует сверки")
        discounts[line_id] = discount
        for key, value in (("gross", gross), ("discount", discount), ("net", net)):
            sums[key] += value
    if any(_amount(app.get(key)) != value for key, value in sums.items()) or sums["discount"] <= 0:
        raise BenefitQuoteError("Итог льготы требует сверки")
    visit_totals = {line_id: gross - discounts.get(line_id, Decimal("0.00"))
                    for line_id, gross in gross_by_line.items() if line_by_id[line_id]["visit"] == visit_id}
    total = sum(visit_totals.values(), Decimal("0.00"))
    if total > Decimal("9999999999.99"):
        raise BenefitQuoteError("Стоимость услуг превышает допустимую")
    return BenefitVisitQuote(total, visit_totals, has_benefit=True)
