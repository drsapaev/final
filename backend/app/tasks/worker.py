"""
arq worker entry point — real wiring (P2.3).

Run with:
    cd backend && arq app.tasks.worker.WorkerSettings

Or via docker-compose (ops/docker-compose.yml worker service).

The worker consumes the single 'clinic' queue (QUEUE_NAME — the same queue
name app/tasks/scheduler.py enqueues onto; the queue must never diverge)
on the Redis instance configured by settings.ARQ_REDIS_URL.

Jobs are defined as async functions in this file. The scheduler in
app/tasks/scheduler.py enqueues them by name.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from arq import cron
from arq.connections import RedisSettings

# Ensure backend/ is on PYTHONPATH when run via `arq app.tasks.worker.WorkerSettings`
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

# The reminder lease TTL lives in app/tasks/lease.py — a deliberately
# arq-free module — because the API/service reschedule paths import the
# SAME constant for their round-11 coordination duty (a schedule mutation
# must never commit under a live lease). The TTL must comfortably outlive
# the worst dispatch: arq's job_timeout is 300s, so a 10-minute TTL can
# only expire for a DEAD worker, never for a live one still awaiting the
# provider.
from app.tasks.lease import LEASE_TTL  # noqa: E402

# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------


def _delivery_retry(ctx, message: str) -> Exception:
    """Codex round 9, P1: arq 0.28 has no ``retry_policy`` worker setting —
    an ordinary exception after a provider outage would permanently fail the
    job on its FIRST attempt and nothing would ever reschedule it. Transient
    delivery failures therefore raise arq ``Retry`` with 10s/60s/300s
    backoff; after the third deferral the failure is made permanent."""
    from arq.worker import Retry

    job_try = int((ctx or {}).get("job_try") or 1)
    backoff = [10, 60, 300]
    if job_try <= len(backoff):
        return Retry(defer=backoff[job_try - 1])
    return RuntimeError(message)


def _parse_schedule_version(version: str) -> tuple:
    """Parse "{date}T{time or '-'}#{generation}" into its three parts."""
    date_part, _, rest = version.partition("T")
    time_part, _, gen_part = rest.partition("#")
    from datetime import date

    return (
        date.fromisoformat(date_part),
        None if (not time_part or time_part == "-") else time_part,
        int(gen_part),
    )


def _claim_still_valid(claimed_visit, schedule_version: str) -> bool:
    """Codex round 10, P1: the post-claim revalidation must recheck the
    lifecycle status TOO — a confirmation/cancellation committing between
    the claim and the dispatch must not receive an obsolete reminder with
    actionable buttons."""
    return (
        claimed_visit is not None
        and claimed_visit.status == "pending_confirmation"
        and _schedule_matches(claimed_visit, schedule_version)
    )


def _schedule_matches(visit, schedule_version: str) -> bool:
    """True when the visit's current date, time AND reminder generation
    still match the schedule version the job was enqueued for."""
    v_date, v_time, v_gen = _parse_schedule_version(schedule_version)
    if visit.visit_date != v_date:
        return False
    if visit.visit_time != v_time:
        return False
    return visit.reminder_generation == v_gen


async def send_visit_reminder(
    ctx,
    *,
    visit_id: int,
    channel: str = "telegram",
    schedule_version: str | None = None,
) -> None:
    """Send a reminder to a patient about an upcoming visit.

    Enqueued by app.tasks.scheduler.enqueue_reminder().

    Delivery protocol (Codex rounds 2-5): a short atomic lease claim bound
    to the visit's CURRENT schedule, the provider dispatch OUTSIDE any
    transaction/lock, and the permanent ``reminder_sent_at`` record only
    AFTER the provider acknowledges.

    1. Lease claim — one conditional UPDATE stamps ``reminder_claimed_at``
       only for a reminder-eligible visit (status ``pending_confirmation``,
       never reminded, no live lease; a lease older than LEASE_TTL belongs
       to a dead worker and is reclaimable). When the producer supplied a
       ``schedule_version`` (the schedule the job was enqueued for), the
       claim ALSO binds to ``visit_date == schedule_version`` — a stale job
       left queued by a reschedule can never deliver for the old schedule
       (Codex round 5, P1). The row lock lives ONLY for this statement —
       never across the notification await. Two overlapping deliveries can
       never both claim (proven against real PostgreSQL by
       tests/integration/test_reminder_pipeline_pg.py, gate_d marker).
    2. Dispatch — NotificationSenderService.send_confirmation_reminder()
       by its real contract. A crash between claim and dispatch leaves a
       lease that expires: the arq retry re-claims and delivers — the
       reminder is never stranded by a crash (Codex round 4, P1). An
       overlapping delivery hitting a LIVE lease raises arq ``Retry`` so
       the redelivery is deferred until the lease resolves instead of
       completing and never coming back (Codex round 5, P1). The residual
       at-least-once window (crash AFTER the provider accepted but BEFORE
       the record) is inherent to external sends without a provider-side
       idempotency key.
    3. Finalize — ``reminder_sent_at`` is recorded and the lease released
       in one statement bound to OUR lease value, so a concurrent
       reschedule/re-claim can never be overwritten by this job (Codex
       round 3, P2). On failure the lease is released the same way and
       arq retries.
    """
    from sqlalchemy import create_engine, func, or_, update
    from sqlalchemy.orm import Session

    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.services.notification_service import NotificationService

    logger.info(
        "job.send_visit_reminder visit_id=%s channel=%s schedule_version=%s",
        visit_id,
        channel,
        schedule_version,
    )

    engine = create_engine(str(settings.DATABASE_URL))
    # expire_on_commit=False (Codex round 12, P2): the notification service
    # ends the read-only transaction before the provider await, and its
    # post-commit attribute reads (patient phone/chat id) must stay
    # in-memory — an expired-instance refresh would reopen a transaction
    # right under the await, defeating the whole point.
    db = Session(engine, expire_on_commit=False)
    # Python-side clock: the lease value must be byte-identical between the
    # claim write and the later equality guards on every dialect (a SQL
    # now() + RETURNING round-trip is fragile on SQLite, where
    # CURRENT_TIMESTAMP is second-precision TEXT).
    our_lease: datetime | None = None
    try:
        our_lease = datetime.now(UTC)
        conditions = [
            Visit.id == visit_id,
            Visit.status == "pending_confirmation",
            Visit.reminder_sent_at.is_(None),
            or_(
                Visit.reminder_claimed_at.is_(None),
                Visit.reminder_claimed_at < our_lease - LEASE_TTL,
            ),
        ]
        if schedule_version is not None:
            # Bind the claim to the FULL schedule this job was enqueued FOR
            # (date, time AND generation — Codex rounds 5-7, P1): a stale
            # job left queued by a reschedule must never deliver for the
            # old schedule, and any schedule change invalidates the
            # version. Format: "{date}T{time or '-'}#{generation}".
            v_date, v_time, v_gen = _parse_schedule_version(schedule_version)
            conditions.append(Visit.visit_date == v_date)
            if v_time is not None:
                conditions.append(Visit.visit_time == v_time)
            else:
                conditions.append(Visit.visit_time.is_(None))
            conditions.append(Visit.reminder_generation == v_gen)
        else:
            # Every producer MUST supply a schedule version (required
            # keyword in enqueue_reminder). An unversioned job cannot be
            # verified against the current schedule and is rejected
            # outright (Codex round 7, P1).
            logger.warning(
                "job.send_visit_reminder: visit %s has no schedule "
                "version — rejecting unversioned delivery",
                visit_id,
            )
            return
        claim = db.execute(
            update(Visit).where(*conditions).values(reminder_claimed_at=our_lease)
        )
        db.commit()
        if claim.rowcount == 0:
            our_lease = None
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                logger.warning("job.send_visit_reminder: visit %s not found", visit_id)
                return
            if schedule_version is not None and not _schedule_matches(
                visit, schedule_version
            ):
                logger.info(
                    "job.send_visit_reminder: visit %s schedule moved on "
                    "(job version %s, visit %s %s) — stale job, skipping",
                    visit_id,
                    schedule_version,
                    visit.visit_date,
                    visit.visit_time,
                )
                return
            if visit.status != "pending_confirmation":
                logger.info(
                    "job.send_visit_reminder: visit %s not pending "
                    "confirmation (status=%s), skipping",
                    visit_id,
                    visit.status,
                )
                return
            if visit.reminder_sent_at is not None:
                logger.info(
                    "job.send_visit_reminder: visit %s already reminded "
                    "at %s, skipping",
                    visit_id,
                    visit.reminder_sent_at,
                )
                return
            # The only remaining reason the claim lost: a LIVE lease held by
            # another delivery. Returning cleanly would end this attempt AND
            # leave nothing to retry after the lease resolves — if the owner
            # then died, the reminder would strand forever (Codex round 5,
            # P1). Defer THIS job until shortly after the observed lease can
            # have expired; arq will re-run us to claim or re-defer.
            from arq.worker import Retry

            claimed_at = visit.reminder_claimed_at
            if claimed_at is not None:
                claimed_at = claimed_at.replace(tzinfo=UTC)
                defer = max(
                    30.0,
                    min(
                        (claimed_at + LEASE_TTL - datetime.now(UTC)).total_seconds(),
                        LEASE_TTL.total_seconds(),
                    ),
                )
            else:
                defer = LEASE_TTL.total_seconds()
            logger.info(
                "job.send_visit_reminder: visit %s has a live lease "
                "(claimed_at=%s), deferring redelivery by %.0fs",
                visit_id,
                visit.reminder_claimed_at,
                defer,
            )
            raise Retry(defer=defer)

        # Post-claim revalidation + snapshot pin (Codex round 9, P1): a
        # reschedule may commit between the claim and the provider call.
        # Re-read the row now to (a) abort BEFORE sending when the claimed
        # schedule version no longer matches, and (b) pin the claimed
        # snapshot in the session's identity map — the real service
        # re-queries the visit through THIS session, so it builds the
        # message from the claimed state instead of a later one.
        claimed_visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not _claim_still_valid(claimed_visit, schedule_version):
            db.execute(
                update(Visit)
                .where(
                    Visit.id == visit_id,
                    Visit.reminder_claimed_at == our_lease,
                )
                .values(reminder_claimed_at=None)
            )
            db.commit()
            logger.info(
                "job.send_visit_reminder: visit %s schedule moved between "
                "claim and dispatch — aborting before send",
                visit_id,
            )
            return
        # Round 16, P2: the stored schedule matching the version is not
        # enough — a job that sat in Redis through a long worker outage
        # may belong to an appointment that has ALREADY started. The
        # sweep's start check cannot invalidate jobs already queued, so
        # the worker rechecks the appointment start itself and never
        # dispatches an obsolete confirmation request for a visit that is
        # underway.
        appointment_start = _appointment_start_utc(claimed_visit)
        if appointment_start is None or appointment_start <= datetime.now(UTC):
            db.execute(
                update(Visit)
                .where(
                    Visit.id == visit_id,
                    Visit.reminder_claimed_at == our_lease,
                )
                .values(reminder_claimed_at=None)
            )
            db.commit()
            logger.info(
                "job.send_visit_reminder: visit %s appointment start is in "
                "the past (or undated) — obsolete job, aborting before send",
                visit_id,
            )
            return
        # Round 16, P1: the confirmation token is issued at booking time
        # with a 48-hour lifetime (doctor_integration/_visits.py) — a visit
        # booked more than 48h ahead would receive a reminder with an
        # UNUSABLE confirmation link/button. Re-issue the token (same
        # generator + lifetime) while the visit still holds the lease and
        # BEFORE the dispatch, so the reminder carries a working link.
        token_expires = claimed_visit.confirmation_expires_at
        if token_expires is not None and token_expires.tzinfo is None:
            token_expires = token_expires.replace(tzinfo=UTC)
        if (
            claimed_visit.confirmation_token is None
            or token_expires is None
            or token_expires <= datetime.now(UTC)
        ):
            import uuid

            claimed_visit.confirmation_token = str(uuid.uuid4())
            claimed_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(
                hours=48
            )
            db.commit()
            logger.info(
                "job.send_visit_reminder: confirmation token for visit %s "
                "was missing or expired — re-issued before dispatch",
                visit_id,
            )

        # Round 17+18, P1: the delivery channel must be PERMITTED BY THE
        # VISIT'S contract AND reachable by the patient.
        # - A NULL/empty channel (GraphQL-created visits) is NORMALIZED to
        #   'auto' in the persisted contract: confirm_by_pwa() accepts only
        #   literal 'pwa'/'auto', so the old null passthrough would send a
        #   reminder whose confirmation link answers 400.
        # - An explicit contract picks the dispatch channel; the reminder
        #   producer pins it via the service's channel parameter instead of
        #   letting the patient-based auto-selection send an unusable link.
        # - 'telegram' additionally requires a live TelegramUser link
        #   (Patient has NO telegram_id column — the linkage lives there).
        service = NotificationService(db)
        patient = (
            db.query(Patient).filter(Patient.id == claimed_visit.patient_id).first()
        )
        raw_channel = claimed_visit.confirmation_channel
        if raw_channel is None or str(raw_channel).strip() == "":
            claimed_visit.confirmation_channel = "auto"
            db.commit()
            logger.info(
                "job.send_visit_reminder: visit %s had no confirmation "
                "channel — normalized to 'auto'",
                visit_id,
            )
            allowed_channel = "auto"
        else:
            allowed_channel = str(raw_channel).strip().lower()

        if allowed_channel == "auto":
            best_channel = (
                service._determine_best_channel(patient)
                if patient is not None
                else None
            )
            dispatch_channel = best_channel
        elif allowed_channel == "telegram":
            from app.models.telegram_config import TelegramUser

            link = (
                db.query(TelegramUser)
                .filter(
                    TelegramUser.patient_id == claimed_visit.patient_id,
                    TelegramUser.active.is_(True),
                    TelegramUser.blocked.is_(False),
                    TelegramUser.appointment_reminders.is_(True),
                )
                .first()
            )
            if link is None:
                # A telegram-contract visit without a live Telegram link
                # has NO working reminder path (a PWA link would be
                # rejected by confirm_by_pwa for this contract, and no
                # chat exists to deliver the Telegram message to).
                # Skipping (without stamping) is the only non-harmful
                # outcome; the lease is released so a later delivery can
                # proceed once the patient links the bot.
                db.execute(
                    update(Visit)
                    .where(
                        Visit.id == visit_id,
                        Visit.reminder_claimed_at == our_lease,
                    )
                    .values(reminder_claimed_at=None)
                )
                db.commit()
                logger.info(
                    "job.send_visit_reminder: visit %s requires telegram but "
                    "the patient has no live Telegram link — skipping without "
                    "stamping",
                    visit_id,
                )
                return
            dispatch_channel = "telegram"
        else:
            # 'pwa' (SMS with a deep link) and 'phone'/'sms' (registrar
            # call task) are always reachable paths.
            dispatch_channel = allowed_channel

        # Dispatch OUTSIDE any transaction/lock. A reschedule during the
        # dispatch is resolved by the generation-guarded finalize below.
        try:
            result = await service.send_confirmation_reminder(
                db,
                visit_id,
                hours_before=REMINDER_HOURS_BEFORE,
                channel=dispatch_channel,
            )
        except Exception as exc:
            raise _delivery_retry(
                ctx, f"notification dispatch error for visit {visit_id}: {exc}"
            ) from exc

        if not result.get("success"):
            logger.warning(
                "job.send_visit_reminder: send failed for visit %s: %s",
                visit_id,
                result.get("error", "unknown"),
            )
            # Release the lease in the handler below; arq defers with
            # backoff (Codex round 9, P1).
            raise _delivery_retry(
                ctx,
                f"Notification send failed: {result.get('error')}",
            )

        # Record the delivery only now — the provider acknowledged it — and
        # release the lease in the same statement, bound to OUR lease value
        # AND the generation we claimed for (Codex round 8, P1): if the
        # schedule changed while we were dispatching, the delivery (for the
        # OLD schedule) must not be recorded — the new generation's job
        # delivers for the new schedule. Codex round 13, P2: the finalize
        # ALSO predicates on the lifecycle status — a confirmation or
        # cancellation committing while the provider call was in flight
        # means this delivery is an obsolete confirmation request and must
        # not be recorded as the visit's reminder (the visit left
        # pending_confirmation, so no replacement job will be enqueued and
        # the stamp staying NULL cannot cause a resend).
        v_gen = (
            _parse_schedule_version(schedule_version)[2]
            if schedule_version is not None
            else None
        )
        finalize_conditions = [
            Visit.id == visit_id,
            Visit.reminder_claimed_at == our_lease,
            Visit.status == "pending_confirmation",
        ]
        if v_gen is not None:
            finalize_conditions.append(Visit.reminder_generation == v_gen)
        finalized = db.execute(
            update(Visit)
            .where(*finalize_conditions)
            .values(reminder_sent_at=func.now(), reminder_claimed_at=None)
        )
        db.commit()
        if finalized.rowcount == 0:
            # Either the lease was taken from us, the generation moved on
            # (reschedule during dispatch), or the lifecycle status
            # changed (confirm/cancel during dispatch). Release the lease
            # if it is still ours, but never record an obsolete delivery.
            db.execute(
                update(Visit)
                .where(
                    Visit.id == visit_id,
                    Visit.reminder_claimed_at == our_lease,
                )
                .values(reminder_claimed_at=None)
            )
            db.commit()
            logger.warning(
                "job.send_visit_reminder: lease for visit %s was no longer "
                "ours or the schedule moved on at finalize; delivery not "
                "recorded",
                visit_id,
            )
        else:
            logger.info(
                "job.send_visit_reminder: visit %s reminded via %s",
                visit_id,
                result.get("channel", channel),
            )
    except Exception as exc:
        # Rollback first — the failed service call may have left uncommitted
        # partial state on the session. Then release ONLY OUR OWN lease (the
        # equality predicate makes this a no-op once a reschedule cleared it
        # or a newer delivery re-claimed) so arq's retry can re-deliver.
        db.rollback()
        if our_lease is not None:
            try:
                db.execute(
                    update(Visit)
                    .where(
                        Visit.id == visit_id,
                        Visit.reminder_claimed_at == our_lease,
                    )
                    .values(reminder_claimed_at=None)
                )
                db.commit()
            except Exception:
                # The DB itself is failing — do not mask the original error;
                # a stranded lease self-heals via LEASE_TTL expiry.
                logger.warning(
                    "job.send_visit_reminder: lease release for visit %s "
                    "failed (database unavailable); relying on LEASE_TTL "
                    "expiry",
                    visit_id,
                )
        from sqlalchemy.exc import DBAPIError

        if isinstance(exc, DBAPIError):
            # Codex round 10, P1: only Retry/RetryJob/cancellation are
            # requeued by arq 0.28 — an ordinary SQLAlchemy exception would
            # permanently drop the reminder on a transient database outage.
            retry_exc = _delivery_retry(
                ctx,
                f"transient database failure for visit {visit_id}: {exc}",
            )
            logger.warning(
                "job.send_visit_reminder: transient database failure for "
                "visit %s — deferring: %r",
                visit_id,
                retry_exc,
            )
            raise retry_exc from exc
        logger.exception("job.send_visit_reminder failed for visit %s", visit_id)
        raise
    finally:
        db.close()


# Reminder horizon shared by the sweep producer and the worker's service
# call — the reminder goes out this many hours before the appointment.
REMINDER_HOURS_BEFORE = 24

# The sweep runs every 5 minutes; a visit whose reminder moment falls
# within this lookahead gets its job enqueued by that sweep run.
REMINDER_SWEEP_LOOKAHEAD_SECONDS = 300.0


def _clinic_timezone() -> ZoneInfo:
    """The clinic wall-clock timezone (Codex round 15, P1).

    ``visit_date``/``visit_time`` are TIMEZONE-LESS clinic wall-clock values
    (the configured default is ``Asia/Tashkent``, settings.TIMEZONE) — the
    sweep must convert the local appointment time to UTC before comparing
    it with ``now``, otherwise a 10:00 appointment in UTC+5 is modeled as
    10:00 UTC and its reminder fires five hours late.
    """
    return ZoneInfo(settings.TIMEZONE)


def _appointment_start_utc(visit) -> "datetime | None":
    """The visit's appointment start as an aware UTC datetime, or None when
    no moment can be derived (no date, or a malformed time string)."""
    if visit.visit_date is None:
        return None
    raw = (visit.visit_time or "12:00").strip()
    try:
        hh, mm = int(raw[:2]), int(raw[3:5])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
    except (ValueError, TypeError):
        return None
    local_start = datetime.combine(
        visit.visit_date, time(hh, mm), tzinfo=_clinic_timezone()
    )
    return local_start.astimezone(UTC)


def _visit_reminder_moment(visit) -> "datetime | None":
    """The intended reminder time for a visit: appointment start − 24h,
    in UTC (Codex round 15, P1 — the wall-clock appointment is resolved in
    the CLINIC timezone first, then converted to UTC). A visit with no
    explicit time is treated as 12:00 clinic time so the reminder lands at
    midday of the previous day rather than at a midnight edge."""
    start = _appointment_start_utc(visit)
    if start is None:
        return None
    return start - timedelta(hours=REMINDER_HOURS_BEFORE)


async def run_visit_reminder_sweep(ctx) -> None:
    """Production reminder producer (Codex round 14, P1).

    Before this job existed ``enqueue_reminder`` had NO production caller:
    no visit ever reached Redis unless an operator ran the staging snippet
    manually, so patients never received automatic confirmation reminders
    despite the worker pipeline itself being functional. This cron sweep
    wires the producer into the scheduler: every 5 minutes it selects the
    reminder-eligible visits whose reminder moment (appointment − 24h,
    resolved in the CLINIC timezone) has arrived — OR is overdue (a missed
    sweep retries the visit until the appointment starts) — and enqueues
    their jobs onto the SAME 'clinic' queue the worker consumes.

    Idempotency layers (a sweep may run repeatedly over the same visit):
    - ``enqueue_reminder`` uses a deterministic job ID bound to the visit's
      schedule version — a job already queued/running is an honest skip;
    - a reminder already delivered (``reminder_sent_at``) is never selected;
    - a visit holding a live lease is skipped — its in-flight delivery is
      the reminder for this schedule;
    - the worker's own claim predicate revalidates status, schedule version
      and the stamp, so even a duplicate delivery cannot double-send.

    Enqueue failures are FAIL-CLOSED per visit: they are logged loudly and
    counted, the sweep never reports a phantom "job enqueued", and the next
    sweep run retries the visit (the moment is still inside the window).
    """
    from datetime import timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.visit import Visit
    from app.tasks.lease import LEASE_TTL as _LEASE_TTL

    logger.info("job.run_visit_reminder_sweep starting")
    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    try:
        now = datetime.now(UTC)
        window_end = now + timedelta(seconds=REMINDER_SWEEP_LOOKAHEAD_SECONDS)
        # Coarse SQL window on the indexed date column; the precise
        # moment/lease checks happen in Python below. The window covers
        # every NOT-YET-STARTED appointment whose reminder moment has
        # arrived (or is about to arrive within the lookahead) — Codex
        # round 15, P2: OVERDUE reminders stay eligible until the
        # appointment starts, so a missed sweep (Redis outage, worker down
        # for one interval) is retried by the next run instead of being
        # lost forever, and Codex round 15, P2: NO candidate LIMIT before
        # the exact due check — a limit would permanently starve due
        # visits behind a full page of not-yet-due rows.
        candidates = (
            db.query(Visit)
            .filter(
                Visit.status == "pending_confirmation",
                Visit.reminder_sent_at.is_(None),
                Visit.visit_date.isnot(None),
                Visit.visit_date >= (now - timedelta(days=2)).date(),
                Visit.visit_date <= (window_end + timedelta(hours=REMINDER_HOURS_BEFORE) + timedelta(days=1)).date(),
            )
            .order_by(Visit.id)
            .all()
        )
        from app.tasks.scheduler import build_reminder_schedule_version, enqueue_reminder
        from app.tasks.scheduler import TaskEnqueueError

        enqueued = skipped = failed = 0
        for visit in candidates:
            moment = _visit_reminder_moment(visit)
            if moment is None:
                skipped += 1
                continue
            start = _appointment_start_utc(visit)
            if start is None or start <= now:
                # Appointment already started/past — no reminder.
                skipped += 1
                continue
            if moment > window_end:
                # Not due yet (this includes every future appointment; the
                # coarse SQL window only narrows the scan). Overdue moments
                # (moment < now) deliberately FALL THROUGH: the reminder
                # stays eligible until the appointment starts, so a missed
                # sweep is retried by the next run (round 15, P2).
                skipped += 1
                continue
            claimed_at = visit.reminder_claimed_at
            if claimed_at is not None:
                if claimed_at.tzinfo is None:
                    claimed_at = claimed_at.replace(tzinfo=UTC)
                if now - claimed_at < _LEASE_TTL:
                    # A live delivery IS the reminder for this schedule.
                    skipped += 1
                    continue
            version = build_reminder_schedule_version(visit)
            try:
                job_id = await enqueue_reminder(
                    visit_id=visit.id, channel="telegram", schedule_version=version
                )
            except TaskEnqueueError as exc:
                failed += 1
                logger.error(
                    "job.run_visit_reminder_sweep: enqueue FAILED for visit "
                    "%s (version %s): %s — the next sweep retries it",
                    visit.id,
                    version,
                    exc,
                )
                continue
            enqueued += 1
            logger.info(
                "job.run_visit_reminder_sweep: visit %s scheduled for "
                "reminder (moment=%s, version=%s, job=%s)",
                visit.id,
                moment.isoformat(),
                version,
                job_id,
            )
        logger.info(
            "job.run_visit_reminder_sweep complete: scanned=%s enqueued=%s "
            "skipped=%s failed=%s",
            len(candidates),
            enqueued,
            skipped,
            failed,
        )
    except Exception:
        db.rollback()
        logger.exception("job.run_visit_reminder_sweep failed")
    finally:
        db.close()


async def run_data_retention(ctx) -> None:
    """Run the daily data retention cleanup. See data_retention.run_scheduled_cleanup."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.services.data_retention import run_scheduled_cleanup

    logger.info("job.run_data_retention starting")
    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    try:
        result = run_scheduled_cleanup(db)
        logger.info("job.run_data_retention complete: %s", result)
    finally:
        db.close()


