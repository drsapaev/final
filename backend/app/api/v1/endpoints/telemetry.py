"""
Telemetry API - Product metrics collection

WHAT THIS IS:
- System usage patterns
- AI suggestion usage stats  
- UX performance metrics

WHAT THIS IS NOT:
- Medical content logging
- PHI collection
- Hidden audit

RULES:
- NO content (text, diagnoses, treatments)
- Events only (clicked, opened, duration)
- Separate storage from audit logs
- Can be disabled globally
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


# =============================================================================
# Configuration
# =============================================================================

# Telemetry can be disabled globally
TELEMETRY_ENABLED = getattr(settings, 'TELEMETRY_ENABLED', True)

# Allowed event types (whitelist)
ALLOWED_EVENTS = {
    # EMR lifecycle
    'emr.load',
    'emr.save',
    'emr.save.error',
    'emr.sign',
    'emr.amend',
    'emr.conflict',
    
    # Section interactions
    'section.open',
    'section.close',
    'section.focus',
    'section.blur',
    
    # AI interactions
    'ai.suggestion.shown',
    'ai.suggestion.applied',
    'ai.suggestion.dismissed',
    'ai.panel.open',
    'ai.panel.close',
    'ai.completeness.check',
    
    # Template usage
    'template.panel.open',
    'template.applied',
    
    # UX metrics
    'undo',
    'redo',
    'keyboard.shortcut',
    'autosave.trigger',
    'autosave.success',
    'autosave.fail',
}


# =============================================================================
# Schemas
# =============================================================================


class TelemetryEvent(BaseModel):
    """Single telemetry event"""
    event: str = Field(..., max_length=50)
    entity: str = Field(default="emr", max_length=20)
    timestamp: Optional[int] = None
    session_id: Optional[str] = Field(None, max_length=50)
    meta: Optional[Dict[str, Any]] = None


class TelemetryBatch(BaseModel):
    """Batch of telemetry events"""
    events: List[TelemetryEvent] = Field(..., max_items=100)


class TelemetryResponse(BaseModel):
    """Response for telemetry submission"""
    accepted: int
    rejected: int


# =============================================================================
# Validation
# =============================================================================


def validate_event(event: TelemetryEvent) -> bool:
    """Validate event - block any PHI"""
    
    # Must be in whitelist
    if event.event not in ALLOWED_EVENTS:
        logger.debug(f"[Telemetry] Rejected unknown event: {event.event}")
        return False
    
    # Check meta for PHI (paranoid)
    if event.meta:
        for key, value in event.meta.items():
            # Block long strings (could be content)
            if isinstance(value, str) and len(value) > 100:
                logger.debug(f"[Telemetry] Rejected: meta value too long")
                return False
            # Block suspicious keys
            if key.lower() in ('content', 'text', 'diagnosis', 'treatment', 'body'):
                logger.debug(f"[Telemetry] Rejected: suspicious key {key}")
                return False
    
    return True


# =============================================================================
# Storage (simple - can be replaced with proper analytics)
# =============================================================================


async def store_events(events: List[TelemetryEvent]):
    """
    Store telemetry events.
    
    For now, just log. In production, send to:
    - Analytics DB
    - BigQuery
    - Mixpanel
    - etc.
    """
    for event in events:
        logger.info(
            f"[Telemetry] {event.event} | "
            f"session={event.session_id} | "
            f"meta={event.meta}"
        )


# =============================================================================
# Endpoint
# =============================================================================


@router.post("", response_model=TelemetryResponse)
async def submit_telemetry(
    batch: TelemetryBatch,
    background_tasks: BackgroundTasks,
):
    """
    Submit telemetry events.
    
    This endpoint:
    - Validates events against whitelist
    - Blocks any potential PHI
    - Stores events asynchronously
    - Never fails (best-effort)
    
    User authentication is not required (anonymous ok).
    """
    if not TELEMETRY_ENABLED:
        return TelemetryResponse(accepted=0, rejected=len(batch.events))
    
    accepted = []
    rejected = 0
    
    for event in batch.events:
        if validate_event(event):
            accepted.append(event)
        else:
            rejected += 1
    
    # Store in background (don't block response)
    if accepted:
        background_tasks.add_task(store_events, accepted)
    
    return TelemetryResponse(
        accepted=len(accepted),
        rejected=rejected,
    )


@router.get("/status")
async def telemetry_status():
    """Check if telemetry is enabled"""
    return {
        "enabled": TELEMETRY_ENABLED,
        "allowed_events": list(ALLOWED_EVENTS),
    }
