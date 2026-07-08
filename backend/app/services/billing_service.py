"""Backward-compatible shim for the billing_service_pkg package.

Originally a large god file — now split into focused mixin modules
under :mod:`billing_service_pkg`.
"""
from __future__ import annotations

from app.services.billing_service_pkg import BillingService

__all__ = ["BillingService"]
