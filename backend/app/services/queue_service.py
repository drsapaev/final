"""Backward-compatible shim for queue_svc package."""
from __future__ import annotations

from datetime import datetime  # noqa: F401

from app.services.queue_svc import QueueBusinessService  # noqa: F401
from app.services.queue_svc._base import (  # noqa: F401
    QueueConflictError,
    QueueError,
    QueueNotFoundError,
    QueueValidationError,
)
from app.services.queue_svc._helpers import get_queue_service  # noqa: F401

queue_service = QueueBusinessService()

__all__ = [
    "QueueBusinessService",
    "queue_service",
    "get_queue_service",
    "datetime",
    "QueueError",
    "QueueValidationError",
    "QueueConflictError",
    "QueueNotFoundError",
]
