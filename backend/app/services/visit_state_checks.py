"""Shared visit status transition checks.

Single source of truth for Visit state-machine rules. Used by:
- ``app/api/v1/endpoints/visits.py:set_status`` (the
  ``POST /visits/{visit_id}/status`` endpoint)
- ``app/api/v1/endpoints/registrar_wizard/_visits.py:complete_visit``
  (visit completion flow)
- Any future service that mutates ``Visit.status``.

This module is intentionally pure: it imports only
``from __future__ import annotations`` and has no knowledge of any
service, repository, model, or API layer. This keeps it reusable and
free of circular-import risk.

Pattern is lifted verbatim from ``app/services/payment_state_checks.py``
so that the two state machines have a consistent shape and the audit
trail of "what transition was rejected and why" is uniform across
the codebase.

Two levels of transition checking are provided:

1. ``ALLOWED_VISIT_TRANSITIONS`` — the explicit, authoritative state
   machine table. Each key maps to a list of allowed target statuses.
   An empty list means the status is terminal (no outgoing transitions
   without an explicit admin reopen).

2. ``is_valid_visit_transition()`` — strict transition check. Returns
   ``(True, None)`` if the transition is allowed, ``(False, reason)``
   otherwise. ``reason`` is a short stable string the caller can use
   in audit logs and HTTP 409 detail payloads.

Why not allow reopening closed/canceled visits at all?
------------------------------------------------------
In a clinic's day-to-day operation, a closed visit that needs editing
should go through the EMR ``amend`` flow (which creates a new revision
with a reason and keeps the original signed record immutable), not
through a status rollback that reopens the visit for arbitrary
mutation. A canceled visit that needs to be reactivated should go
through a new visit creation, not a status flip — this preserves the
audit trail of "visit X was canceled at timestamp Y by user Z".

The single exception is the ``Admin`` role, which can perform an
explicit ``force_reopen`` via the dedicated endpoint (see
``visits.py:force_reopen_visit``). This keeps the common path safe
while preserving a documented break-glass for operational recovery
(e.g. a visit accidentally marked ``closed`` by a misclick).

Terminal statuses
-----------------
- ``closed``: visit finished, EMR signed, payment collected. Only
  ``Admin`` force-reopen can move it back.
- ``canceled``: visit cancelled (no-show, patient request, etc.).
  Only ``Admin`` force-reopen can move it back.

Non-terminal statuses
---------------------
- ``open``: visit created, not yet started.
- ``in_progress``: doctor is seeing the patient.
- ``completed``: clinical work finished, payment may still be
  pending. ``completed`` is NOT terminal — it can move to ``closed``
  once payment is settled, or back to ``in_progress`` if the doctor
  needs to add something.

Diagram
-------
::
    open ──→ in_progress ──→ completed ──→ closed
      │           │              │
      │           │              └──→ in_progress (re-open for clinical add)
      │           │
      │           ├──→ completed
      │           └──→ canceled
      │
      └──→ canceled

    closed, canceled — terminal (admin force_reopen only)

Status enum note
----------------
``app/models/enums.py:VisitStatus`` declares 9 values
(``open``, ``closed``, ``cancelled``, ``paid``, ``in_visit``,
``in_progress``, ``completed``, ``done``, ``pending_confirmation``,
``confirmed``). Of these, only ``open``, ``in_progress``,
``completed``, ``closed``, ``canceled`` are actively used by the
``set_status`` endpoint and the UI; the others are vestigial from
earlier schema iterations and are not part of this state machine.
``cancelled`` (British) is normalized to ``canceled`` (American) on
input to match the endpoint's accepted set.
"""
from __future__ import annotations

# Terminal visit statuses: no outgoing transitions without admin
# force-reopen. A duplicate request or a misclick must not reopen
# these — that would silently break financial/EMR invariants
# (a closed visit has a signed EMR and a collected payment; a
# canceled visit has cascaded queue cleanup that cannot be undone).
TERMINAL_VISIT_STATUSES = frozenset({"closed", "canceled", "expired"})

