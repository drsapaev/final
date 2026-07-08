"""Base infrastructure for billing_service_pkg package.

Split from billing_service.py.
"""
from __future__ import annotations

"""
Сервис для автоматического выставления счетов
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Any

from jinja2 import Environment, select_autoescape
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.billing import (
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
from app.models.enums import PaymentStatus, VisitStatus

# ✅ ИСПРАВЛЕНО: BillingPayment удален из импортов - используем только Payment из app.models.payment (SSOT)
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.queue_service import queue_service
from app.services.service_mapping import normalize_service_code

logger = logging.getLogger(__name__)

REGISTRATION_DISCOUNT_MODES = {"none", "repeat", "benefit", "all_free"}


def _normalize_registration_discount_mode(raw_value: str | None) -> str:
    normalized = str(raw_value or "none").strip().lower()
    if normalized in REGISTRATION_DISCOUNT_MODES:
        return normalized
    return "none"



class BillingServiceMixinBase:
    """Type-hint anchor for BillingService mixins."""
