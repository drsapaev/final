"""Tests for payment_state_checks module (FOLLOWUP-6).

Validates the authoritative ALLOWED_PAYMENT_TRANSITIONS table and the
is_valid_payment_transition() function extracted from
billing_service_pkg/_payments.py.
"""
from __future__ import annotations

import pytest

from app.services.payment_state_checks import (
    ALLOWED_PAYMENT_TRANSITIONS,
    TERMINAL_PAYMENT_STATUSES,
    can_transition_payment_status,
    is_terminal_payment,
    is_valid_payment_transition,
)


@pytest.mark.unit
class TestAllowedPaymentTransitionsTable:
    """Verify the ALLOWED_PAYMENT_TRANSITIONS table matches the project's
    state machine (previously inline in billing_service_pkg/_payments.py).
    """

    def test_table_contains_all_seven_payment_statuses(self):
        """All 7 PaymentStatus enum values must be keys in the table."""
        expected_keys = {
            "pending",
            "processing",
            "paid",
            "failed",
            "cancelled",
            "refunded",
            "void",
        }
        assert set(ALLOWED_PAYMENT_TRANSITIONS.keys()) == expected_keys

    def test_terminal_statuses_have_empty_transition_lists(self):
        """Terminal statuses (cancelled, refunded, void) must have empty
        allowed-transition lists — no outgoing edges."""
        for status in ("cancelled", "refunded", "void"):
            assert ALLOWED_PAYMENT_TRANSITIONS[status] == [], (
                f"Terminal status {status!r} must have empty transition list, "
                f"got {ALLOWED_PAYMENT_TRANSITIONS[status]}"
            )

    def test_pending_allows_four_transitions(self):
        assert ALLOWED_PAYMENT_TRANSITIONS["pending"] == [
            "processing",
            "paid",
            "failed",
            "cancelled",
        ]

    def test_processing_allows_three_transitions(self):
        assert ALLOWED_PAYMENT_TRANSITIONS["processing"] == [
            "paid",
            "failed",
            "cancelled",
        ]

    def test_paid_allows_only_refunded_and_void(self):
        """paid → cancelled is NOT allowed (must go through refunded/void)."""
        assert ALLOWED_PAYMENT_TRANSITIONS["paid"] == ["refunded", "void"]

    def test_failed_allows_pending_and_cancelled(self):
        """failed → paid is NOT allowed (must return to pending first)."""
        assert ALLOWED_PAYMENT_TRANSITIONS["failed"] == [
            "pending",
            "cancelled",
        ]


@pytest.mark.unit
class TestIsValidPaymentTransition:
    """Verify is_valid_payment_transition() enforces the strict table."""

    @pytest.mark.parametrize(
        "current,target,expected",
        [
            # Valid transitions
            ("pending", "processing", True),
            ("pending", "paid", True),
            ("pending", "failed", True),
            ("pending", "cancelled", True),
            ("processing", "paid", True),
            ("processing", "failed", True),
            ("processing", "cancelled", True),
            ("paid", "refunded", True),
            ("paid", "void", True),
            ("failed", "pending", True),
            ("failed", "cancelled", True),
            # Same-status idempotent
            ("pending", "pending", True),
            ("processing", "processing", True),
            ("paid", "paid", True),
            ("failed", "failed", True),
            ("cancelled", "cancelled", True),
            ("refunded", "refunded", True),
            ("void", "void", True),
            # Invalid transitions
            ("paid", "cancelled", False),  # paid → cancelled not allowed
            ("paid", "pending", False),
            ("paid", "processing", False),
            ("paid", "failed", False),
            ("failed", "paid", False),  # failed → paid must go through pending
            ("failed", "processing", False),
            ("failed", "refunded", False),
            ("failed", "void", False),
            ("cancelled", "pending", False),  # terminal
            ("cancelled", "paid", False),
            ("cancelled", "refunded", False),
            ("refunded", "cancelled", False),  # terminal
            ("refunded", "paid", False),
            ("void", "paid", False),  # terminal
            ("void", "refunded", False),
            ("processing", "pending", False),  # no backward to pending
            ("processing", "refunded", False),
            ("processing", "void", False),
            # Unknown current status
            ("unknown", "paid", False),
            ("", "paid", False),
        ],
    )
    def test_transition(self, current, target, expected):
        assert is_valid_payment_transition(current, target) is expected


@pytest.mark.unit
class TestCanTransitionPaymentStatusPermissive:
    """Verify can_transition_payment_status() is permissive (NOT the strict
    table). This is intentional — the strict rejection happens in
    billing_service.update_payment_status().
    """

    def test_paid_to_cancelled_is_permissive(self):
        """paid → cancelled returns True here (permissive), even though
        is_valid_payment_transition() returns False. The authoritative
        rejection happens in billing_service.update_payment_status().
        """
        assert can_transition_payment_status("paid", "cancelled") is True
        assert is_valid_payment_transition("paid", "cancelled") is False

    def test_failed_to_paid_is_blocked(self):
        """Both permissive and strict agree: failed → paid is not allowed."""
        assert can_transition_payment_status("failed", "paid") is False
        assert is_valid_payment_transition("failed", "paid") is False

    def test_terminal_to_non_terminal_is_blocked(self):
        """Both permissive and strict agree: terminal → non-terminal blocked."""
        for terminal in ("cancelled", "refunded", "void"):
            assert can_transition_payment_status(terminal, "paid") is False
            assert is_valid_payment_transition(terminal, "paid") is False

    def test_same_status_is_idempotent(self):
        """Both permissive and strict allow same-status (idempotent)."""
        for status in ("pending", "processing", "paid", "failed",
                       "cancelled", "refunded", "void"):
            assert can_transition_payment_status(status, status) is True
            assert is_valid_payment_transition(status, status) is True


@pytest.mark.unit
class TestTerminalStatusesConsistency:
    """Verify TERMINAL_PAYMENT_STATUSES is consistent with
    ALLOWED_PAYMENT_TRANSITIONS (statuses with empty lists).
    """

    def test_terminal_statuses_match_empty_transition_lists(self):
        """The terminal statuses set must exactly match the set of statuses
        with empty allowed-transition lists."""
        empty_list_statuses = {
            status
            for status, allowed in ALLOWED_PAYMENT_TRANSITIONS.items()
            if allowed == []
        }
        assert TERMINAL_PAYMENT_STATUSES == empty_list_statuses

    def test_is_terminal_payment_matches_table(self):
        """is_terminal_payment() must return True for statuses with empty
        transition lists."""
        for status, allowed in ALLOWED_PAYMENT_TRANSITIONS.items():
            assert is_terminal_payment(status) == (len(allowed) == 0), (
                f"is_terminal_payment({status!r}) = {is_terminal_payment(status)}, "
                f"but allowed list = {allowed}"
            )
