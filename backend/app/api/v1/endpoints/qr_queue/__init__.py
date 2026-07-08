"""qr_queue — split from qr_queue.py (3404 LOC).
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue import (
    _analytics,  # noqa: F401
    _entries,  # noqa: F401
    _join,  # noqa: F401
    _online_entries,  # noqa: F401
    _queue_ops,  # noqa: F401
    _specialists,  # noqa: F401
    _tokens,  # noqa: F401
)
from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router

__all__ = ["router"]