# ─── DOMAIN POLICY: terminal statuses are irreversible via regular flow ──
#
# Issue #06 Phase 1 domain decision (reviewer direction 2026-08-09):
#
# The three terminal statuses — ``closed``, ``canceled``, ``expired`` —
# are IRREVERSIBLE through the regular ``transition_status()`` flow.
# This is an explicit domain policy, not just a technical entry in
# ``ALLOWED_VISIT_TRANSITIONS``.
#
# Rationale per status:
#
# - ``closed``: visit finished, EMR signed, payment collected. Reopening
#   would break financial/EMR invariants. If a closed visit must be
#   reopened (e.g. registrar misclick), use ``force_reopen()`` with a
#   mandatory reason (≥10 chars) logged at WARNING.
#
# - ``canceled``: visit cancelled, queue entries cascaded to ``canceled``.
#   Reopening would leave orphaned canceled queue entries. If a canceled
#   visit must be reactivated, the correct workflow is to create a NEW
#   visit, not to flip the status — this preserves the audit trail of
#   "visit X was canceled at timestamp Y by user Z". Use ``force_reopen()``
#   only for operational recovery (e.g. wrong visit canceled).
#
# - ``expired``: confirmation token timed out. This is a SYSTEM-initiated
#   transition (not user-driven) — the patient did not confirm their
#   appointment in time. If an expired visit must be restored, this must
#   be a separate break-glass admin operation with a reason, NOT a
#   regular lifecycle transition. Future developers MUST NOT add
#   ``expired → open`` to ``ALLOWED_VISIT_TRANSITIONS`` "to recover
#   mistakenly expired visits" — that would defeat the purpose of
#   confirmation timeouts and create a backdoor around the confirmation
#   security policy.
#
# If you need to restore an expired visit, the correct path is:
#   1. Admin reviews the case (why did the token expire? was it a system
#      error or a patient no-show?).
#   2. Admin uses ``VisitLifecycleService.force_reopen(visit_id,
#      target_status="pending_confirmation", reason="...")`` to put the
#      visit back into the confirmation flow.
#   3. A NEW confirmation token is issued (the old one is invalidated).
#   4. The patient re-confirms via the normal flow.
#
# This keeps the confirmation security policy intact while allowing
# operational recovery through an audited break-glass path.
TERMINAL_STATUSES_IRREVERSIBLE_VIA_REGULAR_FLOW = True
# Note: the runtime assert that terminal statuses have empty transition
# lists is placed AFTER the ALLOWED_VISIT_TRANSITIONS table definition
# below, because it references that table.

# ─── Authoritative Visit state machine table ────────────────────────────
#
# Keys are current statuses (lowercase strings). Values are lists of
# allowed target statuses. An empty list means the status is terminal
# — only the admin force-reopen path can move out of it.
#
# Issue #06 Phase 1: extended to cover the full visit lifecycle
# including confirmation flow. The original table covered only 5 of
# 10 statuses actually used in the codebase. The missing statuses
# were: confirmed, pending_confirmation, expired, paid, cancelled
# (British spelling).
#
# "paid" is NOT a visit lifecycle status — payment state lives in
# the Payment table (see Issue #06 Phase 0). It does not enter this
# table.
#
# "cancelled" (British) is normalized to "canceled" (American) by
# _normalize_status() before lookup.
#
# "completed" is intentionally non-terminal: a visit can move from
# "completed" back to "in_progress" if the doctor needs to add a
# clinical finding, and from "completed" forward to "closed" once
# payment is settled. This matches the registrar workflow where
# "complete_visit" sets status=completed and the cashier later
# sets status=closed after payment.
#
# Diagram:
#
#   pending_confirmation ──→ confirmed ──→ open ──→ in_progress ──→ completed ──→ closed
#           │                    │            │           │              │
#           │                    │            │           ├──→ canceled   │
#           │                    │            │           │              │
#           │                    │            │           └──→ completed │
#           │                    │            │                          │
#           │                    │            └──→ canceled              │
#           │                    │                                       │
#           │                    ├──→ canceled                            │
#           │                    │                                        │
#           │                    └──→ expired (if not activated in time)  │
#           │                                                             │
#           └──→ expired (confirmation timeout)                          │
#           │                                                             │
#           └──→ canceled                                                │
#                                                                       │
#   expired — terminal (admin force_reopen only)                       │
#   closed — terminal (admin force_reopen only)                       │
#   canceled — terminal (admin force_reopen only)                     │
#
# Note: same-status transitions (e.g. "in_progress" → "in_progress"
# from a duplicate click) are allowed as idempotent no-ops — see
# ``is_valid_visit_transition`` below.
ALLOWED_VISIT_TRANSITIONS: dict[str, list[str]] = {
    # Confirmation flow (pre-visit)
    "pending_confirmation": ["confirmed", "canceled", "expired"],
    "confirmed": ["open", "canceled", "expired"],
    # Active visit lifecycle
    "open": ["in_progress", "completed", "canceled"],
    "in_progress": ["completed", "canceled"],
    "completed": ["in_progress", "closed"],
    # Terminal states
    "closed": [],  # terminal — admin force_reopen only
    "canceled": [],  # terminal — admin force_reopen only
    "expired": [],  # terminal — confirmation timed out; admin force_reopen only
}

