"""Protected #4195 Mini App reminder acceptance, run inside the pinned images."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.telegram_config import PatientOnboardingRequest, TelegramUser
from app.models.user import User
from app.models.visit import Visit
from app.schemas.patient_onboarding import (
    OnboardingPatientSearchRequest,
    RegistrarPatientLinkDecisionRequest,
)
from app.services.patient_onboarding import PatientOnboardingService
from app.synthetic_seed import (
    STAGING_REMINDER_MARKER,
    SYNTHETIC_PREFIX,
    seed_staging_reminder_fixture,
)
from app.tasks.scheduler import build_reminder_schedule_version, enqueue_reminder
from app.tasks.worker import WorkerSettings, send_visit_reminder
from arq import create_pool
from arq.jobs import Job
from arq.worker import Worker
from sqlalchemy import select, text
from sqlalchemy.orm import Session

DB_NAME = "miniapp_synthetic"
CONTACT_NAME = "SYNTHETIC staging"
CONTACT_PHONE = "+998000000000"
WAITING = 3


class CheckFailed(Exception):
    """Only static, safe messages are written to the job log."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def verify_runtime(db: Session, source_sha: str) -> None:
    require(os.getenv("ENV") == "staging", "The runtime must be staging.")
    require(os.getenv("APP_VERSION") == source_sha, "The runtime SHA does not match.")
    require(
        str(settings.ARQ_REDIS_URL) == "redis://redis:6379/0",
        "The runtime must use the isolated Redis service.",
    )
    url = db.get_bind().url
    require(
        url.get_backend_name() == "postgresql"
        and (url.host, url.database, url.username) == ("postgres", DB_NAME, DB_NAME),
        "The runtime must use the isolated PostgreSQL service.",
    )
    require(
        tuple(db.execute(text("SELECT current_database(), current_user")).one())
        == (DB_NAME, DB_NAME),
        "PostgreSQL reported an unexpected database or role.",
    )


def seed(db: Session) -> None:
    raw_chat = sys.stdin.readline(32).strip()
    require(
        bool(re.fullmatch(r"[1-9][0-9]{0,15}", raw_chat)), "Missing private test chat."
    )
    chat_id = int(raw_chat)
    require(chat_id < 2**52, "Invalid private test chat.")
    for model in (
        Patient,
        Visit,
        TelegramUser,
        PatientOnboardingRequest,
        PatientAccessAuditLog,
    ):
        require(
            db.scalar(select(model.id).limit(1)) is None,
            "Staging fixture tables must be empty.",
        )

    seed_staging_reminder_fixture(db)
    # Provision a chat that already belongs to the allowed test account. Only
    # the canonical onboarding review below can link it to the fixture patient.
    db.add(
        TelegramUser(
            chat_id=chat_id,
            active=True,
            blocked=False,
            notifications_enabled=False,
            appointment_reminders=False,
            lab_notifications=False,
        )
    )
    db.commit()


def fixture(db: Session) -> tuple[Patient, Visit, TelegramUser]:
    patient = db.scalars(select(Patient)).one()
    visit = db.scalars(select(Visit)).one()
    user = db.scalars(select(TelegramUser)).one()
    require(
        patient.address == STAGING_REMINDER_MARKER
        and patient.last_name.startswith(SYNTHETIC_PREFIX)
        and patient.phone == CONTACT_PHONE
        and not patient.is_deleted
        and visit.patient_id == patient.id
        and visit.status == "pending_confirmation"
        and visit.reminder_claimed_at is None
        and 0 < user.chat_id < 2**52
        and user.active
        and not user.blocked
        and not user.lab_notifications,
        "Unexpected synthetic visit or Telegram link state.",
    )
    return patient, visit, user


def link(db: Session, patient: Patient, user: TelegramUser) -> int:
    row = db.scalars(select(PatientOnboardingRequest)).one_or_none()
    if row is None:
        return WAITING
    require(
        row.telegram_user_id == user.id
        and row.telegram_chat_id == user.chat_id
        and row.contact_name == CONTACT_NAME
        and row.contact_phone == CONTACT_PHONE
        and row.desired_date is not None
        and row.desired_time == "09:30"
        and not any(
            (row.desired_service, row.desired_branch, row.desired_doctor_id, row.note)
        )
        and not user.notifications_enabled
        and not user.appointment_reminders,
        "Onboarding request does not match the synthetic test instructions.",
    )
    if row.status == "linked_existing":
        require(
            row.resolved_patient_id == user.patient_id == patient.id,
            "The reviewed request resolved to an unexpected patient.",
        )
        return 0
    require(
        user.patient_id is None and row.status == "pending_review",
        "Expected a new unlinked onboarding request.",
    )
    actor = db.scalars(
        select(User).where(User.username == DB_NAME, User.role == "Admin")
    ).one()
    require(actor.is_active, "The synthetic bootstrap admin is unavailable.")
    service = PatientOnboardingService(db)
    review = service.search_candidates_for_request(
        request_id=row.id,
        actor=actor,
        search_payload=OnboardingPatientSearchRequest(phone=CONTACT_PHONE),
    )
    candidates = review["candidates"]
    require(len(candidates) == 1, "Expected exactly one reviewed synthetic candidate.")
    service.link_existing_patient(
        request_id=row.id,
        actor=actor,
        payload=RegistrarPatientLinkDecisionRequest(
            candidate_id=candidates[0]["candidateId"],
            reason_code="synthetic_staging_check",
        ),
    )
    db.refresh(user)
    require(
        row.status == "linked_existing"
        and row.resolved_patient_id == user.patient_id == patient.id,
        "The canonical review did not link the synthetic patient.",
    )
    return 0


