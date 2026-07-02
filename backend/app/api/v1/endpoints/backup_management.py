"""
Backup Management API Endpoints

✅ SECURITY: Endpoints for database backup management
"""
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.backup_service import BackupService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/backup/create")
async def create_backup(
    backup_type: str = "manual",
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> Dict:
    """
    Create a database backup
    
    ✅ SECURITY: Requires Admin role
    """
    try:
        service = BackupService(db)
        backup_info = service.create_backup(backup_type)
        return backup_info
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {str(e)}",
        )


@router.get("/backup/list")
async def list_backups(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> Dict:
    """
    List all available backups
    
    ✅ SECURITY: Requires Admin role
    """
    try:
        service = BackupService(db)
        backups = service.list_backups()
        return {
            "backups": backups,
            "count": len(backups),
        }
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}",
        )


@router.post("/backup/restore/{backup_filename}")
async def restore_backup(
    backup_filename: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> Dict:
    """
    Restore database from backup
    
    ⚠️ WARNING: This will overwrite the current database!
    
    ✅ SECURITY: Requires Admin role
    """
    try:
        service = BackupService(db)
        result = service.restore_backup(backup_filename)
        return result
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}",
        )


@router.get("/backup/verify/{backup_filename}")
async def verify_backup(
    backup_filename: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> Dict:
    """
    Verify backup integrity
    
    ✅ SECURITY: Requires Admin role
    """
    try:
        service = BackupService(db)
        result = service.verify_backup(backup_filename)
        return result
    except Exception as e:
        logger.error(f"Error verifying backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}",
        )


