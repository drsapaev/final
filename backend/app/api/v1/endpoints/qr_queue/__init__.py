"""qr_queue — split from qr_queue.py (3404 LOC).
"""
from __future__ import annotations
from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router

from app.api.v1.endpoints.qr_queue import _analytics  # noqa: F401
from app.api.v1.endpoints.qr_queue import _entries  # noqa: F401
from app.api.v1.endpoints.qr_queue import _join  # noqa: F401
from app.api.v1.endpoints.qr_queue import _online_entries  # noqa: F401
from app.api.v1.endpoints.qr_queue import _queue_ops  # noqa: F401
from app.api.v1.endpoints.qr_queue import _specialists  # noqa: F401
from app.api.v1.endpoints.qr_queue import _tokens  # noqa: F401

__all__ = ["router"]
