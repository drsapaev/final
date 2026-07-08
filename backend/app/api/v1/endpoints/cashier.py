"""Backward-compatible shim for the cashier package.

Originally a 1787-LOC god file — now split into focused endpoint
modules under :mod:`app.api.v1.endpoints.cashier`.
"""
from __future__ import annotations

from app.api.v1.endpoints.cashier import router

__all__ = ["router"]