def native_cabinet_view(db: Session, patient: Patient, user: TelegramUser) -> bool:
    if user.patient_id != patient.id:
        return False
    request = db.scalars(select(PatientOnboardingRequest)).one()
    require(
        request.status == "linked_existing"
        and request.resolved_patient_id == patient.id
        and request.telegram_user_id == user.id
        and request.telegram_chat_id == user.chat_id,
        "The canonical onboarding link does not match the test chat.",
    )
    audit = PatientAccessAuditLog
    return (
        db.scalar(
            select(audit.id)
            .where(
                audit.subject_patient_id == patient.id,
                audit.actor_patient_id == patient.id,
                audit.actor_telegram_user_id == user.id,
                audit.actor_type == "self",
                audit.resource_type == "cabinet_summary",
                audit.action == "view",
                audit.outcome == "success",
                audit.timestamp >= request.reviewed_at,
            )
            .limit(1)
        )
        is not None
    )


def expected_job(visit: Visit) -> tuple[str, dict]:
    version = build_reminder_schedule_version(visit)
    return f"reminder:visit:{visit.id}:{version}:telegram", {
        "visit_id": visit.id,
        "channel": "telegram",
        "schedule_version": version,
    }


async def run_queue_check(
    command: str, db: Session, visit: Visit, user: TelegramUser
) -> None:
    queue = WorkerSettings.queue_name
    async with await create_pool(WorkerSettings.redis_settings, retry=0) as redis:
        pending_jobs = await redis.zrange(queue, 0, -1)
        if command == "enqueue":
            require(
                not pending_jobs
                and not await redis.all_job_results()
                and not user.notifications_enabled
                and not user.appointment_reminders
                and visit.confirmation_channel == "pwa"
                and visit.reminder_sent_at is None,
                "The synthetic reminder has already been prepared or the queue is not empty.",
            )
            user.notifications_enabled = True
            user.appointment_reminders = True
            visit.confirmation_channel = "telegram"
            db.commit()
            job_id, kwargs = expected_job(visit)
            require(
                await enqueue_reminder(**kwargs) == job_id,
                "Unexpected reminder job ID.",
            )
            return

        require(
            user.notifications_enabled
            and user.appointment_reminders
            and visit.confirmation_channel == "telegram",
            "The test recipient or visit is not enabled for a Telegram reminder.",
        )
        job_id, kwargs = expected_job(visit)
        job = Job(job_id, redis, _queue_name=queue)
        if command == "verify":
            results = await redis.all_job_results()
            require(
                not pending_jobs and len(results) == 1, "Expected one finished ARQ job."
            )
            result = results[0]
            require(
                result.job_id == job_id
                and result.success
                and result.job_try == 1
                and result.function == send_visit_reminder.__name__
                and result.queue_name == queue
                and result.kwargs == kwargs
                and visit.reminder_sent_at is not None,
                "ARQ did not record a successful Telegram delivery for this visit.",
            )
            return

        info = await job.info()
        require(
            pending_jobs == [job_id.encode()]
            and not await redis.all_job_results()
            and info is not None
            and info.function == send_visit_reminder.__name__
            and not info.args
            and info.kwargs == kwargs
            and visit.reminder_sent_at is None,
            "The isolated queue does not contain exactly the expected reminder.",
        )

    # End DB reads before the worker claims and updates the visit. Use the
    # production handler in a real one-shot consumer with no other jobs or retry.
    db.rollback()
    require(
        bool(settings.TELEGRAM_BOT_TOKEN), "The worker has no staging bot credential."
    )
    worker = Worker(
        [send_visit_reminder],
        queue_name=queue,
        redis_settings=WorkerSettings.redis_settings,
        burst=True,
        max_burst_jobs=1,
        max_jobs=1,
        max_tries=1,
        job_timeout=30,
        retry_jobs=False,
        handle_signals=False,
    )
    try:
        require(
            await asyncio.wait_for(worker.run_check(), timeout=45) == 1,
            "Expected one ARQ attempt.",
        )
    finally:
        try:
            await worker.close()
        finally:
            from app.services.telegram.bot import telegram_bot

            if telegram_bot.bot is not None:
                await telegram_bot.bot.session.close()


def main() -> int:
    logging.disable(logging.CRITICAL)
    require(
        len(sys.argv) == 3, "A staging phase and full verified source SHA are required."
    )
    command, source_sha = sys.argv[1:]
    require(
        command in {"seed", "link", "ready", "enqueue", "worker", "verify"},
        "Unknown check phase.",
    )
    require(bool(re.fullmatch(r"[a-f0-9]{40}", source_sha)), "Invalid source SHA.")
    with SessionLocal() as db:
        verify_runtime(db, source_sha)
        if command == "seed":
            seed(db)
            return 0
        patient, visit, user = fixture(db)
        if command == "link":
            return link(db, patient, user)
        if not native_cabinet_view(db, patient, user):
            if command == "ready":
                return WAITING
            raise CheckFailed(
                "No successful native cabinet audit for the approved test patient."
            )
        if command != "ready":
            asyncio.run(run_queue_check(command, db, visit, user))
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except CheckFailed as exc:
        print(str(exc), file=sys.stderr)
        exit_code = 1
    except Exception as exc:  # noqa: BLE001 - CI must never expose exception payloads.
        # Exception payloads can include SQL parameters and HTTP URLs.
        print(f"Staging check failed ({type(exc).__name__}).", file=sys.stderr)
        exit_code = 1
    sys.exit(exit_code)
