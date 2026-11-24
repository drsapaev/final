"""Internal reservation primitives for future provider checkout integration.

No public endpoint calls this service yet. It never contacts a provider and
never stores or returns a checkout URL. Existing payment/invoice writers are
not yet required to take these reservations, so this module alone does not
prove financial fencing, authorization of public routes, or safe settlement.
Unknown/dispatching attempts never expire and this slice exposes no release.
The caller owns the root transaction: the service flushes but never commits.
No returned reservation is durable until the caller has successfully committed.
Before committing, an authenticated caller must recheck bearer expiry and
roll back on expiry; the locked user row alone cannot stop wall-clock time.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core.roles import normalize_role_value
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import (
    ProviderActiveVisitReservation,
    ProviderAttempt,
    ProviderAttemptVisit,
)
from app.models.user import User
from app.models.visit import Visit
from app.services.money_input import MoneyInputError, parse_money
from app.services.profile_contact_security import (
    ProfileBearerInvalid,
    check_bearer_expiry,
    check_profile_bearer,
)


@dataclass
class ProviderAttemptError(Exception):
    status_code: int
    detail: str


@dataclass(frozen=True)
class AttemptResult:
    public_id: str
    status: str
    created: bool


_CLICK_ISSUANCE_TX_KEY = object()

_CURRENCY_EXPONENTS = {("click", "UZS"): 2, ("payme", "UZS"): 2, ("kaspi", "KZT"): 0}


def _minor_units(value: Any, provider: str, currency: str, *, allow_zero: bool = False) -> tuple[str, int]:
    if isinstance(value, (float, bool)):
        raise ProviderAttemptError(422, "Некорректная денежная сумма")
    exponent = _CURRENCY_EXPONENTS.get((provider, currency))
    if exponent is None:
        raise ProviderAttemptError(422, "Валюта не поддерживается провайдером")
    try:
        amount = parse_money(value)
    except MoneyInputError:
        raise ProviderAttemptError(422, "Некорректная денежная сумма") from None
    if not allow_zero and amount == 0:
        raise ProviderAttemptError(422, "Сумма должна быть положительной")
    scaled = amount * (10 ** exponent)
    if scaled != scaled.to_integral_value():
        raise ProviderAttemptError(422, "Сумма не соответствует разрядности валюты")
    return str(int(scaled)), exponent


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _metadata(value: str | None, limit: int) -> str | None:
    if value is not None and (not isinstance(value, str) or len(value) > limit):
        raise ProviderAttemptError(422, "Некорректные параметры запроса")
    return value


class ProviderAttemptService:
    """Reserve attempts in a caller-owned transaction; no external dispatch."""

    def __init__(self, db: Session, provider_manager):
        self.db = db
        self.provider_manager = provider_manager

    def _clean_session(self) -> None:
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ProviderAttemptError(409, "Незавершённая транзакция")

    def _reserve_sqlite(self) -> None:
        if self.db.get_bind().dialect.name == "sqlite":
            self.db.execute(text("UPDATE visits SET id=id WHERE 0"))

    def _lock_actor(self, bearer, target_kind: str):
        if bearer is None or bearer.patient_id is not None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        user = (self.db.query(User).filter(User.id == bearer.user_id)
                .with_for_update().populate_existing().first())
        if user is None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(self.db, user, bearer)
        allowed = {"admin", "registrar", "cashier"} if target_kind == "payment" else {"admin", "registrar"}
        if not user.is_superuser and normalize_role_value(user.role) not in allowed:
            raise ProviderAttemptError(403, "Доступ запрещён")
        return user

    def _merchant_hash(self, provider: str, target_kind: str) -> str:
        adapter = self.provider_manager.get_provider(provider)
        if adapter is None:
            raise ProviderAttemptError(409, "Провайдер недоступен")
        if target_kind == "payment_invoice" and not self.provider_manager.supports_registrar_invoice_payment(provider):
            raise ProviderAttemptError(409, "Провайдер не поддерживает оплату счёта")
        merchant = getattr(adapter, "merchant_id", None)
        service = getattr(adapter, "service_id", None) if provider == "click" else None
        if not isinstance(merchant, str) or not merchant or len(merchant) > 512:
            raise ProviderAttemptError(409, "Провайдер недоступен")
        if provider == "click" and (not isinstance(service, str) or not service or len(service) > 512):
            raise ProviderAttemptError(409, "Провайдер недоступен")
        return _digest([provider, merchant, service])

    def _lock_context(self, target_kind: str, target_id: int, provider: str, currency: str, minor: str):
        if target_kind == "payment":
            probe = self.db.query(Payment.visit_id).filter(Payment.id == target_id).first()
            if probe is None:
                raise ProviderAttemptError(404, "Платёж не найден")
            expected_visits = [probe.visit_id]
            initial_links = None
        else:
            initial_links = (self.db.query(PaymentInvoiceVisit.id, PaymentInvoiceVisit.visit_id, PaymentInvoiceVisit.visit_amount)
                             .filter(PaymentInvoiceVisit.invoice_id == target_id)
                             .order_by(PaymentInvoiceVisit.id).all())
            expected_visits = sorted({link.visit_id for link in initial_links})
            if not expected_visits:
                raise ProviderAttemptError(409, "Состав счёта недоступен")
        visits = (self.db.query(Visit).filter(Visit.id.in_(expected_visits)).order_by(Visit.id)
                  .with_for_update().populate_existing().all())
        if len(visits) != len(expected_visits) or any(not v.patient_id or not v.confirmation_context_epoch or v.confirmation_context_epoch < 1 for v in visits):
            raise ProviderAttemptError(409, "Контекст визита недоступен")
        model = Payment if target_kind == "payment" else PaymentInvoice
        query = self.db.query(model).filter(model.id == target_id).populate_existing()
        if self.db.get_bind().dialect.name == "postgresql":
            # Existing provider paths can hold payment/invoice before Visit.
            # Never wait on them while holding Visit.
            query = query.with_for_update(nowait=True)
        target = query.first()
        if target is None:
            raise ProviderAttemptError(404, "Платёж не найден")
        target_minor, _ = _minor_units(target.amount if target_kind == "payment" else target.total_amount, provider, currency)
        if target_minor != minor or target.currency != currency or str(target.status).lower() != "pending":
            raise ProviderAttemptError(409, "Платёж изменился")
        if target.provider and str(target.provider).lower() != provider:
            raise ProviderAttemptError(409, "Провайдер платежа изменился")
        if target.provider_payment_id or target.provider_transaction_id or target.provider_data:
            raise ProviderAttemptError(409, "Существующий платёж требует сверки")
        if target_kind == "payment":
            if target.visit_id != visits[0].id or target.payment_url or self.db.query(PaymentVisit.id).filter(PaymentVisit.payment_id == target.id).first():
                raise ProviderAttemptError(409, "Состав платежа требует сверки")
            allocations = {visits[0].id: minor}
            link_identity = []
        else:
            links = (self.db.query(PaymentInvoiceVisit.id, PaymentInvoiceVisit.visit_id, PaymentInvoiceVisit.visit_amount)
                     .filter(PaymentInvoiceVisit.invoice_id == target_id)
                     .order_by(PaymentInvoiceVisit.id).all())
            if links != initial_links or any(v.patient_id != target.patient_id for v in visits):
                raise ProviderAttemptError(409, "Состав счёта изменился")
            numeric: dict[int, int] = {visit.id: 0 for visit in visits}
            link_identity = []
            for link in links:
                allocation, _ = _minor_units(link.visit_amount, provider, currency, allow_zero=True)
                numeric[link.visit_id] += int(allocation)
                link_identity.append((link.id, link.visit_id, allocation))
            if sum(numeric.values()) != int(minor):
                raise ProviderAttemptError(409, "Распределение счёта изменилось")
            allocations = {visit_id: str(value) for visit_id, value in numeric.items()}
        return target, visits, allocations, link_identity

    def _abort(self, exc: Exception):
        self.db.rollback()
        if isinstance(exc, ProviderAttemptError):
            raise exc
        if isinstance(exc, ProfileBearerInvalid):
            raise ProviderAttemptError(401, "Сессия недействительна") from None
        if isinstance(exc, DBAPIError):
            dialect = self.db.get_bind().dialect.name
            pg_code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
            if isinstance(exc, IntegrityError) and (
                (dialect == "postgresql" and pg_code == "23505")
                or (dialect == "sqlite" and sqlite_code in (1555, 2067))
            ):
                raise ProviderAttemptError(409, "Попытка оплаты уже существует") from None
            if ((dialect == "postgresql" and pg_code == "55P03") or
                (dialect == "sqlite" and sqlite_code & 255 in (5, 6))):
                raise ProviderAttemptError(409, "Данные изменяются, повторите запрос") from None
        raise exc

    def reserve(self, *, bearer, target_kind: str, target_id: int, provider: str, currency: str,
                amount: Decimal | int | str, description: str | None = None,
                return_url: str | None = None, cancel_url: str | None = None,
                client_request_id: str | None = None) -> AttemptResult:
        self._clean_session()
        if target_kind not in {"payment", "payment_invoice"} or type(target_id) is not int or target_id < 1:
            raise ProviderAttemptError(422, "Некорректная цель платежа")
        if not isinstance(provider, str) or not isinstance(currency, str):
            raise ProviderAttemptError(422, "Некорректные параметры платежа")
        provider, currency = provider.strip().lower(), currency.strip().upper()
        minor, exponent = _minor_units(amount, provider, currency)
        details = [_metadata(description, 1024), _metadata(return_url, 4096),
                   _metadata(cancel_url, 4096), _metadata(client_request_id, 128)]
        if client_request_id is not None and not client_request_id.strip():
            raise ProviderAttemptError(422, "Некорректный ключ запроса")
        client_key_hash = (_digest(["provider-attempt-key-v1", client_request_id])
                           if client_request_id is not None else None)
        try:
            self._reserve_sqlite()
            actor = self._lock_actor(bearer, target_kind)
            merchant_hash = self._merchant_hash(provider, target_kind)
            target, visits, allocations, link_identity = self._lock_context(target_kind, target_id, provider, currency, minor)
            snapshot = [(v.id, v.patient_id, v.confirmation_context_epoch, allocations[v.id]) for v in visits]
            fingerprint = _digest([actor.id, target_kind, target_id, provider, merchant_hash,
                                   minor, currency, exponent, snapshot, link_identity, details])
            key_attempt = None
            if client_key_hash is not None:
                key_attempt = (self.db.query(ProviderAttempt)
                               .filter(ProviderAttempt.actor_user_id_snapshot == actor.id,
                                       ProviderAttempt.client_key_hash == client_key_hash)
                               .populate_existing().first())
                if key_attempt and not hmac.compare_digest(key_attempt.fingerprint, fingerprint):
                    raise ProviderAttemptError(409, "Ключ запроса уже использован для другого платежа")
            reservations = (self.db.query(ProviderActiveVisitReservation)
                            .filter(ProviderActiveVisitReservation.visit_id.in_([v.id for v in visits])).all())
            if reservations:
                attempt_ids = {reservation.attempt_id for reservation in reservations}
                if len(reservations) != len(visits) or len(attempt_ids) != 1:
                    raise ProviderAttemptError(409, "Визит уже зарезервирован для оплаты")
                existing_query = (self.db.query(ProviderAttempt)
                                  .filter(ProviderAttempt.id == next(iter(attempt_ids)))
                                  .populate_existing())
                if self.db.get_bind().dialect.name == "postgresql":
                    existing_query = existing_query.with_for_update(nowait=True)
                existing = existing_query.first()
                if (not existing or not hmac.compare_digest(existing.fingerprint, fingerprint)
                    or (key_attempt is not None and existing.id != key_attempt.id)):
                    raise ProviderAttemptError(409, "Визит уже зарезервирован для оплаты")
                check_bearer_expiry(bearer)
                result = AttemptResult(existing.public_id, existing.status, False)
                return result
            if key_attempt is not None:
                # A historical key cannot resurrect a released or damaged
                # reservation, even if the submitted intent looks identical.
                raise ProviderAttemptError(409, "Попытка оплаты требует сверки")
            public_id = str(uuid.uuid4())
            prefix = "clinic" if target_kind == "payment" else "invoice"
            attempt = ProviderAttempt(
                public_id=public_id, target_kind=target_kind,
                payment_id=target.id if target_kind == "payment" else None,
                payment_id_snapshot=target.id if target_kind == "payment" else None,
                invoice_id=target.id if target_kind == "payment_invoice" else None,
                invoice_id_snapshot=target.id if target_kind == "payment_invoice" else None,
                actor_user_id=actor.id, actor_user_id_snapshot=actor.id, provider=provider,
                merchant_hash=merchant_hash, order_ref=f"{prefix}_{target.id}_{public_id}",
                fingerprint=fingerprint, client_key_hash=client_key_hash, amount_minor=minor, currency=currency,
                currency_exponent=exponent, status="prepared",
            )
            self.db.add(attempt)
            self.db.flush()
            for visit in visits:
                history = ProviderAttemptVisit(attempt_id=attempt.id, visit_id=visit.id,
                    visit_id_snapshot=visit.id, patient_id_snapshot=visit.patient_id,
                    context_epoch=visit.confirmation_context_epoch, amount_minor=allocations[visit.id])
                self.db.add(history)
                self.db.flush()
                self.db.add(ProviderActiveVisitReservation(visit_id=visit.id, attempt_id=attempt.id,
                                                           attempt_visit_id=history.id))
            check_bearer_expiry(bearer)
            self.db.flush()
            return AttemptResult(public_id, "prepared", True)
        except Exception as exc:
            self._abort(exc)

    def reserve_click_issuance(self, *, bearer, target_kind: str, target_id: int,
                               amount: Decimal | int | str, description: str | None = None,
                               return_url: str | None = None, cancel_url: str | None = None,
                               client_request_id: str | None = None) -> AttemptResult:
        """Start Click issuance in canonical actor -> full group lock order.

        The transaction-local marker prevents a historical prepared attempt
        from being silently reclassified as a newly issued checkout.
        """
        from app.services.encounter_financial_fence import preflight_payment_groups

        try:
            self._clean_session()
            if target_kind not in {"payment", "payment_invoice"} or type(target_id) is not int or target_id < 1:
                raise ProviderAttemptError(422, "Некорректная цель платежа")
            self._lock_actor(bearer, target_kind)
            if target_kind == "payment":
                hint = self.db.query(Payment.visit_id).filter(Payment.id == target_id).first()
                ids = [hint[0]] if hint else []
            else:
                ids = sorted({row[0] for row in self.db.query(PaymentInvoiceVisit.visit_id)
                              .filter(PaymentInvoiceVisit.invoice_id == target_id).all()})
            if not ids or any(type(visit_id) is not int or visit_id <= 0 for visit_id in ids):
                raise ProviderAttemptError(409, "Состав платежа недоступен")
            preflight_payment_groups(self.db, ids)
            result = self.reserve(bearer=bearer, target_kind=target_kind, target_id=target_id,
                provider="click", currency="UZS", amount=amount, description=description,
                return_url=return_url, cancel_url=cancel_url, client_request_id=client_request_id)
            if not result.created:
                raise ProviderAttemptError(409, "Попытка оплаты требует сверки")
            self.db.info[_CLICK_ISSUANCE_TX_KEY] = (result.public_id, self.db.get_transaction(),
                self.db.get_nested_transaction(), self.db.connection().get_nested_transaction())
            return result
        except Exception as exc:
            self._abort(exc)

    def seal_click_issuance(self, *, public_id: str, bearer) -> str:
        """Seal a fully locked Click intent; no URL or provider call occurs.

        Caller must hold the actor lock before acquiring any financial lock,
        own the transaction and commit before exposing a checkout URL. This
        operation has no runtime caller until the full checkout integration and
        its database role provisioning are reviewed.
        """
        from app.models.click_prepare import ClickIssuedAttempt
        from app.services.click_webhook_reducer import (
            AttemptAllocation,
            InvoiceAllocation,
            allocation_digest,
        )
        from app.services.encounter_financial_fence import preflight_payment_groups
        from app.services.payment_invariant_service import PaymentInvariantService

        try:
            self._clean_session()
            actor = self._lock_actor(bearer, "payment")
            marker = self.db.info.get(_CLICK_ISSUANCE_TX_KEY)
            if (not isinstance(marker, tuple) or len(marker) != 4 or marker[0] != public_id
                    or marker[1] is not self.db.get_transaction() or not marker[1].is_active
                    or marker[2] is not self.db.get_nested_transaction()
                    or marker[3] is not self.db.connection().get_nested_transaction()):
                raise ProviderAttemptError(409, "История оплаты требует сверки")
            if self.db.get_bind().dialect.name == "postgresql":
                schema = self.db.get_bind().dialect.default_schema_name
                if not schema:
                    raise ProviderAttemptError(409, "Данные платежа недоступны")
                q = self.db.get_bind().dialect.identifier_preparer.quote_schema(schema)
                tables = ("provider_attempts", "provider_attempt_visits", "provider_active_visit_reservations", "click_issued_attempts")
                self.db.execute(text("LOCK TABLE " + ", ".join(f"{q}.{name}" for name in tables) + " IN ACCESS SHARE MODE"))
                visible = self.db.execute(text("""
                  SELECT count(*)=4 AND COALESCE(bool_and(pg_catalog.has_table_privilege(CURRENT_USER,c.oid,'SELECT') AND (
                    NOT c.relrowsecurity OR (EXISTS (SELECT 1 FROM pg_catalog.pg_policy p
                      WHERE p.polrelid=c.oid AND p.polpermissive AND p.polcmd IN ('r','*')
                        AND (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER)=ANY(p.polroles)
                        AND pg_catalog.pg_get_expr(p.polqual,p.polrelid)='true')
                    AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid
                      AND NOT p.polpermissive AND p.polcmd IN ('r','*') AND EXISTS
                      (SELECT 1 FROM pg_catalog.unnest(p.polroles) r WHERE r=0 OR pg_catalog.pg_has_role(CURRENT_USER,r,'MEMBER'))))
                  )),false) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                  WHERE n.nspname=:schema AND c.relname=ANY(:tables) AND c.relkind='r'
                """), {"schema": schema, "tables": list(tables)}).scalar_one()
                if visible is not True:
                    raise ProviderAttemptError(409, "Данные платежа недоступны")
            attempt = self.db.query(ProviderAttempt).filter(ProviderAttempt.public_id == public_id).first()
            if not attempt or attempt.provider != "click" or attempt.actor_user_id_snapshot != actor.id:
                raise ProviderAttemptError(409, "Попытка оплаты недоступна")
            if attempt.target_kind == "payment_invoice" and normalize_role_value(actor.role) not in {"admin", "registrar"} and not actor.is_superuser:
                raise ProviderAttemptError(403, "Доступ запрещён")
            rows = (self.db.query(ProviderAttemptVisit).filter(ProviderAttemptVisit.attempt_id == attempt.id)
                    .order_by(ProviderAttemptVisit.visit_id_snapshot).all())
            ids = [row.visit_id for row in rows]
            if not ids or any(type(visit_id) is not int for visit_id in ids) or len(set(ids)) != len(ids):
                raise ProviderAttemptError(409, "Состав платежа недоступен")
            preflight_payment_groups(self.db, sorted(ids))
            query = self.db.query(ProviderAttempt).filter(ProviderAttempt.id == attempt.id).populate_existing()
            if self.db.get_bind().dialect.name == "postgresql":
                query = query.with_for_update(nowait=True)
            attempt = query.one_or_none()
            if (not attempt or attempt.public_id != public_id or attempt.actor_user_id != actor.id
                    or attempt.actor_user_id_snapshot != actor.id or attempt.status != "prepared"
                    or attempt.provider != "click" or attempt.currency != "UZS" or attempt.currency_exponent != 2):
                raise ProviderAttemptError(409, "Попытка оплаты изменилась")
            target_id = attempt.payment_id if attempt.target_kind == "payment" else attempt.invoice_id
            snapshot_id = attempt.payment_id_snapshot if attempt.target_kind == "payment" else attempt.invoice_id_snapshot
            if type(target_id) is not int or target_id != snapshot_id:
                raise ProviderAttemptError(409, "Цель оплаты изменилась")
            prefix = "clinic" if attempt.target_kind == "payment" else "invoice"
            if (attempt.order_ref != f"{prefix}_{target_id}_{attempt.public_id}"
                    or not hmac.compare_digest(attempt.merchant_hash, self._merchant_hash("click", attempt.target_kind))):
                raise ProviderAttemptError(409, "Настройки оплаты изменились")
            _target, visits, current_amounts, link_identity = self._lock_context(
                attempt.target_kind, target_id, "click", "UZS", attempt.amount_minor)
            rows = (self.db.query(ProviderAttemptVisit).filter(ProviderAttemptVisit.attempt_id == attempt.id)
                    .order_by(ProviderAttemptVisit.visit_id_snapshot).populate_existing().all())
            reservations = (self.db.query(ProviderActiveVisitReservation)
                            .filter(ProviderActiveVisitReservation.attempt_id == attempt.id).all())
            if (len(rows) != len(visits) or len(reservations) != len(rows)
                    or {r.visit_id for r in reservations} != {v.id for v in visits}
                    or {r.attempt_visit_id for r in reservations} != {r.id for r in rows}):
                raise ProviderAttemptError(409, "Резерв платежа изменился")
            by_visit = {visit.id: visit for visit in visits}
            snapshots = []
            invariant = PaymentInvariantService(self.db)
            for row in rows:
                visit = by_visit.get(row.visit_id_snapshot)
                if (visit is None or row.visit_id != visit.id or row.patient_id_snapshot != visit.patient_id
                        or row.context_epoch != visit.confirmation_context_epoch
                        or row.amount_minor != current_amounts.get(visit.id)):
                    raise ProviderAttemptError(409, "Распределение платежа изменилось")
                remaining = max(invariant.compute_total_cost(visit) - invariant.compute_paid_amount(visit.id), Decimal("0"))
                remaining_minor, _ = _minor_units(remaining, "click", "UZS", allow_zero=True)
                if (int(row.amount_minor) > int(remaining_minor)
                        or (attempt.target_kind == "payment_invoice" and row.amount_minor != remaining_minor)):
                    raise ProviderAttemptError(409, "Сумма платежа изменилась")
                snapshots.append(AttemptAllocation(row.id, visit.id, visit.patient_id, row.context_epoch, row.amount_minor))
            digest = allocation_digest(snapshots, [InvoiceAllocation(*link) for link in link_identity])
            if self.db.query(ClickIssuedAttempt.id).filter_by(attempt_id=attempt.id).first() is not None:
                raise ProviderAttemptError(409, "Попытка оплаты требует сверки")
            issued = ClickIssuedAttempt(attempt_id=attempt.id, order_ref=attempt.order_ref,
                merchant_hash=attempt.merchant_hash, fingerprint=attempt.fingerprint,
                amount_minor=attempt.amount_minor, currency=attempt.currency,
                currency_exponent=attempt.currency_exponent, provider=attempt.provider,
                target_kind=attempt.target_kind, actor_user_id_snapshot=attempt.actor_user_id_snapshot,
                allocations_sha256=digest)
            self.db.add(issued)
            attempt.status = "dispatching"
            self.db.flush()
            check_bearer_expiry(bearer)
            self.db.info.pop(_CLICK_ISSUANCE_TX_KEY, None)
            return issued.order_ref
        except Exception as exc:
            self._abort(exc)

    def claim_dispatch(self, *, public_id: str, bearer) -> bool:
        """Do not authorize provider dispatch without target provenance.

        A legacy pending target with no local reference may still have had
        a checkout issued. A future integration must establish that the
        target was created in the same root transaction or was reconciled,
        then atomically CAS prepared -> dispatching before any external
        action. No caller-controlled boolean is proof of provenance.
        """
        raise ProviderAttemptError(409, "История платежа требует сверки")

    def mark_unknown(self, public_id: str) -> bool:
        """Record uncertainty only; this never releases exposure or retries."""
        self._clean_session()
        try:
            self._reserve_sqlite()
            attempt = (self.db.query(ProviderAttempt).filter(ProviderAttempt.public_id == public_id)
                       .with_for_update().populate_existing().first())
            if attempt is None:
                raise ProviderAttemptError(404, "Попытка оплаты не найдена")
            if attempt.status != "dispatching":
                return False
            attempt.status = "unknown"
            attempt.updated_at = datetime.now(UTC)
            self.db.flush()
            return True
        except Exception as exc:
            self._abort(exc)
