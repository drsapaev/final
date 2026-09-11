"""Reminder lease coordination (PR-1, Codex round 11, P1).

``visits.reminder_claimed_at`` is an exclusive lease between an in-flight
reminder delivery (the arq worker) and every schedule-mutating path (the
reschedule endpoints, the service-level reschedule and the Telegram
``/move_visit`` action): committing a schedule change while a delivery
holds the lease lets the old-generation worker dispatch the OBSOLETE
appointment details — its finalize is generation-guarded, so the reminder
is then sent AGAIN for the new generation and the patient receives two
messages, the first describing an appointment that no longer exists.

Round 8 deliberately PRESERVED the lease on reschedule (a delivery in
flight keeps its finalize binding; the live lease defers new-generation
jobs). Round 11 completes the protocol on the mutation side: a schedule
mutation WAITS for a live lease to resolve (a normal dispatch resolves in
seconds) and refuses with 409 when the lease survives the whole wait
budget. A lease older than ``LEASE_TTL`` belongs to a dead worker and
never blocks — the same reclaim contract the worker's claim predicate
uses.

This module is deliberately arq-free: the API/service layer imports it on
every reschedule request, so it must never pull the worker's Redis stack.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# The lease must comfortably outlive the worst dispatch (the arq
# job_timeout is 300s), so a 10-minute TTL can only expire for a DEAD
# worker, never for a live one still awaiting the provider.
LEASE_TTL = timedelta(minutes=10)

# How long a schedule mutation waits for an in-flight dispatch to resolve
# before refusing (409), and how often it re-reads the lease. A normal
# dispatch is one provider call — seconds; the budget only has to cover
# that, not the dead-worker TTL (a stale lease never blocks).
DISPATCH_WAIT_BUDGET_SECONDS = 20.0
DISPATCH_WAIT_POLL_SECONDS = 0.5

# Single source of truth for the HTTP refusal detail shared by every
# lease-coordinated path (reschedule routes, the service-level reschedule,
# and the round-14 lifecycle transitions). Previously the same literal was
# duplicated in the endpoint and service layers; a third consumer (the
# lifecycle service) made the duplication a drift risk.
REMINDER_IN_PROGRESS_DETAIL = (
    "Reminder delivery is in progress for this visit; retry in a few seconds"
)


def wait_for_reminder_lease_clear(
    db: Session,
    visit_id: int,
    *,
    budget: float | None = None,
    poll: float | None = None,
) -> bool:
    """Block until the visit holds no LIVE reminder lease.

    Returns ``True`` when the schedule can be mutated safely:
    - no lease at all, or
    - a lease older than ``LEASE_TTL`` (dead worker — the worker's own
      claim predicate reclaims those).

    Returns ``False`` when a live lease survived the whole wait budget —
    the caller must NOT commit the schedule change and should refuse the
    request (HTTP 409 / adapter error) so the in-flight dispatch can never
    observe the mutated schedule.

    Reads the lease as a bare column on every poll: a column select never
    returns a cached identity-map instance, so each poll sees the freshest
    committed value even when the caller's session has the visit pinned.
    """
    from app.models.visit import Visit

    budget = DISPATCH_WAIT_BUDGET_SECONDS if budget is None else budget
    poll = DISPATCH_WAIT_POLL_SECONDS if poll is None else poll
    deadline = time.monotonic() + budget
    waited = False
    while True:
        claimed_at = (
            db.query(Visit.reminder_claimed_at).filter(Visit.id == visit_id).scalar()
        )
        if claimed_at is None:
            if waited:
                logger.info(
                    "lease.wait: visit %s lease resolved after %.1fs — "
                    "schedule mutation may proceed",
                    visit_id,
                    budget - max(0.0, deadline - time.monotonic()),
                )
            return True
        if claimed_at.tzinfo is None:
            # SQLite stores naive TEXT — normalize exactly like the
            # worker's own lease arithmetic does.
            claimed_at = claimed_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - claimed_at >= LEASE_TTL:
            logger.info(
                "lease.wait: visit %s lease from %s is older than the "
                "TTL — a dead worker's lease never blocks mutations",
                visit_id,
                claimed_at,
            )
            return True
        if time.monotonic() >= deadline:
            logger.warning(
                "lease.wait: visit %s lease (claimed_at=%s) is still live "
                "after the %.0fs budget — refusing the schedule mutation",
                visit_id,
                claimed_at,
                budget,
            )
            return False
        waited = True
        time.sleep(poll)


def lease_free_condition(claimed_at_column, cutoff: datetime):
    """SQLAlchemy condition asserting the row holds NO live lease.

    True when the lease is absent or older than ``cutoff`` (a dead
    worker's lease). Works for ORM class attributes AND reflected Core
    table columns — the atomic mutation of every schedule-mutating path
    binds itself to this predicate (round 13, P1: the wait loop alone is
    not atomic — a claim can land between the last poll and the UPDATE).
    """
    return or_(claimed_at_column.is_(None), claimed_at_column < cutoff)