async def generate_scheduled_report(
    ctx, *, report_type: str, filters: dict | None = None
) -> None:
    """Generate a scheduled report. See reporting_service."""
    logger.info(
        "job.generate_scheduled_report type=%s filters=%s",
        report_type,
        list((filters or {}).keys()),
    )
    # TODO: wire to actual reporting_service.generate_scheduled_report
    # For now, log and complete successfully.
    await asyncio.sleep(0.1)
    logger.info("job.generate_scheduled_report complete (stub)")


async def run_lab_follow_up_reminders(ctx) -> None:
    """Send lab follow-up reminders. See lab_notification_service.send_follow_up_reminders.

    Runs daily — checks for lab orders with upcoming follow-up dates and
    sends reminders to patients 3 days before the scheduled follow-up.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.services.lab_notification_service import LabNotificationService

    logger.info("job.run_lab_follow_up_reminders starting")
    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    try:
        svc = LabNotificationService(db)
        result = await svc.send_follow_up_reminders(days_before=3)
        logger.info("job.run_lab_follow_up_reminders complete: %s", result)
    except Exception:
        db.rollback()
        logger.exception("job.run_lab_follow_up_reminders failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------


async def startup(ctx) -> None:
    logger.info(
        "arq.worker.startup redis=%s", _redact_redis_url(settings.ARQ_REDIS_URL)
    )


async def shutdown(ctx) -> None:
    logger.info("arq.worker.shutdown")


def _redact_redis_url(url: str) -> str:
    """Hide password in logs."""
    if "@" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user, _pw = creds.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
    return url


# ---------------------------------------------------------------------------
# Worker settings — entry point for `arq` CLI
# ---------------------------------------------------------------------------


def _parse_redis_settings(url: str) -> RedisSettings:
    """Parse redis://[:password@]host:port/db into RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
    )


