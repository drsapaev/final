"""One-shot test of the real Telegram reminder handler on disposable Compose."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import sys
import time
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

BOT_USERNAME = "kosmed_staging_bot"
MAX_AGE = 1200


class Refused(RuntimeError):
    pass


def select_recipient(updates: list, challenge: str, now: int) -> tuple[int, int]:
    if not re.fullmatch("[0-9a-f]{32,64}", challenge):
        raise Refused("Invalid one-time challenge")
    matches = []
    for update in updates:
        message = update.get("message") or {}
        chat, sender = message.get("chat") or {}, message.get("from") or {}
        text, date = message.get("text"), message.get("date")
        chat_id, update_id = chat.get("id"), update.get("update_id")
        if (
            chat.get("type") == "private"
            and type(chat_id) is int
            and chat_id > 0
            and type(update_id) is int
            and update_id >= 0
            and sender.get("id") == chat_id
            and sender.get("is_bot") is False
            and type(date) is int
            and 0 <= now - date <= MAX_AGE
            and isinstance(text, str)
            and hmac.compare_digest(text.encode(), f"/staging_check {challenge}".encode())
        ):
            matches.append((chat_id, update_id))
    if len(matches) != 1:
        raise Refused("Expected exactly one fresh private challenge; nothing sent")
    return matches[0]


def api(token: str, method: str, **data: Any) -> Any:
    req = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=urlencode(data).encode(),
    )
    try:
        with urlopen(req, timeout=12) as response:
            value = json.load(response)
        if value.get("ok") is True:
            return value["result"]
    except Exception:
        pass
    raise Refused(f"Telegram {method} not confirmed; do not retry a possible send")


def prove_isolation() -> None:
    database = urlsplit(os.environ.get("DATABASE_URL", ""))
    if not (
        os.environ.get("ENV") == "staging"
        and database.scheme == "postgresql+psycopg"
        and database.hostname == "postgres"
        and database.path == "/clinic_staging"
        and os.environ.get("ARQ_REDIS_URL") == "redis://redis:6379/0"
    ):
        raise Refused("Refusing any database or queue other than disposable Compose")


async def run(token: str, challenge: str) -> None:
    prove_isolation()
    if not re.fullmatch(r"[0-9]{5,}:[A-Za-z0-9_-]{25,}", token):
        raise Refused("Dedicated staging bot credential missing or invalid")

    me = api(token, "getMe")
    if me.get("is_bot") is not True or me.get("username") != BOT_USERNAME:
        raise Refused("Unexpected bot identity; nothing sent")
    allowed_updates = json.dumps(["message"])
    updates = api(token, "getUpdates", allowed_updates=allowed_updates, timeout=0)
    chat_id, update_id = select_recipient(updates, challenge, int(time.time()))
    destination = api(token, "getChat", chat_id=chat_id)
    if destination.get("type") != "private" or destination.get("id") != chat_id:
        raise Refused("Recipient is not the verified private chat; nothing sent")

    # Never put the token into the Compose environment, arguments, or logs.
    os.environ["TELEGRAM_BOT_TOKEN"] = token
    from arq.worker import Worker
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.telegram_config import TelegramConfig, TelegramUser
    from app.models.visit import Visit
    from app.services.telegram.bot import telegram_bot
    from app.synthetic_seed import seed_staging_reminder_fixture
    from app.tasks.scheduler import build_reminder_schedule_version, enqueue_reminder
    from app.tasks.worker import QUEUE_NAME, WorkerSettings, send_visit_reminder

    with SessionLocal() as db:
        if db.scalar(select(TelegramConfig.id).limit(1)) is not None:
            raise Refused("Unexpected database Telegram configuration; nothing sent")
        if db.scalar(select(TelegramUser.id).limit(1)) is not None:
            raise Refused("Unexpected existing Telegram link; nothing sent")
        fixture = seed_staging_reminder_fixture(db)
        visit = db.get(Visit, fixture["visit_id"])
        visit.confirmation_channel = "telegram"
        db.add(TelegramUser(patient_id=fixture["patient_id"], chat_id=chat_id))
        db.commit()
        version = build_reminder_schedule_version(visit)

    if telegram_bot.bot is None or not hmac.compare_digest(telegram_bot.token, token):
        raise Refused("Application did not resolve the approved staging bot")
    real_send = telegram_bot.send_confirmation_invitation
    attempts = 0
    message_id = None

    async def verified_send(*, chat_id: int, message: str, keyboard: list) -> dict:
        nonlocal attempts, message_id
        if attempts or chat_id != destination["id"]:
            return {"success": False}
        attempts += 1
        reply = await real_send(chat_id=chat_id, message=message, keyboard=keyboard)
        if reply.get("success") is True and reply.get("chat_id") == chat_id:
            message_id = reply.get("message_id")
        return reply

    telegram_bot.send_confirmation_invitation = verified_send
    # Telegram acknowledges updates below this offset. Consume the challenge
    # before queueing so a new dispatch cannot replay the same approval.
    remaining = api(token, "getUpdates", allowed_updates=allowed_updates,
                    timeout=0, offset=update_id + 1)
    if any(item.get("update_id", -1) <= update_id for item in remaining):
        raise Refused("Could not consume the one-time challenge")
    try:
        await enqueue_reminder(
            fixture["visit_id"], channel="telegram", schedule_version=version
        )
        worker = Worker(
            functions=[send_visit_reminder],
            redis_settings=WorkerSettings.redis_settings,
            queue_name=QUEUE_NAME,
            burst=True,
            max_jobs=1,
            max_burst_jobs=1,
            max_tries=1,
            retry_jobs=False,
            job_timeout=35,
            handle_signals=False,
            log_results=False,
        )
        try:
            await asyncio.wait_for(worker.async_run(), timeout=55)
        finally:
            await worker.close()
        with SessionLocal() as db:
            persisted = db.get(Visit, fixture["visit_id"])
            if not (attempts == 1 and type(message_id) is int and message_id > 0
                    and persisted and persisted.reminder_sent_at is not None):
                raise Refused("Reminder not confirmed; inspect the recipient chat before any further send")
        print("PASS: arq processed the synthetic visit and Telegram returned a message ID.")
        print("Recipient observation is separate from provider acceptance.")
    finally:
        await telegram_bot.bot.session.close()


if __name__ == "__main__":
    try:
        credentials = json.load(sys.stdin)
        asyncio.run(run(credentials["token"], credentials["challenge"]))
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Staging reminder failed; inspect the private chat before any further send.", file=sys.stderr)
        sys.exit(1)
