"""Backward-compatible shim for qr_queue package."""
from __future__ import annotations

from datetime import datetime  # noqa: F401

from app.services.qr_queue import QRQueueService  # noqa: F401

__all__ = ["QRQueueService", "datetime"]
