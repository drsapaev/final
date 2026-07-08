"""Backward-compatible shim for print_svc package."""
from __future__ import annotations

from app.services.print_svc import PrintService  # noqa: F401
from app.services.print_svc._helpers import get_print_service  # noqa: F401

__all__ = ["PrintService", "get_print_service"]
