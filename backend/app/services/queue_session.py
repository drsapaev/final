"""Queue Session Service

Manages session_id generation and lookup for OnlineQueueEntry grouping.

session_id is an OPAQUE STRING - frontend must NOT interpret its format.
"""
from datetime import date
from sqlalchemy.orm import Session
from app.models.online_queue import OnlineQueueEntry, DailyQueue
import logging

logger = logging.getLogger(__name__)


def get_or_create_session_id(
    db: Session,
    patient_id: int,
    target_queue_id: int,
    queue_day: date
) -> str:
    """
    Returns session_id for a patient in a specific queue.
    
    Rules:
    - Same patient + same queue + same day = same session_id (reuse)
    - Different patient/queue/day = new session_id
    
    CONTRACT: queue_day MUST match DailyQueue.day
    
    Args:
        db: Database session
        patient_id: Patient ID (must not be None)
        target_queue_id: Target DailyQueue ID
        queue_day: Expected queue day (validated against DailyQueue.day)
    
    Returns:
        session_id string (opaque format)
    
    Raises:
        ValueError: if queue_day doesn't match DailyQueue.day
    """
    # ⚠️ Validation: Protect against date mismatch bugs
    actual_day = db.query(DailyQueue.day).filter(
        DailyQueue.id == target_queue_id
    ).scalar()
    
    if actual_day and actual_day != queue_day:
        logger.error(
            "[get_or_create_session_id] queue_day mismatch: expected %s, got %s for queue_id=%d",
            actual_day, queue_day, target_queue_id
        )
        raise ValueError(
            f"queue_day mismatch: expected {actual_day}, got {queue_day}"
        )
    
    # Look for existing active session
    existing = db.query(OnlineQueueEntry.session_id).filter(
        OnlineQueueEntry.patient_id == patient_id,
        OnlineQueueEntry.queue_id == target_queue_id,
        OnlineQueueEntry.session_id.isnot(None),
        OnlineQueueEntry.status.in_(["waiting", "called", "in_service"])
    ).first()
    
    if existing and existing.session_id:
        logger.debug(
            "[get_or_create_session_id] Reusing session_id=%s for patient=%d, queue=%d",
            existing.session_id, patient_id, target_queue_id
        )
        return existing.session_id
    
    # Generate new session_id (opaque format)
    day_str = (actual_day or queue_day).isoformat()
    new_session_id = f"{patient_id}_{target_queue_id}_{day_str}"
    
    logger.info(
        "[get_or_create_session_id] Created new session_id=%s for patient=%d, queue=%d",
        new_session_id, patient_id, target_queue_id
    )
    
    return new_session_id


def generate_session_id_for_entry(entry_id: int) -> str:
    """
    Generate fallback session_id for entries without patient.
    Used for force majeure or migration scenarios.
    """
    return f"entry_{entry_id}"


def generate_session_id_for_visit(visit_id: int) -> str:
    """
    Generate session_id based on visit_id.
    Used for legacy data migration.
    """
    return f"visit_{visit_id}"
