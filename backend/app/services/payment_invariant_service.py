"""PaymentInvariantService — single source of truth for payment creation.

Split from VisitLifecycleService (Issue #06 Phase 2) per reviewer
direction: the original 430-line service was becoming a god service
that owned both visit lifecycle transitions AND payment creation.
The two concerns have different invariants and should be separated.

This service owns:
- Payment row creation with race-condition protection.
- Visit total cost calculation.
- Paid amount aggregation.
- Pre-flight check: is a new payment allowed for this visit?

This service does NOT own:
- Visit status transitions → VisitLifecycleService.
- Refund logic → stays in cashier/_payments.py:refund_payment (has atomic SQL guard).
- Payment provider webhooks → ProviderWebhookService (already has with_for_update + state machine).
- Notifications → stays in _emit_payment_notification().
- Audit log → future AuditService (H-5).

Architecture::

    ┌─────────────────────────────┐
    │   PaymentInvariantService   │
    │   (single source of truth   │
    │    for payment creation)    │
    └──────────────┬──────────────┘
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
   create_payment  mark_paid  payment_create_service
       │           │           │
       └───────────┼───────────┘
                   ↓
        with_for_update() on Visit row
                   +
        paid_amount vs total_cost check
                   +
        overpayment-as-deposit policy
                   +
        IntegrityError defense-in-depth

Concurrency model
-----------------
All payment creation acquires ``SELECT ... FOR UPDATE`` on the parent
Visit row. This serializes concurrent payment attempts on the same
visit:

    Request A: lock Visit → paid_amount = 0 → create payment → commit
    Request B: blocks on lock → paid_amount = 10000 → reject (400)

This works across DIFFERENT endpoints (create_payment + mark_visit_as_paid)
because they both acquire the same row lock. See Issue #02 Level C
mixed-path concurrency tests.

Overpayment policy
------------------
The clinic allows overpayment as an "advance / deposit" — a patient
can pay 15000 for a 10000 visit, with the excess recorded for future
use. This is logged at WARNING level for audit.

P1-1 (post-merge stabilization): the overpayment/deposit policy is an
explicit business decision (Option A). ``Payment.amount`` MAY exceed
``Visit.total_cost``. The overpayment is treated as a patient
deposit/advance.

Business policy nuance (verified by regression tests):
- Overpayment IS allowed when ``remaining_debt > 0`` (a partial payment
  that exceeds the remaining debt is accepted as deposit).
- Overpayment is NOT allowed when ``remaining_debt <= 0`` (visit already
  fully paid → further payments rejected with 400 "Все услуги уже
  оплачены" to prevent accidental double-payment).

This means grouped payments use the same overpayment/deposit policy as
individual payments. A stale allocation (visit fully paid by a concurrent
transaction between allocation calculation and FOR UPDATE lock) is
rejected, not accepted as an additional deposit — the "already fully
paid" check fires before the overpayment-as-deposit policy.

See: tests/regression/test_p1_1_overpayment_policy.py

The ``allow_overpayment`` parameter (default True) can be set to False
by callers that want to reject overpayment (e.g. a strict mode where
only exact amounts are accepted).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.visit import Visit

logger = logging.getLogger(__name__)


class PaymentInvariantError(Exception):
    """Base exception for PaymentInvariantService domain errors."""


class PaymentInvariantService:
    """Single source of truth for cashier-initiated payment creation.

    All endpoints that create Payment rows must go through this service.
    This prevents the H-4 coverage gap from recurring — where
    ``create_payment`` was protected but ``mark_visit_as_paid`` created
    payments directly without a lock.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Visit loading + locking ──────────────────────────────────────

    def _load_visit_for_update(self, visit_id: int) -> Visit:
        """Load a visit row with ``SELECT ... FOR UPDATE``.

        This serializes concurrent payment creation attempts on the
        same visit. The lock is held until the current transaction
        commits or rolls back.

        Raises:
            HTTPException: 404 if the visit does not exist.
        """
        visit = (
            self.db.query(Visit)
            .filter(Visit.id == visit_id)
            .with_for_update()
            .first()
        )
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Visit {visit_id} not found",
            )
        return visit

    # ─── Calculations (single source of truth — remove duplication) ───

    def compute_total_cost(self, visit: Visit) -> Decimal:
        """Compute the total cost of a visit's services.

        This is the canonical implementation — replaces the duplicated
        ``_cashier_visit_total_amount`` in ``cashier/_helpers.py`` and
        the duplicated ``_compute_visit_total_cost`` that was in
        ``VisitLifecycleService``.

        Logic:
        1. Sum ``price * qty`` for all VisitService rows attached to the visit.
        2. If services not loaded or sum is 0, fall back to ``visit.total_price``.
        3. If that is also empty, fall back to ``visit.total_amount``.
        4. If all are empty, return Decimal("0").
        """
        total_cost = Decimal("0")
        if hasattr(visit, "services") and visit.services:
            for vs in visit.services:
                price = (
                    Decimal(str(vs.price))
                    if hasattr(vs, "price") and vs.price
                    else Decimal("0")
                )
                qty = vs.qty if hasattr(vs, "qty") and vs.qty else 1
                total_cost += price * qty

        if total_cost == Decimal("0"):
            # Fallback: if services not loaded, use visit.total_price
            if hasattr(visit, "total_price") and visit.total_price:
                total_cost = Decimal(str(visit.total_price))
            elif hasattr(visit, "total_amount") and visit.total_amount:
                total_cost = Decimal(str(visit.total_amount))

        return total_cost

    def compute_paid_amount(self, visit_id: int) -> Decimal:
        """Compute the total paid amount for a visit.

        Sums all ``paid`` and ``completed`` payments. This is the
        canonical implementation — replaces the duplicated
        ``_cashier_paid_amounts_by_visit_id`` in ``cashier/_helpers.py``.
        """
        payments = (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit_id,
                Payment.status.in_(["paid", "completed"]),
            )
            .all()
        )
        return sum(
            (Decimal(str(p.amount or 0)) for p in payments),
            Decimal("0"),
        )

    def check_payment_allowed(
        self,
        visit_id: int,
        amount: Decimal,
        *,
        allow_overpayment: bool = True,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Pre-flight check: is a new payment allowed for this visit?

        Acquires ``with_for_update()`` on the visit row, computes the
        current paid amount, and checks the overpayment policy.

        Returns:
            Tuple of ``(total_cost, paid_amount, remaining_debt)``.

        Raises:
            HTTPException: 400 if the payment is not allowed (e.g.
                visit already fully paid and overpayment not allowed).
        """
        visit = self._load_visit_for_update(visit_id)
        total_cost = self.compute_total_cost(visit)
        paid_amount = self.compute_paid_amount(visit_id)
        remaining_debt = total_cost - paid_amount

        overpayment = amount - remaining_debt
        if overpayment > Decimal("0"):
            if not allow_overpayment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "reason": "overpayment_not_allowed",
                        "message": (
                            f"Сумма платежа ({amount}) превышает остаток долга "
                            f"({remaining_debt}). Авансы не разрешены."
                        ),
                    },
                )

        # Reject if visit is already fully paid and this is not an
        # advance/deposit.
        if remaining_debt <= Decimal("0") and amount > Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Все услуги уже оплачены. Приём дополнительного платежа "
                    "невозможен без авансового договора."
                ),
            )

        return total_cost, paid_amount, remaining_debt

    # ─── Payment creation ─────────────────────────────────────────────

    def create_payment_for_visit(
        self,
        visit_id: int,
        amount: Decimal,
        method: str,
        note: str | None,
        current_user: Any,
        *,
        currency: str = "UZS",
        provider: str | None = None,
        allow_overpayment: bool = True,
        commit: bool = True,
    ) -> Payment:
        """Create a payment for a visit with race-condition protection.

        This is the single entry point for cashier-initiated payment
        creation. Both ``cashier/_payments.py:create_payment`` and
        ``cashier/_visits.py:mark_visit_as_paid`` call this method.

        Acquires ``with_for_update()`` on the visit row, checks
        ``paid_amount`` against ``total_cost``, and wraps the insert
        in ``IntegrityError`` defense-in-depth.

        Args:
            visit_id: The visit to create a payment for.
            amount: Payment amount (must be > 0).
            method: Payment method (``cash``, ``card``, etc.).
            note: Optional payment note.
            current_user: The user creating the payment (for audit).
            allow_overpayment: If True (default), allow ``amount >
                remaining_debt`` as an advance/deposit (logged at
                WARNING). If False, reject overpayment with 400.
            commit: If True (default), commit the transaction before
                returning. If False, the caller is responsible for
                committing — the mutation is staged but NOT persisted.

                Use ``commit=False`` for grouped payments (multiple
                visits in one transaction) — call the service for each
                visit with ``commit=False``, then commit once at the end.

        Returns:
            The created Payment object (after refresh if committed, or
            the staged object if ``commit=False``).

        Raises:
            HTTPException: 400 for invalid arguments or overpayment
                rejection, 409 for concurrent payment race
                (IntegrityError defense-in-depth).
        """
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount must be positive",
            )

        # Acquire row lock — serializes concurrent payment attempts.
        # This is the critical concurrency control: any other endpoint
        # that calls create_payment_for_visit on the same visit will
        # block here until this transaction commits.
        visit = self._load_visit_for_update(visit_id)

        total_cost = self.compute_total_cost(visit)
        paid_amount = self.compute_paid_amount(visit_id)
        remaining_debt = total_cost - paid_amount

        # Overpayment check: allow as advance/deposit, but log it.
        overpayment = amount - remaining_debt
        if overpayment > Decimal("0"):
            if not allow_overpayment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "reason": "overpayment_not_allowed",
                        "message": (
                            f"Сумма платежа ({amount}) превышает остаток долга "
                            f"({remaining_debt}). Авансы не разрешены."
                        ),
                    },
                )
            # BUG 8 fix (CodeQL): redact patient_id from logs to prevent
            # clear-text logging of sensitive patient identifiers.
            logger.warning(
                "payment.overpayment_accepted visit_id=%s "
                "total_cost=%s paid_amount=%s remaining_debt=%s "
                "payment_amount=%s overpayment=%s cashier_id=%s",
                visit_id,
                str(total_cost),
                str(paid_amount),
                str(remaining_debt),
                str(amount),
                str(overpayment),
                getattr(current_user, "id", None),
            )

        # Reject if visit is already fully paid and this is not an
        # advance/deposit.
        if remaining_debt <= Decimal("0") and amount > Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Все услуги уже оплачены. Приём дополнительного платежа "
                    "невозможен без авансового договора."
                ),
            )

        # Create the payment.
        new_payment = Payment(
            visit_id=visit_id,
            amount=amount,
            currency=currency,
            method=method,
            status="paid",
            provider=provider,
            note=note,
            created_at=datetime.now(UTC),
            paid_at=datetime.now(UTC),
        )

        # Defense-in-depth: if a future schema change reintroduces a
        # unique constraint on payments(visit_id), or the bad index
        # from the original H-4 migration is still present, the
        # IntegrityError handler degrades gracefully to 409.
        try:
            self.db.add(new_payment)
            if commit:
                self.db.commit()
                self.db.refresh(new_payment)
            else:
                # Flush to send the INSERT to the DB (so IntegrityError
                # can fire), but do NOT commit — caller owns the transaction.
                self.db.flush()
        except IntegrityError as integrity_exc:
            self.db.rollback()
            logger.warning(
                "payment.create IntegrityError (defense-in-depth, "
                "expected row-lock to have prevented this): "
                "visit_id=%s amount=%s cashier_id=%s error=%s",
                visit_id,
                str(amount),
                getattr(current_user, "id", None),
                str(integrity_exc.orig) if integrity_exc.orig else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "payment_already_in_progress",
                    "message": (
                        "Платёж по этому визиту уже обрабатывается. "
                        "Обновите список платежей."
                    ),
                },
            ) from integrity_exc

        logger.info(
            "payment.created payment_id=%s visit_id=%s amount=%s method=%s "
            "cashier_id=%s paid_amount_before=%s paid_amount_after=%s",
            new_payment.id,
            visit_id,
            str(amount),
            method,
            getattr(current_user, "id", None),
            str(paid_amount),
            str(paid_amount + amount),
        )

        return new_payment

    # ─── Online payment initialization ────────────────────────────────

    def create_pending_payment(
        self,
        visit_id: int,
        amount: Decimal,
        currency: str,
        method: str,
        provider: str,
        note: str | None,
        current_user: Any,
        *,
        commit: bool = True,
    ) -> Payment:
        """Create a PENDING payment for online provider flow.

        Issue #06 Phase 4b B1: Online payment lifecycle is different
        from cashier payment:

        ```
        Cashier:     create Payment → paid (immediate)
        Online:      create Payment → pending → provider redirect →
                     webhook → verify → paid
        ```

        This method handles the FIRST step of the online flow — creating
        a PENDING payment that will be settled later via provider webhook.

        Key differences from ``create_payment_for_visit()``:
        - Does NOT apply ``paid_amount`` invariant — pending payments
          are not counted toward ``paid_amount`` (only ``paid``/
          ``completed`` are). A visit can have multiple pending payments
          (e.g. user starts PayMe, then switches to Click).
        - Does NOT apply overpayment check — the provider controls the
          amount, and the pending state is not a financial commitment.
        - DOES acquire ``with_for_update()`` on the visit row — serializes
          concurrent pending payment initializations.
        - DOES check for existing pending payments with the same provider
          (B1/B4 coordination) — prevents uncontrolled duplicates.

        Args:
            visit_id: The visit to create a pending payment for.
            amount: Payment amount (must be > 0).
            currency: ISO currency code (e.g. "UZS").
            method: Payment method (typically "online").
            provider: Provider identifier ("payme", "click", "kaspi").
            note: Optional payment note.
            current_user: The user initiating the payment (for audit).
            commit: If True (default), commit before returning. If False,
                the caller owns the transaction (same contract as
                ``create_payment_for_visit()``).

        Returns:
            The created Payment object with status='pending'.

        Raises:
            HTTPException: 400 for invalid arguments, 409 for duplicate
                pending payment with same provider.
        """
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount must be positive",
            )

        if provider not in ("payme", "click", "kaspi"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {provider!r}",
            )

        # Acquire row lock — serializes concurrent pending payment attempts.
        visit = self._load_visit_for_update(visit_id)

        # B1/B4 coordination: check for existing pending payment with
        # the same provider. This prevents uncontrolled duplicates —
        # if the user already has a pending PayMe payment, don't create
        # another one for the same provider.
        existing_pending = (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit_id,
                Payment.provider == provider,
                Payment.status == "pending",
            )
            .first()
        )
        if existing_pending:
            logger.info(
                "payment.pending_already_exists payment_id=%s visit_id=%s "
                "provider=%s — returning existing pending payment",
                existing_pending.id,
                visit_id,
                provider,
            )
            # Return the existing pending payment — idempotent behavior.
            # The caller can resume the provider redirect with the
            # existing payment_id.
            return existing_pending

        # Create the pending payment.
        new_payment = Payment(
            visit_id=visit_id,
            amount=amount,
            currency=currency,
            method=method,
            status="pending",
            provider=provider,
            note=note,
            created_at=datetime.now(UTC),
            # paid_at is NOT set — payment is not paid yet
        )

        try:
            self.db.add(new_payment)
            if commit:
                self.db.commit()
                self.db.refresh(new_payment)
            else:
                # Flush to send INSERT to DB (so payment.id is available
                # and IntegrityError can fire), but do NOT commit.
                self.db.flush()
        except IntegrityError as integrity_exc:
            self.db.rollback()
            logger.warning(
                "payment.create_pending IntegrityError (defense-in-depth): "
                "visit_id=%s provider=%s error=%s",
                visit_id,
                provider,
                str(integrity_exc.orig) if integrity_exc.orig else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "pending_payment_already_in_progress",
                    "message": (
                        "Уже есть ожидающий платёж для этого визита. "
                        "Обновите страницу."
                    ),
                },
            ) from integrity_exc

        logger.info(
            "payment.pending_created payment_id=%s visit_id=%s amount=%s "
            "provider=%s user_id=%s",
            new_payment.id,
            visit_id,
            str(amount),
            provider,
            getattr(current_user, "id", None),
        )

        return new_payment
