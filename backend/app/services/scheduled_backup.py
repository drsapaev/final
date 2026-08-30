"""
Scheduled Backup Service

✅ SECURITY: Automated scheduled database backups
"""
import asyncio
import functools
import logging
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.services.backup_service import BackupService

logger = logging.getLogger(__name__)

# Bounded wait in stop() for an in-flight pg_dump worker thread; past this the
# job finishes detached (the thread itself is non-daemon, so interpreter exit
# still joins it).
_SHUTDOWN_GRACE_SECONDS = 30


class ScheduledBackupService:
    """Service for scheduled database backups"""

    def __init__(self, db: Session, backup_dir: str = "backups"):
        self.db = db
        self.backup_service = BackupService(db, backup_dir)
        self.running = False
        self.task: asyncio.Task | None = None
        self._inflight: set[asyncio.Future] = set()

    async def start_daily_backups(
        self, backup_time: time = time(2, 0)  # 2 AM by default
    ):
        """
        Start daily backup scheduler

        Args:
            backup_time: Time of day to run backups (default: 2:00 AM)
        """
        if self.running:
            logger.warning("Backup scheduler already running")
            return

        self.running = True
        logger.info(f"✅ Starting daily backup scheduler (time: {backup_time})")

        async def backup_loop():
            while self.running:
                try:
                    now = datetime.now()
                    next_backup = datetime.combine(now.date(), backup_time)

                    # If backup time has passed today, schedule for tomorrow
                    if next_backup < now:
                        next_backup += timedelta(days=1)

                    wait_seconds = (next_backup - now).total_seconds()
                    logger.info(f"⏰ Next backup scheduled for: {next_backup} (in {wait_seconds/3600:.1f} hours)")

                    await asyncio.sleep(wait_seconds)

                    if self.running:
                        logger.info("🔄 Starting scheduled backup...")
                        try:
                            # P0 2026-08-28: create_backup shells out to
                            # pg_dump (subprocess.run). On the event loop it
                            # froze every HTTP request for the whole dump, so
                            # it must run in a worker thread.
                            job = asyncio.get_running_loop().run_in_executor(
                                None,
                                functools.partial(
                                    self.backup_service.create_backup, "scheduled"
                                ),
                            )
                            self._inflight.add(job)
                            job.add_done_callback(self._inflight.discard)
                            # shield(): cancelling the scheduler task must not
                            # cancel the tracked job itself, or stop() would
                            # lose sight of the still-running pg_dump thread.
                            backup_info = await asyncio.shield(job)
                            logger.info(
                                f"✅ Scheduled backup completed: {backup_info['filename']}"
                            )
                        except Exception as e:
                            logger.error(f"❌ Scheduled backup failed: {e}")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in backup scheduler: {e}")
                    await asyncio.sleep(3600)  # Wait 1 hour before retrying

        self.task = asyncio.create_task(backup_loop())

    async def stop(self):
        """Stop the backup scheduler"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        # P0 2026-08-28: wait (bounded) for an in-flight pg_dump worker thread
        # so shutdown never leaves detached background work behind.
        if self._inflight:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*list(self._inflight), return_exceptions=True),
                    timeout=_SHUTDOWN_GRACE_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "Backup shutdown grace (%ss) expired; %d job(s) will finish"
                    " detached",
                    _SHUTDOWN_GRACE_SECONDS,
                    len(self._inflight),
                )
        logger.info("🛑 Backup scheduler stopped")


