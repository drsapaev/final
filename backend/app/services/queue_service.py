"""Backward-compatible shim for queue_svc package."""
from __future__ import annotations
from app.services.queue_svc import QueueBusinessService
from app.services.queue_svc._base import QueueError, QueueValidationError, QueueConflictError, QueueNotFoundError
from app.services.queue_svc._helpers import get_queue_service

queue_service = QueueBusinessService()

__all__ = [
    "QueueBusinessService",
    "queue_service",
    "get_queue_service",
    "QueueError",
    "QueueValidationError",
    "QueueConflictError",
    "QueueNotFoundError",
]
