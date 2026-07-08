"""queue_svc — split from queue_service.py.

Re-exports QueueBusinessService for backward compatibility.
"""
from __future__ import annotations

from app.services.queue_svc._base import *  # noqa: F401, F403
from app.services.queue_svc._base import QueueBusinessServiceMixinBase
from app.services.queue_svc._core import CoreMixin
from app.services.queue_svc._helpers import HelpersMixin
from app.services.queue_svc._operations import OperationsMixin

__all__ = ["QueueBusinessService"]


class QueueBusinessService(
    CoreMixin,
    OperationsMixin,
    HelpersMixin,
    QueueBusinessServiceMixinBase,
):
    """Composed of focused mixin modules."""

    def __init__(self) -> None:
        self._cached_settings: dict[str, Any] | None = None
