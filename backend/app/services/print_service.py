"""Backward-compatible shim for print_svc package."""
from __future__ import annotations
from app.services.print_svc import PrintService
from app.services.print_svc._helpers import get_print_service

__all__ = ["PrintService", "get_print_service"]
