"""billing_service_pkg — split from billing_service.py.

Re-exports BillingService for backward compatibility.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import BillingServiceMixinBase
from app.services.billing_service_pkg._core import CoreMixin
from app.services.billing_service_pkg._invoices import InvoicesMixin
from app.services.billing_service_pkg._payments import PaymentsMixin
from app.services.billing_service_pkg._calculations import CalculationsMixin
from app.services.billing_service_pkg._reminders import RemindersMixin
from app.services.billing_service_pkg._recurring import RecurringMixin

__all__ = ["BillingService"]


class BillingService(
    CoreMixin,
    InvoicesMixin,
    PaymentsMixin,
    CalculationsMixin,
    RemindersMixin,
    RecurringMixin,
    BillingServiceMixinBase,
):
    """Composed of focused mixin modules under billing_service_pkg/."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
