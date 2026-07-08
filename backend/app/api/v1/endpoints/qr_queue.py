"""Backward-compatible shim for qr_queue package."""
from __future__ import annotations
from app.api.v1.endpoints.qr_queue import router
__all__ = ["router"]
