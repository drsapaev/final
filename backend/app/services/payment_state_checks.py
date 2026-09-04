"""Shared payment status transition checks.

Single source of truth for Payment and PaymentTransaction state-machine
rules. Used by:
- ProviderWebhookService (provider_webhook_service.py)
- PaymentCancelService (payment_cancel_service.py)
- BillingService (billing_service_pkg/_payments.py)

This module is intentionally pure: it imports only
``from __future__ import annotations`` and has no knowledge of any
service, repository, model, or API layer. This keeps it reusable and
free of circular-import risk.

Two levels of transition checking are provided:

1. ``ALLOWED_PAYMENT_TRANSITIONS`` — the explicit, authoritative state
   machine table. Each key maps to a list of allowed target statuses.
   An empty list means the status is terminal (no outgoing transitions).
   This is the **strict** check used by
   ``billing_service.update_payment_status()`` to validate transitions
   before mutating ``Payment.status``.

2. ``can_transition_payment_status()`` — a **permissive** pre-check
   used by ``ProviderWebhookService`` to decide whether to attempt a
   transition. It allows same-status idempotent updates and blocks
   only terminal→non-terminal and failed→paid. It does NOT enforce
   the full allowed-transitions table (e.g. it allows paid→cancelled,
   which the strict table forbids). This permissiveness is intentional:
   the webhook handler uses it to decide whether to skip the update,
   and the authoritative rejection happens later in
   ``billing_service.update_payment_status()`` via the strict table.
"""
from __future__ import annotations

# Terminal payment states: no outgoing transitions allowed.
# A duplicate webhook or cancellation must not reopen these.
TERMINAL_PAYMENT_STATUSES = frozenset({"refunded", "cancelled", "void"})

# Terminal transaction states: no outgoing transitions allowed.
TERMINAL_TRANSACTION_STATUSES = frozenset({"cancelled", "refunded"})

# ─── FOLLOWUP-6: authoritative Payment state machine table ──────────────
#
# Extracted from billing_service_pkg/_payments.py:423-446 (PR #2678).
# This is the single source of truth for Payment status transitions.
#
# Keys are current statuses (lowercase strings matching PaymentStatus
# enum values). Values are lists of allowed target statuses. An empty
# list means the status is terminal.
#
# Diagram:
#
#   pending ──→ processing ──→ paid ──→ refunded
#      │            │            │
#      │            │            └──→ void
#      │            │
#      │            ├──→ failed ──→ pending (retry)
#      │            │         │
#      │            │         └──→ cancelled
#      │            │
#      │            └──→ cancelled
#      │
#      ├──→ paid (direct, e.g. cash)
#      ├──→ failed
#      └──→ cancelled
#
#   cancelled, refunded, void — terminal (no outgoing edges)
#
ALLOWED_PAYMENT_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["processing", "paid", "failed", "cancelled"],
    "processing": ["paid", "failed", "cancelled"],
    "paid": ["refunded", "void", "cancelled"],
    "completed": ["refunded", "void", "cancelled"],
    "failed": ["pending", "cancelled"],
    "cancelled": [],
    "refunded": [],
    "void": [],
}


def is_terminal_payment(status: str) -> bool:
    """Return True if a Payment status is terminal (no outgoing transitions)."""
    return status in TERMINAL_PAYMENT_STATUSES


def is_terminal_transaction(status: str) -> bool:
    """Return True if a PaymentTransaction status is terminal."""
    return status in TERMINAL_TRANSACTION_STATUSES


def is_valid_payment_transition(current_status: str, target_status: str) -> bool:
    """Strict transition check using ALLOWED_PAYMENT_TRANSITIONS.

    Returns True if ``current_status → target_status`` is an allowed
    transition per the authoritative state machine table.

    Same-status transitions (e.g. ``paid → paid`` from a duplicate
    webhook) are allowed as idempotent no-ops.

    Unknown ``current_status`` (not in the table) returns False —
    callers should reject unknown statuses explicitly before calling
    this function if they need to distinguish "unknown" from
    "forbidden".

    Used by: ``billing_service.update_payment_status()`` (the SSOT
    mutation path for ``Payment.status``).
    """
    if current_status == target_status:
        return True
    allowed = ALLOWED_PAYMENT_TRANSITIONS.get(current_status)
    if allowed is None:
        return False
    return target_status in allowed


def can_transition_payment_status(current_status: str, target_status: str) -> bool:
    """Permissive transition pre-check (NOT the authoritative table).

    Same-status transitions (e.g. ``paid → paid`` from a duplicate
    webhook) are allowed as idempotent no-ops.

    This is a **permissive** check used by ``ProviderWebhookService``
    to decide whether to skip a status update. It blocks only:
    - terminal → non-terminal (e.g. cancelled → paid)
    - failed → paid (must return to pending first)

    It does NOT enforce the full ``ALLOWED_PAYMENT_TRANSITIONS`` table.
    For example, ``paid → cancelled`` returns True here but would be
    rejected by ``is_valid_payment_transition()`` and by
    ``billing_service.update_payment_status()``.

    The permissiveness is intentional: the webhook handler uses this
    to decide whether to skip the update, and the authoritative
    rejection happens later in ``billing_service.update_payment_status()``.
    """
    if current_status == target_status:
        return True
    if is_terminal_payment(current_status):
        return False
    # failed → paid is not a valid direct transition per project
    # state-machine (failed must return to pending first).
    if current_status == "failed" and target_status == "paid":
        return False
    return True


def can_transition_transaction_status(current_status: str, target_status: str) -> bool:
    """Check if a PaymentTransaction status transition is allowed.

    Same-status transitions are allowed as idempotent no-ops.
    """
    if current_status == target_status:
        return True
    if is_terminal_transaction(current_status):
        return False
    return True
