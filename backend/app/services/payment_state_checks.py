"""Shared payment status transition checks.

Single source of truth for Payment and PaymentTransaction state-machine
rules. Used by:
- ProviderWebhookService (provider_webhook_service.py)
- PaymentCancelService (payment_cancel_service.py)

FOLLOWUP-6 will extend this into a full state-machine module with
ALLOWED_TRANSITIONS tables. For now, these functions encapsulate the
rules that were previously inlined in ProviderWebhookService.

This module is intentionally pure: it imports only
``from __future__ import annotations`` and has no knowledge of any
service, repository, model, or API layer. This keeps it reusable and
free of circular-import risk.
"""
from __future__ import annotations

# Terminal payment states: no outgoing transitions allowed.
# A duplicate webhook or cancellation must not reopen these.
TERMINAL_PAYMENT_STATUSES = frozenset({"refunded", "cancelled", "void"})

# Terminal transaction states: no outgoing transitions allowed.
TERMINAL_TRANSACTION_STATUSES = frozenset({"cancelled", "refunded"})


def is_terminal_payment(status: str) -> bool:
    """Return True if a Payment status is terminal (no outgoing transitions)."""
    return status in TERMINAL_PAYMENT_STATUSES


def is_terminal_transaction(status: str) -> bool:
    """Return True if a PaymentTransaction status is terminal."""
    return status in TERMINAL_TRANSACTION_STATUSES


def can_transition_payment_status(current_status: str, target_status: str) -> bool:
    """Check if a Payment status transition is allowed.

    Same-status transitions (e.g. ``paid → paid`` from a duplicate
    webhook) are allowed as idempotent no-ops.
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
