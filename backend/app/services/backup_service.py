"""
Database Backup Service

✅ SECURITY: Automated database backup strategy for disaster recovery
"""
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class BackupService:
    """Service for automated database backups"""

    def __init__(self, db: Session, backup_dir: str = "backups"):
        self.db = db
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup retention policy
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        self.max_backups = int(os.getenv("MAX_BACKUPS", "100"))

    def create_backup(self, backup_type: str = "manual") -> Dict[str, any]:
        """
        Create a database backup
        
        Args:
            backup_type: Type of backup (manual, scheduled, before_migration)
        
        Returns:
            Backup information dict
        """
        try:
            # Get database URL
            from app.core.config import settings
            db_url = getattr(settings, "DATABASE_URL", "sqlite:///./clinic.db")
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{backup_type}_{timestamp}.db"
            backup_path = self.backup_dir / backup_filename
            
            # Create backup based on database type
            if db_url.startswith("sqlite"):
                # SQLite backup
                source_db = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite://", "")
                if not os.path.isabs(source_db):
                    source_db = os.path.join(os.getcwd(), source_db)
                
                # Use SQLite backup API for atomic copy
                import sqlite3
                source_conn = sqlite3.connect(source_db)
                backup_conn = sqlite3.connect(str(backup_path))
                source_conn.backup(backup_conn)
                backup_conn.close()
                source_conn.close()
                
            elif db_url.startswith("postgresql"):
                # PostgreSQL backup using pg_dump
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url.replace("postgresql://", "http://"))
                
                env = os.environ.copy()
                env["PGPASSWORD"] = parsed.password or ""
                
                cmd = [
                    "pg_dump",
                    "-h", parsed.hostname or "localhost",
                    "-p", str(parsed.port or 5432),
                    "-U", parsed.username or "postgres",
                    "-d", parsed.path.lstrip("/"),
                    "-F", "c",  # Custom format
                    "-f", str(backup_path),
                ]
                
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"pg_dump failed: {result.stderr}")
            
            else:
                raise ValueError(f"Unsupported database type: {db_url}")
            
            # Get backup size
            backup_size = backup_path.stat().st_size
            
            # Compress backup (optional)
            compressed_path = None
            if os.getenv("BACKUP_COMPRESS", "true").lower() == "true":
                compressed_path = self._compress_backup(backup_path)
                if compressed_path:
                    backup_path.unlink()  # Remove uncompressed
                    backup_path = compressed_path
                    backup_size = backup_path.stat().st_size
            
            backup_info = {
                "filename": backup_path.name,
                "path": str(backup_path),
                "size": backup_size,
                "size_mb": round(backup_size / (1024 * 1024), 2),
                "type": backup_type,
                "created_at": datetime.utcnow().isoformat(),
                "compressed": compressed_path is not None,
            }
            
            logger.info(f"✅ Backup created: {backup_path.name} ({backup_info['size_mb']} MB)")
            
            # Cleanup old backups
            self._cleanup_old_backups()
            
            return backup_info
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            raise

    def _compress_backup(self, backup_path: Path) -> Optional[Path]:
        """Compress backup file"""
        try:
            import gzip
            
            compressed_path = backup_path.with_suffix(backup_path.suffix + ".gz")
            
            with open(backup_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            return compressed_path
        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            return None

    def _cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        try:
            backups = sorted(
                self.backup_dir.glob("backup_*.db*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Remove backups older than retention period
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            removed_count = 0
            
            for backup in backups:
                backup_time = datetime.fromtimestamp(backup.stat().st_mtime)
                if backup_time < cutoff_date:
                    backup.unlink()
                    removed_count += 1
                    logger.info(f"🗑️  Removed old backup: {backup.name}")
            
            # Also limit total number of backups
            if len(backups) > self.max_backups:
                for backup in backups[self.max_backups:]:
                    backup.unlink()
                    removed_count += 1
                    logger.info(f"🗑️  Removed backup (max limit): {backup.name}")
            
            if removed_count > 0:
                logger.info(f"✅ Cleaned up {removed_count} old backups")
                
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def list_backups(self) -> List[Dict[str, any]]:
        """List all available backups"""
        backups = []
        
        for backup_path in sorted(
            self.backup_dir.glob("backup_*.db*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            stat = backup_path.stat()
            backups.append({
                "filename": backup_path.name,
                "path": str(backup_path),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "compressed": backup_path.suffix == ".gz",
            })
        
        return backups

    def restore_backup(self, backup_filename: str) -> Dict[str, any]:
        """
        Restore database from backup
        
        ⚠️ WARNING: This will overwrite the current database!
        """
        try:
            backup_path = self.backup_dir / backup_filename
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup not found: {backup_filename}")
            
            # Create a backup before restore
            logger.warning("⚠️  Creating safety backup before restore...")
            safety_backup = self.create_backup("before_restore")
            
            # Get database URL
            from app.core.config import settings
            db_url = getattr(settings, "DATABASE_URL", "sqlite:///./clinic.db")
            
            # Decompress if needed
            if backup_path.suffix == ".gz":
                import gzip
                import tempfile
                
                temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                with gzip.open(backup_path, "rb") as f_in:
                    with open(temp_path.name, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                restore_source = temp_path.name
            else:
                restore_source = str(backup_path)
            
            # Restore based on database type
            if db_url.startswith("sqlite"):
                target_db = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite://", "")
                if not os.path.isabs(target_db):
                    target_db = os.path.join(os.getcwd(), target_db)
                
                # Close all connections first
                self.db.close()
                
                # Copy backup to target
                shutil.copy(restore_source, target_db)
                
            elif db_url.startswith("postgresql"):
                # PostgreSQL restore using pg_restore
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url.replace("postgresql://", "http://"))
                
                env = os.environ.copy()
                env["PGPASSWORD"] = parsed.password or ""
                
                cmd = [
                    "pg_restore",
                    "-h", parsed.hostname or "localhost",
                    "-p", str(parsed.port or 5432),
                    "-U", parsed.username or "postgres",
                    "-d", parsed.path.lstrip("/"),
                    "-c",  # Clean (drop) database objects before recreating
                    restore_source,
                ]
                
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"pg_restore failed: {result.stderr}")
            
            else:
                raise ValueError(f"Unsupported database type: {db_url}")
            
            # Cleanup temp file if created
            if backup_path.suffix == ".gz" and os.path.exists(restore_source):
                os.unlink(restore_source)
            
            logger.info(f"✅ Database restored from: {backup_filename}")
            
            return {
                "success": True,
                "backup_used": backup_filename,
                "safety_backup": safety_backup["filename"],
                "restored_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            raise

    def verify_backup(self, backup_filename: str) -> Dict[str, any]:
        """Verify backup integrity"""
        try:
            backup_path = self.backup_dir / backup_filename
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup not found: {backup_filename}")
            
            # Basic checks
            stat = backup_path.stat()
            size = stat.st_size
            
            if size == 0:
                return {
                    "valid": False,
                    "error": "Backup file is empty",
                }
            
            # For SQLite, try to open and check integrity
            if backup_path.suffix == ".db" or (backup_path.suffix == ".gz" and backup_path.stem.endswith(".db")):
                import sqlite3
                import tempfile
                import gzip
                
                # Extract if compressed
                if backup_path.suffix == ".gz":
                    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                    with gzip.open(backup_path, "rb") as f_in:
                        with open(temp_db.name, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    check_path = temp_db.name
                else:
                    check_path = str(backup_path)
                
                # Check SQLite integrity
                conn = sqlite3.connect(check_path)
                try:
                    result = conn.execute("PRAGMA integrity_check").fetchone()
                    is_valid = result[0] == "ok"
                finally:
                    conn.close()
                    if backup_path.suffix == ".gz":
                        os.unlink(check_path)
                
                return {
                    "valid": is_valid,
                    "size": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            
            # For other formats, just check size
            return {
                "valid": size > 0,
                "size": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }


def get_backup_service(db: Session, backup_dir: str = "backups") -> BackupService:
    """
    Get BackupService instance
    
    Args:
        db: Database session
        backup_dir: Backup directory path
    
    Returns:
        BackupService instance
    """
    return BackupService(db, backup_dir)