# The single application queue. SSOT for both sides of the pipeline:
# the worker consumes this queue (WorkerSettings.queue_name) and the
# scheduler enqueues onto it (_queue_name=QUEUE_NAME) — previously the
# scheduler silently fell back to arq's default 'arq:queue' while the
# worker listened here, so every reminder was stranded.
QUEUE_NAME = "clinic"


class WorkerSettings:
    """arq worker configuration. Run with:
    arq app.tasks.worker.WorkerSettings
    """

    functions = [
        send_visit_reminder,
        run_data_retention,
        generate_scheduled_report,
        run_lab_follow_up_reminders,
        run_visit_reminder_sweep,
    ]

    on_startup = startup
    on_shutdown = shutdown

    redis_settings = _parse_redis_settings(settings.ARQ_REDIS_URL)

    max_jobs = 10
    job_timeout = 300  # 5 min per job
    health_check_interval = 30
    queue_name = QUEUE_NAME

    # Cron jobs — run on the schedule, regardless of enqueues.
    # run_visit_reminder_sweep is the PRODUCTION reminder producer (round
    # 14, P1): it wires enqueue_reminder into the visit lifecycle — every
    # 5 minutes it enqueues jobs for visits whose reminder moment
    # (appointment − 24h) has arrived. Before it existed no production
    # path ever called enqueue_reminder and patients never got reminders.
    cron_jobs = [
        cron(run_data_retention, hour=3, minute=0),  # Daily 03:00 UTC
        cron(run_lab_follow_up_reminders, hour=8, minute=0),  # Daily 08:00 UTC
        cron(
            run_visit_reminder_sweep,
            minute=set(range(0, 60, 5)),  # every 5 minutes
        ),
    ]


# Make functions importable from app.tasks (for scheduler.py)
__all__ = [
    "QUEUE_NAME",
    "REMINDER_HOURS_BEFORE",
    "send_visit_reminder",
    "run_data_retention",
    "generate_scheduled_report",
    "run_lab_follow_up_reminders",
    "run_visit_reminder_sweep",
]