# Runtime invariant: terminal statuses MUST have empty transition lists.
# This assert enforces the domain policy documented above — if a future
# developer adds a transition out of a terminal status, this will fail
# at import time, forcing them to either remove the transition or
# explicitly document why the terminal policy is being violated.
assert all(
    not ALLOWED_VISIT_TRANSITIONS.get(ts)
    for ts in TERMINAL_VISIT_STATUSES
), (
    f"Terminal statuses {TERMINAL_VISIT_STATUSES} must have empty "
    f"transition lists. If you need to restore a terminal visit, use "
    f"VisitLifecycleService.force_reopen() with a reason — do NOT add "
    f"a regular transition. See DOMAIN POLICY comment above."
)

# Statuses accepted by the set_status endpoint. Kept here (not in
# the endpoint) so that the state machine module is the single
# source of truth for "what statuses can the API receive".
ACCEPTED_VISIT_STATUSES = frozenset(ALLOWED_VISIT_TRANSITIONS.keys())


def _normalize_status(status: str) -> str:
    """Normalize a visit status string.

    - Lowercase.
    - Map British ``cancelled`` → American ``canceled`` to match
      the endpoint's accepted set (the ``VisitStatus`` enum in
      ``enums.py:48`` uses ``cancelled`` but the endpoint and UI use
      ``canceled``; this normalizes the input so both spellings work).
    """
    s = status.strip().lower()
    if s == "cancelled":
        s = "canceled"
    return s


def is_terminal_visit(status: str) -> bool:
    """Return True if a visit status is terminal (no outgoing transitions)."""
    return _normalize_status(status) in TERMINAL_VISIT_STATUSES


def is_valid_visit_transition(
    current_status: str,
    target_status: str,
) -> tuple[bool, str | None]:
    """Strict transition check using ``ALLOWED_VISIT_TRANSITIONS``.

    Returns a ``(allowed, reason)`` tuple:
    - ``(True, None)`` — transition is allowed.
    - ``(False, reason)`` — transition is rejected; ``reason`` is a
      short stable string suitable for audit logs and HTTP 409 detail.

    Same-status transitions (e.g. ``in_progress → in_progress`` from a
    duplicate click) are allowed as idempotent no-ops.

    Unknown ``current_status`` (not in the table) returns
    ``(False, "unknown_current_status")`` — callers should reject
    unknown statuses explicitly before calling.
    Unknown ``target_status`` returns ``(False, "unknown_target_status")``.

    Reasons emitted:
    - ``"unknown_current_status"``: current status not in table.
    - ``"unknown_target_status"``: target status not in accepted set.
    - ``"terminal_to_non_terminal"``: terminal → non-terminal (the
      most dangerous case — would reopen a closed/canceled visit).
    - ``"invalid_transition"``: non-terminal → non-terminal that is
      not in the allowed list (e.g. ``open → closed`` skipping
      ``in_progress`` and ``completed``).
    - ``None`` (with ``True``): transition allowed.
    """
    cur = _normalize_status(current_status)
    tgt = _normalize_status(target_status)

    # Validate that both statuses are known.
    if cur not in ALLOWED_VISIT_TRANSITIONS:
        return False, "unknown_current_status"
    if tgt not in ACCEPTED_VISIT_STATUSES:
        return False, "unknown_target_status"

    # Idempotent same-status update: always allowed (no-op).
    if cur == tgt:
        return True, None

    # Terminal status with non-empty target: the only legitimate path
    # is admin force-reopen, which bypasses this function entirely.
    # If we reach here, the caller is trying to move out of a terminal
    # status via the regular endpoint — reject.
    if cur in TERMINAL_VISIT_STATUSES:
        return False, "terminal_to_non_terminal"

    # Regular transition: must be in the allowed list.
    if tgt in ALLOWED_VISIT_TRANSITIONS[cur]:
        return True, None

    return False, "invalid_transition"


def force_reopen_target_allowed(target_status: str) -> bool:
    """Validate that a force-reopen target is a non-terminal status.

    Admin force-reopen (``POST /visits/{id}/force-reopen``) moves a
    visit out of a terminal state. The target must be a non-terminal
    status (``open``, ``in_progress``, or ``completed``) — never
    another terminal status (``closed`` or ``canceled``), which would
    be a no-op or a confusing state flip.
    """
    tgt = _normalize_status(target_status)
    return tgt in ACCEPTED_VISIT_STATUSES and tgt not in TERMINAL_VISIT_STATUSES
