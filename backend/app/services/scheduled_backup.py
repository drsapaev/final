"""
Scheduled Backup Service

✅ SECURITY: Automated scheduled database backups
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Optional

from sqlalchemy.orm import Session

from app.services.backup_service import BackupService

logger = logging.getLogger(__name__)


class ScheduledBackupService:
    """Service for scheduled database backups"""

    def __init__(self, db: Session, backup_dir: str = "backups"):
        self.db = db
        self.backup_service = BackupService(db, backup_dir)
        self.running = False
        self.task: Optional[asyncio.Task] = None

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
                        next_backup += asyncio.timedelta(days=1)
                    
                    wait_seconds = (next_backup - now).total_seconds()
                    logger.info(f"⏰ Next backup scheduled for: {next_backup} (in {wait_seconds/3600:.1f} hours)")
                    
                    await asyncio.sleep(wait_seconds)
                    
                    if self.running:
                        logger.info("🔄 Starting scheduled backup...")
                        try:
                            backup_info = self.backup_service.create_backup("scheduled")
                            logger.info(f"✅ Scheduled backup completed: {backup_info['filename']}")
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
        logger.info("🛑 Backup scheduler stopped")


