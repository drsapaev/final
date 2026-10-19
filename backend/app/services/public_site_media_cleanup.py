"""Daily public-site media backup-copy cleanup, independent of DB backups."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone

from app.core.background_jobs import spawn_daemon_job
from app.services.public_site_media_service import PublicSiteMediaService

logger = logging.getLogger(__name__)

_TASHKENT_TZ = timezone(timedelta(hours=5), name="Asia/Tashkent")
_SHUTDOWN_GRACE_SECONDS = 30


def _next_cleanup_at(now: datetime, cleanup_time: time) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=_TASHKENT_TZ)
    else:
        now = now.astimezone(_TASHKENT_TZ)

    next_run = datetime.combine(
        now.date(), time(cleanup_time.hour, cleanup_time.minute), tzinfo=_TASHKENT_TZ
    )
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run


def _seconds_until_next_cleanup(now: datetime, cleanup_time: time) -> float:
    if now.tzinfo is None:
        now = now.replace(tzinfo=_TASHKENT_TZ)
    else:
        now = now.astimezone(_TASHKENT_TZ)
    return max(0.0, (_next_cleanup_at(now, cleanup_time) - now).total_seconds())


class PublicSiteMediaCleanupScheduler:
    """Run the existing 30-day backup-copy cleanup once per Tashkent day."""

    def __init__(
        self,
        cleanup_time: time,
        *,
        cleanup: Callable[[], int] | None = None,
    ) -> None:
        self.cleanup_time = time(cleanup_time.hour, cleanup_time.minute)
        self._cleanup = cleanup or PublicSiteMediaService.cleanup_expired_backups
        self.running = False
        self.task: asyncio.Task | None = None
        self._inflight: set[asyncio.Future] = set()

    async def start(self) -> None:
        if self.running:
            logger.warning("public_site_media.cleanup_scheduler_already_running")
            return

        self.running = True
        self.task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            "public_site_media.cleanup_scheduler_started time=%s timezone=Asia/Tashkent",
            self.cleanup_time.strftime("%H:%M"),
        )

    async def _cleanup_loop(self) -> None:
        while self.running:
            now = datetime.now(_TASHKENT_TZ)
            delay = _seconds_until_next_cleanup(now, self.cleanup_time)
            await asyncio.sleep(delay)
            if not self.running:
                break

            try:
                cleanup_job = spawn_daemon_job(self._cleanup)
                self._inflight.add(cleanup_job)
                cleanup_job.add_done_callback(self._inflight.discard)
                removed_count = await asyncio.shield(cleanup_job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "public_site_media.backup_cleanup_failed error_type=%s",
                    type(exc).__name__,
                )
            else:
                logger.info(
                    "public_site_media.backup_cleanup_completed removed_count=%s",
                    removed_count,
                )

    async def stop(self) -> None:
        self.running = False
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

        if self._inflight:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*list(self._inflight), return_exceptions=True),
                    timeout=_SHUTDOWN_GRACE_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "public_site_media.cleanup_shutdown_grace_expired jobs=%s",
                    len(self._inflight),
                )
        logger.info("public_site_media.cleanup_scheduler_stopped")
