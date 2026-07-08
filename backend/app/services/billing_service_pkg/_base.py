"""Base infrastructure for billing_service_pkg package.

Split from billing_service.py.
"""
from __future__ import annotations

"""
Сервис для автоматического выставления счетов
"""

import logging  # noqa: F401
from datetime import UTC, datetime, timedelta  # noqa: F401
from typing import Any  # noqa: F401

from jinja2 import Environment, select_autoescape  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.models.appointment import Appointment  # noqa: F401
from app.models.billing import (  # noqa: F401
    BillingRule,
    BillingSettings,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    InvoiceTemplate,
    InvoiceType,
    PaymentMethod,
    PaymentReminder,
    RecurrenceType,
)
from app.models.enums import PaymentStatus, VisitStatus  # noqa: F401

# ✅ ИСПРАВЛЕНО: BillingPayment удален из импортов - используем только Payment из app.models.payment (SSOT)
from app.models.patient import Patient  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.visit import Visit, VisitService  # noqa: F401
from app.services.queue_service import queue_service  # noqa: F401
from app.services.service_mapping import normalize_service_code  # noqa: F401

logger = logging.getLogger(__name__)

REGISTRATION_DISCOUNT_MODES = {"none", "repeat", "benefit", "all_free"}


def _normalize_registration_discount_mode(raw_value: str | None) -> str:
    normalized = str(raw_value or "none").strip().lower()
    if normalized in REGISTRATION_DISCOUNT_MODES:
        return normalized
    return "none"



class BillingServiceMixinBase:
    """Type-hint anchor for BillingService mixins."""
