"""Backward-compatible shim for qr_queue package."""
from __future__ import annotations
from app.services.qr_queue import QRQueueService
__all__ = ["QRQueueService"]
