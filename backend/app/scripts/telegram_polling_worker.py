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
from app.db.session import SessionLocal
from app.services.telegram_bot import get_telegram_bot_service
# PR-3: update_id dedup shared with the webhook endpoint.
from app.services.telegram_webhook_dedup import (
    DUPLICATE,
    IN_FLIGHT,
    claim_update,
    mark_processed,
    release_claim,
    reset_ledger,
    resolve_ledger_bot_identity,
)
from app.services.telegram_token_store import resolve_patient_bot_token

LOGGER = logging.getLogger("telegram_polling_worker")
DEFAULT_POLL_TIMEOUT_SECONDS = 25
DEFAULT_REQUEST_TIMEOUT_SECONDS = 35
DEFAULT_RETRY_DELAY_SECONDS = 3
DEFAULT_LOG_FILE = (
    Path(__file__).resolve().parents[2] / "logs" / "telegram_polling_worker.log"
)
DEFAULT_PID_FILE = (
    Path(__file__).resolve().parents[2] / "logs" / "telegram_polling_worker.pid"
)


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

    def _clear_dedup_ledger(self, bot_identity: str | None) -> None:
        """PR-3: purge the SUPERSEDED bot's ledger rows when the identity
        changes (codex round 24).

        The delete is scoped to the superseded identity: webhook workers
        may already have claimed or completed updates for the NEW bot
        before the polling worker observes the credential change — a
        global reset would delete those claims and let a retry run the
        handler again (or concurrently). The composite key isolates the
        namespaces; anything not purged here ages out via the retention
        sweep. Fail-open: a failed purge is logged.
        """
        db: Session = SessionLocal()
        try:
            deleted = reset_ledger(db, bot_identity)
            LOGGER.info(
                "Telegram dedup ledger cleared for the superseded bot "
                "rows_deleted=%s",
                deleted,
            )
        finally:
            db.close()

    async def run(self) -> int:
        token = await self._load_bot_token()
        if not token:
            LOGGER.error("Telegram bot token is not configured")
            return 2
        # PR-3 (round 22): claims are scoped to the STABLE per-bot identity
        # (getMe bot id), not the rotatable credential.
        ledger_identity = await resolve_ledger_bot_identity(token)

        session = requests.Session()
        if not self.keep_webhook:
            self._delete_webhook(session, token)

        offset: int | None = None
        processed_updates = 0
        # PR-2 (round 11): a deleteWebhook that failed after a token swap is
        # retried on later cycles — without it Telegram keeps rejecting
        # getUpdates (409, the stale webhook counts as another poller) and
        # the worker can never resume.
        pending_webhook_deletion = False
        LOGGER.info("Telegram polling worker started")

        while not self._stop_requested:
            # PR-2 (round 7): a rotation keeps the old token VALID (200s
            # forever), so the 401 branch alone never fires — re-resolve the
            # canonical credential every cycle instead.
            try:
                canonical = await self._load_bot_token()
            except Exception as exc:
                # PR-2 (round 12): fail closed for this cycle - do NOT
                # consume updates with an unverifiable credential; Telegram
                # keeps them pending until the SSOT check succeeds.
                LOGGER.warning(
                    "Telegram token re-resolve failed error_type=%s — "
                    "skipping cycle",
                    type(exc).__name__,
                )
                time.sleep(self.retry_delay)
                continue
            else:
                if not canonical:
                    LOGGER.error("Telegram bot token was revoked — stopping")
                    return 2
                if canonical != token:
                    canonical_identity = await resolve_ledger_bot_identity(
                        canonical
                    )
                    identity_changed = canonical_identity != ledger_identity
                    LOGGER.info("Telegram bot token changed — reloading")
                    superseded_identity = ledger_identity
                    token = canonical
                    ledger_identity = canonical_identity
                    if not self.keep_webhook:
                        # Retained as pending: retried on later cycles until
                        # Telegram actually removes the webhook (codex
                        # round 11).
                        pending_webhook_deletion = True
                    offset = None
                    if identity_changed:
                        # The ledger and the offset are both cursors of the
                        # superseded bot. A same-bot token rotation keeps
                        # the identity — and its dedup continuity (round
                        # 22) — so only the SUPERSEDED identity's rows are
                        # purged, never the new bot's claims (round 24).
                        self._clear_dedup_ledger(superseded_identity)
            if pending_webhook_deletion:
                try:
                    self._delete_webhook(session, token)
                    pending_webhook_deletion = False
                except Exception as exc:
                    LOGGER.warning(
                        "Telegram deleteWebhook retry failed error_type=%s",
                        type(exc).__name__,
                    )

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
                elif status_code == 401:
                    # PR-2 (round 6): the credential may have been rotated or
                    # revoked in the DB after this process started —
                    # re-resolve through the SSOT chain instead of polling
                    # with the stale token forever.
                    try:
                        refreshed = await self._load_bot_token()
                    except Exception as exc:
                        # PR-2 (round 13): a transient resolver failure must
                        # not terminate run() — recover like the per-cycle
                        # refresh does.
                        LOGGER.warning(
                            "Telegram token re-resolve failed error_type=%s "
                            "— skipping cycle",
                            type(exc).__name__,
                        )
                        time.sleep(self.retry_delay)
                        continue
                    if refreshed and refreshed != token:
                        refreshed_identity = await resolve_ledger_bot_identity(
                            refreshed
                        )
                        if refreshed_identity != ledger_identity:
                            offset = None
                            self._clear_dedup_ledger(ledger_identity)
                        ledger_identity = refreshed_identity
                        LOGGER.info("Telegram bot token rotated — reloading")
                        token = refreshed
                        if not self.keep_webhook:
                            pending_webhook_deletion = True
                        continue
                    LOGGER.warning(
                        "Telegram getUpdates unauthorized error_status=%s",
                        status_code,
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

            # PR-2 (round 17): the default 25-second getUpdates long poll
            # can span a rotation or revocation — the batch returned by the
            # poll must NOT be dispatched under the stale credential, or the
            # old (possibly revoked/compromised) bot executes state-changing
            # handlers one full cycle past the change. Re-resolve BEFORE
            # dispatching; on any change/failure the batch is dropped
            # (Telegram keeps unacked updates pending for the next cycle).
            try:
                post_poll = await self._load_bot_token()
            except Exception as exc:
                LOGGER.warning(
                    "Telegram token re-resolve after long poll failed "
                    "error_type=%s — dropping batch, skipping cycle",
                    type(exc).__name__,
                )
                if self.once:
                    return 1
                time.sleep(self.retry_delay)
                continue
            if post_poll != token:
                if not post_poll:
                    LOGGER.error(
                        "Telegram bot token was revoked during the long poll "
                        "— stopping"
                    )
                    return 2
                LOGGER.info(
                    "Telegram bot token changed during the long poll — "
                    "dropping the batch fetched with the superseded credential"
                )
                post_poll_identity = await resolve_ledger_bot_identity(post_poll)
                identity_changed = post_poll_identity != ledger_identity
                superseded_identity = ledger_identity
                token = post_poll
                ledger_identity = post_poll_identity
                if not self.keep_webhook:
                    pending_webhook_deletion = True
                offset = None
                if identity_changed:
                    # Same rule as the cycle-top swap: purge only the
                    # superseded identity's rows (round 24).
                    self._clear_dedup_ledger(superseded_identity)
                if self.once:
                    return 0
                time.sleep(self.retry_delay)
                continue

            for update in updates:
                update_id = update.get("update_id")
                disposition = await self._handle_update(update, ledger_identity)
                if disposition == IN_FLIGHT and update_id is not None:
                    # Codex round 22 (P1): do NOT confirm an in-flight
                    # update — advancing the offset past it would ACK it
                    # before the stale-reclaim path can ever run (a
                    # crashed worker's orphaned claim would be confirmed
                    # away). Leave it unconfirmed; Telegram redelivers
                    # once the owner completes (→ duplicate) or releases
                    # (→ reclaim/reprocess).
                    LOGGER.info(
                        "Telegram update in flight — left unconfirmed "
                        "update_id=%s",
                        update_id,
                    )
                    break
                if update_id is not None:
                    offset = int(update_id) + 1

                processed_updates += 1
                if (
                    self.max_updates is not None
                    and processed_updates >= self.max_updates
                ):
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

            # PR-2: SSOT fallback chain (config decrypted -> legacy settings
            # -> env) instead of duplicated raw-column reads.
            return resolve_patient_bot_token(db)
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

    async def _handle_update(
        self, update: dict[str, Any], bot_identity: str | None = None
    ) -> str | None:
        """Handle one update under ``bot_identity``; returns the claim
        disposition so ``run()`` knows whether the delivery was safely
        handled (CLAIMED/DUPLICATE) or must stay unconfirmed
        (IN_FLIGHT — codex round 22). None = the handler failed and the
        claim was released (pre-existing crash-window semantics)."""
        update_id = update.get("update_id")
        db: Session = SessionLocal()
        try:
            bot_service = await get_telegram_bot_service()
            if not bot_service.active:
                await bot_service.initialize(db)

            # PR-3: the same update_id dedup as the webhook endpoint. The
            # offset cursor alone is not sufficient — a restart or token
            # rotation resets it to None and Telegram re-delivers every
            # unconfirmed update of the last 24h.
            claim = claim_update(db, update_id, bot_identity)
            if claim in (DUPLICATE, IN_FLIGHT):
                LOGGER.info(
                    "Telegram update skipped as %s update_id=%s",
                    claim,
                    update_id,
                )
                return claim

            handled = await _handle_clinic_bot_update(update, db, bot_service)
            if not handled:
                await bot_service.process_webhook_update(update, db)
            mark_processed(db, update_id, bot_identity)
            LOGGER.info(
                "Telegram update handled update_id=%s handled=%s", update_id, handled
            )
            # CLAIMED (we processed it) or UNAVAILABLE (fail-open — we
            # processed it without a claim). Both are safe to confirm.
            return claim
        except Exception as exc:
            db.rollback()
            # PR-3: release the claim so a re-fetched batch reprocesses
            # this update instead of suppressing it forever.
            release_claim(db, update_id, bot_identity)
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
        if os.name == "nt":
            return PidFile._windows_process_exists(pid)

        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _windows_process_exists(pid: int) -> bool:
        if pid <= 0:
            return False

        import ctypes

        process_query_limited_information = 0x1000
        error_access_denied = 5
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            int(pid),
        )
        if handle:
            kernel32.CloseHandle(handle)
            return True

        return ctypes.get_last_error() == error_access_denied


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
    parser.add_argument(
        "--poll-timeout", type=int, default=DEFAULT_POLL_TIMEOUT_SECONDS
    )
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
