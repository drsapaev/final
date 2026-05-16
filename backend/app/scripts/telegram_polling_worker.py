from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.api.v1.endpoints.telegram_webhook import _handle_clinic_bot_update
from app.crud import clinic as crud_clinic, telegram_config as crud_telegram
from app.db.session import SessionLocal
from app.services.telegram_bot import get_telegram_bot_service

LOGGER = logging.getLogger("telegram_polling_worker")
DEFAULT_POLL_TIMEOUT_SECONDS = 25
DEFAULT_REQUEST_TIMEOUT_SECONDS = 35
DEFAULT_RETRY_DELAY_SECONDS = 3
DEFAULT_LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "telegram_polling_worker.log"
DEFAULT_PID_FILE = Path(__file__).resolve().parents[2] / "logs" / "telegram_polling_worker.pid"


class TelegramPollingWorker:
    def __init__(
        self,
        *,
        poll_timeout: int,
        request_timeout: int,
        retry_delay: int,
        drop_pending_updates: bool,
        keep_webhook: bool,
        once: bool,
        max_updates: int | None,
    ) -> None:
        self.poll_timeout = poll_timeout
        self.request_timeout = request_timeout
        self.retry_delay = retry_delay
        self.drop_pending_updates = drop_pending_updates
        self.keep_webhook = keep_webhook
        self.once = once
        self.max_updates = max_updates
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    async def run(self) -> int:
        token = await self._load_bot_token()
        if not token:
            LOGGER.error("Telegram bot token is not configured")
            return 2

        session = requests.Session()
        if not self.keep_webhook:
            self._delete_webhook(session, token)

        offset: int | None = None
        processed_updates = 0
        LOGGER.info("Telegram polling worker started")

        while not self._stop_requested:
            try:
                updates = self._get_updates(session, token, offset)
            except requests.HTTPError as exc:
                status_code = (
                    exc.response.status_code if exc.response is not None else None
                )
                if status_code == 409:
                    LOGGER.warning(
                        "Telegram polling conflict: another polling worker may be running"
                    )
                else:
                    LOGGER.warning(
                        "Telegram getUpdates HTTP error error_type=%s status_code=%s",
                        type(exc).__name__,
                        status_code,
                    )
                if self.once:
                    return 1
                time.sleep(self.retry_delay)
                continue
            except requests.RequestException as exc:
                LOGGER.warning(
                    "Telegram getUpdates request failed error_type=%s",
                    type(exc).__name__,
                )
                if self.once:
                    return 1
                time.sleep(self.retry_delay)
                continue
            except Exception as exc:
                LOGGER.warning(
                    "Telegram getUpdates failed error_type=%s",
                    type(exc).__name__,
                )
                if self.once:
                    return 1
                time.sleep(self.retry_delay)
                continue

            for update in updates:
                update_id = update.get("update_id")
                await self._handle_update(update)
                if update_id is not None:
                    offset = int(update_id) + 1

                processed_updates += 1
                if self.max_updates is not None and processed_updates >= self.max_updates:
                    LOGGER.info("Telegram polling worker reached max_updates")
                    return 0

            if self.once:
                LOGGER.info("Telegram polling worker completed one polling cycle")
                return 0

        LOGGER.info("Telegram polling worker stopped")
        return 0

    async def _load_bot_token(self) -> str | None:
        db = SessionLocal()
        try:
            bot_service = await get_telegram_bot_service()
            await bot_service.initialize(db)
            if bot_service.bot_token:
                return str(bot_service.bot_token)

            config = crud_telegram.get_telegram_config(db)
            if config and config.bot_token:
                return str(config.bot_token)

            token_setting = crud_clinic.get_setting_by_key(db, "bot_token")
            token = getattr(token_setting, "value", None) if token_setting else None
            return str(token) if token else None
        finally:
            db.close()

    def _delete_webhook(self, session: requests.Session, token: str) -> None:
        response = session.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={"drop_pending_updates": self.drop_pending_updates},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description") or "deleteWebhook failed")
        LOGGER.info(
            "Telegram webhook disabled for polling drop_pending_updates=%s",
            self.drop_pending_updates,
        )

    def _get_updates(
        self, session: requests.Session, token: str, offset: int | None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": self.poll_timeout,
            "allowed_updates": json.dumps(["message", "callback_query"]),
        }
        if offset is not None:
            params["offset"] = offset

        response = session.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params=params,
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description") or "getUpdates failed")
        return list(payload.get("result") or [])

    async def _handle_update(self, update: dict[str, Any]) -> None:
        update_id = update.get("update_id")
        db: Session = SessionLocal()
        try:
            bot_service = await get_telegram_bot_service()
            if not bot_service.active:
                await bot_service.initialize(db)

            handled = await _handle_clinic_bot_update(update, db, bot_service)
            if not handled:
                await bot_service.process_webhook_update(update, db)
            LOGGER.info("Telegram update handled update_id=%s handled=%s", update_id, handled)
        except Exception as exc:
            db.rollback()
            LOGGER.warning(
                "Telegram update failed update_id=%s error_type=%s",
                update_id,
                type(exc).__name__,
            )
        finally:
            db.close()


class PidFile:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.acquired = False

    def acquire(self) -> None:
        if self.path is None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
            except FileExistsError:
                existing_pid = self._read_existing_pid()
                if existing_pid and self._process_exists(existing_pid):
                    raise RuntimeError(
                        f"Telegram polling worker is already running pid={existing_pid}"
                    )
                self.path.unlink(missing_ok=True)
                continue

            with os.fdopen(fd, "w", encoding="utf-8") as pid_file:
                pid_file.write(str(os.getpid()))
            self.acquired = True
            atexit.register(self.release)
            return

    def release(self) -> None:
        if self.path is not None and self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def _read_existing_pid(self) -> int | None:
        if self.path is None:
            return None

        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    @staticmethod
    def _process_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


def configure_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Kosmed Clinic Telegram bot in polling mode."
    )
    parser.add_argument("--poll-timeout", type=int, default=DEFAULT_POLL_TIMEOUT_SECONDS)
    parser.add_argument(
        "--request-timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT_SECONDS
    )
    parser.add_argument("--retry-delay", type=int, default=DEFAULT_RETRY_DELAY_SECONDS)
    parser.add_argument("--drop-pending-updates", action="store_true")
    parser.add_argument("--keep-webhook", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-updates", type=int, default=None)
    parser.add_argument(
        "--log-file",
        default=str(DEFAULT_LOG_FILE),
        help="Use 'none' to disable file logging.",
    )
    parser.add_argument(
        "--pid-file",
        default=str(DEFAULT_PID_FILE),
        help="Use 'none' to disable the single-instance pid file.",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    log_file = None if str(args.log_file).lower() == "none" else Path(args.log_file)
    configure_logging(log_file)
    pid_file = None if str(args.pid_file).lower() == "none" else Path(args.pid_file)
    pid_guard = PidFile(pid_file)
    try:
        pid_guard.acquire()
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 3

    worker = TelegramPollingWorker(
        poll_timeout=args.poll_timeout,
        request_timeout=args.request_timeout,
        retry_delay=args.retry_delay,
        drop_pending_updates=args.drop_pending_updates,
        keep_webhook=args.keep_webhook,
        once=args.once,
        max_updates=args.max_updates,
    )

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, lambda *_args: worker.request_stop())
        except ValueError:
            pass

    try:
        return await worker.run()
    finally:
        pid_guard.release()


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
