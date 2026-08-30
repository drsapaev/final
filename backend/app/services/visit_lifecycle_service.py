"""VisitLifecycleService — single source of truth for visit status transitions.

Split from the original 430-line service (Issue #06 Phase 2). Payment
creation moved to ``PaymentInvariantService``. This service now owns
ONLY visit lifecycle transitions.

Architecture::

    ┌─────────────────────────────┐
    │   VisitLifecycleService     │
    │   (visit status only)       │
    └──────────────┬──────────────┘
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
   Registrar    Doctor      Cashier/Telegram/Batch
   complete     complete    cancel
   start        start       force_reopen
   confirm      cancel
   cancel
       │           │           │
       └───────────┼───────────┘
                   ↓
        state transition guard
        (is_valid_visit_transition)
                   +
        with_for_update() row lock

Domain operations
-----------------
Per reviewer direction: do NOT force every status through one universal
``transition_status()``. ``expired`` and ``pending_confirmation`` have
different semantics (system-initiated vs user-initiated). Use explicit
domain operations that internally use the common transition policy.

- ``transition_status()`` — user-driven transitions (open → in_progress, etc.)
- ``force_reopen()`` — admin break-glass (terminal → non-terminal)
- ``complete_visit()`` — convenience for target=completed
- ``cancel_visit()`` — convenience for target=canceled
- ``start_visit()`` — convenience for target=in_progress
- ``close_visit()`` — convenience for target=closed
- ``confirm_visit()`` — domain op: pending_confirmation → confirmed → open
- ``activate_confirmed_visit()`` — domain op: confirmed → open (morning batch)
- ``expire_confirmation()`` — domain op: pending_confirmation/confirmed → expired (timeout)
- ``restore_operational_status_after_payment_change()`` — payment-driven side effect

What this service does NOT own
------------------------------
- ❌ Payment creation → ``PaymentInvariantService``
- ❌ Payment calculation (total cost, paid amount) → ``PaymentInvariantService``
- ❌ Refund logic → ``cashier/_payments.py:refund_payment``
- ❌ Notifications → ``_emit_payment_notification()``
- ❌ Audit log → future ``AuditService`` (H-5)
- ❌ Queue operations → ``queue_svc/``
- ❌ Laboratory state → ``lab_reporting/``
- ❌ Telegram integration → ``telegram_staff_action_adapter_service.py``
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.visit import Visit
from app.services.visit_state_checks import (
    ACCEPTED_VISIT_STATUSES,
    force_reopen_target_allowed,
    is_valid_visit_transition,
)

logger = logging.getLogger(__name__)


class VisitLifecycleError(Exception):
    """Base exception for VisitLifecycleService domain errors."""


class VisitNotFoundError(VisitLifecycleError):
    """Raised when a visit with the given ID does not exist."""


class VisitLifecycleService:
    """Single source of truth for visit status transitions.

    All endpoints that mutate ``Visit.status`` must go through this
    service. This prevents the H-3 coverage gap from recurring as new
    endpoints are added.

    See module docstring for design rationale and domain operations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Visit loading + locking ──────────────────────────────────────

    def _load_visit_for_update(self, visit_id: int) -> Visit:
        """Load a visit row with ``SELECT ... FOR UPDATE``.

        This serializes concurrent requests that depend on the current
        visit state. The lock is held until the current transaction
        commits or rolls back.

        Raises:
            VisitNotFoundError: if the visit does not exist.
        """
        visit = (
            self.db.query(Visit)
            .filter(Visit.id == visit_id)
            .with_for_update()
            .first()
        )
        if not visit:
            raise VisitNotFoundError(f"Visit {visit_id} not found")
        return visit

    # ─── Core transition logic ────────────────────────────────────────

    def transition_status(
        self,
        visit_id: int,
        target_status: str,
        current_user: Any,
        *,
        force: bool = False,
        reason: str | None = None,
        set_started_at: bool = True,
        set_finished_at: bool = True,
        commit: bool = True,
    ) -> Visit:
        """Transition a visit to a new status via the state machine.

        Args:
            visit_id: The visit to transition.
            target_status: The target status (must be in
                ``ACCEPTED_VISIT_STATUSES``).
            current_user: The user performing the transition (for audit).
            force: If True, bypass the state machine (admin break-glass).
                Requires ``reason`` (≥10 chars).
            reason: Required when ``force=True``. Logged at WARNING.
            set_started_at: If True, set ``visit.started_at = now()`` when
                transitioning to ``in_progress``.
            set_finished_at: If True, set ``visit.finished_at = now()`` when
                transitioning to ``closed``, ``canceled``, or ``expired``.
            commit: If True (default), commit the transaction before
                returning. If False, the caller is responsible for
                committing — the mutation is staged but NOT persisted.

                ``commit=False`` means **"this operation participates in
                an already-existing transaction"**, NOT "commit will
                happen eventually". The caller MUST commit or rollback
                the transaction; otherwise the lock is held indefinitely
                and the mutation is lost on session close.

                Use cases for ``commit=False``:
                - Composition: multiple service calls in one atomic unit
                  (e.g. ``confirm_visit()`` + ``assign_queue_numbers()`` +
                  ``activate_confirmed_visit()`` in one transaction).
                - Batch operations: N mutations with a single commit at
                  the end (e.g. ``batch_patient_service.process()``).
                - Service-layer callers that manage their own transaction
                  via a repository pattern (e.g.
                  ``visit_confirmation_service.py``).

                When ``commit=False``, the ``with_for_update()`` lock is
                still acquired and held until the caller commits or
                rolls back. This is the correct behavior — the lock
                serializes concurrent access for the duration of the
                caller's transaction.

        Returns:
            The updated Visit object (after refresh if committed, or
            the staged object if ``commit=False``).

        Raises:
            VisitNotFoundError: visit does not exist.
            HTTPException: 400 for invalid arguments, 409 for invalid
                transitions (when raised from an endpoint context).
        """
        if target_status not in ACCEPTED_VISIT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target status: {target_status!r}",
            )

        if force and (not reason or len(reason) < 10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reason is required (≥10 chars) when force=True",
            )

        visit = self._load_visit_for_update(visit_id)

        if force:
            # Admin break-glass: bypass state machine, but require
            # non-terminal target (force-reopen to another terminal
            # status makes no sense).
            if not force_reopen_target_allowed(target_status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "reason": "invalid_force_target",
                        "message": (
                            f"force=True requires a non-terminal target "
                            f"(open, in_progress, completed). Got: {target_status!r}"
                        ),
                    },
                )
            # P1 #2 fix (PR 2723): remove reason from application log.
            # Reason is AUDIT DATA — stored in visit.notes (DB) below.
            # WARNING level auto-captured as Sentry breadcrumb → PII risk.
            logger.warning(
                "visit.force_transition visit_id=%s current=%s target=%s "
                "user_id=%s",
                visit_id,
                visit.status,
                target_status,
                getattr(current_user, "id", None),
            )
            # P1 #2 fix (PR 2723): store reason in visit.notes (DB audit).
            # This is ATOMIC with the status change — same transaction.
            # Append (not overwrite) to preserve existing clinical notes.
            if reason and hasattr(visit, "notes"):
                existing_notes = visit.notes or ""
                visit.notes = (
                    existing_notes
                    + f"\n[Force reopen: {visit.status} → {target_status}] "
                    f"Reason: {reason}"
                )
            # Clear finished_at when force-reopening a terminal status,
            # so duration metrics are not corrupted by the gap.
            if visit.status in ("closed", "canceled", "expired") and hasattr(visit, "finished_at"):
                visit.finished_at = None
        else:
            allowed, reason_code = is_valid_visit_transition(
                visit.status, target_status
            )
            if not allowed:
                logger.warning(
                    "visit.transition_rejected visit_id=%s current=%s "
                    "target=%s reason=%s user_id=%s",
                    visit_id,
                    visit.status,
                    target_status,
                    reason_code,
                    getattr(current_user, "id", None),
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "reason": reason_code,
                        "message": (
                            f"Недопустимый переход статуса визита: "
                            f"'{visit.status}' → '{target_status}'."
                        ),
                        "current_status": visit.status,
                        "target_status": target_status,
                    },
                )

        visit.status = target_status

        # Set timestamps based on the target status.
        if target_status == "in_progress" and set_started_at and hasattr(visit, "started_at"):
            visit.started_at = datetime.now(UTC)
        if target_status in ("closed", "canceled", "expired") and set_finished_at and hasattr(visit, "finished_at"):
            visit.finished_at = datetime.now(UTC)

        # Commit boundary: only commit if the caller did not request
        # ``commit=False``. When ``commit=False``, the mutation is staged
        # but NOT persisted — the caller owns the transaction and must
        # commit or rollback. The ``with_for_update()`` lock acquired in
        # ``_load_visit_for_update()`` is held until the caller's commit.
        if commit:
            self.db.commit()
            self.db.refresh(visit)
        return visit

    # ─── Admin break-glass ────────────────────────────────────────────

    def force_reopen(
        self,
        visit_id: int,
        target_status: str,
        reason: str,
        current_user: Any,
    ) -> Visit:
        """Admin break-glass: reopen a closed/canceled/expired visit.

        Convenience alias for ``transition_status(force=True, reason=reason)``.
        Separated as its own method because the semantics are different
        (admin override, not user workflow) and call sites should be
        explicit about using the break-glass path.
        """
        return self.transition_status(
            visit_id=visit_id,
            target_status=target_status,
            current_user=current_user,
            force=True,
            reason=reason,
        )

    # ─── User-driven convenience methods ──────────────────────────────

    def complete_visit(
        self,
        visit_id: int,
        current_user: Any,
        *,
        from_status: tuple[str, ...] | None = None,
        commit: bool = True,
    ) -> Visit:
        """Mark a visit as completed (doctor finished clinical work).

        Args:
            visit_id: The visit to complete.
            current_user: The user completing the visit.
            from_status: Optional tuple of allowed current statuses.
                If provided, the transition is only allowed if the
                current status is in this tuple. This is for endpoints
                that want to restrict completion to specific starting
                states (e.g. only ``in_progress`` → ``completed``).
            commit: See ``transition_status()`` docstring. Default True.
        """
        visit = self._load_visit_for_update(visit_id)

        if from_status is not None and visit.status not in from_status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "invalid_source_status",
                    "message": (
                        f"Невозможно завершить визит в статусе '{visit.status}'. "
                        f"Допустимые исходные статусы: {', '.join(from_status)}."
                    ),
                    "current_status": visit.status,
                },
            )

        return self.transition_status(
            visit_id=visit_id,
            target_status="completed",
            current_user=current_user,
            commit=commit,
        )

    def cancel_visit(
        self,
        visit_id: int,
        current_user: Any,
        *,
        reason: str | None = None,
        commit: bool = True,
    ) -> Visit:
        """Mark a visit as canceled.

        The cancellation reason is NOT logged via logger (narrative PII risk).
        Callers should store the reason in ``visit.notes`` for DB audit trail.

        Args:
            commit: See ``transition_status()`` docstring. Default True.
        """
        # P1 #2 fix (PR 2723): remove reason from application log.
        # Reason is AUDIT DATA, not LOG DATA. Narrative text (patient names,
        # diagnoses, complaints) cannot be masked by pattern-based PIIMaskingFilter.
        # The caller (_visits.py) already appends reason to visit.notes (DB).
        logger.info(
            "visit.cancel visit_id=%s user_id=%s",
            visit_id,
            getattr(current_user, "id", None),
        )
        return self.transition_status(
            visit_id=visit_id,
            target_status="canceled",
            current_user=current_user,
            commit=commit,
        )

    def start_visit(
        self,
        visit_id: int,
        current_user: Any,
        *,
        commit: bool = True,
    ) -> Visit:
        """Mark a visit as in_progress (doctor started seeing the patient).

        Args:
            commit: See ``transition_status()`` docstring. Default True.
        """
        return self.transition_status(
            visit_id=visit_id,
            target_status="in_progress",
            current_user=current_user,
            commit=commit,
        )

    def close_visit(
        self,
        visit_id: int,
        current_user: Any,
        *,
        commit: bool = True,
    ) -> Visit:
        """Mark a visit as closed (final state, after payment).

        Args:
            commit: See ``transition_status()`` docstring. Default True.
        """
        return self.transition_status(
            visit_id=visit_id,
            target_status="closed",
            current_user=current_user,
            commit=commit,
        )

    # ─── Domain-specific operations (different semantics) ─────────────

    def confirm_visit(
        self,
        visit_id: int,
        current_user: Any,
        *,
        confirmed_by: str | None = None,
        commit: bool = True,
    ) -> Visit:
        """Confirm a pending visit: pending_confirmation → confirmed.

        This is ONE-STEP transition. The visit moves to ``confirmed``
        but does NOT automatically become ``open``. Activation
        (``confirmed → open``) is a separate domain operation
        (``activate_confirmed_visit()``) that should be called by the
        caller if the visit is for today and queue numbers should be
        assigned immediately.

        This separation preserves the original semantics where a visit
        confirmed for a FUTURE date stays in ``confirmed`` status until
        the morning assignment batch activates it.

        If the visit is already ``confirmed``, this is an idempotent
        no-op (but confirmation metadata is refreshed).
        If the visit is already ``open`` or later, this raises 409
        (cannot confirm an already-active visit).

        Args:
            visit_id: The visit to confirm.
            current_user: The user confirming the visit.
            confirmed_by: Optional string identifying who confirmed
                (e.g. "registrar_42"). Logged for audit.
            commit: See ``transition_status()`` docstring. Default True.
                Use ``commit=False`` when composing with
                ``activate_confirmed_visit()`` in one transaction.
        """
        visit = self._load_visit_for_update(visit_id)

        logger.info(
            "visit.confirm visit_id=%s current_status=%s user_id=%s confirmed_by=%r",
            visit_id,
            visit.status,
            getattr(current_user, "id", None),
            confirmed_by,
        )

        # Set confirmation metadata if the visit supports it.
        if hasattr(visit, "confirmed_at"):
            visit.confirmed_at = datetime.now(UTC)
        if hasattr(visit, "confirmed_by") and confirmed_by:
            visit.confirmed_by = confirmed_by

        # Transition: pending_confirmation → confirmed
        #
        # TH-2 (post-merge stabilization): also accept "confirmation_processing"
        # as a valid source status. This is an internal lock/claim status set
        # by VisitConfirmationService._claim_pending_visit_for_confirmation()
        # to serialize concurrent confirmations. It is logically equivalent to
        # pending_confirmation — the only difference is that the visit has
        # been atomically claimed by one confirmer.
        #
        # Without this, the confirmation flow returns HTTP 500:
        #   1. _claim_pending_visit_for_confirmation() sets status to
        #      "confirmation_processing"
        #   2. _confirm_visit() calls confirm_visit()
        #   3. confirm_visit() sees "confirmation_processing" → hits else → 409
        #   4. confirm_by_telegram/confirm_by_pwa catches Exception → 500
        #
        # "confirmation_processing" is never committed between transactions
        # (rollback on error restores "pending_confirmation"), so the only
        # way confirm_visit() sees it is via _confirm_visit() in the same
        # transaction. Accepting it here does NOT expand the public state
        # transition API in a dangerous way — it recognizes an existing
        # internal transition path.
        if visit.status in ("pending_confirmation", "confirmation_processing"):
            visit.status = "confirmed"
        elif visit.status == "confirmed":
            # Idempotent — already confirmed, just refresh metadata.
            pass
        else:
            # Cannot confirm a visit that's already active or terminal.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "not_pending_confirmation",
                    "message": (
                        f"Визит в статусе '{visit.status}' не может быть "
                        f"подтверждён. Подтверждение применяется только к "
                        f"pending_confirmation."
                    ),
                    "current_status": visit.status,
                },
            )

        if commit:
            self.db.commit()
            self.db.refresh(visit)
        return visit

    def activate_confirmed_visit(
        self,
        visit_id: int,
        current_user: Any | None = None,
        *,
        commit: bool = True,
    ) -> Visit:
        """Activate a confirmed visit: confirmed → open.

        Used by the morning batch assignment to activate visits that
        were confirmed the day before. This is a system-initiated
        transition (current_user may be None for batch jobs).

        If the visit is already ``open`` or later, this is a no-op.
        If the visit is ``pending_confirmation``, this raises 409
        (must confirm first).

        Args:
            commit: See ``transition_status()`` docstring. Default True.
                Use ``commit=False`` when composing with
                ``confirm_visit()`` in one transaction.
        """
        visit = self._load_visit_for_update(visit_id)

        if visit.status == "pending_confirmation":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "not_confirmed_yet",
                    "message": (
                        "Визит ожидает подтверждения. Активация невозможна до "
                        "подтверждения (используйте confirm_visit)."
                    ),
                    "current_status": visit.status,
                },
            )

        if visit.status == "confirmed":
            logger.info(
                "visit.activate_confirmed visit_id=%s user_id=%s",
                visit_id,
                getattr(current_user, "id", None) if current_user else "batch",
            )
            visit.status = "open"
            if commit:
                self.db.commit()
                self.db.refresh(visit)

        # If already open or later — idempotent no-op.
        return visit

    def expire_confirmation(
        self,
        visit_id: int,
        *,
        reason: str = "confirmation_timeout",
        commit: bool = True,
    ) -> Visit:
        """Expire a pending/confirmed visit: → expired (terminal).

        Used by the confirmation security cleanup job to mark visits
        whose confirmation token has expired. This is a system-initiated
        transition — there is no ``current_user`` (it's a background job).

        If the visit is already ``expired``, this is a no-op.
        If the visit is in any other active state (open, in_progress,
        completed), this raises 409 — expiry only applies to
        pre-confirmation states.

        Args:
            visit_id: The visit to expire.
            reason: Expiration reason (logged). Default: "confirmation_timeout".
            commit: See ``transition_status()`` docstring. Default True.
                Use ``commit=False`` when running inside a batch job that
                commits once at the end.
        """
        visit = self._load_visit_for_update(visit_id)

        if visit.status == "expired":
            # Idempotent — already expired.
            return visit

        if visit.status not in ("pending_confirmation", "confirmed"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "reason": "not_expirable",
                    "message": (
                        f"Визит в статусе '{visit.status}' не может быть "
                        f"истёкшим. Expire применяется только к "
                        f"pending_confirmation и confirmed."
                    ),
                    "current_status": visit.status,
                },
            )

        logger.info(
            "visit.expire_confirmation visit_id=%s current_status=%s reason=%r",
            visit_id,
            visit.status,
            reason,
        )

        # Clear confirmation token metadata if present.
        if hasattr(visit, "confirmation_token"):
            visit.confirmation_token = None
        if hasattr(visit, "confirmation_expires_at"):
            visit.confirmation_expires_at = None

        visit.status = "expired"
        if hasattr(visit, "finished_at"):
            visit.finished_at = datetime.now(UTC)

        if commit:
            self.db.commit()
            self.db.refresh(visit)
        return visit

    # ─── Payment-driven side effect ───────────────────────────────────

    def restore_operational_status_after_payment_change(
        self,
        visit_id: int,
        *,
        commit: bool = True,
    ) -> Visit:
        """Restore the visit's operational status after a payment change.

        This is the canonical replacement for the legacy
        ``_preserve_cashier_visit_status()`` and
        ``_preserve_operational_status_on_payment()`` helper functions
        that were duplicated across ``cashier/_helpers.py`` and
        ``registrar_wizard/_visits.py``.

        The visit's operational status (open, in_progress, completed)
        is independent of payment state. When a payment is created,
        refunded, or cancelled, the visit's status should NOT be
        overwritten to "paid" — that was the legacy behavior removed
        in Issue #06 Phase 0.

        CRITICAL INVARIANT (reviewer direction 2026-08-09):
        This method MUST NOT turn a terminal visit (closed, canceled,
        expired) back into an operational status. A payment change
        (refund, cancel, manual confirm) on a terminal visit is a
        financial operation that does not reopen the visit's lifecycle.
        If the visit must be reopened, use ``force_reopen()`` with a
        reason.

        Behavior:
        1. If status is terminal (closed/canceled/expired) → no-op,
           return as-is. Payment changes do not reopen terminal visits.
        2. If status is "paid" (legacy data from before Phase 0) →
           normalize to "waiting" (which the frontend maps to the
           appropriate queue display).
        3. If status is None (should not happen, but defensive) →
           normalize to "waiting".
        4. Otherwise (valid operational status) → no-op.

        Args:
            visit_id: The visit to normalize.
            commit: See ``transition_status()`` docstring. Default True.
                Use ``commit=False`` when composing with a payment
                mutation in one transaction (e.g. cancel_payment +
                restore_operational_status in one atomic unit).

        Returns:
            The updated Visit object.
        """
        visit = self._load_visit_for_update(visit_id)

        # CRITICAL: terminal statuses are NEVER touched by payment
        # changes. A refund on a closed visit is a financial operation,
        # not a lifecycle transition. The visit stays closed.
        if visit.status in ("closed", "canceled", "expired"):
            logger.debug(
                "visit.restore_operational_status_skipped terminal "
                "visit_id=%s status=%s (payment change does not reopen "
                "terminal visits)",
                visit_id,
                visit.status,
            )
            return visit

        # Normalize legacy "paid" status → operational status.
        # This handles old data that may still have visit.status = "paid"
        # from before Issue #06 Phase 0 removed the producer.
        # Also handle None (defensive — should not happen but the
        # legacy _preserve_cashier_visit_status handled it).
        if visit.status in ("paid", None):
            old_status = visit.status
            visit.status = "waiting"
            logger.info(
                "visit.normalize_legacy_paid_status visit_id=%s "
                "old_status=%r new_status='waiting'",
                visit_id,
                old_status,
            )
            if commit:
                self.db.commit()
                self.db.refresh(visit)

        # If the visit has a valid operational status, no change needed.
        # The payment state is tracked separately in the Payment table.
        return visit
